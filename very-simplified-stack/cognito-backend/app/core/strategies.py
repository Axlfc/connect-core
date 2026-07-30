import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from app.core.runtime import ActorRuntime
from app.core.sandbox import SandboxedExecutor

class ExecutionStrategy(ABC):
    @abstractmethod
    async def execute(self, prompt: str, runtime: ActorRuntime) -> Any:
        pass

class PredictStrategy(ExecutionStrategy):
    """
    Strategy Predict: resolves user objective in a single, structured turn (NOOA-13).
    """
    async def execute(self, prompt: str, runtime: ActorRuntime) -> Any:
        llm = getattr(runtime.agent, "llm_client", None)
        if not llm:
            from app.services.unified_llm import UnifiedLLM
            llm = UnifiedLLM()

        runtime.event_manager.record_event("thinking", "Predicting structured response in single turn.")
        raw_res = await llm.generate(prompt)
        runtime.event_manager.record_event("assistant_response", raw_res)
        return raw_res

class CodeActStrategy(ExecutionStrategy):
    """
    Strategy CodeAct: executes a persistent, iterative REPL Python loop (NOOA-14).
    """
    def __init__(self, sandbox: Optional[SandboxedExecutor] = None, max_turns: int = 5):
        self.sandbox = sandbox or SandboxedExecutor()
        self.max_turns = max_turns

    async def execute(self, prompt: str, runtime: ActorRuntime) -> Any:
        llm = getattr(runtime.agent, "llm_client", None)
        if not llm:
            from app.services.unified_llm import UnifiedLLM
            llm = UnifiedLLM()

        runtime.event_manager.record_event("thinking", f"Starting CodeAct REPL cycle (max_turns={self.max_turns}).")
        current_context = prompt
        turn = 0

        while turn < self.max_turns:
            turn += 1
            # Prompt the agent to output executable Python code
            instructed_prompt = (
                f"{current_context}\n\n"
                f"Por favor, responde exclusivamente con un bloque de código Python encerrado entre ```python ... ``` para ejecutar en el Sandbox. "
                f"Si ya has alcanzado la solución final, escribe simplemente: 'DONE' y tu respuesta."
            )

            raw_res = await llm.generate(instructed_prompt)
            runtime.event_manager.record_event("agent_thought", raw_res)

            if "DONE" in raw_res:
                return raw_res

            # Extract python block
            code = ""
            if "```python" in raw_res:
                try:
                    parts = raw_res.split("```python")
                    code = parts[1].split("```")[0].strip()
                except Exception:
                    pass

            if not code:
                # No code output or plain text, assume done
                return raw_res

            runtime.event_manager.record_event("sandbox_run", f"Executing code:\n{code}")
            res = await self.sandbox.execute_code(code)

            sandbox_output = f"STDOUT:\n{res['stdout']}\nSTDERR:\n{res['stderr']}\nEXIT CODE: {res['exit_code']}"
            runtime.event_manager.record_event("sandbox_result", sandbox_output)

            # Accumulate history for next turn
            current_context += f"\nTurno {turn} ejecutó código:\n{code}\nResultado:\n{sandbox_output}"

        return "Reached maximum CodeAct turns."
