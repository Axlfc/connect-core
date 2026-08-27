import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.metrics import metrics

client = TestClient(app)

def test_metrics_endpoint_scraping_and_format():
    # Record test metrics across operations, failures, retries, tokens, and cost
    trace_id_1 = "tr-test-12345"
    metrics.record_operation_duration("agent_loop", 1.25, trace_id=trace_id_1)
    metrics.record_tool_failure("bash", trace_id=trace_id_1)
    metrics.record_retry("worker_client", trace_id=trace_id_1)
    metrics.record_tokens("user_42", "claude-3-5-sonnet", "prompt", 150, trace_id=trace_id_1)
    metrics.record_tokens("user_42", "claude-3-5-sonnet", "completion", 50, trace_id=trace_id_1)
    metrics.record_cost("user_42", "claude-3-5-sonnet", 0.0025, trace_id=trace_id_1)

    # Scrape /metrics endpoint
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "version=0.0.4" in response.headers["content-type"]

    body = response.text

    # Verify Prometheus headers
    assert "# HELP cognito_operation_duration_seconds" in body
    assert "# TYPE cognito_operation_duration_seconds histogram" in body
    assert "# HELP cognito_tool_failures_total" in body
    assert "# TYPE cognito_tool_failures_total counter" in body
    assert "# HELP cognito_tokens_total" in body
    assert "# HELP cognito_cost_dollars_total" in body

    # Verify labels and trace_id cross-referencing
    assert 'cognito_operation_duration_seconds_sum{operation="agent_loop",trace_id="tr-test-12345"} 1.25' in body
    assert 'cognito_operation_duration_seconds_count{operation="agent_loop",trace_id="tr-test-12345"} 1' in body
    assert 'cognito_tool_failures_total{tool_name="bash",trace_id="tr-test-12345"} 1' in body
    assert 'cognito_retries_total{operation="worker_client",trace_id="tr-test-12345"} 1' in body
    assert 'cognito_tokens_total{model="claude-3-5-sonnet",token_type="prompt",trace_id="tr-test-12345",user_id="user_42"} 150' in body
    assert 'cognito_tokens_total{model="claude-3-5-sonnet",token_type="completion",trace_id="tr-test-12345",user_id="user_42"} 50' in body
    assert 'cognito_cost_dollars_total{model="claude-3-5-sonnet",trace_id="tr-test-12345",user_id="user_42"} 0.0025' in body
