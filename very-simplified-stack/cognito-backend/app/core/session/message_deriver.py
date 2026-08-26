import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field

from app.core.system_prompt import build_system_message
from app.core.token_budget import apply_token_budget_reminder
from app.core.context_spill import default_spill_manager, SpillManager
from app.core.compaction import format_ledger_for_system_prompt

logger = logging.getLogger(__name__)

# Pydantic models for strong typing of event log records (.jsonl)

class BaseSessionEvent(BaseModel):
    type: str
    ts: Optional[str] = None

class MessageEvent(BaseSessionEvent):
    type: Literal["message"] = "message"
    role: str
    content: str
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

class CompactionEvent(BaseSessionEvent):
    type: Literal["compaction"] = "compaction"
    summary: str
    covers_through_line: int
    context_ledger: Optional[Dict[str, Any]] = None

class InternalSystemEvent(BaseSessionEvent):
    type: Literal["internal_system", "system_internal", "telemetry", "audit", "hook_internal"]
    data: Optional[Dict[str, Any]] = None

SessionEvent = Union[MessageEvent, CompactionEvent, InternalSystemEvent, BaseSessionEvent]

class DerivationConfig(BaseModel):
    cwd: Optional[str] = None
    model_name: Optional[str] = None
    sessions_dir: Optional[Path] = None
    exclude_internal: bool = True
    enable_spill_injection: bool = True
    spill_threshold_tokens: int = 2000
    spill_manager: Optional[Any] = None
    extra_messages: List[Dict[str, Any]] = Field(default_factory=list)

def _parse_event_line(line: str) -> Optional[SessionEvent]:
    line_str = line.strip()
    if not line_str:
        return None
    try:
        data = json.loads(line_str)
        event_type = data.get("type")
        if event_type == "message":
            return MessageEvent(**data)
        elif event_type == "compaction":
            return CompactionEvent(**data)
        elif event_type in ("internal_system", "system_internal", "telemetry", "audit", "hook_internal"):
            return InternalSystemEvent(**data)
        else:
            return BaseSessionEvent(**data)
    except Exception as e:
        logger.warning(f"Failed to parse session event line: {e}")
        return None

def _format_message(msg: MessageEvent, spill_mgr: Optional[SpillManager], enable_spill: bool, spill_threshold: int) -> Dict[str, Any]:
    content = msg.content
    if enable_spill and spill_mgr and spill_mgr.should_spill(content, threshold=spill_threshold):
        try:
            spill_id = spill_mgr.spill(content, metadata={"role": msg.role, "tool_name": msg.tool_name})
            content = f"[Context Spill References Active: Content exceeded threshold. Spilled to ID: {spill_id}. Use query_spill tool with spill_id '{spill_id}' to inspect.]"
        except Exception as e:
            logger.error(f"Failed to spill message content for LLM derivation: {e}")

    item: Dict[str, Any] = {"role": msg.role, "content": content}
    if msg.role == "tool" or msg.tool_name:
        item["name"] = msg.tool_name
    if msg.tool_call_id:
        item["tool_call_id"] = msg.tool_call_id
    if msg.tool_calls:
        item["tool_calls"] = msg.tool_calls
    return item

async def derive_messages_for_llm(
    session_id: str,
    config: DerivationConfig,
) -> List[Dict[str, Any]]:
    """
    Derives the LLM messages prompt array from a session's persistent JSONL event log.
    Decouples raw event persistence from LLM prompt formatting.
    """
    sessions_dir = config.sessions_dir or (Path.home() / ".cognito" / "sessions")
    session_file = Path(sessions_dir) / f"{session_id}.jsonl"

    entries: List[tuple[int, SessionEvent]] = []

    if session_file.exists():
        with open(session_file, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                event = _parse_event_line(line)
                if event:
                    entries.append((idx, event))

    # Identify latest compaction event and effective range
    compaction_event: Optional[CompactionEvent] = None
    compaction_line_idx: int = -1

    for idx, event in entries:
        if isinstance(event, CompactionEvent):
            compaction_event = event
            compaction_line_idx = idx

    derived_messages: List[Dict[str, Any]] = []

    # 1. System Prompt injection if cwd provided
    if config.cwd:
        system_prompt = build_system_message(config.cwd)
        derived_messages.append({"role": "system", "content": system_prompt})

    # 2. Compaction summary injection
    if compaction_event:
        compaction_content = f"[Resumen de la conversación anterior]: {compaction_event.summary}"
        if compaction_event.context_ledger:
            ledger_text = format_ledger_for_system_prompt(compaction_event.context_ledger)
            if ledger_text:
                compaction_content += f"\n\n{ledger_text}"

        summary_msg = {"role": "system", "content": compaction_content}
        derived_messages.append(summary_msg)
        start_line = compaction_event.covers_through_line
    else:
        start_line = -1

    spill_mgr = config.spill_manager or default_spill_manager

    # 3. Process events following compaction rules and filtering
    for idx, event in entries:
        # Skip events covered by compaction
        if compaction_event and idx <= start_line:
            continue

        # Filter internal system events
        if config.exclude_internal and isinstance(event, InternalSystemEvent):
            continue

        if isinstance(event, MessageEvent):
            formatted_msg = _format_message(
                event,
                spill_mgr=spill_mgr,
                enable_spill=config.enable_spill_injection,
                spill_threshold=config.spill_threshold_tokens,
            )
            derived_messages.append(formatted_msg)

    # 4. Append extra unpersisted messages (e.g., incoming request messages)
    if config.extra_messages:
        for msg in config.extra_messages:
            derived_messages.append(msg)

    # 5. Apply Token Budget Reminder injection
    final_messages = apply_token_budget_reminder(derived_messages, model=config.model_name or "")
    return final_messages
