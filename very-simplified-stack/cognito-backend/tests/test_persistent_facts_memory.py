import pytest
from app.core.fact_memory import fact_memory_manager, FactMemoryManager
from app.core.tools.remember_fact_tool import RememberFactTool
from app.core.tools.base import ToolContext
from app.core.system_prompt import build_system_message
from app.core.session_manager import SessionManager
from app.core.session.message_deriver import derive_messages_for_llm, DerivationConfig

@pytest.mark.asyncio
async def test_fact_memory_manager_save_and_retrieve():
    mgr = FactMemoryManager()

    user_id = "usr-test-fact-01"
    project_id = "proj-test-fact-01"

    # Save a fact
    fact1 = mgr.save_fact(
        fact_text="Utilizar siempre sintaxis TypeScript estricta",
        category="estilo",
        user_id=user_id,
        project_id=project_id,
    )
    assert fact1.fact_id.startswith("fact-")
    assert fact1.category == "estilo"
    assert fact1.fact_text == "Utilizar siempre sintaxis TypeScript estricta"

    # Retrieve facts
    facts = mgr.get_facts_for_context(user_id=user_id, project_id=project_id)
    assert len(facts) >= 1
    assert any(f.fact_text == "Utilizar siempre sintaxis TypeScript estricta" for f in facts)

    # Format for prompt
    prompt_text = mgr.format_facts_for_prompt(user_id=user_id, project_id=project_id)
    assert "Hechos recordados (User / Project Memory):" in prompt_text
    assert "[Estilo] [Usuario, Proyecto]: Utilizar siempre sintaxis TypeScript estricta" in prompt_text

@pytest.mark.asyncio
async def test_remember_fact_tool_execution(tmp_path):
    tool = RememberFactTool()
    ctx = ToolContext(cwd=str(tmp_path), trusted=True, protected_files=set())

    res = await tool.execute(
        arguments={
            "fact": "El puerto por defecto para el backend es 8080",
            "category": "configuracion",
            "user_id": "usr-test-tool",
            "project_id": "proj-test-tool"
        },
        context=ctx
    )

    assert res.is_error is False
    assert "Hecho recordado con éxito" in res.output
    assert "El puerto por defecto para el backend es 8080" in res.output

    # Check that it's persisted in DB
    facts = fact_memory_manager.get_facts_for_context(user_id="usr-test-tool")
    assert len(facts) >= 1
    assert facts[0].fact_text == "El puerto por defecto para el backend is 8080" or "El puerto por defecto para el backend es 8080" in facts[0].fact_text

@pytest.mark.asyncio
async def test_facts_injection_across_independent_sessions(tmp_path):
    user_id = "usr-multi-session"
    project_id = "proj-multi-session"
    cwd = str(tmp_path)

    # Session 1: User asks agent to remember fact
    session_mgr = SessionManager()
    session1_id = session_mgr.create(cwd=cwd, user_id=user_id, project_id=project_id)

    tool = RememberFactTool()
    ctx = ToolContext(cwd=cwd, trusted=True, protected_files=set())
    await tool.execute(
        arguments={
            "fact": "Preferir funciones puras y evitar efectos secundarios en app/core",
            "category": "arquitectura",
            "user_id": user_id,
            "project_id": project_id
        },
        context=ctx
    )

    # Session 2: Distinct independent session for the SAME user / project
    session2_id = session_mgr.create(cwd=cwd, user_id=user_id, project_id=project_id)

    config = DerivationConfig(
        cwd=cwd,
        user_id=user_id,
        project_id=project_id,
        extra_messages=[{"role": "user", "content": "¿Qué reglas de arquitectura debo seguir?"}]
    )

    derived_messages = await derive_messages_for_llm(session2_id, config=config)

    # Verify System Prompt contains remembered fact in Session 2
    system_msg = next((m for m in derived_messages if m.get("role") == "system"), None)
    assert system_msg is not None
    assert "Hechos recordados (User / Project Memory):" in system_msg["content"]
    assert "Preferir funciones puras y evitar efectos secundarios en app/core" in system_msg["content"]

@pytest.mark.asyncio
async def test_facts_tenant_isolation(tmp_path):
    user_a = "usr-alice"
    proj_a = "proj-alice"

    user_b = "usr-bob"
    proj_b = "proj-bob"

    # Save fact for User A / Proj A
    fact_memory_manager.save_fact(
        fact_text="Secret key de desarrollo de Alice: ALICE_SECRET_123",
        category="secreto",
        user_id=user_a,
        project_id=proj_a
    )

    # Build system prompt for User B
    system_prompt_b = build_system_message(str(tmp_path), user_id=user_b, project_id=proj_b)

    # Verify User B does NOT see User A's facts
    assert "ALICE_SECRET_123" not in system_prompt_b

    # Build system prompt for User A
    system_prompt_a = build_system_message(str(tmp_path), user_id=user_a, project_id=proj_a)
    assert "ALICE_SECRET_123" in system_prompt_a
