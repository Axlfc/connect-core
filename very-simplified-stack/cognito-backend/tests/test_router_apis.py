import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.task_store import task_store
from unittest.mock import AsyncMock, patch

@pytest.fixture
def client():
    return TestClient(app)

def test_get_combined_catalog(client):
    resp = client.get("/api/agent/models/catalog")
    assert resp.status_code == 200
    data = resp.json()
    assert "catalog" in data
    # Standard fallback models should be listed
    models = [m["model_identifier"] for m in data["catalog"]]
    assert "codex.economy" in models
    assert "codex.balanced" in models
    assert "codex.max" in models

def test_route_preview(client):
    payload = {
        "user_task": "rename variable name from user_id to uid",
        "workspace_folder": "/tmp/test",
        "detected_technologies": ["python"]
    }
    resp = client.post("/api/agent/route/preview", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "executor" in data
    assert "logical_tier" in data
    assert "resolved_model_identifier" in data
    # Mechanical rename should prefer Luna
    assert data["logical_tier"] == "luna"

@patch("app.services.escalation_service.worker_client.start_task")
@patch("app.services.escalation_service.worker_client.verify_task")
def test_task_creation_and_escalation_flow(mock_verify, mock_start, client):
    # Mock worker calls
    mock_start.return_value = AsyncMock()
    mock_verify.return_value = {
        "exit_status": 1,
        "failed_tests": ["test_feature"],
        "failure_classification": "model_related"
    }

    # 1. Create a task
    task_payload = {
        "task_id": "test-task-123",
        "session_id": "session-123",
        "title": "Rename task",
        "requirements": "Rename calculate_sum to calc_sum",
        "context": {
            "repository": {
                "repository_id": "repo-123",
                "root_path": "/tmp/repo",
                "current_branch": "main",
                "base_commit": "abc1234",
                "is_dirty": False,
                "changed_files_count": 0
            },
            "editor": {
                "workspace_folder": "/tmp/repo"
            },
            "user_task": "Rename calculate_sum to calc_sum"
        }
    }

    resp = client.post("/api/agent/tasks", json=task_payload)
    assert resp.status_code == 200
    task_data = resp.json()
    assert task_data["task_id"] == "test-task-123"
    assert task_data["route_decision"]["logical_tier"] == "luna"

    # 2. Cancel the task
    resp_cancel = client.post("/api/agent/tasks/test-task-123/cancel")
    assert resp_cancel.status_code == 200
    assert resp_cancel.json()["status"] == "success"

    # Verify task status updated
    resp_get = client.get("/api/agent/tasks/test-task-123")
    assert resp_get.json()["status"] == "cancelled"

    # 3. Manual Retry/Escalate
    resp_retry = client.post("/api/agent/tasks/test-task-123/retry")
    assert resp_retry.status_code == 200
    retry_data = resp_retry.json()
    assert "attempt" in retry_data
    # First attempt should run on the default computed tier (luna)
    assert retry_data["attempt"]["route_decision"]["logical_tier"] == "luna"
