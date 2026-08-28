import os
from typing import Dict, Any, Optional, List

class Skill:
    """
    Declarative skill representation parsed from SKILL.md format (AUD-022).
    Contains metadata (name, description, optional allowed_tools restriction)
    and free-text Markdown instructions.
    """
    def __init__(
        self,
        name: str,
        description: str,
        instructions: str,
        allowed_tools: Optional[List[str]] = None,
        filepath: Optional[str] = None
    ):
        self.name = name
        self.description = description
        self.instructions = instructions
        self.allowed_tools = allowed_tools or []
        self.filepath = filepath

    @property
    def system_prompt(self) -> str:
        return f"Eres un experto en {self.name}."

def parse_skill_md(content: str, filepath: Optional[str] = None) -> Skill:
    """
    Parses SKILL.md content using standard library string operations (no PyYAML).
    Supports frontmatter delimited by `---` with key-value pairs (name, description, allowed_tools),
    followed by free-text Markdown instructions.
    """
    if not content or not content.strip():
        return Skill(name="", description="", instructions="", filepath=filepath)

    text = content.strip()
    frontmatter_lines: List[str] = []
    body_text = text

    # Check for frontmatter delimited by ---
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm_part = parts[1]
            body_text = parts[2].strip()
            frontmatter_lines = fm_part.strip().splitlines()

    name = ""
    description = ""
    allowed_tools: List[str] = []
    current_list_key: Optional[str] = None

    for line in frontmatter_lines:
        line_str = line.strip()
        if not line_str or line_str.startswith("#"):
            continue

        # Handle list items if previous line set current_list_key
        if line_str.startswith("- ") and current_list_key:
            item = line_str[2:].strip().strip("'\"`")
            if current_list_key == "allowed_tools" and item:
                allowed_tools.append(item)
            continue

        if ":" in line_str:
            key, _, val = line_str.partition(":")
            key = key.strip().lower()
            val = val.strip()

            if key in ("name", "nombre"):
                name = val.strip("'\"`")
                current_list_key = None
            elif key in ("description", "descripcion"):
                description = val.strip("'\"`")
                current_list_key = None
            elif key in ("allowed_tools", "tools", "tool_restrictions", "herramientas_permitidas"):
                current_list_key = "allowed_tools"
                if val:
                    # Clean brackets e.g. [read_file, search_files]
                    cleaned_val = val.strip("[]()").strip()
                    if cleaned_val:
                        tools_split = [t.strip().strip("'\"`") for t in cleaned_val.split(",")]
                        allowed_tools.extend([t for t in tools_split if t])

    # Fallback if no name in frontmatter: parse first Markdown header or fallback to filename
    if not name:
        for line in body_text.splitlines():
            if line.strip().startswith("# "):
                name = line.strip()[2:].strip()
                break
        if not name and filepath:
            name = os.path.basename(os.path.dirname(filepath)) or os.path.basename(filepath)

    return Skill(
        name=name,
        description=description,
        instructions=body_text,
        allowed_tools=allowed_tools,
        filepath=filepath
    )

async def skill_tool_restriction_hook(payload: Any) -> Optional[str]:
    """
    Hook handler for `on_tool_pre_exec` that enforces `allowed_tools` restrictions
    declared in SKILL.md files (AUD-020 + AUD-022).
    """
    from app.core.resource_loader import ResourceLoader
    cwd = getattr(payload, "cwd", None)
    if not cwd:
        return None

    loader = ResourceLoader(cwd)
    skills = loader.discover_skills()
    tool_name = getattr(payload, "tool_name", "")

    for skill in skills:
        if skill.allowed_tools and tool_name:
            if tool_name not in skill.allowed_tools:
                return (
                    f"La herramienta '{tool_name}' no está autorizada por la habilidad '{skill.name}'. "
                    f"Herramientas permitidas: {', '.join(skill.allowed_tools)}"
                )
    return None

def register_skill_hooks(registry=None):
    """
    Registers the SKILL.md tool restriction hook into the ExtensionRegistry.
    """
    if registry is None:
        from app.core.extensions.registry import extension_registry
        registry = extension_registry
    registry.register_hook("on_tool_pre_exec", skill_tool_restriction_hook, origin=None)

# Backward compatibility alias for legacy TextSkill
TextSkill = Skill

class SkillRegistry:
    """
    Registry managing discovery and injection of Skills dynamically.
    """
    def __init__(self):
        self.skills: Dict[str, Skill] = {}

    def register_skill(self, skill: Skill):
        self.skills[skill.name] = skill

    def load_from_markdown(self, filepath: str):
        """
        Parses skills defined in a SKILL.md format file.
        """
        if not os.path.exists(filepath):
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            skill = parse_skill_md(content, filepath=filepath)
            if skill and skill.name:
                self.register_skill(skill)
        except Exception:
            pass

    def inject_to_agent(self, agent: Any, skill_name: str):
        skill = self.skills.get(skill_name)
        if skill:
            # Dynamically attach prompts without bloating class definition
            setattr(agent, f"skill_{skill_name.lower()}", skill)
