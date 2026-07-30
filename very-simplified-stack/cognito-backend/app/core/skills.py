import os
import yaml
from typing import Dict, Any, Optional

class TextSkill:
    """
    Skill representation from SKILL.md containing prompts and context (NOOA-16).
    """
    def __init__(self, name: str, system_prompt: str, instructions: str):
        self.name = name
        self.system_prompt = system_prompt
        self.instructions = instructions

class SkillRegistry:
    """
    Registry managing discovery and injection of Skills dynamically.
    """
    def __init__(self):
        self.skills: Dict[str, TextSkill] = {}

    def register_skill(self, skill: TextSkill):
        self.skills[skill.name] = skill

    def load_from_markdown(self, filepath: str):
        """
        Parses skills defined in a SKILL.md format.
        """
        if not os.path.exists(filepath):
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            # Simple custom parsing of headers
            sections = content.split("\n# ")
            for section in sections:
                if not section.strip():
                    continue
                lines = section.split("\n")
                name = lines[0].strip()
                # find description / instructions
                instructions = "\n".join(lines[1:]).strip()
                self.register_skill(TextSkill(name, f"Eres un experto en {name}.", instructions))
        except Exception:
            pass

    def inject_to_agent(self, agent: Any, skill_name: str):
        skill = self.skills.get(skill_name)
        if skill:
            # Dynamically attach prompts without bloating class definition
            setattr(agent, f"skill_{skill_name.lower()}", skill)
