import pytest
import json
import io
from unittest.mock import MagicMock, AsyncMock
from cli.modes.print_mode import print_mode, get_uncertainty_color
from cli.modes.json_mode import json_mode
from cli.modes.rpc_mode import rpc_mode
from cli.config import CognitoConfig

def test_uncertainty_color():
    # Blue-ish
    c1 = get_uncertainty_color(0.1)
    # 0.1 / 0.5 = 0.2
    # R = 100 + 0.2*(255-100) = 100 + 31 = 131
    # G = 200
    # B = 255 + 0.2*(60-255) = 255 - 39 = 216
    assert "\x1b[38;2;131;200;216m" == c1

    # Red-ish
    c2 = get_uncertainty_color(0.9)
    # (0.9 - 0.5) / 0.5 = 0.8
    # R = 255
    # G = 200 + 0.8*(60-200) = 200 - 112 = 88
    # B = 60 + 0.8*(40-60) = 60 - 16 = 44
    assert "\x1b[38;2;255;88;44m" == c2

@pytest.mark.asyncio
async def test_json_mode(capsys):
    async def event_iter():
        yield {"type": "text_delta", "content": "hi"}
        yield {"type": "done", "stop_reason": "end_turn"}

    config = MagicMock(spec=CognitoConfig)
    code = await json_mode(event_iter(), config)

    out, err = capsys.readouterr()
    lines = out.strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["content"] == "hi"
    assert code == 0

@pytest.mark.asyncio
async def test_rpc_mode(monkeypatch, capsys):
    # Mock stdin
    req1 = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "health"})
    monkeypatch.setattr("sys.stdin", io.StringIO(req1 + "\n"))

    client = MagicMock()
    client.health = AsyncMock(return_value={"status": "ok"})
    config = MagicMock(spec=CognitoConfig)

    await rpc_mode(client, config)

    out, err = capsys.readouterr()
    resp = json.loads(out.strip())
    assert resp["id"] == 1
    assert resp["result"]["status"] == "ok"
