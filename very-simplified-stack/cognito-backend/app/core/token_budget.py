import os
import logging
import tiktoken
from typing import List, Dict, Any, Tuple, Optional, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class TokenBudgetExceededError(Exception):
    """Raised when token consumption exceeds the configured budget hard limit."""
    def __init__(
        self,
        message: str,
        scope: str,
        scope_id: str,
        max_tokens: int,
        current_usage: int,
        requested_tokens: int = 0
    ):
        super().__init__(message)
        self.message = message
        self.scope = scope
        self.scope_id = scope_id
        self.max_tokens = max_tokens
        self.current_usage = current_usage
        self.requested_tokens = requested_tokens

class BudgetConfig(BaseModel):
    scope: Literal["organization", "project", "user", "session"]
    scope_id: str
    max_tokens: int
    warning_threshold_ratio: float = 0.80
    hard_limit_action: Literal["block", "warn_only"] = "block"

class BudgetCheckResult(BaseModel):
    is_warning: bool = False
    is_blocked: bool = False
    exceeded_scope: Optional[str] = None
    exceeded_scope_id: Optional[str] = None
    warning_scopes: List[str] = Field(default_factory=list)
    details: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

class TokenBudgetManager:
    """
    Manages hierarchical token budgets defined at Organization, Project, User, and Session levels.
    Tracks usage across all levels simultaneously and enforces warning alerts and hard limits.
    """
    def __init__(self):
        self.budgets: Dict[Tuple[str, str], BudgetConfig] = {}
        self.usage: Dict[Tuple[str, str], int] = {}

    def _make_key(self, scope: str, scope_id: str) -> Tuple[str, str]:
        return (scope.lower(), scope_id)

    def set_budget(
        self,
        scope: str,
        scope_id: str,
        max_tokens: int,
        warning_threshold_ratio: float = 0.80,
        hard_limit_action: str = "block"
    ) -> BudgetConfig:
        key = self._make_key(scope, scope_id)
        config = BudgetConfig(
            scope=scope.lower(), # type: ignore
            scope_id=scope_id,
            max_tokens=max_tokens,
            warning_threshold_ratio=warning_threshold_ratio,
            hard_limit_action=hard_limit_action # type: ignore
        )
        self.budgets[key] = config
        logger.info(f"Set token budget for [{scope}:{scope_id}] -> max_tokens={max_tokens}, warning={warning_threshold_ratio*100}%")
        return config

    def get_budget(self, scope: str, scope_id: str) -> Optional[BudgetConfig]:
        return self.budgets.get(self._make_key(scope, scope_id))

    def remove_budget(self, scope: str, scope_id: str) -> bool:
        key = self._make_key(scope, scope_id)
        if key in self.budgets:
            del self.budgets[key]
            return True
        return False

    def record_usage(
        self,
        session_id: str,
        tokens_consumed: int,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        org_id: Optional[str] = None
    ) -> None:
        """
        Records token consumption and aggregates it across session, user, project, and organization scopes.
        """
        if tokens_consumed <= 0:
            return

        scopes_to_update = [("session", session_id)]
        if user_id:
            scopes_to_update.append(("user", user_id))
        if project_id:
            scopes_to_update.append(("project", project_id))
        if org_id:
            scopes_to_update.append(("organization", org_id))

        for scope, sid in scopes_to_update:
            key = self._make_key(scope, sid)
            self.usage[key] = self.usage.get(key, 0) + tokens_consumed

    def get_usage(self, scope: str, scope_id: str) -> int:
        return self.usage.get(self._make_key(scope, scope_id), 0)

    def reset_usage(self, scope: str, scope_id: str) -> None:
        key = self._make_key(scope, scope_id)
        if key in self.usage:
            self.usage[key] = 0

    def reset_all_usage(self) -> None:
        self.usage.clear()

    def check_budget(
        self,
        session_id: str,
        additional_tokens: int = 0,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        org_id: Optional[str] = None,
        raise_on_block: bool = False
    ) -> BudgetCheckResult:
        """
        Checks token usage hierarchically across Session, User, Project, and Organization levels.
        Returns a BudgetCheckResult indicating warnings and blocks.
        If raise_on_block is True and a hard limit is breached, raises TokenBudgetExceededError.
        """
        scopes_to_check = [("session", session_id)]
        if user_id:
            scopes_to_check.append(("user", user_id))
        if project_id:
            scopes_to_check.append(("project", project_id))
        if org_id:
            scopes_to_check.append(("organization", org_id))

        result = BudgetCheckResult()

        for scope, sid in scopes_to_check:
            key = self._make_key(scope, sid)
            budget = self.budgets.get(key)
            current_use = self.usage.get(key, 0)
            total_candidate = current_use + additional_tokens

            if not budget:
                result.details[f"{scope}:{sid}"] = {
                    "current_usage": current_use,
                    "candidate_usage": total_candidate,
                    "max_tokens": None,
                    "is_warning": False,
                    "is_blocked": False
                }
                continue

            max_t = budget.max_tokens
            warn_limit = int(max_t * budget.warning_threshold_ratio)
            scope_warning = total_candidate >= warn_limit
            scope_blocked = (total_candidate > max_t) and (budget.hard_limit_action == "block")

            result.details[f"{scope}:{sid}"] = {
                "current_usage": current_use,
                "candidate_usage": total_candidate,
                "max_tokens": max_t,
                "warning_threshold_ratio": budget.warning_threshold_ratio,
                "is_warning": scope_warning,
                "is_blocked": scope_blocked
            }

            if scope_warning:
                result.is_warning = True
                result.warning_scopes.append(f"{scope}:{sid}")

            if scope_blocked:
                result.is_blocked = True
                if not result.exceeded_scope:
                    result.exceeded_scope = scope
                    result.exceeded_scope_id = sid

                if raise_on_block:
                    err_msg = (
                        f"Presupuesto de tokens superado a nivel de {scope.capitalize()} [{sid}]: "
                        f"Uso acumulado ({total_candidate}) supera el límite máximo asignado ({max_t})."
                    )
                    logger.error(err_msg)
                    raise TokenBudgetExceededError(
                        message=err_msg,
                        scope=scope,
                        scope_id=sid,
                        max_tokens=max_t,
                        current_usage=current_use,
                        requested_tokens=additional_tokens
                    )

        return result

# Singleton manager instance
token_budget_manager = TokenBudgetManager()

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
