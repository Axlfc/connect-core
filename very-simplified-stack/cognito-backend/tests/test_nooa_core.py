import pytest
import asyncio
from pydantic import BaseModel
from app.core.config import ConfigurationManager
from app.core.visibility import VisibilityFilter, hidden
from app.core.agent_doc import AgentDocGenerator
from app.services.unified_llm import UnifiedLLM, FakeLLMClient
from app.core.meta import NOOAMeta
from app.core.event_manager import EventManager
from app.core.context_blocks import DynamicContextManager
from app.core.sandbox import SandboxedExecutor
from app.core.runtime import ActorRuntime
from app.core.strategies import PredictStrategy, CodeActStrategy
from app.core.skills import SkillRegistry, TextSkill
from app.core.tools.nooa_tools import TodoTools
from app.core.tracing import TraceScrubber
from app.core.atif import ATIFTrajectory

# Test Pydantic contract model
class PersonContract(BaseModel):
    name: str
    age: int

# An Agent subclass using NOOAMeta
class MockNooaAgent(metaclass=NOOAMeta):
    """
    Test agent class documentation.
    """
    def __init__(self):
        # Attach a fake LLM to ensure deterministic testing
        self.llm_client = FakeLLMClient(replays=[
            '{"name": "Alice", "age": 30}',
            '42'
        ])

    async def generate_profile(self) -> PersonContract:
        """
        Genera el perfil de una persona.
        ...
        """
        ...

    async def get_meaning_of_life(self) -> int:
        """
        Devuelve el significado de la vida.
        ...
        """
        ...

    @hidden
    def invisible_method(self):
        pass

    def _private_method(self):
        pass

def test_configuration_manager_hierarchy():
    config = ConfigurationManager.resolve(overrides={"model": {"model_identifier": "custom-override"}})
    assert config.model.model_identifier == "custom-override"

def test_visibility_selective():
    agent = MockNooaAgent()
    assert not VisibilityFilter.is_visible("invisible_method", agent.invisible_method)
    assert not VisibilityFilter.is_visible("_private_method", agent._private_method)
    assert VisibilityFilter.is_visible("generate_profile", agent.generate_profile)

def test_agent_doc_generation():
    doc = AgentDocGenerator.generate(MockNooaAgent)
    assert "MockNooaAgent" in doc
    assert "generate_profile" in doc
    assert "invisible_method" not in doc
    assert "_private_method" not in doc

@pytest.mark.asyncio
async def test_nooa_meta_wrapping_and_contracts():
    agent = MockNooaAgent()
    profile = await agent.generate_profile()
    assert isinstance(profile, PersonContract)
    assert profile.name == "Alice"
    assert profile.age == 30

    meaning = await agent.get_meaning_of_life()
    assert meaning == 42

def test_event_manager():
    em = EventManager()
    em.record_event("thought", "Analyzing code")
    em.record_event("action", "Run sandbox")
    summary = em.summarize_short_term()
    assert "THOUGHT" in summary
    assert "ACTION" in summary

def test_context_blocks():
    mgr = DynamicContextManager()
    mgr.register_block("os_type", lambda: "linux-x64")
    xml = mgr.evaluate_all("xml")
    assert "<os_type>" in xml
    assert "linux-x64" in xml

@pytest.mark.asyncio
async def test_sandbox_executor():
    box = SandboxedExecutor()
    res = await box.execute_code("print('hello sandbox')")
    assert "hello sandbox" in res["stdout"]
    assert res["exit_code"] == 0

@pytest.mark.asyncio
async def test_actor_runtime_and_predict_strategy():
    agent = MockNooaAgent()
    runtime = ActorRuntime(agent)
    strategy = PredictStrategy()
    res = await runtime.execute_turn("Hola", strategy)
    assert "{" in res or "Mock" in res

def test_skill_registry():
    reg = SkillRegistry()
    skill = TextSkill("PythonDev", "System Prompt", "Write pure Python")
    reg.register_skill(skill)
    agent = MockNooaAgent()
    reg.inject_to_agent(agent, "PythonDev")
    assert hasattr(agent, "skill_pythondev")

@pytest.mark.asyncio
async def test_nooa_todo_tools():
    tool = TodoTools()
    from app.core.tools.base import ToolContext
    ctx = ToolContext(cwd=".", trusted=True, protected_files=set())
    res = await tool.execute({"action": "add", "item": "Buy groceries"}, ctx)
    assert "Added" in res.output

def test_trace_scrubbing():
    scrubbed = TraceScrubber.scrub_text("api_key = sk-1234567890abcdef1234567890abcdef")
    assert "[REDACTED]" in scrubbed

def test_atif_trajectory():
    traj = ATIFTrajectory()
    traj.add_step("Thought process", "tool_x", {"arg": 1}, "output_y")
    res = traj.export_json()
    assert "atif_version" in res
    assert "trajectory" in res
