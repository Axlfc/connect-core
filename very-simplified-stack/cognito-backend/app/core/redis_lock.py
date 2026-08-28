import os
import time
import uuid
import logging
import fcntl
from contextlib import contextmanager, asynccontextmanager
from typing import Optional
from pathlib import Path

logger = logging.getLogger("cognito.backend.redis_lock")

# Redis configuration from environment
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
DEFAULT_REDIS_URL = f"redis://:{REDIS_PASSWORD}@localhost:6379/0" if REDIS_PASSWORD else "redis://localhost:6379/0"
REDIS_URL = os.getenv("COGNITO_REDIS_URL", os.getenv("REDIS_URL", DEFAULT_REDIS_URL))

_redis_client = None
_async_redis_client = None

def get_redis_client():
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            client.ping()
            _redis_client = client
        except Exception as e:
            logger.warning(f"Failed to connect to sync Redis at {REDIS_URL}: {e}")
            return None
    return _redis_client

async def get_async_redis_client():
    global _async_redis_client
    if _async_redis_client is None:
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(REDIS_URL, decode_responses=True)
            await client.ping()
            _async_redis_client = client
        except Exception as e:
            logger.warning(f"Failed to connect to async Redis at {REDIS_URL}: {e}")
            return None
    return _async_redis_client

class RedisDistributedLock:
    """
    Sync distributed lock implementation using Redis SET key token NX PX timeout.
    Falls back to local file locking if Redis is unavailable or unconfigured.
    """
    def __init__(self, key: str, timeout_ms: int = 10000, retry_delay_sec: float = 0.005, lock_dir: Optional[Path] = None):
        self.key = f"cognito:lock:{key}"
        self.timeout_ms = timeout_ms
        self.retry_delay_sec = retry_delay_sec
        self.token = str(uuid.uuid4())
        self.lock_dir = (lock_dir.parent / "locks") if lock_dir else (Path.home() / ".cognito" / "locks")
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self._local_lock_file = None

    def acquire(self) -> bool:
        redis_cli = get_redis_client()
        if redis_cli:
            start_time = time.time()
            max_wait_sec = self.timeout_ms / 1000.0
            while time.time() - start_time < max_wait_sec:
                acquired = redis_cli.set(self.key, self.token, nx=True, px=self.timeout_ms)
                if acquired:
                    return True
                time.sleep(self.retry_delay_sec)
            logger.warning(f"Timeout acquiring Redis lock for {self.key}, falling back to file lock")

        # Local file lock fallback
        safe_key = self.key.replace(":", "_")
        lock_file_path = self.lock_dir / f"{safe_key}.lock"
        self._local_lock_file = open(lock_file_path, "a+")
        try:
            fcntl.flock(self._local_lock_file.fileno(), fcntl.LOCK_EX)
            return True
        except Exception as e:
            logger.error(f"Failed local file lock for {safe_key}: {e}")
            return False

    def release(self):
        redis_cli = get_redis_client()
        if redis_cli:
            lua_release = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            try:
                redis_cli.eval(lua_release, 1, self.key, self.token)
            except Exception as e:
                logger.warning(f"Error releasing Redis lock {self.key}: {e}")

        if self._local_lock_file:
            try:
                fcntl.flock(self._local_lock_file.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                self._local_lock_file.close()
            except Exception:
                pass
            self._local_lock_file = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class AsyncRedisDistributedLock:
    """
    Async distributed lock implementation using redis.asyncio.
    Falls back to local file locking if Redis is unavailable or unconfigured.
    """
    def __init__(self, key: str, timeout_ms: int = 10000, retry_delay_sec: float = 0.005, lock_dir: Optional[Path] = None):
        self.key = f"cognito:lock:{key}"
        self.timeout_ms = timeout_ms
        self.retry_delay_sec = retry_delay_sec
        self.token = str(uuid.uuid4())
        self.lock_dir = (lock_dir.parent / "locks") if lock_dir else (Path.home() / ".cognito" / "locks")
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self._local_lock_file = None

    async def acquire(self) -> bool:
        redis_cli = await get_async_redis_client()
        if redis_cli:
            import asyncio
            start_time = time.time()
            max_wait_sec = self.timeout_ms / 1000.0
            while time.time() - start_time < max_wait_sec:
                acquired = await redis_cli.set(self.key, self.token, nx=True, px=self.timeout_ms)
                if acquired:
                    return True
                await asyncio.sleep(self.retry_delay_sec)
            logger.warning(f"Timeout acquiring async Redis lock for {self.key}, falling back to file lock")

        # Local file lock fallback
        import anyio
        def _lock_file():
            safe_key = self.key.replace(":", "_")
            lock_file_path = self.lock_dir / f"{safe_key}.lock"
            f = open(lock_file_path, "a+")
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            return f

        self._local_lock_file = await anyio.to_thread.run_sync(_lock_file)
        return True

    async def release(self):
        redis_cli = await get_async_redis_client()
        if redis_cli:
            lua_release = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            try:
                await redis_cli.eval(lua_release, 1, self.key, self.token)
            except Exception as e:
                logger.warning(f"Error releasing async Redis lock {self.key}: {e}")

        if self._local_lock_file:
            import anyio
            def _unlock_file(f):
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                try:
                    f.close()
                except Exception:
                    pass
            await anyio.to_thread.run_sync(_unlock_file, self._local_lock_file)
            self._local_lock_file = None

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()


@contextmanager
def distributed_lock(key: str, lock_dir: Optional[Path] = None):
    lock = RedisDistributedLock(key, lock_dir=lock_dir)
    lock.acquire()
    try:
        yield lock
    finally:
        lock.release()

@asynccontextmanager
async def async_distributed_lock(key: str, lock_dir: Optional[Path] = None):
    lock = AsyncRedisDistributedLock(key, lock_dir=lock_dir)
    await lock.acquire()
    try:
        yield lock
    finally:
        await lock.release()
