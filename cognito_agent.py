"""
Cognito Stack - Versión Simplificada y Unificada
Usa agent_loop.py de cognito-backend como motor de orquestación,
manteniendo la interfaz CLI y reutilizando ExecPolicy, ToolLoopDetector y SessionManager.
"""

import sys
import os
import time
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any
from pathlib import Path

# Asegurar importabilidad de cognito-backend y cognito-worker
BASE_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = BASE_DIR / "very-simplified-stack" / "cognito-backend"
WORKER_DIR = BASE_DIR / "very-simplified-stack" / "cognito-worker"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

# Imports del backend unificado
from app.core.agent_loop import agent_loop
from app.core.tools.base import ToolContext
from app.core.session_manager import SessionManager
from app.core.resource_loader import ResourceLoader
from app.core.project_trust import ProjectTrustStore
from app.core.extensions.registry import extension_registry
from app.services.backend_router import backend_router
from app.services.semantic_orchestrator import semantic_orchestrator
from app.core.steering import steering_manager
from app.core.events import (
    TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent, ErrorEvent
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleCognitoStack:
    """Sistema de razonamiento multi-módulo cliente CLI sobre el agent_loop unificado"""

    def __init__(self, ollama_url: str = "http://localhost:11434", cwd: Optional[str] = None):
        self.ollama_url = ollama_url
        self.cwd = str(Path(cwd or os.getcwd()).resolve())

        # Modelos optimizados para RTX 5070 12GB
        self.models = {
            "routing": "deepseek-r1:7b",
            "deduction": "deepseek-r1:14b",
            "induction": "gemma3:12b",
            "abduction": "cogito:14b",
            "conduction": "qwen2.5-coder:14b",
            "analogy": "phi4:14b",
            "generative": "llama3.1:8b",
            "social": "gemma3:12b",
            "metareasoning": "cogito:8b"
        }

        # Inicialización de infraestructura compartida de cognito-backend
        self.session_manager = SessionManager()
        self.trust_store = ProjectTrustStore()
        self.loader = ResourceLoader(self.cwd)
        self.session_id = self.session_manager.create(self.cwd)

        logger.info(f"✅ Cognito Stack inicializado | CWD={self.cwd} | SessionID={self.session_id}")

    def generate(self, model: str, prompt: str, system: Optional[str] = None, temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """
        Genera respuesta delegando en agent_loop sin herramientas de forma síncrona.
        Mantiene compatibilidad con el método legacy generate.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        return self._run_loop_sync(
            messages=messages,
            model=model,
            tools=[],
            temperature=temperature,
            max_tokens=max_tokens
        )

    def route_task(self, task: str) -> str:
        """Determina qué tipo de razonamiento usar"""

        prompt = f"""Analiza esta tarea y determina el mejor tipo de razonamiento.

TIPOS:
- deduction: Lógica formal
- induction: Detectar patrones  
- abduction: Generar hipótesis
- conduction: Planificar/escribir código
- analogy: Transferir conocimiento
- generative: Crear contenido
- social: Consenso social

TAREA: {task[:500]}

Responde SOLO: deduction, induction, abduction, conduction, analogy, generative, o social"""

        result = self.generate(
            model=self.models["routing"],
            prompt=prompt,
            temperature=0.2,
            max_tokens=50
        )

        # Extraer tipo de la respuesta
        result_lower = result.lower().strip()
        for rtype in ["deduction", "induction", "abduction", "conduction", "analogy", "generative", "social"]:
            if rtype in result_lower:
                logger.info(f"🧭 Routing: {rtype}")
                return rtype

        logger.warning("No se pudo determinar tipo, usando generative")
        return "generative"

    async def _execute_loop_async(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """
        Ejecuta agent_loop compartiendo la gestión de sesión, herramientas, ExecPolicy,
        ToolLoopDetector y sanitización nonce.
        """
        # Cargar herramientas y contexto del proyecto CWD
        extension_registry.refresh("project_local", self.cwd, backend_router, semantic_orchestrator)
        tools = extension_registry.tools_for(self.cwd)

        context = ToolContext(
            cwd=self.cwd,
            trusted=self.trust_store.is_trusted(self.cwd),
            protected_files=self.loader.get_effective_protected_files()
        )

        model_params = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        # Sincronizar steering queue e locks por sesión
        await steering_manager.sync_pending_steering_async(self.session_id, self.session_manager)
        steering_queue = steering_manager.get_queue(self.session_id)
        history_lock = steering_manager.get_lock(self.session_id)

        # Registrar mensajes de entrada en el log de sesión
        async with history_lock:
            for msg in messages:
                await self.session_manager.append_message_async(self.session_id, msg["role"], msg.get("content", ""))

        accumulated_text = ""
        assistant_content = ""
        current_tool_calls = []

        try:
            async for event in agent_loop(
                messages=messages,
                tools=tools,
                context=context,
                backend_router=backend_router,
                model_params=model_params,
                steering_queue=steering_queue,
                history_lock=history_lock,
                session_manager=self.session_manager,
                session_id=self.session_id,
                steering_manager=steering_manager,
            ):
                if isinstance(event, TextDeltaEvent):
                    accumulated_text += event.content
                    assistant_content += event.content
                elif isinstance(event, ToolCallEvent):
                    logger.info(f"🔧 Invoking tool: {event.tool_name}({json.dumps(event.arguments)})")
                    current_tool_calls.append({
                        "id": event.tool_call_id,
                        "type": "function",
                        "function": {"name": event.tool_name, "arguments": json.dumps(event.arguments)}
                    })
                elif isinstance(event, ToolResultEvent):
                    status_icon = "❌" if event.is_error else "✅"
                    logger.info(f"{status_icon} Tool {event.tool_name} output received")

                    async with history_lock:
                        if assistant_content or current_tool_calls:
                            await self.session_manager.append_message_async(
                                self.session_id,
                                role="assistant",
                                content=assistant_content,
                                tool_calls=current_tool_calls if current_tool_calls else None
                            )
                            assistant_content = ""
                            current_tool_calls = []

                        await self.session_manager.append_message_async(
                            self.session_id,
                            role="tool",
                            content=event.output,
                            tool_name=event.tool_name,
                            tool_call_id=event.tool_call_id
                        )
                elif isinstance(event, DoneEvent):
                    async with history_lock:
                        if assistant_content or current_tool_calls:
                            await self.session_manager.append_message_async(
                                self.session_id,
                                role="assistant",
                                content=assistant_content,
                                tool_calls=current_tool_calls if current_tool_calls else None
                            )
                elif isinstance(event, ErrorEvent):
                    logger.error(f"Error in agent loop: {event.message}")
                    if not accumulated_text:
                        accumulated_text = f"Error: {event.message}"

        except Exception as e:
            logger.error(f"Error executing agent loop: {e}", exc_info=True)
            if not accumulated_text:
                accumulated_text = f"Error: {str(e)}"

        return accumulated_text

    def _run_loop_sync(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Any]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """Helper para ejecutar corrutina asíncrona de agent_loop desde contexto síncrono CLI"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Si se invoca dentro de un event loop ya en ejecución
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(
                self._execute_loop_async(messages, model, temperature, max_tokens)
            )
        else:
            return asyncio.run(
                self._execute_loop_async(messages, model, temperature, max_tokens)
            )

    def execute_reasoning(self, task: str, reasoning_type: str) -> str:
        """Ejecuta razonamiento específico utilizando agent_loop"""

        model = self.models.get(reasoning_type, self.models["generative"])

        prompts = {
            "deduction": "Aplica razonamiento DEDUCTIVO riguroso. Identifica premisas, aplica lógica formal, deriva conclusiones válidas.",
            "induction": "Aplica razonamiento INDUCTIVO. Examina datos, identifica patrones, formula generalizaciones.",
            "abduction": "Aplica razonamiento ABDUCTIVO. Analiza observaciones, genera hipótesis explicativas, evalúa la mejor explicación.",
            "conduction": "Aplica razonamiento CONDUCTIVO. Define objetivos, planifica acciones concretas, escribe código funcional.",
            "analogy": "Aplica razonamiento ANALÓGICO. Identifica dominio origen, mapea estructuras, transfiere conocimiento.",
            "generative": "Genera contenido CREATIVO y ORIGINAL. Explora ideas innovadoras, combina conceptos, aporta valor único.",
            "social": "Aplica razonamiento SOCIAL. Identifica perspectivas, analiza normas, busca consenso."
        }

        full_prompt = f"""{prompts.get(reasoning_type, prompts['generative'])}

TAREA:
{task}

Tu respuesta:"""

        system_prompt = None
        if reasoning_type == "abduction" and "cogito" in model:
            system_prompt = "Enable deep thinking subroutine."
            logger.info("🧠 Deep thinking habilitado")

        logger.info(f"⚙️  Ejecutando {reasoning_type} con {model} a través de agent_loop unificado")

        start = time.time()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": full_prompt})

        result = self._run_loop_sync(
            messages=messages,
            model=model,
            temperature=0.7,
            max_tokens=2048
        )
        elapsed = time.time() - start

        logger.info(f"✅ Completado en {elapsed:.2f}s")

        return result

    def solve(self, task: str) -> str:
        """Resuelve tarea usando el sistema completo"""

        logger.info(f"\n{'='*80}\n🎯 TAREA: {task[:100]}...\n{'='*80}")

        # 1. Routing
        reasoning_type = self.route_task(task)

        # 2. Ejecución
        result = self.execute_reasoning(task, reasoning_type)

        logger.info(f"\n{'='*80}\n✅ COMPLETADO\n{'='*80}")

        return result


# =============================================================================
# EJEMPLOS DE USO
# =============================================================================

if __name__ == "__main__":
    # Inicializar
    cognito = SimpleCognitoStack()

    print("\n" + "="*80)
    print("COGNITO STACK - EJEMPLOS")
    print("="*80)

    # =============================================================================
    # EJEMPLO 1: Análisis de Bug
    # =============================================================================

    task1 = """
Analiza este código Python y encuentra el bug:

```python
def calcular_promedio(numeros):
    suma = 0
    for num in numeros:
        suma += num
    return suma / len(numeros)

resultado = calcular_promedio([])
print(resultado)
```

Explica el problema y proporciona la solución.
"""

    print("\n" + "="*80)
    print("EJEMPLO 1: Análisis de Bug")
    print("="*80)

    solution1 = cognito.solve(task1)
    print(f"\n{solution1}\n")

    # =============================================================================
    # EJEMPLO 2: Detección de Patrones
    # =============================================================================

    task2 = """
Observa estos números: 2, 6, 12, 20, 30, 42

¿Cuál es el patrón y cuál sería el siguiente número?
"""

    print("\n" + "="*80)
    print("EJEMPLO 2: Detección de Patrones")
    print("="*80)

    solution2 = cognito.solve(task2)
    print(f"\n{solution2}\n")

    # =============================================================================
    # EJEMPLO 3: Script Bash
    # =============================================================================

    task3 = """
Escribe un script bash que:
1. Busque archivos .log mayores de 100MB en /var/log
2. Los comprima con gzip
3. Mueva los comprimidos a /var/backups/
4. Elimine los originales solo si la compresión fue exitosa
5. Registre todo en un log

El script debe ser robusto con manejo de errores.
"""

    print("\n" + "="*80)
    print("EJEMPLO 3: Script Bash")
    print("="*80)

    solution3 = cognito.solve(task3)
    print(f"\n{solution3}\n")

    print("\n" + "="*80)
    print("✅ TODOS LOS EJEMPLOS COMPLETADOS")
    print("="*80)
