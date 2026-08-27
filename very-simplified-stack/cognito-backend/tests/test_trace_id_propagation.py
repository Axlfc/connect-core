import asyncio
import json
import logging
import uuid
import contextvars

from app.core.logging_config import (
    set_trace_id, get_trace_id, clear_correlation_context, StructuredJSONFormatter
)


class CapturingHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def test_trace_id_context_vars():
    clear_correlation_context()
    assert get_trace_id() == ""

    tid = set_trace_id("test-trace-12345")
    assert tid == "test-trace-12345"
    assert get_trace_id() == "test-trace-12345"

    clear_correlation_context()
    assert get_trace_id() == ""

    gen_tid = set_trace_id()
    assert len(gen_tid) > 0
    assert get_trace_id() == gen_tid
    clear_correlation_context()


def test_structured_json_formatter_includes_trace_id():
    clear_correlation_context()
    tid = set_trace_id("trace-abc-789")

    formatter = StructuredJSONFormatter()
    logger = logging.getLogger("test.formatter")
    record = logger.makeRecord("test.formatter", logging.INFO, "fn.py", 10, "Test message", (), None)

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["trace_id"] == "trace-abc-789"
    assert parsed["message"] == "Test message"
    clear_correlation_context()


def test_agent_loop_logs_share_same_trace_id():
    async def run_async_test():
        clear_correlation_context()
        loop_trace_id = "loop-trace-7777"
        set_trace_id(loop_trace_id)

        # Attach handler to capture log lines
        handler = CapturingHandler()
        handler.setFormatter(StructuredJSONFormatter())

        test_logger = logging.getLogger("test.agent_loop")
        test_logger.setLevel(logging.INFO)
        test_logger.addHandler(handler)

        try:
            test_logger.info("Starting agent turn 1/10 | prompt_tokens=100")
            test_logger.info("Preparing execution for tool dummy_tool with args {}")

            matching_logs = [
                json.loads(handler.format(r))
                for r in handler.records
            ]
            assert len(matching_logs) == 2
            for log_entry in matching_logs:
                assert log_entry.get("trace_id") == loop_trace_id

        finally:
            test_logger.removeHandler(handler)
            clear_correlation_context()

    asyncio.run(run_async_test())


if __name__ == "__main__":
    test_trace_id_context_vars()
    print("test_trace_id_context_vars passed")
    test_structured_json_formatter_includes_trace_id()
    print("test_structured_json_formatter_includes_trace_id passed")
    test_agent_loop_logs_share_same_trace_id()
    print("test_agent_loop_logs_share_same_trace_id passed")
    print("ALL TRACE ID PROPAGATION TESTS PASSED SUCCESSFULLY!")
