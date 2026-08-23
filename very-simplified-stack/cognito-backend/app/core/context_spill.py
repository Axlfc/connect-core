import os
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Union, Dict, Any
from app.core.token_budget import estimate_tokens

logger = logging.getLogger(__name__)

DEFAULT_SPILL_DIR = Path.home() / ".cognito" / "spill"
DEFAULT_TOKEN_THRESHOLD = 2000
DEFAULT_CHAR_THRESHOLD = 4000
DEFAULT_TTL_SECONDS = 24 * 3600  # 24 hours
DEFAULT_MAX_STORAGE_BYTES = 50 * 1024 * 1024  # 50 MB


def clean_old_spills(spill_dir: Optional[Path] = None, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> int:
    """
    Cleans up spill files older than ttl_seconds using pathlib.
    Returns the number of deleted files.
    """
    target_dir = Path(spill_dir) if spill_dir else DEFAULT_SPILL_DIR
    if not target_dir.exists():
        return 0

    now = time.time()
    deleted_count = 0

    for file_path in target_dir.glob("*.txt"):
        if not file_path.is_file():
            continue
        try:
            mtime = file_path.stat().st_mtime
            if now - mtime > ttl_seconds:
                file_path.unlink(missing_ok=True)
                deleted_count += 1
        except Exception as e:
            logger.warning(f"Error cleaning up old spill file {file_path}: {e}")

    return deleted_count


def spill_large_content(
    content: str,
    cwd: Optional[Path] = None,
    threshold: int = DEFAULT_CHAR_THRESHOLD,
    spill_dir: Optional[Path] = None,
) -> str:
    """
    Evaluates the content length. If it exceeds threshold (e.g. 4000 chars),
    saves it to a secure temp file in ~/.cognito/spill/ with a UUID,
    and returns a reference string.
    """
    if not content or len(content) <= threshold:
        return content

    target_dir = Path(spill_dir) if spill_dir else DEFAULT_SPILL_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    # Basic cleanup on spill
    clean_old_spills(spill_dir=target_dir)

    spill_id = f"spill_{uuid.uuid4().hex}"
    file_path = target_dir / f"{spill_id}.txt"

    try:
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Spilled large content to {file_path} (ID: {spill_id})")
    except Exception as e:
        logger.error(f"Failed to write spill file {file_path}: {e}")
        raise

    return f"[SPILL: contenido almacenado en {spill_id}. Usa la herramienta 'read_spill' para consultarlo.]"


class SpillManager:
    """
    Manages external storage of context fragments exceeding token limits.
    Stores fragments in local filesystem (~/.cognito/spill/) with automatic cleanup mechanisms.
    """

    def __init__(
        self,
        spill_dir: Optional[Union[str, Path]] = None,
        token_threshold: int = DEFAULT_TOKEN_THRESHOLD,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_storage_bytes: int = DEFAULT_MAX_STORAGE_BYTES,
    ):
        if spill_dir is None:
            self.spill_dir = DEFAULT_SPILL_DIR
        else:
            self.spill_dir = Path(spill_dir)

        self.token_threshold = token_threshold
        self.ttl_seconds = ttl_seconds
        self.max_storage_bytes = max_storage_bytes

        # Ensure directory exists
        self.spill_dir.mkdir(parents=True, exist_ok=True)

    def should_spill(self, content: str, threshold: Optional[int] = None) -> bool:
        """
        Determines whether the text content exceeds the token threshold.
        """
        if not content:
            return False
        limit = threshold if threshold is not None else self.token_threshold
        tokens = estimate_tokens(content)
        return tokens > limit

    def spill(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Saves content to a unique file in spill directory and returns spill_id.
        Triggers automatic cleanup.
        """
        self.cleanup()

        spill_id = f"spill_{uuid.uuid4().hex[:12]}"
        file_path = self.spill_dir / f"{spill_id}.txt"

        try:
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"Spilled context content to {file_path} (ID: {spill_id})")
        except Exception as e:
            logger.error(f"Failed to write spill file {file_path}: {e}")
            raise

        return spill_id

    def get_spill_path(self, spill_id: str) -> Path:
        """
        Returns Path object for a given spill_id.
        """
        # Ensure simple filename matching to prevent directory traversal
        safe_id = Path(spill_id).name
        if not safe_id.endswith(".txt"):
            safe_id = f"{safe_id}.txt"
        return self.spill_dir / safe_id

    def read_spill(self, spill_id: str) -> Optional[str]:
        """
        Reads the full content of a spilled file.
        """
        path = self.get_spill_path(spill_id)
        if not path.exists() or not path.is_file():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Error reading spill file {path}: {e}")
            return None

    def query_spill(
        self,
        spill_id: str,
        query: Optional[str] = None,
        line_range: Optional[List[int]] = None,
    ) -> str:
        """
        Queries a spilled document using either a keyword/search string or a 1-indexed line range [start, end].
        """
        content = self.read_spill(spill_id)
        if content is None:
            return f"Error: Spill content with ID '{spill_id}' was not found or has expired."

        lines = content.splitlines()
        total_lines = len(lines)

        # 1. Line range query takes precedence or combines with content
        if line_range and len(line_range) == 2:
            start_line, end_line = line_range[0], line_range[1]
            # Ensure 1-indexed boundaries
            start_idx = max(0, start_line - 1)
            end_idx = min(total_lines, end_line)

            selected_lines = lines[start_idx:end_idx]
            result_header = f"--- Showing lines {start_idx + 1} to {min(end_idx, total_lines)} of {total_lines} for spill ID {spill_id} ---\n"
            formatted_lines = [f"{i + start_idx + 1}: {line}" for i, line in enumerate(selected_lines)]
            return result_header + "\n".join(formatted_lines)

        # 2. Text/keyword search query
        if query:
            query_lower = query.lower()
            matching_lines = []
            for idx, line in enumerate(lines, start=1):
                if query_lower in line.lower():
                    matching_lines.append(f"{idx}: {line}")

            if not matching_lines:
                return f"No matches found for query '{query}' in spill ID {spill_id} ({total_lines} total lines)."

            result_header = f"--- Found {len(matching_lines)} matching line(s) for query '{query}' in spill ID {spill_id} ---\n"
            return result_header + "\n".join(matching_lines)

        # 3. Default fallback if neither query nor line_range provided
        preview_count = min(30, total_lines)
        preview_lines = [f"{i+1}: {lines[i]}" for i in range(preview_count)]
        return (
            f"--- Spill ID {spill_id} summary ({total_lines} total lines) ---\n"
            f"Showing first {preview_count} lines:\n" +
            "\n".join(preview_lines) +
            (f"\n... ({total_lines - preview_count} more lines available. Use line_range or query to inspect)." if total_lines > preview_count else "")
        )

    def cleanup(self) -> int:
        """
        Cleans up expired spill files (older than TTL) and ensures total storage does not exceed max_storage_bytes.
        Returns the number of deleted files.
        """
        if not self.spill_dir.exists():
            return 0

        now = time.time()
        deleted_count = 0

        # Gather files with mtime and size
        files = []
        total_size = 0

        for file_path in self.spill_dir.glob("*.txt"):
            if not file_path.is_file():
                continue
            try:
                stat = file_path.stat()
                mtime = stat.st_mtime
                size = stat.st_size

                # TTL check
                if now - mtime > self.ttl_seconds:
                    file_path.unlink(missing_ok=True)
                    deleted_count += 1
                    continue

                files.append((file_path, mtime, size))
                total_size += size
            except Exception as e:
                logger.warning(f"Error checking spill file {file_path}: {e}")

        # If total storage exceeds max limit, remove oldest files until within limit
        if total_size > self.max_storage_bytes:
            # Sort by mtime ascending (oldest first)
            files.sort(key=lambda x: x[1])
            for file_path, _, size in files:
                try:
                    file_path.unlink(missing_ok=True)
                    deleted_count += 1
                    total_size -= size
                    if total_size <= self.max_storage_bytes:
                        break
                except Exception as e:
                    logger.warning(f"Error unlinking spill file {file_path}: {e}")

        return deleted_count


# Global singleton instance for easy usage
default_spill_manager = SpillManager()
