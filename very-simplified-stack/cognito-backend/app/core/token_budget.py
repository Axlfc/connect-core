import os
import logging
import tiktoken
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

# Default model context window limits (in tokens)
MODEL_CONTEXT_LIMITS: Dict[str, int] = {
    # OpenAI Models
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
    "o1": 128000,
    "o3": 128000,
    # Ollama / Open Source Models
    "llama3.3": 128000,
    "llama3.2": 128000,
    "llama3.1": 128000,
    "llama3": 8192,
    "llama2": 4096,
    "qwen2.5": 128000,
    "qwen2": 32768,
    "deepseek-r1": 128000,
    "deepseek-v3": 128000,
    "deepseek": 64000,
    "mistral": 32768,
    "mixtral": 32768,
    "codex": 128000,
}

DEFAULT_CONTEXT_LIMIT = int(os.getenv("COGNITO_DEFAULT_MODEL_CONTEXT_LIMIT", "8192"))


def get_model_context_limit(model: str = "") -> int:
    """
    Returns the maximum token limit (context window size) for a given model.
    Checks exact match first, then substring match against known models,
    and falls back to DEFAULT_CONTEXT_LIMIT.
    """
    if not model:
        return DEFAULT_CONTEXT_LIMIT

    model_lower = model.lower()

    # Exact or prefix match
    for key, limit in MODEL_CONTEXT_LIMITS.items():
        if key in model_lower:
            return limit

    return DEFAULT_CONTEXT_LIMIT


def _get_encoding_for_model(model: str = ""):
    """
    Safely retrieves a tiktoken encoding for a model, falling back to cl100k_base.
    """
    if model:
        try:
            return tiktoken.encoding_for_model(model)
        except Exception:
            pass

    # Default fallback encoder (used by gpt-4, gpt-3.5-turbo, and many open-source models)
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        logger.warning(f"Failed to load tiktoken cl100k_base encoding: {e}")
        return None


def estimate_tokens(text: str, model: str = "") -> int:
    """
    Estimates token count for a text string using tiktoken.
    Falls back to character-based heuristic (chars // 4) if tiktoken fails.
    """
    if not text:
        return 0

    encoding = _get_encoding_for_model(model)
    if encoding is not None:
        try:
            return len(encoding.encode(text, disallowed_special=()))
        except Exception as e:
            logger.debug(f"tiktoken encoding failed for text length {len(text)}: {e}")

    # Fallback heuristic: 1 token approx 4 characters
    return len(text) // 4


def estimate_messages_tokens(messages: List[Dict[str, Any]], model: str = "") -> int:
    """
    Estimates total prompt tokens across all messages in a conversation.
    Includes role names, content, tool call arguments, and tool call IDs.
    """
    total_tokens = 0
    encoding = _get_encoding_for_model(model)

    for msg in messages:
        # Every message has a role overhead (approx 4 tokens per message)
        total_tokens += 4

        role = msg.get("role", "")
        if role:
            total_tokens += estimate_tokens(role, model)

        content = msg.get("content")
        if content:
            if isinstance(content, str):
                total_tokens += estimate_tokens(content, model)
            elif isinstance(content, list):
                # Handle structured content (e.g., text blocks / image descriptions)
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            total_tokens += estimate_tokens(item.get("text", ""), model)
                    elif isinstance(item, str):
                        total_tokens += estimate_tokens(item, model)

        # Count tool call details
        if "tool_calls" in msg and isinstance(msg["tool_calls"], list):
            for tc in msg["tool_calls"]:
                if isinstance(tc, dict):
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "")
                    fn_args = fn.get("arguments", "")
                    total_tokens += estimate_tokens(fn_name, model)
                    total_tokens += estimate_tokens(str(fn_args), model)

        if "name" in msg and msg["name"]:
            total_tokens += estimate_tokens(msg["name"], model)

        if "tool_call_id" in msg and msg["tool_call_id"]:
            total_tokens += estimate_tokens(msg["tool_call_id"], model)

    # Overhead for priming the assistant response (~3 tokens)
    total_tokens += 3
    return total_tokens


def check_token_budget(
    messages: List[Dict[str, Any]],
    model: str = "",
    threshold_ratio: float = 0.80
) -> Tuple[int, int, int, bool]:
    """
    Calculates token usage and determines if it exceeds the threshold ratio (default 80%).

    Returns:
        Tuple of (total_tokens, limit, remaining_tokens, is_exceeded)
    """
    limit = get_model_context_limit(model)
    total_tokens = estimate_messages_tokens(messages, model)
    remaining_tokens = max(0, limit - total_tokens)
    is_exceeded = total_tokens >= (limit * threshold_ratio)

    return total_tokens, limit, remaining_tokens, is_exceeded


def apply_token_budget_reminder(
    messages: List[Dict[str, Any]],
    model: str = "",
    threshold_ratio: float = 0.80
) -> List[Dict[str, Any]]:
    """
    Checks token usage. If prompt tokens exceed threshold_ratio (default 80%) of the model's limit,
    injects a TokenBudgetReminder system message warning the model to be concise.
    """
    total_tokens, limit, remaining_tokens, is_exceeded = check_token_budget(messages, model, threshold_ratio)

    if not is_exceeded:
        return messages

    reminder_text = (
        f"Advertencia: Quedan aproximadamente {remaining_tokens} tokens. "
        "Sé extremadamente conciso, evita leer archivos grandes innecesariamente y prioriza la ejecución de la tarea."
    )

    # Check if reminder message already present to avoid duplicating it
    for msg in reversed(messages):
        if msg.get("role") in ("system", "developer") and "Advertencia: Quedan aproximadamente" in msg.get("content", ""):
            return messages

    logger.warning(
        f"Token budget threshold exceeded: {total_tokens}/{limit} tokens ({total_tokens/limit*100:.1f}%). "
        f"Injecting TokenBudgetReminder ({remaining_tokens} tokens remaining)."
    )

    reminder_msg = {"role": "system", "content": reminder_text, "type": "TokenBudgetReminder"}

    # Inject after initial system prompt if present, or at the end of messages
    updated_messages = list(messages)
    if updated_messages and updated_messages[0].get("role") == "system":
        updated_messages.insert(1, reminder_msg)
    else:
        updated_messages.append(reminder_msg)

    return updated_messages
