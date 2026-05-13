"""
backend_registry.py

Defines all available AI backends and their priority order.
Last verified: 2026-03-23 — model lists confirmed via /api/tags and /v1/models.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NODE INVENTORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Priority 1 — 192.168.1.15:11434  Windows GPU / Ollama native
    Available models (change `model` field to switch default):
      "qwen3-coder:30b"                  30.5B Q4_K_M  ← best for code
      "qwen2.5:72b-instruct-q4_K_M"     72.7B Q4_K_M  ← best quality
      "llama3.3:70b-instruct-q4_K_M"    70.6B Q4_K_M
      "glm-4.7-flash:latest"            29.9B Q4_K_M
      "qwen3.5:9b"                        9.7B Q4_K_M  ← fast default ✓
      "qwen3:8b"                          8.2B Q4_K_M
      "llama3:8b"                         8.0B Q4_0
      "cogito:14b"                       14.8B Q4_K_M
      "devstral-small-2:latest"          24.0B Q4_K_M
      "mistral:latest"                    7.2B Q4_K_M
      "translategemma:latest"             4.3B Q4_K_M
      "kimi-k2.5:cloud"                  remote / cloud proxy
      "nomic-embed-text:latest"          137M  embeddings only

  Priority 2 — 192.168.1.100:8000  M5Stack LLM630 (AX630C, 3.2 TOPS)
    Available models:
      "qwen2.5-1.5B-ax630c"            ← primary LLM ✓
      "qwen2.5-0.5B-Int4-ax630c"
      "qwen2.5-0.5B-prefill-20e"
      "qwen2.5-coder-0.5B-ax630c"
      "qwen3-0.6B-ax630c"
      "deepseek-r1-1.5B-ax630c"
      "llama3.2-1B-prefill-ax630c"
      "internvl2.5-1B-ax630c"          vision
      "internvl2.5-1B-364-ax630c"      vision
      "whisper-tiny"                    ASR
      "sherpa-ncnn-streaming-zipformer-20M-2023-02-17"   ASR
      "sherpa-ncnn-streaming-zipformer-zh-14M-2023-02-23" ASR
      "melotts-zh-cn"                   TTS
      "melotts-es-es"                   TTS
      "single-speaker-english-fast"     TTS
      "single-speaker-fast"             TTS

  Priority 3 — 192.168.1.75:8000   Axera AX650N / RPi5
    Available models:
      "AXERA-TECH/Qwen3-0.6B"          ← only model ✓

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from dataclasses import dataclass, field
from enum import Enum


class BackendType(str, Enum):
    OLLAMA = "ollama"   # Native Ollama  → POST /api/generate
    OPENAI = "openai"   # OpenAI-compat  → POST /v1/chat/completions


@dataclass
class BackendConfig:
    name: str
    base_url: str           # No trailing slash. /v1 appended automatically for OPENAI.
    backend_type: BackendType
    model: str              # Must match exactly what the backend exposes
    priority: int           # Lower = tried first
    timeout: int = 120
    health_timeout: int = 5
    enabled: bool = True
    extra_headers: dict = field(default_factory=dict)


# ── Active backends ────────────────────────────────────────────────────────────

BACKENDS: list[BackendConfig] = [

    # -- Priority 1: Local Blackwell GPU (CachyOS) -----------------------------
    BackendConfig(
        name="ollama-local",
        base_url="http://host.docker.internal:11434",
        backend_type=BackendType.OLLAMA,
        model="qwen3.5:9b", 
        priority=1,
    ),  # <--- ESTA COMA ES VITAL

    # -- Priority 2: M5Stack LLM630 ---------------------
    BackendConfig(
        name="m5stack-llm630",
        base_url="http://192.168.1.100:8000",
        backend_type=BackendType.OPENAI,
        model="qwen2.5-1.5B-ax630c",
        priority=2,
        enabled=True,
    ), # <--- Aquí también, por buena práctica

    # -- Priority 3: Axera AX650N / RPi5 ---------------------------------------
    BackendConfig(
        name="axera-ax650n-rpi5",
        base_url="http://192.168.1.75:8000",
        backend_type=BackendType.OPENAI,
        model="AXERA-TECH/Qwen3-0.6B",
        priority=3,
        enabled=False,
    ),
]

# Pre-sorted at import time — no runtime cost
BACKENDS_BY_PRIORITY: list[BackendConfig] = sorted(
    [b for b in BACKENDS if b.enabled],
    key=lambda b: b.priority,
)
