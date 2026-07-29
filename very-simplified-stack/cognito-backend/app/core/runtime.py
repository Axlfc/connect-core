import logging
from typing import Any, Callable, Dict, List, Optional
from app.core.event_manager import EventManager
from app.core.context_blocks import DynamicContextManager

logger = logging.getLogger(__name__)

class ActorRuntime:
    """
    Orchestrates agent life cycle, connecting EventManager, ContextBlocks,
    and handling custom pre/post hooks via intercept() (NOOA-12).
    """
    def __init__(self, agent_instance: Any, session_id: Optional[str] = None):
        self.agent = agent_instance
        self.event_manager = EventManager(session_id=session_id)
        self.context_manager = DynamicContextManager()
        self._interceptors: List[Callable[[str, Dict[str, Any]], None]] = []

        # Connect event manager to agent if possible
        if hasattr(self.agent, "event_manager"):
            self.agent.event_manager = self.event_manager

    def register_interceptor(self, interceptor: Callable[[str, Dict[str, Any]], None]):
        """
        Registers hook 'intercept()' to monitor LLM/Tool interactions.
        """
        self._interceptors.append(interceptor)

    def trigger_intercept(self, phase: str, payload: Dict[str, Any]):
        for cb in self._interceptors:
            try:
                cb(phase, payload)
            except Exception as e:
                logger.error(f"Error executing intercept hook: {e}")

    async def execute_turn(self, user_prompt: str, strategy) -> Any:
        """
        Executes a turn orchestrating all modules.
        """
        self.event_manager.record_event("user_input", user_prompt)
        self.trigger_intercept("pre_turn", {"prompt": user_prompt})

        # Inject context blocks
        live_context = self.context_manager.evaluate_all()
        full_prompt = f"{user_prompt}\n\n[CONTESTO VIVO]\n{live_context}" if live_context else user_prompt

        # Run selected strategy
        result = await strategy.execute(full_prompt, self)

        self.trigger_intercept("post_turn", {"result": result})
        self.event_manager.record_event("turn_complete", str(result))
        return result
