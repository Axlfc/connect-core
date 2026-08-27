import os
import sys
import json
import shutil
import tempfile
import asyncio
import subprocess
from typing import List, Dict, Any, Optional

# Path setup to ensure app modules can be imported
evals_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
stack_dir = os.path.dirname(evals_dir)
backend_dir = os.path.join(stack_dir, "cognito-backend")

sys.path.insert(0, stack_dir)
sys.path.insert(0, backend_dir)
sys.path.insert(0, evals_dir)

from app.core.agent_loop import agent_loop
from app.core.tools.base import ToolContext
from app.core.tools.read_tool import ReadTool
from app.core.tools.write_tool import WriteTool
from app.core.tools.edit_tool import EditTool
from app.core.tools.bash_tool import BashTool
from app.core.tools.code_review_tool import CodeReviewTool
from app.core.events import (
    AgentEvent, TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent, ApprovalRequiredEvent
)

from evals.e2e.schemas import (
    E2ETaskCase, VerificationCriterion, EvalResultCase, E2EEvalReport
)
from evals.e2e.dataset import get_default_e2e_tasks


class DeterministicMockRouter:
    """
    Deterministic mock router for E2E trajectory evaluations in offline/CI environments.
    Simulates agent LLM responses with multi-turn tool calling and reasoning deltas.
    """
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.turn = 0

    async def generate_with_tools(self, messages: List[Dict[str, Any]], tools_schema: List[Dict[str, Any]], model_params: Optional[Dict[str, Any]] = None):
        self.turn += 1

        if self.task_id == "E2E-001":
            if self.turn == 1:
                yield {"token": "Leyendo archivo config.txt...\n"}
                yield {
                    "tool_calls": [{
                        "id": "tc_001",
                        "function": {"name": "read", "arguments": {"path": "config.txt"}}
                    }]
                }
            else:
                yield {"token": "Resumen: El archivo configura Cognito en puerto 8080 en producción."}

        elif self.task_id == "E2E-002":
            if self.turn == 1:
                yield {"token": "Actualizando src/version.py...\n"}
                yield {
                    "tool_calls": [{
                        "id": "tc_002_1",
                        "function": {"name": "write", "arguments": {"path": "src/version.py", "content": "__version__ = '2.0.0'\n"}}
                    }]
                }
            elif self.turn == 2:
                yield {"token": "Actualizando README.md...\n"}
                yield {
                    "tool_calls": [{
                        "id": "tc_002_2",
                        "function": {"name": "write", "arguments": {"path": "README.md", "content": "# Project\nVersion: 2.0.0\n"}}
                    }]
                }
            else:
                yield {"token": "Versión actualizada a 2.0.0 en ambos archivos."}

        elif self.task_id == "E2E-003":
            if self.turn == 1:
                yield {"token": "Ejecutando test para verificar fallo...\n"}
                yield {
                    "tool_calls": [{
                        "id": "tc_003_1",
                        "function": {"name": "bash", "arguments": {"command": "python test_math.py", "user_approved": True}}
                    }]
                }
            elif self.turn == 2:
                yield {"token": "Corrigiendo bug en src/math_utils.py...\n"}
                yield {
                    "tool_calls": [{
                        "id": "tc_003_2",
                        "function": {"name": "write", "arguments": {"path": "src/math_utils.py", "content": "def add(a, b):\n    return a + b\n"}}
                    }]
                }
            elif self.turn == 3:
                yield {"token": "Re-ejecutando test...\n"}
                yield {
                    "tool_calls": [{
                        "id": "tc_003_3",
                        "function": {"name": "bash", "arguments": {"command": "python test_math.py", "user_approved": True}}
                    }]
                }
            else:
                yield {"token": "Test corregido y pasando con éxito."}

        elif self.task_id == "E2E-004":
            if self.turn == 1:
                yield {"token": "Eliminando archivo temp.log...\n"}
                yield {
                    "tool_calls": [{
                        "id": "tc_004",
                        "function": {"name": "bash", "arguments": {"command": "rm temp.log", "user_approved": True}}
                    }]
                }
            else:
                yield {"token": "Archivo temp.log eliminado."}

        elif self.task_id == "E2E-005":
            if self.turn == 1:
                yield {"token": "Refactorizando utils.py...\n"}
                yield {
                    "tool_calls": [{
                        "id": "tc_005_1",
                        "function": {"name": "write", "arguments": {"path": "utils.py", "content": "def new_helper():\n    return 'ok'\n"}}
                    }]
                }
            elif self.turn == 2:
                yield {"token": "Refactorizando main.py...\n"}
                yield {
                    "tool_calls": [{
                        "id": "tc_005_2",
                        "function": {"name": "write", "arguments": {"path": "main.py", "content": "from utils import new_helper\nprint(new_helper())\n"}}
                    }]
                }
            else:
                yield {"token": "Refactorización completada."}

        elif self.task_id == "E2E-006":
            if self.turn == 1:
                yield {"token": "Ejecutando revisión de código...\n"}
                yield {
                    "tool_calls": [{
                        "id": "tc_006",
                        "function": {"name": "code_review", "arguments": {"file_path": "src/app.py"}}
                    }]
                }
            else:
                yield {"token": "Revisión finalizada con análisis de vulnerabilidades."}

        elif self.task_id == "E2E-007":
            if self.turn == 1:
                yield {"token": "Intentando comando sensible...\n"}
                yield {
                    "tool_calls": [{
                        "id": "tc_007",
                        "function": {"name": "bash", "arguments": {"command": "git reset --hard HEAD"}}
                    }]
                }
            else:
                yield {"token": "Acción detenida."}

        elif self.task_id == "E2E-008":
            if self.turn in (1, 2, 3, 4):
                yield {"token": "Reintentando lectura...\n"}
                yield {
                    "tool_calls": [{
                        "id": f"tc_008_{self.turn}",
                        "function": {"name": "read", "arguments": {"path": "bad.txt"}}
                    }]
                }
            else:
                yield {"token": "Bucle detectado y recuperado."}

        elif self.task_id == "E2E-009":
            if self.turn == 1:
                yield {"token": "Creando estructura de directorios...\n"}
                yield {
                    "tool_calls": [{
                        "id": "tc_009_1",
                        "function": {"name": "bash", "arguments": {"command": "mkdir output", "user_approved": True}}
                    }]
                }
            elif self.turn == 2:
                yield {"token": "Creando archivo...\n"}
                yield {
                    "tool_calls": [{
                        "id": "tc_009_2",
                        "function": {"name": "bash", "arguments": {"command": "touch output/result.txt", "user_approved": True}}
                    }]
                }
            else:
                yield {"token": "Directorio y archivo creados."}

        elif self.task_id == "E2E-010":
            if self.turn == 1:
                yield {"token": "Inspeccionando module_a.py...\n"}
                yield {
                    "tool_calls": [{
                        "id": "tc_010_1",
                        "function": {"name": "read", "arguments": {"path": "module_a.py"}}
                    }]
                }
            elif self.turn == 2:
                yield {"token": "Generando DOCS.md...\n"}
                yield {
                    "tool_calls": [{
                        "id": "tc_010_2",
                        "function": {"name": "write", "arguments": {"path": "DOCS.md", "content": "# Architecture Docs\nModule A provides base services.\nModule B provides extension logic.\n"}}
                    }]
                }
            else:
                yield {"token": "Documentación generada."}
        else:
            yield {"token": "Tarea completada."}


async def run_single_e2e_task(task: E2ETaskCase) -> EvalResultCase:
    os.environ["COGNITO_DISABLE_SANDBOX_DEV_ONLY"] = "true"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    workspace_dir = tempfile.mkdtemp(prefix=f"cognito_eval_{task.id}_")
    try:
        # Register directory in ProjectTrustStore so project is recognized as trusted
        from app.core.project_trust import ProjectTrustStore
        trust_store = ProjectTrustStore()
        trust_store.set_trusted(workspace_dir, True)

        # Populate workspace
        for rel_path, content in task.initial_files.items():
            full_path = os.path.join(workspace_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

        context = ToolContext(
            cwd=workspace_dir,
            trusted=True,
            protected_files=set()
        )

        tools = [
            ReadTool(),
            WriteTool(),
            EditTool(),
            BashTool(),
            CodeReviewTool()
        ]

        messages = [{"role": "user", "content": task.user_prompt}]
        router = DeterministicMockRouter(task.id)

        events: List[AgentEvent] = []
        executed_tools: List[str] = []

        async for event in agent_loop(
            messages=messages,
            tools=tools,
            context=context,
            backend_router=router,
            max_turns=task.max_turns
        ):
            events.append(event)
            if isinstance(event, ToolCallEvent):
                executed_tools.append(event.tool_name)

        # Verification
        verification_details: List[str] = []
        failure_reasons: List[str] = []

        for crit in task.verification_criteria:
            ctype = crit.criterion_type
            target = crit.target
            exp = crit.expected_value

            if ctype == "file_exists":
                fp = os.path.join(workspace_dir, target)
                exists = os.path.exists(fp)
                if exists == exp:
                    verification_details.append(f"✓ File '{target}' existence matches expected ({exp})")
                else:
                    failure_reasons.append(f"✗ File '{target}' existence ({exists}) does not match expected ({exp})")

            elif ctype == "file_content_contains":
                fp = os.path.join(workspace_dir, target)
                if not os.path.exists(fp):
                    failure_reasons.append(f"✗ Target file '{target}' does not exist for content check.")
                else:
                    with open(fp, "r", encoding="utf-8") as f:
                        c = f.read()
                    if str(exp) in c:
                        verification_details.append(f"✓ File '{target}' contains expected substring '{exp}'")
                    else:
                        failure_reasons.append(f"✗ File '{target}' missing expected substring '{exp}'")

            elif ctype == "file_deleted":
                fp = os.path.join(workspace_dir, target)
                deleted = not os.path.exists(fp)
                if deleted == exp:
                    verification_details.append(f"✓ File '{target}' deletion matches expected ({exp})")
                else:
                    failure_reasons.append(f"✗ File '{target}' deletion status ({deleted}) does not match expected ({exp})")

            elif ctype == "test_passes":
                env = os.environ.copy()
                env["PYTHONPATH"] = workspace_dir
                env["PYTHONDONTWRITEBYTECODE"] = "1"
                proc = subprocess.run(
                    target,
                    shell=True,
                    cwd=workspace_dir,
                    env=env,
                    capture_output=True,
                    text=True
                )
                if proc.returncode == (exp or 0):
                    verification_details.append(f"✓ Test command '{target}' passed with code {proc.returncode}")
                else:
                    failure_reasons.append(f"✗ Test command '{target}' failed with code {proc.returncode}: {proc.stderr}")

            elif ctype == "event_occurred":
                matched = False
                for ev in events:
                    if ev.__class__.__name__ == target:
                        if exp is None or getattr(ev, "tool_name", getattr(ev, "content", getattr(ev, "stop_reason", ""))) == exp:
                            matched = True
                            break
                if matched:
                    verification_details.append(f"✓ Event '{target}' (value={exp}) occurred during trajectory.")
                else:
                    failure_reasons.append(f"✗ Event '{target}' (value={exp}) did not occur during trajectory.")

        passed = len(failure_reasons) == 0
        score = 1.0 if passed else max(0.0, 1.0 - (len(failure_reasons) / max(1, len(task.verification_criteria))))

        return EvalResultCase(
            task_id=task.id,
            task_name=task.name,
            category=task.category,
            passed=passed,
            score=score,
            turns_used=router.turn,
            executed_tools=executed_tools,
            verification_details=verification_details,
            failure_reasons=failure_reasons
        )
    finally:
        shutil.rmtree(workspace_dir, ignore_errors=True)


async def run_e2e_evaluation() -> E2EEvalReport:
    tasks = get_default_e2e_tasks()
    results: List[EvalResultCase] = []

    category_totals: Dict[str, int] = {}
    category_passes: Dict[str, int] = {}

    for task in tasks:
        res = await run_single_e2e_task(task)
        results.append(res)
        cat = task.category
        category_totals[cat] = category_totals.get(cat, 0) + 1
        if res.passed:
            category_passes[cat] = category_passes.get(cat, 0) + 1

    passed_tasks = sum(1 for r in results if r.passed)
    total_tasks = len(results)
    pass_rate = passed_tasks / total_tasks if total_tasks > 0 else 1.0

    category_scores = {}
    for cat, total in category_totals.items():
        category_scores[cat] = category_passes.get(cat, 0) / total

    report = E2EEvalReport(
        total_tasks=total_tasks,
        passed_tasks=passed_tasks,
        pass_rate=pass_rate,
        category_scores=category_scores,
        results=results
    )

    report_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))

    return report
