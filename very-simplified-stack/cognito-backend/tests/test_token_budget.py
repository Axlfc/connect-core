import pytest
from app.core.token_budget import (
    estimate_tokens,
    get_model_context_limit,
    estimate_messages_tokens,
    check_token_budget,
    apply_token_budget_reminder,
    DEFAULT_CONTEXT_LIMIT,
)


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("Hello world") > 0

    # Tiktoken estimation for OpenAI models
    tokens_gpt4 = estimate_tokens("def hello_world(): return 'hello'", model="gpt-4o")
    assert tokens_gpt4 > 0

    # Tiktoken estimation for Ollama models (fallback to cl100k_base or heuristic)
    tokens_ollama = estimate_tokens("def hello_world(): return 'hello'", model="llama3:latest")
    assert tokens_ollama > 0


def test_get_model_context_limit():
    assert get_model_context_limit("gpt-4o") == 128000
    assert get_model_context_limit("gpt-4") == 8192
    assert get_model_context_limit("gpt-3.5-turbo") == 16385
    assert get_model_context_limit("qwen2.5:7b") == 128000
    assert get_model_context_limit("llama3.1:8b") == 128000
    assert get_model_context_limit("unknown-custom-model") == DEFAULT_CONTEXT_LIMIT
    assert get_model_context_limit("") == DEFAULT_CONTEXT_LIMIT


def test_estimate_messages_tokens():
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a python function to compute fibonacci numbers."},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": '{"filepath": "main.py"}'},
                }
            ],
        },
    ]

    total_tokens = estimate_messages_tokens(messages, model="gpt-4o")
    assert total_tokens > 20


def test_check_token_budget_under_threshold():
    small_messages = [{"role": "user", "content": "Hello"}]
    total_tokens, limit, remaining, is_exceeded = check_token_budget(small_messages, model="gpt-4o")

    assert not is_exceeded
    assert limit == 128000
    assert remaining > 0


def test_check_token_budget_over_threshold():
    # Construct a large prompt that exceeds 80% of a model with small limit (e.g., custom/small model context or large text)
    large_text = "This is a long sentence repeated many times. " * 300
    messages = [{"role": "user", "content": large_text}]

    # Force a lower context limit or use gpt-4 (8192 limit) with very large text
    huge_text = "Word " * 7000
    messages_huge = [{"role": "user", "content": huge_text}]

    total_tokens, limit, remaining, is_exceeded = check_token_budget(messages_huge, model="gpt-4", threshold_ratio=0.80)
    assert is_exceeded
    assert total_tokens >= limit * 0.80


def test_apply_token_budget_reminder():
    normal_messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Short question"},
    ]
    res_normal = apply_token_budget_reminder(normal_messages, model="gpt-4o")
    assert len(res_normal) == 2

    # Huge message that triggers threshold
    huge_messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Word " * 7000},
    ]
    res_reminded = apply_token_budget_reminder(huge_messages, model="gpt-4")
    assert len(res_reminded) == 3

    # Check that TokenBudgetReminder message was inserted
    reminder_msg = res_reminded[1]
    assert reminder_msg["role"] == "system"
    assert reminder_msg.get("type") == "TokenBudgetReminder"
    assert "Advertencia: Quedan aproximadamente" in reminder_msg["content"]
    assert "Sé extremadamente conciso, evita leer archivos grandes innecesariamente y prioriza la ejecución de la tarea." in reminder_msg["content"]

    # Re-applying does not duplicate the reminder
    res_duplicated = apply_token_budget_reminder(res_reminded, model="gpt-4")
    assert len(res_duplicated) == 3
