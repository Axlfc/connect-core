# Propuestas de Mejora para Cognito Stack

Este documento evalúa 8 propuestas de mejora para el sistema Cognito, analizando si la funcionalidad ya existe en el repositorio, cómo se integraría con la arquitectura actual (`very-simplified-stack/`), los archivos que requerirían cambios, sus riesgos asociados y el esfuerzo estimado (S/M/L).

---

## 1. Revisión del plan antes de ejecutar (Paso crítico previo a escribir código)

- **¿Existe en el repo?:** [PARCIAL]
  Actualmente existe la capacidad de generar planes en texto y pausar acciones individuales mediante `ApprovalManager` (`app/core/approval.py`), pero no existe una fase formal e ineludible de "Plan Review" que congele las herramientas de modificación hasta recibir aprobación previa.
- **Integración con componentes actuales:**
  Se integraría directamente en `agent_loop.py`. Se añadiría un estado inicial obligatorio `PLANNING`. En este estado, la lista de herramientas disponibles para el agente se filtra para incluir **únicamente herramientas de solo lectura** (`read_tool`, `fs_tools`, `query_spill_tool`). Al concluir la formulación del plan, el agente crea una solicitud en `ApprovalManager` con el plan estructurado. La transición al estado `EXECUTION` (que habilita `edit_tool`, `write_tool`, `unified_patch_tool` y `bash_tool`) solo ocurre tras una decisión positiva del operador.
- **Ficheros a cambiar:**
  - `very-simplified-stack/cognito-backend/app/core/agent_loop.py`
  - `very-simplified-stack/cognito-backend/app/core/approval.py`
  - `very-simplified-stack/cognito-backend/app/api/routes/ai_agents.py`
- **Riesgos:**
  Latencia adicional en la ejecución si el operador no responde rápidamente a la aprobación del plan; bloqueo del flujo de tareas desatendidas.
- **Esfuerzo:** M (Medio)

---

## 2. Verificación visual para tareas de frontend con Playwright

- **¿Existe en el repo?:** [NO EXISTE]
  No hay integración con Playwright ni captura/procesamiento de imágenes o navegadores en `cognito-backend` o `cognito-worker`.
- **Integración con componentes actuales:**
  Se extendería `VerificationEngine` (`very-simplified-stack/cognito-worker/worker_app/verification.py`). Al recibir una solicitud de verificación para un repositorio de frontend (detectado vía `package.json`), el worker iniciará un servidor web de desarrollo efímero y ejecutará un script de Playwright en modo headless dentro del directorio de trabajo. Las capturas de pantalla (`.png`) o grabaciones (`.webm`) resultantes se enviarán como adjuntos en la respuesta de `/v1/verify` hacia `cognito-backend` para su registro en la sesión.
- **Ficheros a cambiar:**
  - `very-simplified-stack/cognito-worker/worker_app/verification.py`
  - `very-simplified-stack/cognito-worker/Dockerfile`
  - `very-simplified-stack/cognito-backend/app/models/domain.py`
  - `very-simplified-stack/cognito-backend/app/services/escalation_service.py`
- **Riesgos:**
  Incremento significativo del tamaño de la imagen Docker del worker (al instalar binarios de Chromium/Firefox); consumo elevado de memoria RAM y CPU; fallos en entornos Linux sin servidor gráfico o sin dependencias de renderizado.
- **Esfuerzo:** L (Grande)

---

## 3. Bucle de reintento automático tras fallo de verificación, con límite de intentos

- **¿Existe en el repo?:** [IMPLEMENTADO]
  Existe en `EscalationService.run_verification_and_escalate_if_needed` (`app/services/escalation_service.py:129`). Cuando la verificación falla con clasificación `model_related`, se compila un resumen de la falla (`compile_attempt_summary`), se adjunta al contexto y se ejecuta un nuevo intento escalando el modelo a través de la cadena `local` -> `luna` -> `terra` -> `sol`.
- **Integración con componentes actuales:**
  La infraestructura base ya está presente. La mejora consiste en permitir múltiples reintentos configurables dentro del mismo modelo/tier antes de forzar el escalado al siguiente tier, agregando un parámetro `max_attempt_retries` en la definición del objeto `Task`.
- **Ficheros a cambiar:**
  - `very-simplified-stack/cognito-backend/app/services/escalation_service.py`
  - `very-simplified-stack/cognito-backend/app/models/domain.py`
- **Riesgos:**
  Consumo acelerado de tokens o bucles de reintento infructuosos si la falla es ambiental (ej. librerías faltantes) y no del código generado por el modelo.
- **Esfuerzo:** S (Pequeño)

---

## 4. Atribución de commits configurable (agente, humano o co-autoría)

- **¿Existe en el repo?:** [NO EXISTE]
  Actualmente, las ramas y commits generados en el worktree utilizan la configuración predeterminada de Git del entorno sin atribución personalizada (`worker_app/worktree.py:138`).
- **Integración con componentes actuales:**
  Se añadiría el campo `commit_attribution` (`agent`, `human`, `co_authored`) en `TaskContext`. Al aplicar parches o realizar confirmaciones en `worktree.py`, `GitWorktreeManager` configurará temporalmente las variables `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` y `GIT_COMMITTER_EMAIL`, o inyectará la cabecera `Co-authored-by: Operador <email>` en el mensaje del commit.
- **Ficheros a cambiar:**
  - `very-simplified-stack/cognito-worker/worker_app/worktree.py`
  - `very-simplified-stack/cognito-worker/worker_app/main.py`
  - `very-simplified-stack/cognito-backend/app/models/domain.py`
- **Riesgos:**
  Rechazo de commits si el servidor Git de destino (`Forgejo`/`GitHub`) requiere firmas GPG/SSH obligatorias o restringe direcciones de correo no verificadas.
- **Esfuerzo:** S (Pequeño)

---

## 5. Memoria por repositorio con opción de desactivarla

- **¿Existe en el repo?:** [PARCIAL]
  Existen servicios de memoria como `FactMemoryManager` (`app/core/fact_memory.py`), `QdrantMemoryService` (`app/services/qdrant_memory.py`) y `NooaMemory` (`app/core/nooa_memory.py`), pero los recuerdos no están acotados ni filtrados por `repo_id`, ni existe un modificador para desactivar la memoria por repositorio.
- **Integración con componentes actuales:**
  Se incluiría `repo_id` como campo de índice y filtro en los metadatos de Qdrant (`qdrant_memory.py`) y en la tabla `facts` de PostgreSQL (`models/db.py`). En `TaskContext` o en la configuración general, se añadirá el indicador booleano `enable_repo_memory`. Si está en `false`, `system_prompt.py` omitirá la recuperación e inyección de contexto desde la memoria.
- **Ficheros a cambiar:**
  - `very-simplified-stack/cognito-backend/app/services/qdrant_memory.py`
  - `very-simplified-stack/cognito-backend/app/core/fact_memory.py`
  - `very-simplified-stack/cognito-backend/app/core/system_prompt.py`
  - `very-simplified-stack/cognito-backend/app/models/domain.py`
- **Riesgos:**
  Contaminación de hechos obsoletos entre distintas ramas del mismo repositorio; posible aumento de latencia por consultas vectoriales adicionales.
- **Esfuerzo:** M (Medio)

---

## 6. Eventos de sesión inmutables consultables por fecha

- **¿Existe en el repo?:** [PARCIAL]
  `SessionManager` almacena eventos secuenciales con marca de tiempo ISO en archivos `.jsonl` o en la tabla `session_messages` de PostgreSQL, pero no implementa inmutabilidad estricta ni ofrece endpoints para filtrar eventos por rangos de fecha (`start_time`, `end_time`).
- **Integración con componentes actuales:**
  Se añadirá un índice por columna `ts` en `DBSessionMessage` y un endpoint GET `/v1/ai-agents/sessions/{session_id}/events` que acepte parámetros de filtrado por fecha. La inmutabilidad se garantizará restringiendo las operaciones de actualización/eliminación a nivel de aplicación e introduciendo un disparador (trigger) en PostgreSQL que impida la modificación de registros de eventos existentes.
- **Ficheros a cambiar:**
  - `very-simplified-stack/cognito-backend/app/core/session_manager.py`
  - `very-simplified-stack/cognito-backend/app/api/routes/ai_agents.py`
  - `very-simplified-stack/cognito-backend/app/models/db.py`
- **Riesgos:**
  Crecimiento sostenido del volumen de almacenamiento en la base de datos si no se definen políticas de retención o archivado histórico.
- **Esfuerzo:** M (Medio)

---

## 7. Tareas recurrentes con revisión humana obligatoria

- **¿Existe en el repo?:** [NO EXISTE]
  El sistema no cuenta con programación de tareas periódicas, cron ni ejecuciones automatizadas por calendario.
- **Integración con componentes actuales:**
  Se integrará un programador asíncrono (como `APScheduler` o `Celery`) en `cognito-backend`. Al cumplirse el intervalo programado, el programador creará la tarea en estado `pending_approval` e iniciará una solicitud en `ApprovalManager`. La tarea no se enviará al worker hasta que el operador apruebe explícitamente su ejecución.
- **Ficheros a cambiar:**
  - `very-simplified-stack/cognito-backend/app/main.py`
  - `very-simplified-stack/cognito-backend/app/services/task_store.py`
  - `very-simplified-stack/cognito-backend/app/api/routes/ai_agents.py`
  - `very-simplified-stack/cognito-backend/requirements.txt`
- **Riesgos:**
  Acumulación imprevista de tareas pendientes si el operador no responde; ejecuciones no deseadas en caso de errores en la sintaxis cron.
- **Esfuerzo:** L (Grande)

---

## 8. Límites de concurrencia y de tareas diarias

- **¿Existe en el repo?:** [PARCIAL]
  `TokenBudgetManager` (`app/core/token_budget.py`) limita el consumo total de tokens a nivel de sesión, usuario, proyecto u organización. Sin embargo, no hay control sobre el número de tareas concurrentes simultáneas ni un límite de cantidad de tareas por día.
- **Integración con componentes actuales:**
  Se creará la clase `TaskQuotaManager` utilizando un semáforo asíncrono (`asyncio.Semaphore`) o cierres distribuidos en Redis para limitar la cantidad de tareas ejecutándose en paralelo. Para el límite diario, se registrarán contadores en Redis con tiempo de vida (TTL) de 24 horas, bloqueando la creación de tareas en `POST /v1/ai-agents/tasks` cuando se alcance la cuota diaria configurada.
- **Ficheros a cambiar:**
  - `very-simplified-stack/cognito-backend/app/core/token_budget.py` (o nuevo `app/core/task_quota.py`)
  - `very-simplified-stack/cognito-backend/app/api/routes/ai_agents.py`
- **Riesgos:**
  Rechazo de tareas legítimas si la cuota está mal dimensionada; posibles bloqueos si el decremento del semáforo falla ante excepciones no capturadas.
- **Esfuerzo:** M (Medio)

---

## Clasificación y Ordenación por Relación Valor / Esfuerzo

1. **Bucle de reintento automático tras fallo de verificación** (Valor: Alto, Esfuerzo: S)
   - *Razón:* Alta relación V/E. La infraestructura básica ya existe en `EscalationService`; perfeccionarla requiere cambios mínimos y mejora significativamente la tasa de éxito autónomo.
2. **Atribución de commits configurable** (Valor: Medio, Esfuerzo: S)
   - *Razón:* Alta relación V/E. Requiere un esfuerzo mínimo de implementación y proporciona trazabilidad clara en auditorías de código.
3. **Revisión del plan antes de ejecutar** (Valor: Muy Alto, Esfuerzo: M)
   - *Razón:* Muy alta relación V/E. Evita modificaciones no deseadas o erróneas en el código al imponer una puerta de control previa.
4. **Límites de concurrencia y de tareas diarias** (Valor: Alto, Esfuerzo: M)
   - *Razón:* Alta relación V/E. Esencial para proteger la infraestructura y prevenir la saturación de recursos en entornos multiusuario.
5. **Memoria por repositorio con opción de desactivarla** (Valor: Alto, Esfuerzo: M)
   - *Razón:* Media-Alta relación V/E. Aumenta la relevancia del contexto del LLM y evita mezclar conocimientos entre proyectos distintos.
6. **Eventos de sesión inmutables consultables por fecha** (Valor: Medio, Esfuerzo: M)
   - *Razón:* Media relación V/E. Aporta valor para auditorías de cumplimiento normativo y trazabilidad operativa.
7. **Verificación visual para tareas de frontend con Playwright** (Valor: Alto, Esfuerzo: L)
   - *Razón:* Media relación V/E. Aunque es de gran utilidad para el desarrollo web, su implementación requiere introducir dependencias complejas y pesadas.
8. **Tareas recurrentes con revisión humana obligatoria** (Valor: Medio, Esfuerzo: L)
   - *Razón:* Baja-Media relación V/E. Requiere introducir e integrar un sistema completo de programación de tareas (scheduler) e infraestructura adicional.
