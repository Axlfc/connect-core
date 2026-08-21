import json
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Union

from app.core.exec_policy import default_exec_policy, ExecPolicy

DEFAULT_LEGACY_TRUSTED = {
    "read": True,
    "write": True,
    "shell": "approval",
    "network": False,
    "git_commit": "approval",
    "git_push": False,
    "extensions": False,
    "secrets": False,
    "destructive_operations": False,
    "migrated_from_legacy": True,
    "requires_review": True
}

DEFAULT_LEGACY_UNTRUSTED = {
    "read": True,
    "write": False,
    "shell": False,
    "network": False,
    "git_commit": False,
    "git_push": False,
    "extensions": False,
    "secrets": False,
    "destructive_operations": False,
    "migrated_from_legacy": True,
    "requires_review": False
}

DEFAULT_NEW_UNTRUSTED = {
    "read": True,
    "write": False,
    "shell": False,
    "network": False,
    "git_commit": False,
    "git_push": False,
    "extensions": False,
    "secrets": False,
    "destructive_operations": False,
    "migrated_from_legacy": False,
    "requires_review": False
}

class ProjectTrustStore:
    def __init__(self, store_path: Optional[Union[str, Path]] = None, exec_policy: Optional[ExecPolicy] = None):
        if store_path is None:
            self.store_path = Path.home() / ".cognito" / "trust.json"
        elif isinstance(store_path, str):
            self.store_path = Path(store_path)
        else:
            self.store_path = store_path

        self.exec_policy = exec_policy or default_exec_policy
        self._ensure_dir()
        self._load_and_migrate()

    def _ensure_dir(self):
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_raw(self) -> Dict[str, Any]:
        if not self.store_path.exists():
            return {}
        try:
            with open(self.store_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _load_and_migrate(self) -> Dict[str, Dict[str, Any]]:
        data = self._load_raw()
        migrated_data, was_migrated = self._migrate_data_if_needed(data)
        if was_migrated:
            self._save(migrated_data)
        return migrated_data

    def _migrate_data_if_needed(self, data: Dict[str, Any]) -> tuple[Dict[str, Dict[str, Any]], bool]:
        migrated = False
        new_data = {}
        for path, val in data.items():
            normalized_path = os.path.realpath(path)
            if isinstance(val, bool):
                migrated = True
                if val:
                    new_data[normalized_path] = DEFAULT_LEGACY_TRUSTED.copy()
                else:
                    new_data[normalized_path] = DEFAULT_LEGACY_UNTRUSTED.copy()
            elif isinstance(val, dict):
                # Ensure all standard keys exist
                updated_val = DEFAULT_NEW_UNTRUSTED.copy()
                updated_val.update(val)
                new_data[normalized_path] = updated_val
            else:
                migrated = True
                new_data[normalized_path] = DEFAULT_NEW_UNTRUSTED.copy()
        return new_data, migrated

    def _save(self, data: Dict[str, Any]):
        if self.store_path.exists():
            backup_path = self.store_path.with_suffix(".json.bak")
            try:
                shutil.copy2(self.store_path, backup_path)
            except Exception:
                pass
        with open(self.store_path, "w") as f:
            json.dump(data, f, indent=2)

    def is_trusted(self, repo_path: str) -> bool:
        """
        Backward compatible helper. Returns True if the project has 'write' permission.
        """
        path = os.path.realpath(repo_path)
        permissions = self.get_permissions(path)
        return permissions.get("write", False)

    def set_trusted(self, repo_path: str, trusted: bool) -> None:
        """
        Backward compatible helper. Sets basic write trust and sets shell to 'approval'.
        """
        path = os.path.realpath(repo_path)
        data = self._load_and_migrate()
        if trusted:
            data[path] = DEFAULT_LEGACY_TRUSTED.copy()
            data[path]["migrated_from_legacy"] = False
            data[path]["requires_review"] = False
        else:
            data[path] = DEFAULT_NEW_UNTRUSTED.copy()
        self._save(data)

    def get_permissions(self, repo_path: str) -> Dict[str, Any]:
        path = os.path.realpath(repo_path)
        data = self._load_and_migrate()
        return data.get(path, DEFAULT_NEW_UNTRUSTED.copy())

    def has_permission(self, repo_path: str, permission: str) -> bool:
        """
        Checks if the permission is explicitly allowed (returns True).
        Returns False if the permission is False or 'approval'.
        """
        path = os.path.realpath(repo_path)
        permissions = self.get_permissions(path)
        val = permissions.get(permission, False)
        return val is True

    def get_permission_level(self, repo_path: str, permission: str) -> Any:
        path = os.path.realpath(repo_path)
        permissions = self.get_permissions(path)
        return permissions.get(permission, False)

    def set_permission(self, repo_path: str, permission: str, value: Any) -> None:
        path = os.path.realpath(repo_path)
        data = self._load_and_migrate()
        if path not in data:
            data[path] = DEFAULT_NEW_UNTRUSTED.copy()
        data[path][permission] = value
        self._save(data)

    def evaluates_command_approval(self, repo_path: str, command: str) -> bool:
        """
        Evaluates whether a command requires explicit human approval for the given project path.
        Returns True if approval is required, False if it can run automatically.
        """
        trusted = self.is_trusted(repo_path)
        return self.exec_policy.requires_explicit_approval(command, project_trusted=trusted)
