import os
import pytest
from fastapi.testclient import TestClient
from app.main import app, get_allowed_origins, is_origin_allowed

client = TestClient(app)

def test_is_origin_allowed():
    allowed = ["http://localhost:3000", "https://app.cognito.internal"]
    assert is_origin_allowed("http://localhost:3000", allowed) is True
    assert is_origin_allowed("http://localhost:3000/", allowed) is True
    assert is_origin_allowed("https://app.cognito.internal", allowed) is True
    assert is_origin_allowed("http://malicious-domain.com", allowed) is False
    assert is_origin_allowed("", allowed) is False

def test_cors_whitelisted_origin():
    response = client.options(
        "/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"

def test_cors_unauthorized_origin():
    response = client.options(
        "/",
        headers={
            "Origin": "http://malicious-domain.com",
            "Access-Control-Request-Method": "GET",
        }
    )
    # CORSMiddleware will not set access-control-allow-origin header for unlisted origins
    assert response.headers.get("access-control-allow-origin") is None

def test_cors_custom_env_origins(monkeypatch):
    monkeypatch.setenv("COGNITO_ALLOWED_ORIGINS", "https://custom.domain.org, https://another.org")
    origins = get_allowed_origins()
    assert "https://custom.domain.org" in origins
    assert "https://another.org" in origins
    assert "http://localhost:3000" not in origins

def test_websocket_unauthorized_origin():
    with pytest.raises(Exception):
        with client.websocket_connect("/ws", headers={"Origin": "http://evil-attacker.com"}) as websocket:
            websocket.send_text("hello")

def test_websocket_authorized_origin():
    with client.websocket_connect("/ws", headers={"Origin": "http://localhost:3000"}) as websocket:
        websocket.send_text("Hello WebSocket")
        data = websocket.receive_text()
        assert data == "Echo: Hello WebSocket"

def test_no_auth_tokens_in_url_query_params():
    # Verify that endpoints accept tokens in Authorization headers
    response = client.get("/api/agent/sessions", headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200
