# Preguntas y Respuestas sobre el Repositorio Hypenosys (`Axlfc/connect-core`)

Este documento reúne el análisis de arquitectura, ejecución, seguridad, operaciones y mecanismos del agente dentro de la carpeta `very-simplified-stack/`.

---

## Arquitectura y ejecución

### 1. ¿Cómo se comunica `cognito-backend` con `cognito-worker`? Describe el flujo completo de una petición, desde el endpoint hasta la ejecución en el worker.

- **Estado:** [IMPLEMENTADO]
- **Respuesta breve:**
  1. Un cliente realiza una petición HTTP a la API de `cognito-backend` (ej. `POST /v1/ai-agents/tasks/{task_id}/attempts`), lo cual invoca a `escalation_service.execute_task_attempt(...)`.
  2. `escalation_service` compila el historial previo y la información de la tarea, llamando a `worker_client.start_task(payload)`.
  3. `WorkerClient` genera la petición HTTP POST hacia `${COGNITO_WORKER_URL}/v1/task` (por defecto `http://host.docker.internal:8765`).
  4. `WorkerClient._get_headers` firma la petición calculando un resumen HMAC-SHA256 e incluye las cabeceras `X-Cognito-Worker-Id`, `X-Cognito-Timestamp`, `X-Cognito-Nonce`, `X-Cognito-Body-SHA256` y `X-Cognito-Signature`.
  5. En `cognito-worker`, FastAPI recibe la petición en `/v1/task`, donde la dependencia `authenticate` invoca a `verify_cognito_request`, comprobando la firma HMAC con `SHARED_SECRETS`, la vigencia del timestamp (máximo 5 minutos) y descartando nonces reutilizados.
  6. `cognito-worker` invoca `validate_repo_path` para garantizar que la ruta base del repositorio esté contenida dentro de `ALLOWED_REPOSITORY_ROOTS`.
  7. `worktree_manager.create_worktree(...)` inicializa un `git worktree` aislado para la tarea e intento.
  8. `codex_provider.execute_task(...)` ejecuta las instrucciones de Codex/LLM dentro del directorio del worktree (usando subproceso o mock).
  9. Los resultados se transmiten asíncronamente de vuelta a `cognito-backend` mediante un flujo Server-Sent Events (SSE `text/event-stream`).
  10. Posteriormente, `cognito-backend` puede invocar `/v1/verify` para correr pruebas/linters y `/v1/cleanup` para limpiar el entorno.
- **Citas:**
  - `very-simplified-stack/cognito-backend/app/api/routes/ai_agents.py:623`
  - `very-simplified-stack/cognito-backend/app/services/escalation_service.py:48,85,133`
  - `very-simplified-stack/cognito-backend/app/services/worker_client.py:17-43,76-90`
  - `very-simplified-stack/cognito-worker/worker_app/auth.py:30-81`
  - `very-simplified-stack/cognito-worker/worker_app/main.py:92,118-146,149-156,158-162`

---

### 2. ¿Dónde y cómo se crea el `git worktree` por tarea? ¿Se limpia al terminar? ¿Qué pasa si la tarea falla a mitad?

- **Estado:** [PARCIAL]
- **Respuesta breve:**
  - **Dónde:** Se crea en la máquina del worker, bajo el directorio `~/.cognito/worktrees/<repo_id>/<task_id>/attempt-<attempt:02d>`.
  - **Cómo:** `GitWorktreeManager.create_worktree` sanitiza las entradas contra inyección de flags y caracteres no permitidos, genera la rama con `git branch -- cognito/task-<task_id>-attempt-<attempt:02d> <base_commit>` y añade el worktree con `git worktree add -- <worktree_path> <branch_name>`.
  - **Limpieza al terminar:** Se expone el endpoint POST `/v1/cleanup` que llama a `cleanup_worktree`. Sin embargo, si existen cambios no confirmados (`has_uncommitted_changes`) y el parámetro `force=False`, **se omite la eliminación física** para proteger los cambios. Además, `escalation_service` no invoca automáticamente `cleanup_task` al terminar los intentos.
  - **Si falla a mitad:** El directorio del worktree permanece intacto en disco. La función `recover_orphaned_worktrees` solo ejecuta `git worktree prune` (limpia referencias a rutas borradas, pero no elimina carpetas físicamente si existen), por lo que las tareas fallidas o abandonadas ocupan disco hasta que se ejecute un cleanup manual forzado.
- **Citas:**
  - `very-simplified-stack/cognito-worker/worker_app/worktree.py:110-156,165-203,205-210`
  - `very-simplified-stack/cognito-worker/worker_app/main.py:158-162`
  - `very-simplified-stack/cognito-backend/app/services/escalation_service.py:53`
  - `very-simplified-stack/cognito-backend/app/services/worker_client.py:120-143`

---

### 3. ¿El `SandboxedExecutor` tiene acceso a red? ¿Hereda variables de entorno del host? Indica si se pasa el parámetro `env` al subproceso. ¿Qué límites de CPU, memoria y tiempo aplica en el código (no en la documentación)?

- **Estado:** [PARCIAL] / [SOLO DOCUMENTADO]
- **Respuesta breve:**
  - **Nombre en código:** La clase se denomina `SandboxedExecutor` en `very-simplified-stack/cognito-backend/app/core/sandbox.py:190`.
  - **Acceso a red:** [IMPLEMENTADO] No tiene acceso a red. Se aísla mediante Bubblewrap (`bwrap`) utilizando la opción `--unshare-all` y omitiendo explícitamente `--share-net`. Esto desactiva todas las interfaces de red dentro del subproceso aislado.
  - **Herencia de variables de entorno del host:** [IMPLEMENTADO] **Hereda todas las variables de entorno del host (`os.environ`)**. En las llamadas `asyncio.create_subprocess_exec` (`sandbox.py:300,378`), **NO se pasa el parámetro `env`**, por lo que Python pasa por defecto `env=None`, haciendo que el subproceso en el sandbox herede todo el entorno del proceso padre (incluidas claves API y secretos del host).
  - **Límites en el código (vs documentación):**
    - **Tiempo:** [IMPLEMENTADO] Aplica un timeout rígido mediante `timeout: int = 30` (por defecto 30s), implementado con `asyncio.wait_for(..., timeout=self.timeout)` (`sandbox.py:198,305,383`).
    - **CPU y Memoria:** [NO EXISTE EN CÓDIGO / SOLO DOCUMENTADO] **No existe ningún límite de CPU ni de memoria en el código**. Aunque la documentación (`README.md:54`, `BACKLOG.md` tarea `NOOA-11`) menciona límites estrictos de CPU y memoria, no hay uso de `cgroups`, `ulimit` ni restricciones de hardware en `sandbox.py`.
- **Citas:**
  - `very-simplified-stack/cognito-backend/app/core/sandbox.py:173-184,190,198,300,305,378,383`
  - `README.md:54`
  - `very-simplified-stack/cognito-backend/docs/BACKLOG.md:197,203`

---

## Seguridad

### 4. ¿Cómo se genera y valida la firma HMAC? ¿Hay valor por defecto para el secreto? ¿Se valida la marca temporal y se evita el replay de nonces?

- **Estado:** [IMPLEMENTADO]
- **Respuesta breve:**
  - **Generación:** `calculate_signature` genera la firma creando la cadena canónica `f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_sha256}\n{worker_id}"` y calculando HMAC-SHA256 con el secreto codificado en UTF-8.
  - **Validación:** `verify_cognito_request` calcula el SHA-256 del cuerpo recibido, comprueba la coincidencia con `X-Cognito-Body-SHA256`, e itera la lista `SHARED_SECRETS` comparando firmas con `hmac.compare_digest` en tiempo constante.
  - **Valor por defecto para el secreto:**
    - En `cognito-backend`: `COGNITO_WORKER_SECRET` usa por defecto cadena vacía `""`.
    - En `cognito-worker`: Lee `COGNITO_WORKER_SECRETS` al iniciar. **No tiene valor por defecto** y la aplicación falla al arrancar con `RuntimeError` si la variable no está configurada.
  - **Marca temporal y Replay Protection:**
    - **Timestamp:** Valida `abs(now - req_time) <= 300` segundos (5 minutos). Rechaza con HTTP 401 si expira.
    - **Nonce:** Mantiene `_SEEN_NONCES` en memoria. Rechaza con HTTP 401 si un nonce ya fue procesado.
- **Citas:**
  - `very-simplified-stack/cognito-backend/app/services/worker_client.py:17-20,27,31-43`
  - `very-simplified-stack/cognito-worker/worker_app/auth.py:11-28,30-81`
  - `very-simplified-stack/cognito-worker/worker_app/main.py:65-71`

---

### 5. ¿Qué endpoints están expuestos vía zrok o nginx y cuáles validan firmas de webhooks?

- **Estado:** [PARCIAL] / [NO EXISTE]
- **Respuesta breve:**
  - **Endpoints expuestos vía zrok / nginx:** [IMPLEMENTADO] `nginx-proxy` actúa como proxy inverso en los puertos 80/443 exponiendo los servicios del stack (`cognito-backend:8000`, `forgejo:3000`, `n8n:5678`, `authelia:9091`). `zrok-tunnel` expone públicamente `ZROK_TARGET_URL` (por defecto `http://nginx-proxy:80`) ejecutando `zrok share public`.
  - **Validación de firmas de webhooks:** [NO EXISTE EN CÓDIGO DE COGNITO] No existe ningún endpoint receptor de webhooks ni validación de firmas de webhooks entrantes en `cognito-backend`. El único componente de webhook en `cognito-backend` es un emisor saliente de auditoría (`WebhookExporter`). Si se configuran webhooks entrantes en `n8n` o `Forgejo`, la firma se valida dentro de esas aplicaciones externas.
- **Citas / Ficheros a revisar:**
  - `docker-compose.yml:1650-1675,1855-1875`
  - `very-simplified-stack/scripts/zrok-entrypoint.sh:83`
  - `very-simplified-stack/cognito-backend/app/core/audit.py:84`
  - *Fichero a revisar para webhooks entrantes:* `very-simplified-stack/cognito-backend/app/api/routes/`

---

### 6. ¿El `.env` está en `.gitignore`? ¿Hay secretos o contraseñas por defecto en ficheros versionados (docker-compose.yml, .env.example)?

- **Estado:** [IMPLEMENTADO]
- **Respuesta breve:**
  - **Exclusión en `.gitignore`:** [IMPLEMENTADO] Sí, `.env` y `.env*` están explícitamente excluidos en `.gitignore:40,42`.
  - **Secretos/contraseñas por defecto versionados:** [IMPLEMENTADO] Sí, existen valores por defecto en texto plano dentro de archivos de configuración versionados en Git, tales como `POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-admin_password}` y `REDIS_PASSWORD=${REDIS_PASSWORD:-redis_password}` en `very-simplified-stack/docker-compose.yml:32,107` y `docker-compose.yml:58,85`.
- **Citas:**
  - `.gitignore:40,42`
  - `very-simplified-stack/docker-compose.yml:32,107`
  - `docker-compose.yml:58,85`

---

### 7. ¿Puede una ruta proporcionada por el usuario salir del directorio de trabajo? Revisa `read_tool.py`, `edit_tool.py`, `write_tool.py` y `unified_patch_tool.py`, y confirma si llaman a `is_path_contained` o a otra validación. Cita la cadena completa de llamadas, no solo la línea de uso.

- **Estado:** [PARCIAL]
- **Respuesta breve:**
  - **Análisis de la herramienta `read_tool.py`:**
    - **Cadena de llamadas:** `ReadTool.execute(...)` (`read_tool.py:27`) -> extrae `path` (`read_tool.py:28`) -> construye `target_path = Path(context.cwd) / path` (`read_tool.py:40`) -> verifica `policy.is_path_ignored(target_path)` (`read_tool.py:43` -> llama a `FSObservationPolicy.is_path_ignored` en `fs_observation_policy.py:43`) -> resuelve `resolved_target = target_path.resolve()` (`read_tool.py:46`) -> lee archivo con `resolved_target.read_text()` (`read_tool.py:53`).
    - **¿Llama a `is_path_contained`?:** **NO LLAMA A `is_path_contained`**. Permite leer archivos fuera de `context.cwd` (ej. `../../etc/passwd`) si no coinciden con los patrones ignorados por la política de observación.
  - **Análisis de la herramienta `edit_tool.py`:**
    - **Cadena de llamadas:** `EditTool.execute(...)` (`edit_tool.py:23`) -> extrae `path` (`edit_tool.py:24`) -> construye `target_path = Path(context.cwd) / path` (`edit_tool.py:36`) -> verifica `policy.is_path_ignored(target_path)` (`edit_tool.py:38` -> llama a `FSObservationPolicy.is_path_ignored`) -> resuelve `resolved_target = target_path.resolve()` (`edit_tool.py:41`) -> modifica archivo con `resolved_target.write_text(...)` (`edit_tool.py:63`).
    - **¿Llama a `is_path_contained`?:** **NO LLAMA A `is_path_contained`**. Permite editar archivos fuera de `context.cwd` si no están bloqueados por `policy`.
  - **Análisis de la herramienta `write_tool.py`:**
    - **Cadena de llamadas:** `WriteTool.execute(...)` (`write_tool.py:24`) -> obtiene `abs_cwd = os.path.realpath(context.cwd)` (`write_tool.py:31`) -> normaliza y une `target_path = os.path.realpath(os.path.join(abs_cwd, norm_path))` (`write_tool.py:33`) -> evalúa `is_path_contained(target_path, abs_cwd)` (`write_tool.py:36` -> llama a `is_path_contained` en `path_safety.py:3` que verifica null bytes, `realpath` y `commonpath == abs_base`) -> rechaza con error si la ruta sale del espacio de trabajo.
    - **¿Llama a `is_path_contained`?:** **SÍ LLAMA A `is_path_contained`**. Bloquea efectivamente los intentos de salir del directorio.
  - **Análisis de la herramienta `unified_patch_tool.py`:**
    - **Cadena de llamadas:** `UnifiedPatchTool.execute(...)` (`unified_patch_tool.py:214`) -> llama a `apply_patch_atomically(...)` (`unified_patch_tool.py:215`) -> resuelve `cwd_path = Path(cwd).resolve()` (`unified_patch_tool.py:53`) -> extrae `target_rel_path` del parche diff (`unified_patch_tool.py:65-79`) -> calcula `target_path = (cwd_path / target_rel_path).resolve()` (`unified_patch_tool.py:80`) -> evalúa `is_path_contained(str(target_path), str(cwd_path))` (`unified_patch_tool.py:82` -> llama a `path_safety.py:3`) -> rechaza el parche si intenta path traversal.
    - **¿Llama a `is_path_contained`?:** **SÍ LLAMA A `is_path_contained`**. Bloquea efectivamente los intentos de salirse del repositorio mediante parches diff.
- **Citas:**
  - `very-simplified-stack/cognito-backend/app/core/tools/read_tool.py:27-53`
  - `very-simplified-stack/cognito-backend/app/core/tools/edit_tool.py:23-63`
  - `very-simplified-stack/cognito-backend/app/core/tools/write_tool.py:24-36`
  - `very-simplified-stack/cognito-backend/app/core/tools/unified_patch_tool.py:45-82,214-215`
  - `very-simplified-stack/cognito-backend/app/core/path_safety.py:3-23`

---

## Agente y verificación

### 8. ¿Qué pasos de verificación se ejecutan antes de abrir un PR? Si no existen, dilo.

- **Estado:** [IMPLEMENTADO] / [SOLO DOCUMENTADO]
- **Respuesta breve:**
  - **Flujos de CI (`.github/workflows/validate.yml` y `build.yml`):**
    1. `validate-yaml`: Validación sintáctica de archivos YAML y JSON.
    2. `lint-shell`: ShellCheck sobre scripts shell.
    3. `lint-dockerfile`: Hadolint sobre Dockerfiles.
    4. `validate-compose`: `docker compose config` para verificar sintaxis de compose.
    5. `lint-markdown`: markdownlint sobre README.md y CONTRIBUTING.md.
    6. `security`: Búsqueda estática de contraseñas predeterminadas y claves API vivas (`sk_live_`, `pk_live_`).
    7. `validate-lockfiles`: Verificación de sincronización de `requirements.lock` mediante `uv pip compile`.
    8. `run-pytest`: Pruebas Pytest para `mcp-server/tests/`.
  - **Verificación en el Agente (`VerificationEngine`):** `VerificationEngine.detect_commands` detecta y ejecuta comandos de prueba (`pytest` o `npm test`), linter (`flake8` o `npm run lint`) y chequeo de tipos (`mypy` o `npm run typecheck`) según la estructura del proyecto antes de finalizar un intento.
  - **Aclaración:** No se ejecutan escaneos dinámicos de secretos tipo `gitleaks` o `trufflehog` antes de abrir un PR.
- **Citas:**
  - `.github/workflows/validate.yml:25,50,70,88,118,142,165`
  - `.github/workflows/build.yml:145`
  - `very-simplified-stack/cognito-worker/worker_app/verification.py:15-32,54-94`

---

### 9. ¿Se guarda algún registro de sesión (prompt, plan, log, resultado)? ¿Formato y ubicación?

- **Estado:** [IMPLEMENTADO]
- **Respuesta breve:**
  - **Sesiones:**
    - **Backend Local (por defecto):** Archivos JSON Lines (`.jsonl`) y JSON de metadatos (`.meta.json`) en `~/.cognito/sessions/<session_id>.jsonl` y `~/.cognito/sessions/<session_id>.meta.json`.
    - **Backend PostgreSQL:** Tablas `sessions` y `session_messages` en PostgreSQL cuando `COGNITO_STORAGE_BACKEND=postgres` o `postgres_redis`.
  - **Tareas, Planes e Intentos:**
    - Persistidos en PostgreSQL (tablas `tasks`, `execution_attempts`, `verification_runs`, `approval_requests`) con respaldo en memoria en `TaskStore`.
  - **Registros de Auditoría y Aprobaciones:**
    - Archivo JSONL en `~/.cognito/sessions/approval_audit_logs.jsonl` y registros estructurados en el registrador de auditoría.
- **Citas:**
  - `very-simplified-stack/cognito-backend/app/core/session_manager.py:44,98,101,234,367`
  - `very-simplified-stack/cognito-backend/app/services/task_store.py:11-200`
  - `very-simplified-stack/cognito-backend/app/models/db.py:27,62,126,162,192,225`
  - `very-simplified-stack/cognito-backend/app/core/approval.py:45`
  - `very-simplified-stack/cognito-backend/app/core/audit.py:45`

---

### 10. ¿Cómo se decide el escalado de modelo? ¿Hay límite de coste o de llamadas por tarea?

- **Estado:** [IMPLEMENTADO]
- **Respuesta breve:**
  - **Decisión de Escalado:**
    1. **Por fallo de verificación:** `EscalationService.run_verification_and_escalate_if_needed` escala automáticamente a través de la cadena `local` -> `luna` -> `terra` -> `sol` si `exit_status != 0` y la falla se clasifica como `"model_related"`.
    2. **Por umbral de incertidumbre:** `OllamaClassifier` y `SemanticOrchestrator` miden la incertidumbre. Si supera el umbral, escalan según `ESCALATION_ROUTING` (`fast` -> `qwen3.5:9b`, `general`/`coding`/`analysis` -> `phi4:latest`).
  - **Límite de Coste / Presupuesto de Tokens:**
    - `TokenBudgetManager` gestiona presupuestos por nivel (`session`, `user`, `project`, `organization`). Permite definir `max_tokens` y la acción `hard_limit_action` (`block` o `warn_only`). Adicionalmente inyecta un mensaje `TokenBudgetReminder` cuando la conversación alcanza el 80% de la ventana de contexto del modelo.
  - **Límite de número de llamadas por tarea:**
    - El bucle del agente está limitado por `max_turns` (por defecto `10` turnos).
    - La cadena de escalado permite un máximo de 4 intentos por tarea (uno por nivel de la cadena: `local`, `luna`, `terra`, `sol`).
- **Citas:**
  - `very-simplified-stack/cognito-backend/app/services/escalation_service.py:12,129-158`
  - `very-simplified-stack/cognito-backend/app/services/escalation_routing.py:13-18`
  - `very-simplified-stack/cognito-backend/app/core/token_budget.py:33,39,118,284`
  - `very-simplified-stack/cognito-backend/app/core/agent_loop.py:48,135,523`

---

### 11. ¿Hay aprobación humana antes de fusionar? ¿Puede haber merge automático?

- **Estado:** [IMPLEMENTADO] / [NO EXISTE]
- **Respuesta breve:**
  - **Aprobación Humana de Acciones:** [IMPLEMENTADO] `ApprovalManager` y `ExecPolicy` pausar la ejecución del agente y exigen aprobación explícita del operador para comandos y modificaciones sensibles. Las decisiones se toman mediante el endpoint `POST /v1/ai-agents/agent/approvals/{approval_id}/decide`.
  - **Merge Automático en Git:** [NO EXISTE EN CÓDIGO] No existe código ni flujo de automatización para ejecutar `git merge` o auto-fusión de Pull Requests. La fusión final en Git requiere intervención manual humana.
- **Citas:**
  - `very-simplified-stack/cognito-backend/app/core/approval.py:37,185`
  - `very-simplified-stack/cognito-backend/app/services/policy_engine.py:11`
  - `very-simplified-stack/cognito-backend/app/api/routes/ai_agents.py:429`

---

## Operación

### 12. ¿Qué variables de entorno son obligatorias y cuáles tienen valor por defecto?

- **Estado:** [IMPLEMENTADO]
- **Respuesta breve:**
  - **Variables Obligatorias (Sin Valor por Defecto):**
    - En `cognito-worker`: `COGNITO_WORKER_SECRETS` (Lanza `RuntimeError` en `worker_app/main.py:65-71` si está vacía).
    - En el arranque interactivo global (`init_env.sh` / `.env.example`): `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `N8N_ENCRYPTION_KEY`, `N8N_RUNNERS_AUTH_TOKEN`, `FORGEJO_DB_PASSWORD`.
  - **Variables con Valor por Defecto en Código:**
    - `COGNITO_WORKER_ID`: `"local-worker-01"`
    - `COGNITO_WORKER_URL`: `"http://host.docker.internal:8765"`
    - `COGNITO_WORKER_SECRET`: `""`
    - `ALLOWED_REPOSITORY_ROOTS`: `"/tmp"`
    - `USE_MOCK_CODEX`: `"true"`
    - `CODEX_APP_SERVER_PATH`: `"codex-app-server"`
    - `COGNITO_STORAGE_BACKEND`: `"local"`
    - `COGNITO_APPROVAL_TIMEOUT_SECONDS`: `"30"`
    - `COGNITO_DISABLE_SANDBOX_DEV_ONLY`: `"false"`
    - `OLLAMA_API_URL`: `"http://host.docker.internal:11434/api/generate"`
    - `OLLAMA_MODEL`: `"qwen3.5:9b"`
    - `QDRANT_URL`: `"http://qdrant:6333"`
    - `POSTGRES_USER`: `"admin"`
    - `POSTGRES_DB`: `"postgres"`
- **Citas:**
  - `very-simplified-stack/cognito-worker/worker_app/main.py:64,65-71,73,84,88`
  - `very-simplified-stack/cognito-backend/app/services/worker_client.py:25-27`
  - `very-simplified-stack/cognito-backend/app/core/session_manager.py:21`
  - `very-simplified-stack/cognito-backend/app/core/approval.py:15`
  - `very-simplified-stack/docker-compose.yml:19-21,50-52`
  - `init_env.sh:105-113`

---

### 13. ¿Qué tests existen y cómo se ejecutan? Cuenta los tests reales (`pytest --co -q`) y di si la cobertura está verificada o solo documentada.

- **Estado:** [IMPLEMENTADO]
- **Respuesta breve:**
  - **Conteo Real de Tests (`pytest --co -q`):**
    - Ejecutando `pytest --co -q` sobre las carpetas de pruebas se contabilizan **359 tests reales** (345 en `cognito-backend/tests/` y 14 en `cognito-worker/tests/`).
  - **Cómo se ejecutan:**
    ```bash
    COGNITO_WORKER_SECRETS="test-secret" PYTHONPATH=very-simplified-stack/cognito-backend:very-simplified-stack/cognito-worker pytest very-simplified-stack/cognito-backend/tests/ very-simplified-stack/cognito-worker/tests/
    ```
  - **Verificación de Cobertura:** **VERIFICADA EN CÓDIGO/EJECUCIÓN REAL**. Al ejecutar `pytest --cov`, se verifica una cobertura real del **75%** sobre el código de `cognito-backend/app` y `cognito-worker/worker_app` (357 pasados, 2 omitidos de 359 tests ejecutados).
- **Citas:**
  - `very-simplified-stack/cognito-backend/tests/`
  - `very-simplified-stack/cognito-worker/tests/`
  - `.github/workflows/build.yml:145`

---

## Riesgos encontrados (Ordenados por Severidad)

1. **CRÍTICO: Ausencia de validación de contención de ruta (`is_path_contained`) en `read_tool` y `edit_tool` (Path Traversal)**
   - **Fichero:** `very-simplified-stack/cognito-backend/app/core/tools/read_tool.py:40` y `edit_tool.py:36`
   - **Descripción:** A diferencia de `write_tool.py` y `unified_patch_tool.py`, las herramientas `read_tool` y `edit_tool` no llaman a `is_path_contained`. Esto permite leer o editar archivos fuera del directorio de trabajo si no coinciden con los patrones ignorados por `FSObservationPolicy`.

2. **ALTO: Herencia imprevista de variables de entorno y credenciales sensibles dentro de `SandboxedExecutor`**
   - **Fichero:** `very-simplified-stack/cognito-backend/app/core/sandbox.py:300,378`
   - **Descripción:** `asyncio.create_subprocess_exec` se invoca sin pasar el parámetro `env`, por lo que el proceso dentro del sandbox hereda todo `os.environ` del host, exponiendo tokens, claves y secretos configurados en la máquina principal.

3. **ALTO: Acumulación indeseada de Worktrees huérfanos sin eliminación automática en tareas fallidas o canceladas**
   - **Fichero:** `very-simplified-stack/cognito-worker/worker_app/worktree.py:186` y `very-simplified-stack/cognito-backend/app/services/escalation_service.py:85`
   - **Descripción:** Si una tarea falla o si `cleanup_worktree` encuentra cambios no confirmados con `force=False`, el directorio del worktree no se borra. La función `recover_orphaned_worktrees` solo ejecuta `git worktree prune`, pero no borra directorios existentes físicamente.

4. **MEDIO: Inexistencia de límites de recursos de hardware (CPU / Memoria) en `SandboxedExecutor`**
   - **Fichero:** `very-simplified-stack/cognito-backend/app/core/sandbox.py:190`
   - **Descripción:** Aunque la documentación menciona límites de CPU y memoria, no hay implementación de `cgroups` ni `ulimit` en el código. Un comando ejecutado en el sandbox puede saturar la CPU o agotar la memoria de la máquina host.

5. **MEDIO: Contraseñas por defecto / fallback en archivos de configuración versionados en Git**
   - **Fichero:** `very-simplified-stack/docker-compose.yml:32,107` y `docker-compose.yml:58,85`
   - **Descripción:** Existen valores por defecto en texto plano para `POSTGRES_PASSWORD` (`admin_password`) y `REDIS_PASSWORD` (`redis_password`) en archivos versionados.

---

## Preguntas sin respuesta en el repo

1. **Validación de firmas para Webhooks de aplicaciones externas (`n8n`, `Forgejo`):**
   - *Explicación y fichero a revisar:* `cognito-backend` no expone endpoints receptores de webhooks. Para verificar la validación de firmas de webhooks recibidos en `n8n` o `Forgejo`, se deben revisar los flujos internos de `n8n/` y la consola de administración de `Forgejo`.
2. **Reglas específicas de auto-merge en servidores Git externos:**
   - *Explicación y fichero a revisar:* El repositorio no contiene bots para la fusión automática de Pull Requests. La configuración de reglas de protección de ramas debe revisarse en la interfaz de administración del servidor Git (`Forgejo` o `GitHub`).
3. **Límites de recursos cgroups/cgroupv2 asignados al servicio `cognito-worker` en el host:**
   - *Explicación y fichero a revisar:* El archivo `very-simplified-stack/cognito-worker/cognito-worker.service` no define directivas `CPUQuota` o `MemoryMax`. Debe verificarse la configuración del demonio systemd en la máquina host.
