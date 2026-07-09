"""
Mapeo de escalado: qué backend+modelo usar como reintento cuando la incertidumbre
agregada de una subtarea supera el umbral. Es un punto de partida con los modelos
que ya aparecen en MODEL_ROUTING (app/services/semantic_orchestrator.py) — no se
inventan modelos nuevos que no estén confirmados como disponibles en el stack real.

Axel: revisa y ajusta estas entradas según qué modelos tengas realmente disponibles.
No todos los intents tienen un target de escalado por defecto — traducción, visión y
edge son tareas especializadas donde "escalar" a un modelo de texto genérico rompería
la tarea en vez de mejorarla, así que se dejan sin target (no se escalan).
"""
from typing import Dict

ESCALATION_ROUTING: Dict[str, Dict[str, str]] = {
    "fast": {"backend": "ollama-local", "model": "qwen3.5:9b"},
    "general": {"backend": "ollama-local", "model": "phi4:latest"},
    "coding": {"backend": "ollama-local", "model": "phi4:latest"},
    "analysis": {"backend": "ollama-local", "model": "phi4:latest"},
    # reasoning, translation, vision, edge: sin entrada -> no se escalan.
}
