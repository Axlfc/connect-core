import logging
from typing import Dict, List, Any, Optional, Callable, Awaitable, Literal
from pathlib import Path
from pydantic import BaseModel

logger = logging.getLogger("cognito.extensions.registry")

class ExtensionRegistry:
    def __init__(self):
        self._global_tools: Dict[str, Any] = {}
        self._project_tools: Dict[str, Dict[str, Any]] = {}   # cwd -> {tool_name: tool}
        self._hooks: Dict[str, List[tuple[Optional[str], Callable]]] = {}  # event -> [(origin, handler)]

    def register_tool(self, tool: Any, origin: Optional[str]):
        if origin is None:
            if tool.name in self._global_tools:
                logger.warning(f"Overwriting global tool: {tool.name}")
            self._global_tools[tool.name] = tool
        else:
            if origin not in self._project_tools:
                self._project_tools[origin] = {}
            if tool.name in self._project_tools[origin]:
                 logger.warning(f"Overwriting project-local tool: {tool.name} in {origin}")
            self._project_tools[origin][tool.name] = tool

    def register_hook(self, event: str, handler: Callable, origin: Optional[str]):
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append((origin, handler))

    def register_backend(self, config: Any):
        from app.services.backend_router import backend_router
        backend_router.register_backend(config)

    def register_intent(self, intent: str, backend_name: str, model: str):
        from app.services.semantic_orchestrator import semantic_orchestrator
        semantic_orchestrator.add_intent_route(intent, backend_name, model)

    def tools_for(self, cwd: str) -> List[Any]:
        # Merge Global and project-local tools. Project-local wins.
        from app.core.tools import (
            ReadTool, WriteTool, EditTool, BashTool, UnifiedPatchTool,
            CodeReviewTool, ListDirectoryTool, SearchFilesTool, ReadSpillTool,
            SubAgentTool
        )
        patch_tool = UnifiedPatchTool()
        tools = {
            "read": ReadTool(),
            "read_file": ReadTool(),
            "read_spill": ReadSpillTool(),
            "list_directory": ListDirectoryTool(),
            "search_files": SearchFilesTool(),
            "write": WriteTool(),
            "edit": EditTool(),
            "bash": BashTool(),
            "apply_unified_patch": patch_tool,
            "unified_patch": patch_tool,
            "code_review": CodeReviewTool(),
            "delegate_subagent": SubAgentTool(),
        }
        tools.update(self._global_tools)
        if cwd in self._project_tools:
            for name, tool in self._project_tools[cwd].items():
                if name in tools:
                    logger.warning(f"Project-local tool '{name}' overwriting global tool in {cwd}")
                tools[name] = tool
        return list(tools.values())

    async def fire(self, event: str, payload: BaseModel, cwd: str) -> Optional[str]:
        if event not in self._hooks:
            return None

        for origin, handler in self._hooks[event]:
            if origin is None or origin == cwd:
                try:
                    res = await handler(payload)
                    if event in ("before_tool_call", "on_tool_pre_exec") and res:
                        return str(res)
                except Exception as e:
                    logger.warning(f"Handler {getattr(handler, '__name__', str(handler))} for event {event} failed: {e}", exc_info=True)
        return None

    def clear_project_local(self, cwd: str):
        if cwd in self._project_tools:
            self._project_tools[cwd].clear()

        # Clear hooks for this origin
        for event in self._hooks:
            self._hooks[event] = [h for h in self._hooks[event] if h[0] != cwd]

    def refresh(self, level: Literal["global", "configured", "project_local"],
                cwd: Optional[str], backend_router, semantic_orchestrator) -> None:
        from app.core.extensions.loader import (
            discover_global, discover_configured, discover_project_local,
            load_extension_file
        )
        from app.core.extensions.api import ExtensionAPI

        if level == "global":
            paths = discover_global()
            for p in paths:
                api = ExtensionAPI(self, None)
                load_extension_file(p, api)
        elif level == "configured":
            paths = discover_configured()
            for p in paths:
                api = ExtensionAPI(self, None)
                load_extension_file(p, api)
        elif level == "project_local" and cwd:
            self.clear_project_local(cwd)
            paths = discover_project_local(cwd)
            for p in paths:
                api = ExtensionAPI(self, cwd)
                load_extension_file(p, api)


# Singleton
extension_registry = ExtensionRegistry()
