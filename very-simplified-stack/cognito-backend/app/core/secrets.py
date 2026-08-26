import os
import json
import time
import logging
import secrets
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("cognito.backend.secrets")


class SecretsProvider(ABC):
    """
    Abstract interface for managing secrets (auth tokens, API keys, credentials)
    with support for dynamic rotation, invalidation, and external secrets managers.
    """

    @abstractmethod
    def get_secret(self, name: str) -> Optional[str]:
        """
        Retrieves a secret by its identifier (e.g. 'AuthToken', 'APIKey').
        Returns None if the secret is not found.
        """
        pass

    @abstractmethod
    def invalidate(self, name: Optional[str] = None) -> None:
        """
        Invalidates cached secret(s). If name is None, invalidates all cached secrets.
        This forces the provider to re-fetch/reload the secret on the next get_secret() call.
        """
        pass

    def refresh(self, name: Optional[str] = None) -> None:
        """
        Refreshes cached secret(s). Default implementation delegates to invalidate(name).
        """
        self.invalidate(name)


class LocalFileSecretsProvider(SecretsProvider):
    """
    Local file-backed SecretsProvider wrapping hierarchical resolution:
    Environment Variables -> ~/.cognito/config.json (0o600 permissions, 0o700 directory) -> Auto-generated ephemeral token.

    Supports in-memory caching with configurable TTL (COGNITO_SECRETS_TTL_SECONDS)
    and explicit invalidation for zero-downtime secret rotation.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        ttl_seconds: Optional[float] = None,
    ):
        self._custom_config_path = config_path
        if ttl_seconds is None:
            ttl_env = os.getenv("COGNITO_SECRETS_TTL_SECONDS", "0")
            try:
                self.ttl_seconds = float(ttl_env)
            except ValueError:
                self.ttl_seconds = 0.0
        else:
            self.ttl_seconds = ttl_seconds

        self._cache: Dict[str, str] = {}
        self._last_load_time: float = 0.0

    @property
    def effective_config_path(self) -> Path:
        if self._custom_config_path is not None:
            return self._custom_config_path
        return Path.home() / ".cognito" / "config.json"

    def _canonical_name(self, name: str) -> str:
        name_lower = name.lower()
        if name_lower in ("authtoken", "auth_token"):
            return "AuthToken"
        elif name_lower in ("apikey", "api_key"):
            return "APIKey"
        return name

    def _is_cache_valid(self) -> bool:
        if not self._cache:
            return False
        if self.ttl_seconds <= 0:
            return False
        return (time.time() - self._last_load_time) < self.ttl_seconds

    def _load_secrets(self) -> Dict[str, str]:
        loaded: Dict[str, str] = {}
        config_path = self.effective_config_path

        # Layer 1: Read ~/.cognito/config.json if present
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                    if isinstance(file_data, dict):
                        for k, v in file_data.items():
                            if isinstance(v, str):
                                c_name = self._canonical_name(k)
                                loaded[c_name] = v
            except Exception as e:
                logger.warning(f"Could not load secrets from {config_path}: {e}")

        # Layer 2: Environment variables override file config
        env_auth_token = os.getenv("COGNITO_AUTH_TOKEN")
        if env_auth_token:
            loaded["AuthToken"] = env_auth_token

        env_api_key = os.getenv("COGNITO_API_KEY")
        if env_api_key:
            loaded["APIKey"] = env_api_key

        # Layer 3: Auto-generate AuthToken if absent in both file and environment
        if not loaded.get("AuthToken") and not loaded.get("APIKey"):
            generated_token = secrets.token_urlsafe(32)
            loaded["AuthToken"] = generated_token
            try:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.chmod(config_path.parent, 0o700)
                except Exception:
                    pass

                file_data = {}
                if config_path.exists():
                    try:
                        with open(config_path, "r", encoding="utf-8") as f:
                            file_data = json.load(f)
                    except Exception:
                        file_data = {}

                file_data["AuthToken"] = generated_token
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(file_data, f, indent=2)

                try:
                    os.chmod(config_path, 0o600)
                except Exception:
                    pass

                logger.warning(
                    f"No auth token configured. Generated ephemeral AuthToken '{generated_token}' and persisted to {config_path}"
                )
            except Exception as e:
                logger.error(f"Could not persist generated AuthToken to {config_path}: {e}")
                raise RuntimeError(f"Failed to persist generated AuthToken to {config_path}: {e}") from e

        return loaded

    def get_secret(self, name: str) -> Optional[str]:
        canonical = self._canonical_name(name)
        if not self._is_cache_valid() or canonical not in self._cache:
            secrets_data = self._load_secrets()
            self._cache.update(secrets_data)
            self._last_load_time = time.time()

        return self._cache.get(canonical)

    def invalidate(self, name: Optional[str] = None) -> None:
        if name is None:
            self._cache.clear()
            self._last_load_time = 0.0
            logger.info("LocalFileSecretsProvider: all secrets invalidated.")
        else:
            canonical = self._canonical_name(name)
            self._cache.pop(canonical, None)
            logger.info(f"LocalFileSecretsProvider: secret '{canonical}' invalidated.")


class VaultSecretsProvider(SecretsProvider):
    """
    HashiCorp Vault / AWS Secrets Manager external secrets provider stub.

    -------------------------------------------------------------------------
    UNTESTED INFRASTRUCTURE NOTICE:
    This class implements the SecretsProvider interface for external vault systems.
    Real network integration with HashiCorp Vault / AWS Secrets Manager is marked
    as UNTESTED against live infrastructure in this PR and remains as follow-up
    infrastructure work.
    -------------------------------------------------------------------------

    Operator Configuration Guide:
    To enable VaultSecretsProvider in a production deployment, set the following environment variables:
      - COGNITO_SECRETS_PROVIDER=vault
      - VAULT_ADDR: URL of the Vault server (e.g. "https://vault.internal.example.com:8200")
      - VAULT_TOKEN: Authentication token or mount role token
      - VAULT_SECRET_PATH: Path to secret engine KV data (e.g. "secret/data/cognito/mcp")
      - VAULT_KV_VERSION: Key-Value engine version ("1" or "2", default "2")
      - AWS_SECRETS_MANAGER_SECRET_ID: (Optional for AWS) Secret ARN/name
      - AWS_REGION: (Optional for AWS) e.g. "us-east-1"
    """

    def __init__(
        self,
        vault_addr: Optional[str] = None,
        vault_token: Optional[str] = None,
        secret_path: Optional[str] = None,
        ttl_seconds: float = 60.0,
    ):
        self.vault_addr = vault_addr or os.getenv("VAULT_ADDR", "http://localhost:8200")
        self.vault_token = vault_token or os.getenv("VAULT_TOKEN", "")
        self.secret_path = secret_path or os.getenv("VAULT_SECRET_PATH", "secret/data/cognito")
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, str] = {}
        self._last_load_time: float = 0.0

    def get_secret(self, name: str) -> Optional[str]:
        canonical = name.lower()
        # Fallback to local environment override or mock values during testing
        env_val = os.getenv(f"VAULT_SECRET_{name.upper()}") or os.getenv(name.upper())
        if env_val:
            return env_val

        logger.warning(
            f"VaultSecretsProvider: Attempted to read secret '{name}' from path '{self.secret_path}' at '{self.vault_addr}'. "
            "Real Vault infrastructure connection is unconfigured/untested in this environment. Falling back to env var."
        )
        return self._cache.get(canonical)

    def invalidate(self, name: Optional[str] = None) -> None:
        if name is None:
            self._cache.clear()
            self._last_load_time = 0.0
        else:
            self._cache.pop(name.lower(), None)
        logger.info(f"VaultSecretsProvider: secret cache invalidated (name={name}).")


_global_secrets_provider: Optional[SecretsProvider] = None


def get_secrets_provider() -> SecretsProvider:
    """
    Returns the configured global SecretsProvider instance (Singleton).
    Configured via environment variable COGNITO_SECRETS_PROVIDER:
      - "local" (default): LocalFileSecretsProvider
      - "vault": VaultSecretsProvider (stub)
    """
    global _global_secrets_provider
    if _global_secrets_provider is None:
        provider_type = os.getenv("COGNITO_SECRETS_PROVIDER", "local").lower()
        if provider_type == "vault":
            _global_secrets_provider = VaultSecretsProvider()
        else:
            _global_secrets_provider = LocalFileSecretsProvider()
    return _global_secrets_provider


def reset_secrets_provider(provider: Optional[SecretsProvider] = None) -> None:
    """
    Resets or replaces the global SecretsProvider instance (primarily for testing).
    """
    global _global_secrets_provider
    _global_secrets_provider = provider
