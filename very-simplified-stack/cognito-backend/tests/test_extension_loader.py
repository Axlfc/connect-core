import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from app.core.extensions.loader import discover_global, discover_configured, discover_project_local, load_extension_file
from app.core.extensions.api import ExtensionAPI

def test_discover_global(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_home = Path(tmpdir)
        monkeypatch.setattr(Path, "home", lambda: tmp_home)

        ext_dir = tmp_home / ".cognito" / "extensions"
        ext_dir.mkdir(parents=True)
        (ext_dir / "ext1.py").touch()
        (ext_dir / "ext2.py").touch()
        (ext_dir / "README.md").touch() # skip non-py

        paths = discover_global()
        assert len(paths) == 2
        assert paths[0].name == "ext1.py"
        assert paths[1].name == "ext2.py"

def test_discover_configured(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_home = Path(tmpdir)
        monkeypatch.setattr(Path, "home", lambda: tmp_home)

        ext_file = tmp_home / "my_ext.py"
        ext_file.touch()

        ext_dir = tmp_home / "extra_exts"
        ext_dir.mkdir()
        (ext_dir / "a.py").touch()

        config_dir = tmp_home / ".cognito"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        import json
        config_file.write_text(json.dumps({
            "ExtensionPaths": [str(ext_file), str(ext_dir)]
        }))

        paths = discover_configured()
        assert len(paths) == 2
        assert ext_file in paths
        assert (ext_dir / "a.py") in paths

def test_load_broken_extension():
    api = MagicMock()
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w") as tmp:
        tmp.write("def register(api): raise RuntimeError('Boom')")
        tmp.flush()

        # Should not raise
        load_extension_file(Path(tmp.name), api)

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w") as tmp:
        tmp.write("invalid python code")
        tmp.flush()

        # Should not raise
        load_extension_file(Path(tmp.name), api)
