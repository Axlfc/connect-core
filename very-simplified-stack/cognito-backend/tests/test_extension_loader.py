import json
import pytest
import tempfile
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock
from app.core.extensions.loader import (
    discover_global, discover_configured, discover_project_local,
    load_extension_file, load_extension_package, PluginEnvironment
)
from app.core.extensions.api import ExtensionAPI
from app.core.extensions.registry import ExtensionRegistry


def test_discover_global(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_home = Path(tmpdir)
        monkeypatch.setattr(Path, "home", lambda: tmp_home)

        ext_dir = tmp_home / ".cognito" / "extensions"
        ext_dir.mkdir(parents=True)
        (ext_dir / "ext1.py").touch()
        (ext_dir / "ext2.py").touch()
        (ext_dir / "README.md").touch()  # skip non-py

        # Create a packaged plugin directory
        pkg_dir = ext_dir / "pkg_plugin"
        pkg_dir.mkdir()
        (pkg_dir / "plugin.json").write_text(json.dumps({"name": "pkg_plugin", "main": "main.py"}))
        (pkg_dir / "main.py").touch()

        paths = discover_global()
        assert len(paths) == 3
        names = [p.name for p in paths]
        assert "ext1.py" in names
        assert "ext2.py" in names
        assert "pkg_plugin" in names


def test_discover_configured(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_home = Path(tmpdir)
        monkeypatch.setattr(Path, "home", lambda: tmp_home)

        ext_file = tmp_home / "my_ext.py"
        ext_file.touch()

        ext_dir = tmp_home / "extra_exts"
        ext_dir.mkdir()
        (ext_dir / "a.py").touch()

        pkg_dir = ext_dir / "my_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "manifest.json").write_text(json.dumps({"name": "my_pkg"}))
        (pkg_dir / "main.py").touch()

        config_dir = tmp_home / ".cognito"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({
            "ExtensionPaths": [str(ext_file), str(ext_dir)]
        }))

        paths = discover_configured()
        assert len(paths) == 3
        assert ext_file in paths
        assert (ext_dir / "a.py") in paths
        assert pkg_dir in paths


def test_discover_project_local():
    with tempfile.TemporaryDirectory() as tmpdir:
        cwd = Path(tmpdir)
        ext_dir = cwd / ".cognito" / "extensions"
        ext_dir.mkdir(parents=True)

        (ext_dir / "local_ext.py").touch()
        pkg_dir = ext_dir / "local_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "main.py").touch()

        paths = discover_project_local(str(cwd))
        assert len(paths) == 2
        names = [p.name for p in paths]
        assert "local_ext.py" in names
        assert "local_pkg" in names


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


def test_load_packaged_plugin_venv_creation():
    registry = ExtensionRegistry()
    api = ExtensionAPI(registry, origin=None)

    with tempfile.TemporaryDirectory() as tmpdir:
        pkg_dir = Path(tmpdir) / "test_plugin"
        pkg_dir.mkdir()

        (pkg_dir / "plugin.json").write_text(json.dumps({
            "name": "test_plugin",
            "entrypoint": "main.py",
            "dependencies": []
        }))

        (pkg_dir / "main.py").write_text("""
def register(api):
    class CustomTool:
        name = "custom_tool"
        async def execute(self, params, ctx):
            return "tool_ok"
    api.register_tool(CustomTool())
""")

        load_extension_file(pkg_dir, api)

        # Verify .venv was created
        assert (pkg_dir / ".venv").is_dir()

        # Verify tool was registered in registry
        tools = registry.tools_for("/some/cwd")
        registered_tool_names = [t.name for t in tools]
        assert "custom_tool" in registered_tool_names


@pytest.mark.asyncio
async def test_conflicting_dependencies_plugin_isolation():
    """
    AUD-023 Acceptance Criteria:
    Two plugins with different conflicting versions of the same library can be loaded
    and used simultaneously without breaking each other.
    """
    registry = ExtensionRegistry()
    api = ExtensionAPI(registry, origin=None)

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)

        # Plugin A setup
        plugin_a_dir = base_dir / "plugin_a"
        plugin_a_dir.mkdir()
        (plugin_a_dir / "plugin.json").write_text(json.dumps({
            "name": "plugin_a",
            "entrypoint": "main.py",
        }))
        (plugin_a_dir / "main.py").write_text("""
import conflicting_pkg

async def hook_a(payload):
    import conflicting_pkg
    return f"plugin_a:{conflicting_pkg.VERSION}"

class ToolA:
    name = "tool_a"
    async def execute(self, params, ctx):
        import conflicting_pkg
        return f"tool_a:{conflicting_pkg.VERSION}"

def register(api):
    api.on("on_agent_start", hook_a)
    api.register_tool(ToolA())
""")

        # Plugin B setup
        plugin_b_dir = base_dir / "plugin_b"
        plugin_b_dir.mkdir()
        (plugin_b_dir / "plugin.json").write_text(json.dumps({
            "name": "plugin_b",
            "entrypoint": "main.py",
        }))
        (plugin_b_dir / "main.py").write_text("""
import conflicting_pkg

async def hook_b(payload):
    import conflicting_pkg
    return f"plugin_b:{conflicting_pkg.VERSION}"

class ToolB:
    name = "tool_b"
    async def execute(self, params, ctx):
        import conflicting_pkg
        return f"tool_b:{conflicting_pkg.VERSION}"

def register(api):
    api.on("on_agent_start", hook_b)
    api.register_tool(ToolB())
""")

        # Pre-create venvs and inject conflicting_pkg into site-packages of each plugin
        env_a = PluginEnvironment(plugin_a_dir)
        env_b = PluginEnvironment(plugin_b_dir)

        sp_a = Path(env_a.site_packages[0])
        sp_b = Path(env_b.site_packages[0])

        # Write v1.0.0 to Plugin A's site-packages
        (sp_a / "conflicting_pkg.py").write_text('VERSION = "1.0.0"')
        # Write v2.0.0 to Plugin B's site-packages
        (sp_b / "conflicting_pkg.py").write_text('VERSION = "2.0.0"')

        # Load both plugins
        load_extension_file(plugin_a_dir, api)
        load_extension_file(plugin_b_dir, api)

        # Retrieve registered tools
        tools = {t.name: t for t in registry.tools_for("/test/cwd")}
        assert "tool_a" in tools
        assert "tool_b" in tools

        # Execute Tool A and Tool B
        res_a = await tools["tool_a"].execute({}, None)
        res_b = await tools["tool_b"].execute({}, None)

        assert res_a == "tool_a:1.0.0"
        assert res_b == "tool_b:2.0.0"

        # Fire registered hooks
        payload = MagicMock()
        res_hook_a = await registry.fire("on_agent_start", payload, "/test/cwd")
        # Notice fire returns the result of the first matching hook or executes all
        # Let's verify handlers directly in registry hooks list
        hooks = registry._hooks.get("on_agent_start", [])
        assert len(hooks) == 2

        out_hook_0 = await hooks[0][1](payload)
        out_hook_1 = await hooks[1][1](payload)

        results = {out_hook_0, out_hook_1}
        assert "plugin_a:1.0.0" in results
        assert "plugin_b:2.0.0" in results
