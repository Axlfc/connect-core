from app.core.tools.base import AgentTool, ToolResult
from app.core.extensions.api import BeforeToolCallPayload, AfterToolCallPayload

class HookedTool(AgentTool):
    def __init__(self, inner, registry, session_id: str, cwd: str):
        self.name = inner.name
        self.description = inner.description
        self.parameters_schema = inner.parameters_schema
        self._inner = inner
        self._registry = registry
        self._session_id = session_id
        self._cwd = cwd

    async def execute(self, arguments, context):
        veto = await self._registry.fire(
            "before_tool_call",
            BeforeToolCallPayload(
                session_id=self._session_id,
                cwd=self._cwd,
                tool_name=self.name,
                arguments=arguments
            ),
            self._cwd,
        )

        if veto:
            return ToolResult(is_error=True, output=f"Llamada bloqueada por extensión: {veto}")

        result = await self._inner.execute(arguments, context)

        await self._registry.fire(
            "after_tool_call",
            AfterToolCallPayload(
                session_id=self._session_id,
                cwd=self._cwd,
                tool_name=self.name,
                arguments=arguments,
                output=result.output,
                is_error=result.is_error
            ),
            self._cwd,
        )

        return result
