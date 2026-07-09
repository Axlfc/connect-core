import math
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

def compute_uncertainty(logprob_data: Any) -> Optional[float]:
    """
    Shannon entropy of the top-k distribution, normalized to [0, 1].
    Expects Ollama-style logprobs data.
    """
    if not logprob_data:
        return None

    top_logprobs = {}
    if isinstance(logprob_data, list) and logprob_data:
        # Ollama returns a list of token info, usually just one for the current token
        entry = logprob_data[0]
        for candidate in entry.get("top_logprobs", []):
            top_logprobs[candidate["token"]] = candidate["logprob"]
    elif isinstance(logprob_data, dict):
        # Already parsed or different format
        top_logprobs = logprob_data

    if not top_logprobs:
        return None

    try:
        probs = [math.exp(lp) for lp in top_logprobs.values()]
        total = sum(probs)
        if total == 0:
            return 0.0
        probs = [p / total for p in probs]
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        max_entropy = math.log2(len(probs)) if len(probs) > 1 else 1.0
        return entropy / max_entropy if max_entropy > 0 else 0.0
    except Exception as e:
        logger.error("[Uncertainty] Error computing entropy: %s", e)
        return None

def aggregate_uncertainty(per_token_values: list[float]) -> Optional[float]:
    """Media aritmética simple de las incertidumbres por token de una respuesta completa.
    Devuelve None si la lista está vacía (el backend no devolvió logprobs).
    Se usa la media y no el máximo para no disparar escalado por un único token ruidoso."""
    if not per_token_values:
        return None
    return sum(per_token_values) / len(per_token_values)
