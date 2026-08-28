import os
import tempfile
import pytest
from app.core.skills import parse_skill_md, Skill, register_skill_hooks, skill_tool_restriction_hook
from app.core.resource_loader import ResourceLoader
from app.core.system_prompt import build_system_message
from app.core.extensions.api import ToolPreExecPayload
from app.core.extensions.registry import ExtensionRegistry

def test_parse_skill_md_flat_frontmatter_without_pyyaml():
    content = """---
name: DatabaseExpert
description: Expert in PostgreSQL and SQL queries
allowed_tools:
  - read_file
  - search_files
---

# Instructions

You are a database expert. Follow SQL best practices.
- Always use index on queries.
- Do not drop tables.
"""
    skill = parse_skill_md(content, filepath="/tmp/SKILL.md")
    assert skill.name == "DatabaseExpert"
    assert skill.description == "Expert in PostgreSQL and SQL queries"
    assert skill.allowed_tools == ["read_file", "search_files"]
    assert "You are a database expert." in skill.instructions
    assert "Do not drop tables." in skill.instructions

def test_parse_skill_md_alternative_keys_and_inline_list():
    content = """---
nombre: CodeReviewer
descripcion: Reviews code quality
tools: [read_file, code_review]
---

Please check for syntax errors and security bugs.
"""
    skill = parse_skill_md(content)
    assert skill.name == "CodeReviewer"
    assert skill.description == "Reviews code quality"
    assert skill.allowed_tools == ["read_file", "code_review"]
    assert "Please check for syntax errors" in skill.instructions

def test_parse_skill_md_no_frontmatter_fallback_header():
    content = """# PythonRefactorer

Refactor old Python code to modern 3.12 syntax.
"""
    skill = parse_skill_md(content)
    assert skill.name == "PythonRefactorer"
    assert "Refactor old Python code" in skill.instructions

def test_recursive_skill_discovery_and_system_prompt_injection():
    with tempfile.TemporaryDirectory() as tmpdir:
        root_skill_file = os.path.join(tmpdir, "SKILL.md")
        with open(root_skill_file, "w", encoding="utf-8") as f:
            f.write("""---
name: ProjectRootSkill
description: Skill at root level
allowed_tools: [read_file, bash]
---
Follow repository coding conventions.
""")

        sub_dir = os.path.join(tmpdir, "subdir", "deep")
        os.makedirs(sub_dir, exist_ok=True)
        sub_skill_file = os.path.join(sub_dir, "SKILL.md")
        with open(sub_skill_file, "w", encoding="utf-8") as f:
            f.write("""---
name: DeepSubdirSkill
description: Special skill in deep directory
allowed_tools: [read_file]
---
Use strict linting rules here.
""")

        loader = ResourceLoader(sub_dir)
        skills = loader.discover_skills()
        assert len(skills) == 2
        skill_names = [s.name for s in skills]
        assert "ProjectRootSkill" in skill_names
        assert "DeepSubdirSkill" in skill_names

        system_prompt = build_system_message(cwd=sub_dir)
        assert "Habilidades disponibles (SKILL.md):" in system_prompt
        assert "ProjectRootSkill" in system_prompt
        assert "Follow repository coding conventions." in system_prompt
        assert "DeepSubdirSkill" in system_prompt
        assert "Use strict linting rules here." in system_prompt

@pytest.mark.asyncio
async def test_skill_tool_restriction_hook_aud020():
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_file = os.path.join(tmpdir, "SKILL.md")
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write("""---
name: ReadOnlySkill
allowed_tools:
  - read_file
  - search_files
---
Only read files.
""")

        registry = ExtensionRegistry()
        register_skill_hooks(registry)

        allowed_payload = ToolPreExecPayload(
            cwd=tmpdir,
            tool_name="read_file",
            arguments={"path": "main.py"},
            tool_call_id="call_1"
        )
        veto_allowed = await registry.fire("on_tool_pre_exec", allowed_payload, tmpdir)
        assert veto_allowed is None

        forbidden_payload = ToolPreExecPayload(
            cwd=tmpdir,
            tool_name="write_file",
            arguments={"path": "main.py", "content": "bad"},
            tool_call_id="call_2"
        )
        veto_forbidden = await registry.fire("on_tool_pre_exec", forbidden_payload, tmpdir)
        assert veto_forbidden is not None
        assert "Herramientas permitidas: read_file, search_files" in veto_forbidden
