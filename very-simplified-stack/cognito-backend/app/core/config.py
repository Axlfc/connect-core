import os
import json
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class ModelConfig(BaseModel):
    model_identifier: str = "gpt-4o"
    provider: str = "openai"
    temperature: float = 0.7
    max_tokens: int = 2048
    api_key: Optional[str] = None
    base_url: Optional[str] = None

class StrategyConfig(BaseModel):
    strategy_name: str = "Predict"  # "Predict" or "CodeAct"
    max_turns: int = 10
    timeout_seconds: int = 300

class TruncationConfig(BaseModel):
    max_context_tokens: int = 16384
    truncation_mode: str = "rolling"  # "rolling", "compaction", "fail"

class ExecutionConfig(BaseModel):
    model: ModelConfig = Field(default_factory=ModelConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    truncation: TruncationConfig = Field(default_factory=TruncationConfig)
    extra: Dict[str, Any] = Field(default_factory=dict)

class ConfigurationManager:
    """
    Manages hierarchically resolved configurations for the NOOA framework.
    Cascade order of precedence: CLI/In-Memory overrides > Environment Variables > JSON Config (nooa.json) > Defaults.
    """
    @staticmethod
    def load_from_json(filepath: str) -> Dict[str, Any]:
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    @classmethod
    def resolve(cls, json_path: str = "nooa.json", overrides: Optional[Dict[str, Any]] = None) -> ExecutionConfig:
        # 1. Start with defaults
        config_dict = {
            "model": {},
            "strategy": {},
            "truncation": {},
            "extra": {}
        }

        # 2. Layer JSON file if exists
        json_data = cls.load_from_json(json_path)
        for key in ["model", "strategy", "truncation", "extra"]:
            if key in json_data and isinstance(json_data[key], dict):
                config_dict[key].update(json_data[key])

        # 3. Layer Environment variables
        # Format: NOOA_MODEL_MODEL_IDENTIFIER, NOOA_STRATEGY_STRATEGY_NAME, etc.
        for env_key, val in os.environ.items():
            if env_key.startswith("NOOA_"):
                parts = env_key.split("_")
                if len(parts) >= 3:
                    section = parts[1].lower()
                    option = "_".join(parts[2:]).lower()
                    if section in config_dict:
                        # Convert basic types
                        if val.isdigit():
                            config_dict[section][option] = int(val)
                        elif val.lower() in ("true", "false"):
                            config_dict[section][option] = val.lower() == "true"
                        else:
                            try:
                                config_dict[section][option] = float(val)
                            except ValueError:
                                config_dict[section][option] = val

        # 4. Layer In-Memory overrides
        if overrides:
            for section, sub_dict in overrides.items():
                if section in config_dict and isinstance(sub_dict, dict):
                    config_dict[section].update(sub_dict)
                elif section not in ["model", "strategy", "truncation", "extra"]:
                    config_dict["extra"][section] = sub_dict

        return ExecutionConfig.model_validate(config_dict)
