import os
import json
import tempfile
from pathlib import Path
from cli.config import load_config

def test_load_config_defaults():
    config = load_config()
    assert config.endpoint == "http://localhost:8000"
    assert config.uncertainty_threshold == 0.55
    assert config.enable_uncertainty is True

def test_load_config_file(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_home = Path(tmpdir)
        monkeypatch.setattr(Path, "home", lambda: tmp_home)

        cognito_dir = tmp_home / ".cognito"
        cognito_dir.mkdir()
        config_file = cognito_dir / "config.json"
        config_file.write_text(json.dumps({
            "Endpoint": "http://remote:9000",
            "UncertaintyThreshold": 0.8,
            "ColorMode": "threshold"
        }))

        config = load_config()
        assert config.endpoint == "http://remote:9000"
        assert config.uncertainty_threshold == 0.8
        assert config.color_mode == "threshold"

def test_load_config_env(monkeypatch):
    monkeypatch.setenv("COGNITO_ENDPOINT", "http://env:7000")
    monkeypatch.setenv("COGNITO_UNCERTAINTY_THRESHOLD", "0.4")

    config = load_config()
    assert config.endpoint == "http://env:7000"
    assert config.uncertainty_threshold == 0.4

def test_load_config_cli():
    config = load_config(cli_endpoint="http://cli:6000", cli_threshold=0.1)
    assert config.endpoint == "http://cli:6000"
    assert config.uncertainty_threshold == 0.1
