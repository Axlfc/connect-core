import inspect
from typing import Any, Dict, List
from app.core.visibility import VisibilityFilter

class AgentDocGenerator:
    """
    Dynamically generates API documentation from Agent classes/methods
    to be injected into the LLM prompt, respecting visibility selectively.
    """
    @staticmethod
    def generate(agent_cls: Any) -> str:
        doc_lines = []
        doc_lines.append(f"# Agent API: {agent_cls.__name__}")
        cls_doc = inspect.getdoc(agent_cls)
        if cls_doc:
            doc_lines.append(cls_doc)
        doc_lines.append("\n## Methods / Available Tools:")

        # Retrieve all visible members
        for name, member in inspect.getmembers(agent_cls):
            if not VisibilityFilter.is_visible(name, member):
                continue
            if not (inspect.isfunction(member) or inspect.ismethod(member)):
                continue

            # Parse signature
            try:
                sig = inspect.signature(member)
            except Exception:
                sig = ""

            doc = inspect.getdoc(member) or "No description provided."
            doc_lines.append(f"\n### `{name}{sig}`")
            doc_lines.append(doc)

        return "\n".join(doc_lines)
