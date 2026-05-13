"""
semantic_orchestrator.py

A Perplexity Computer-style orchestration layer for your local AI stack.

Architecture:
  1. The ORCHESTRATOR (largest capable model on Ollama-GPU) receives the raw input.
  2. It produces a structured XML routing plan — no prose, pure machine-readable intent.
  3. The OrchestratorEngine parses the plan and dispatches each subtask to the
     most appropriate backend+model combination.
  4. Results are merged and returned as a single AIResponse.

Routing map (edit MODEL_ROUTING below to tune):
  ┌─────────────────┬──────────────────────────────────┬──────────────────────┐
  │ Intent          │ Backend                          │ Model                │
  ├─────────────────┼──────────────────────────────────┼──────────────────────┤
  │ coding          │ ollama-windows-gpu               │ qwen3-coder:30b      │
  │ reasoning       │ ollama-windows-gpu               │ qwen2.5:72b          │
  │ general         │ ollama-windows-gpu               │ qwen3.5:9b           │
  │ fast/simple     │ m5stack-llm630                   │ qwen2.5-1.5B-ax630c  │
  │ edge/fallback   │ axera-ax650n-rpi5                │ AXERA-TECH/Qwen3-0.6B│
  └─────────────────┴──────────────────────────────────┴──────────────────────┘
"""

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.backend_client import BackendClient
from app.services.backend_registry import BackendConfig, BackendType, BACKENDS_BY_PRIORITY
from app.models.ai import AIRequest, AIResponse

logger = logging.getLogger(__name__)


# ── Routing table: intent → (backend_name, model) ────────────────────────────
# Edit here to reassign tasks to different nodes.

MODEL_ROUTING: Dict[str, Dict[str, str]] = {
    "coding": {
        "backend": "ollama-local",
        "model":   "qwen3:14b",          # Qwen3 de 14B es excelente siguiendo sintaxis
    },
    "reasoning": {
        "backend": "ollama-local",
        "model":   "phi4:latest",        # Phi-4 (Microsoft) supera a casi todos en lógica pura
    },
    "analysis": {
        "backend": "ollama-local",
        "model":   "qwen2.5:14b",       # Usamos la 2.5 de 14B para análisis denso de datos
    },
    "general": {
        "backend": "ollama-local",
        "model":   "qwen3.5:9b",         # Tu modelo equilibrado por defecto
    },
    "fast": {
        "backend": "ollama-local",       # Cambiado a local para máxima velocidad
        "model":   "cogito:8b",         # Tu modelo ligero de confianza
    },
    "translation": {
        "backend": "ollama-local",
        "model":   "translategemma:latest", # Especializado en traducción
    },
    "vision": {
        "backend": "ollama-local",
        "model":   "llava:13b",          # Multimodal para describir imágenes
    },
    "edge": {
        "backend": "axera-ax650n-rpi5",
        "model":   "AXERA-TECH/Qwen3-0.6B",
    },
}

# El ORCHESTRATOR debe ser rápido y preciso con el XML.
# Qwen 3.5 9B es perfecto porque cabe de sobra junto a otros procesos.
ORCHESTRATOR_BACKEND = "ollama-local"
ORCHESTRATOR_MODEL   = "qwen3.5:9b"


# ── Orchestrator system prompt ─────────────────────────────────────────────────
# This is the key: we instruct the planning model to output ONLY XML.
# The XML structure drives all downstream routing decisions.

ORCHESTRATOR_SYSTEM_PROMPT = """You are a routing orchestrator. Your ONLY job is to analyze the user's input and produce a structured XML routing plan. You do NOT answer the user directly.

OUTPUT FORMAT — respond with ONLY this XML, no prose, no markdown, no explanation:

<routing_plan>
  <intent>SINGLE_WORD_INTENT</intent>
  <complexity>low|medium|high</complexity>
  <language>detected language code, e.g. en, es, zh</language>
  <subtasks>
    <task id="1">
      <description>What this subtask does</description>
      <intent>coding|reasoning|analysis|general|fast|translation|edge</intent>
      <input_slice>The exact portion of the user input relevant to this task</input_slice>
      <depends_on></depends_on>
    </task>
    <task id="2">
      <description>What this subtask does</description>
      <intent>coding|reasoning|analysis|general|fast|translation|edge</intent>
      <input_slice>The exact portion of the user input relevant to this task</input_slice>
      <depends_on>1</depends_on>
    </task>
  </subtasks>
</routing_plan>

RULES:
- Use only ONE subtask for simple, single-intent inputs.
- Use multiple subtasks when the input has clearly separable concerns (e.g. "explain X and write code for it").
- intent values map to specialized models: coding→code model, reasoning→large model, fast→edge NPU, translation→translate model.
- depends_on: comma-separated task IDs this task must wait for. Empty if no dependency.
- Do not include any text outside the <routing_plan> tags.
"""


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class SubTask:
    id: str
    description: str
    intent: str
    input_slice: str
    depends_on: List[str]


@dataclass
class RoutingPlan:
    intent: str
    complexity: str
    language: str
    subtasks: List[SubTask]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_client_map(configs: List[BackendConfig]) -> Dict[str, BackendClient]:
    """Build a {backend_name: BackendClient} lookup, with per-request model override support."""
    return {c.name: BackendClient(c) for c in configs}


def _parse_routing_plan(xml_text: str) -> RoutingPlan:
    """Parse the orchestrator's XML output into a RoutingPlan."""
    # Strip any accidental prose wrapping
    match = re.search(r"<routing_plan>.*?</routing_plan>", xml_text, re.DOTALL)
    if not match:
        raise ValueError(f"Orchestrator did not return valid XML. Raw output:\n{xml_text[:500]}")

    root = ET.fromstring(match.group(0))

    subtasks = []
    for task_el in root.findall(".//task"):
        depends_raw = (task_el.findtext("depends_on") or "").strip()
        depends = [d.strip() for d in depends_raw.split(",") if d.strip()]
        subtasks.append(SubTask(
            id          = task_el.get("id", "1"),
            description = (task_el.findtext("description") or "").strip(),
            intent      = (task_el.findtext("intent") or "general").strip().lower(),
            input_slice = (task_el.findtext("input_slice") or "").strip(),
            depends_on  = depends,
        ))

    return RoutingPlan(
        intent     = (root.findtext("intent") or "general").strip().lower(),
        complexity = (root.findtext("complexity") or "medium").strip().lower(),
        language   = (root.findtext("language") or "en").strip().lower(),
        subtasks   = subtasks,
    )


def _resolve_route(intent: str, client_map: Dict[str, BackendClient]) -> BackendClient:
    """
    Given an intent string, return the appropriate BackendClient with the
    correct model injected. Falls back to 'general' then to first available.
    """
    route = MODEL_ROUTING.get(intent) or MODEL_ROUTING.get("general")
    backend_name = route["backend"]
    model_name   = route["model"]

    client = client_map.get(backend_name)
    if client is None:
        # Backend not in pool — use first available
        client = next(iter(client_map.values()))
        logger.warning("Backend '%s' not found, falling back to '%s'", backend_name, client.config.name)

    # Override the model for this specific call (non-destructive copy)
    import copy
    patched_config = copy.copy(client.config)
    patched_config.model = model_name
    return BackendClient(patched_config)


# ── Main orchestrator engine ───────────────────────────────────────────────────

class SemanticOrchestrator:
    """
    Two-phase engine:
      Phase 1 — Planning:  send the raw prompt to the orchestrator model,
                           receive a structured XML routing plan.
      Phase 2 — Execution: dispatch subtasks to specialized backends,
                           respecting dependency order.
    """

    def __init__(self, configs: List[BackendConfig]):
        self._client_map = _build_client_map(configs)
        self._orchestrator_client = self._build_orchestrator_client()

    def _build_orchestrator_client(self) -> BackendClient:
        import copy
        base = self._client_map.get(ORCHESTRATOR_BACKEND)
        if base is None:
            base = next(iter(self._client_map.values()))
        cfg = copy.copy(base.config)
        cfg.model = ORCHESTRATOR_MODEL
        return BackendClient(cfg)

    # ── Phase 1: Planning ──────────────────────────────────────────────────────

    async def _plan(self, user_input: str) -> RoutingPlan:
        """Ask the orchestrator model to produce a routing plan."""
        planning_prompt = (
            f"{ORCHESTRATOR_SYSTEM_PROMPT}\n\n"
            f"<user_input>{user_input}</user_input>"
        )
        logger.info("[Orchestrator] Planning phase → %s / %s", ORCHESTRATOR_BACKEND, ORCHESTRATOR_MODEL)
        result = await self._orchestrator_client.generate(prompt=planning_prompt)
        raw_xml = result.get("response", "")
        logger.debug("[Orchestrator] Raw plan:\n%s", raw_xml)
        plan = _parse_routing_plan(raw_xml)
        logger.info(
            "[Orchestrator] Plan: intent=%s complexity=%s subtasks=%d",
            plan.intent, plan.complexity, len(plan.subtasks),
        )
        return plan

    # ── Phase 2: Execution ─────────────────────────────────────────────────────

    async def _execute_plan(self, plan: RoutingPlan, original_input: str) -> Dict[str, str]:
        """
        Execute subtasks respecting dependency order.
        Returns {task_id: response_text}.
        """
        results: Dict[str, str] = {}
        pending = list(plan.subtasks)

        # Simple topological execution: iterate until all tasks are done
        max_rounds = len(pending) + 1
        for _ in range(max_rounds):
            if not pending:
                break

            # Find tasks whose dependencies are all satisfied
            ready = [t for t in pending if all(dep in results for dep in t.depends_on)]
            if not ready:
                logger.error("Dependency deadlock detected in routing plan.")
                break

            # Execute ready tasks concurrently
            async def _run(task: SubTask) -> tuple[str, str]:
                client = _resolve_route(task.intent, self._client_map)
                # Enrich the input slice with context from upstream tasks
                context = ""
                for dep_id in task.depends_on:
                    context += f"\n<context from_task='{dep_id}'>{results[dep_id]}</context>"

                full_prompt = task.input_slice or original_input
                if context:
                    full_prompt = f"{context}\n\n{full_prompt}"

                logger.info(
                    "[Orchestrator] Task %s → %s (%s) | intent=%s",
                    task.id, client.config.name, client.config.model, task.intent,
                )
                res = await client.generate(prompt=full_prompt)
                return task.id, res.get("response", "")

            batch_results = await asyncio.gather(*[_run(t) for t in ready])
            for task_id, response in batch_results:
                results[task_id] = response

            pending = [t for t in pending if t.id not in results]

        return results

    # ── Public interface ───────────────────────────────────────────────────────

    async def process(self, request: AIRequest) -> AIResponse:
        import time
        start = time.perf_counter()

        # Phase 1: Plan
        try:
            plan = await self._plan(request.prompt)
        except Exception as e:
            logger.warning("[Orchestrator] Planning failed (%s), falling back to direct routing.", e)
            # Graceful fallback: treat entire input as a single 'general' task
            plan = RoutingPlan(
                intent="general", complexity="medium", language="en",
                subtasks=[SubTask(
                    id="1", description="Direct execution (plan failed)",
                    intent="general", input_slice=request.prompt, depends_on=[],
                )],
            )

        # Phase 2: Execute
        results = await self._execute_plan(plan, request.prompt)

        # Merge results: if single task, return as-is; if multiple, concatenate with separators
        if len(results) == 1:
            final_response = next(iter(results.values()))
        else:
            parts = []
            for task in plan.subtasks:
                if task.id in results:
                    parts.append(f"[{task.description}]\n{results[task.id]}")
            final_response = "\n\n---\n\n".join(parts)

        duration_ms = (time.perf_counter() - start) * 1000

        # Build routing metadata for observability
        routing_info = [
            {
                "task_id":     t.id,
                "description": t.description,
                "intent":      t.intent,
                "backend":     MODEL_ROUTING.get(t.intent, MODEL_ROUTING["general"])["backend"],
                "model":       MODEL_ROUTING.get(t.intent, MODEL_ROUTING["general"])["model"],
            }
            for t in plan.subtasks
        ]

        return AIResponse(
            response=final_response,
            session_id=request.session_id,
            metadata={
                "duration_ms":   duration_ms,
                "orchestration": {
                    "top_intent":  plan.intent,
                    "complexity":  plan.complexity,
                    "language":    plan.language,
                    "subtask_count": len(plan.subtasks),
                    "routing":     routing_info,
                },
            },
        )


# ── Singleton ──────────────────────────────────────────────────────────────────
from app.services.backend_registry import BACKENDS_BY_PRIORITY
semantic_orchestrator = SemanticOrchestrator(configs=BACKENDS_BY_PRIORITY)
