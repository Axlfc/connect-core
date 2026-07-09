import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class CognitoConfig:
    endpoint: str
    uncertainty_threshold: float
    enable_uncertainty: bool
    color_mode: str
    timeout: float
    no_color: bool = False

def load_config(
    cli_endpoint: Optional[str] = None,
    cli_threshold: Optional[float] = None,
    cli_no_color: bool = False,
    cli_timeout: Optional[float] = None,
    cli_color_mode: Optional[str] = None
) -> CognitoConfig:
    # 1. Defaults
    config = {
        "Endpoint": "http://localhost:8000",
        "UncertaintyThreshold": 0.55,
        "EnableUncertainty": True,
        "ColorMode": "full",
        "Timeout": 120.0
    }

    # 2. config.json
    config_path = Path.home() / ".cognito" / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                file_config = json.load(f)
                for k, v in file_config.items():
                    if k in config:
                        config[k] = v
        except Exception:
            pass

    # 3. Environment variables
    if os.getenv("COGNITO_ENDPOINT"):
        config["Endpoint"] = os.getenv("COGNITO_ENDPOINT")
    if os.getenv("COGNITO_UNCERTAINTY_THRESHOLD"):
        config["UncertaintyThreshold"] = float(os.getenv("COGNITO_UNCERTAINTY_THRESHOLD"))
    if os.getenv("COGNITO_ENABLE_UNCERTAINTY"):
        config["EnableUncertainty"] = os.getenv("COGNITO_ENABLE_UNCERTAINTY").lower() != "false"
    if os.getenv("COGNITO_COLOR_MODE"):
        config["ColorMode"] = os.getenv("COGNITO_COLOR_MODE")

    # 4. CLI arguments (highest priority)
    if cli_endpoint:
        config["Endpoint"] = cli_endpoint
    if cli_threshold is not None:
        config["UncertaintyThreshold"] = cli_threshold
    if cli_timeout is not None:
        config["Timeout"] = cli_timeout
    if cli_color_mode:
        config["ColorMode"] = cli_color_mode

    return CognitoConfig(
        endpoint=config["Endpoint"],
        uncertainty_threshold=config["UncertaintyThreshold"],
        enable_uncertainty=config["EnableUncertainty"],
        color_mode=config["ColorMode"],
        timeout=config["Timeout"],
        no_color=cli_no_color or config["ColorMode"] == "none"
    )
