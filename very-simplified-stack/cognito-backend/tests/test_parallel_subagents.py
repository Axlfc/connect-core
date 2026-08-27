import asyncio
import time
import pytest
from typing import AsyncIterator, Dict, Any
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.agent_loop import agent_loop
from app.core.events import ToolResultEvent, TextDeltaEvent, DoneEvent
from app.core.tools.subagent_tool import SubAgentTool
from app.core.token_budget import estimate_messages_tokens

class MockSlowSearchTool(AgentTool):
    name = "slow_search"
    description = "Simulates a search operation taking artificial delay."
    parameters_schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"]
    }
    is_read_only = True
    concurrency_safe = True

    def __init__(self, delay: float = 0.3):
        self.delay = delay

    async def execute(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        await asyncio.sleep(self.delay)
        return ToolResult(is_error=False, output=f"Search result for '{arguments.get('query')}'")

class MockBackendRouter:
    """
    Mock LLM router that requests two slow_search tool calls simultaneously in turn 1,
    and finishes in turn 2.
    """
    def __init__(self):
        self.call_count = 0

    async def generate_with_tools(self, messages, tools_schema, model_params=None):
        self.call_count += 1
        if self.call_count == 1:
            yield {
                "token": "Searching for both queries...",
                "tool_calls": [
                    {
                        "id": "tc_1",
                        "function": {"name": "slow_search", "arguments": {"query": "auth_service"}}
                    },
                    {
                        "id": "tc_2",
                        "function": {"name": "slow_search", "arguments": {"query": "database_pool"}}
                    }
                ]
            }
        else:
            yield {"token": "Both searches completed successfully."}

@pytest.mark.asyncio
async def test_parallel_tool_execution_speedup():
    # Warm up token budget estimator / tiktoken encoding cache to avoid first-run import/cache latency
    estimate_messages_tokens([{"role": "user", "content": "warmup"}], model="default")

    router = MockBackendRouter()
    tool_parallel = MockSlowSearchTool(delay=0.3)
    ctx = ToolContext(cwd="/tmp", trusted=True, protected_files=set())

    # Measure Parallel execution
    start_time = time.perf_counter()
    events = []
    async for ev in agent_loop(
        messages=[{"role": "user", "content": "Find info on auth and db"}],
        tools=[tool_parallel],
        context=ctx,
        backend_router=router,
        max_turns=3,
        planning_phase=False,
        read_only_turns=0,
    ):
        events.append(ev)

    parallel_elapsed = time.perf_counter() - start_time

    tool_results = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_results) == 2

    # Measure Sequential execution (with concurrency_safe = False)
    router_seq = MockBackendRouter()
    tool_seq = MockSlowSearchTool(delay=0.3)
    tool_seq.concurrency_safe = False

    start_time = time.perf_counter()
    async for _ in agent_loop(
        messages=[{"role": "user", "content": "Find info on auth and db"}],
        tools=[tool_seq],
        context=ctx,
        backend_router=router_seq,
        max_turns=3,
        planning_phase=False,
        read_only_turns=0,
    ):
        pass

    seq_elapsed = time.perf_counter() - start_time

    # Parallel (1 x 0.3s) must be significantly faster than sequential execution (2 x 0.3s = 0.6s)
    assert parallel_elapsed < seq_elapsed, f"Parallel ({parallel_elapsed:.3f}s) should be faster than sequential ({seq_elapsed:.3f}s)"
    assert (seq_elapsed - parallel_elapsed) >= 0.15, f"Parallel execution saved {seq_elapsed - parallel_elapsed:.3f}s (expected >= 0.15s)"

@pytest.mark.asyncio
async def test_subagent_tool_delegation_timeout():
    class TimeoutSubAgentRouter:
        async def generate_with_tools(self, messages, tools_schema, model_params=None):
            await asyncio.sleep(2.0)
            yield {"token": "Delayed"}

    slow_router = TimeoutSubAgentRouter()
    sub_tool = SubAgentTool(backend_router=slow_router, available_tools=[])
    ctx = ToolContext(cwd="/tmp", trusted=True, protected_files=set())

    res = await sub_tool.execute({
        "task_description": "Search deep logs",
        "timeout_seconds": 1,
        "max_turns": 2
    }, ctx)

    assert res.is_error is True
    assert "[SUB-AGENT TIMEOUT]" in res.output
    assert "exceeded the limit of 1s" in res.output
