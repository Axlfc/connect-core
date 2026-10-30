# Preguntas y Respuestas sobre el Repositorio Hypenosys (`Axlfc/connect-core`)

Este documento reúne el análisis de arquitectura, ejecución, seguridad, operaciones y mecanismos del agente dentro de la carpeta `very-simplified-stack/`.

---

## Arquitectura y ejecución

### 1. ¿Cómo se comunica `cognito-backend` con `cognito-worker`? Describe el flujo completo de una petición, desde el endpoint hasta la ejecución en el worker.

- **Estado:** [IMPLEMENTADO]
- **Respuesta breve:**
  1. Un cliente realiza una petición a los endpoints de la API en `cognito-backend` (ej. `POST /v1/ai-agents/tasks/{task_id}/attempts`), lo cual invoca a `escalation_service.execute_task_attempt(...)`.
  2. `escalation_service` genera la estructura de trabajo e invoca `worker_client.start_task(payload)`.
  3. `WorkerClient` genera la solicitud HTTP POST hacia `${COGNITO_WORKER_URL}/v1/task` (por defecto `http://host.docker.internal:8765`).
  4. `WorkerClient._get_headers` firma la petición mediante HMAC-SHA256 e incluye las cabeceras `X-Cognito-Worker-Id`, `X-Cognito-Timestamp`, `X-Cognito-Nonce`, `X-Cognito-Body-SHA256` y `X-Cognito-Signature`.
  5. En `cognito-worker`, el endpoint `/v1/task` autentica la petición invocando a `verify_cognito_request`, comprobando la firma HMAC, la caducidad del timestamp (máximo 5 minutos) y descartando nonces reutilizados.
  6. `cognito-worker` valida que el directorio del repositorio esté dentro de `ALLOWED_REPOSITORY_ROOTS` mediante `validate_repo_path`.
  7. Se crea un `git worktree` mediante `worktree_manager.create_worktree(...)`.
  8. `codex_provider.execute_task(...)` ejecuta las instrucciones dentro del worktree en un subproceso o mock.
  9. Los resultados se transmiten en tiempo real de vuelta a `cognito-backend` mediante un flujo Server-Sent Events (SSE `text/event-stream`).
  10. Opcionalmente, `cognito-backend` invoca `/v1/verify` para correr tests o linter, y `/v1/cleanup` para limpiar el entorno.
- **Citas:**
  - `very-simplified-stack/cognito-backend/app/api/routes/ai_agents.py:623`
  - `very-simplified-stack/cognito-backend/app/services/escalation_service.py:48,85,133`
  - `very-simplified-stack/cognito-backend/app/services/worker_client.py:17-43,76-90`
  - `very-simplified-stack/cognito-worker/worker_app/auth.py:30-81`
  - `very-simplified-stack/cognito-worker/worker_app/main.py:92,118-146,149-156,158-162`

---

### 2. ¿Dónde y cómo se crea el `git worktree` para cada tarea? ¿Se limpia al terminar? ¿Qué pasa si la tarea falla a mitad?

- **Estado:** [IMPLEMENTADO]
- **Respuesta breve:**
  - **Dónde:** En la máquina del worker, bajo la ruta `~/.cognito/worktrees/<repo_id>/<task_id>/attempt-<attempt:02d>`.
  - **Cómo:** `GitWorktreeManager.create_worktree` sanitiza los identificadores para evitar inyección de flags, crea la rama git con `git branch -- cognito/task-<task_id>-attempt-<attempt:02d> <base_commit>` y añade el worktree con `git worktree add -- <worktree_path> <branch_name>`.
  - **Limpieza al terminar:** Se expone el endpoint `/v1/cleanup` que invoca `cleanup_worktree`. Sin embargo, si existen cambios no confirmados (`has_uncommitted_changes`) y el parámetro `force=False`, **se omite la eliminación física** para proteger el progreso. Además, `escalation_service` no invoca automáticamente la limpieza tras completar cada intento.
  - **Si falla a mitad:** El directorio del worktree permanece intacto en disco. Aunque existe la función `recover_orphaned_worktrees`, esta solo ejecuta `git worktree prune` (el cual elimina referencias pero no borra carpetas físicamente si siguen existiendo), dejando carpetas abandonadas en el sistema hasta que se invoque manualmente un cleanup forzado.
- **Citas:**
  - `very-simplified-stack/cognito-worker/worker_app/worktree.py:110-156,165-203,205-210`
  - `very-simplified-stack/cognito-worker/worker_app/main.py:158-162`
  - `very-simplified-stack/cognito-backend/app/services/escalation_service.py:53`
  - `very-simplified-stack/cognito-backend/app/services/worker_client.py:120-143`

---

### 3. ¿El `SandboxExecutor` tiene acceso a red? ¿Monta credenciales o variables de entorno del host? ¿Qué límites de CPU, memoria y tiempo aplica exactamente?

- **Estado:** [IMPLEMENTADO] / [SOLO DOCUMENTADO]
- **Respuesta breve:**
  - **Nombre en código:** La clase implementada en el código se denomina `SandboxedExecutor`.
  - **Acceso a red:** [IMPLEMENTADO] No tiene acceso a red. Se ejecuta mediante Bubblewrap (`bwrap`) utilizando la opción `--unshare-all` y omitiendo explícitamente `--share-net`. Esto deshabilita todas las interfaces de red dentro del subproceso aislado.
  - **Credenciales y variables de entorno:** [IMPLEMENTADO] Monta el sistema de archivos raíz en modo solo lectura (`--ro-bind / /`), más `/dev`, `/proc`, `/tmp` y el directorio de trabajo actual (`cwd`). Sin embargo, al crear el subproceso con `asyncio.create_subprocess_exec`, no se restringe `env`, por lo que el proceso dentro del sandbox **hereda todas las variables de entorno del host (`os.environ`)**, incluidas claves API y credenciales expuestas en la máquina principal.
  - **Límites de tiempo, CPU y memoria:**
    - **Tiempo:** [IMPLEMENTADO] Aplica un timeout rígido configurable mediante el parámetro `timeout` (por defecto `30` segundos), enforced vía `asyncio.wait_for`.
    - **CPU y Memoria:** [SOLO DOCUMENTADO] **No existen límites de CPU ni de memoria implementados en el código** de `sandbox.py`. Aunque en la documentación (`README.md`, `BACKLOG.md` tarea `NOOA-11`) se afirman límites estrictos de CPU y cuota de memoria, el código no hace uso de `cgroups`, `ulimit` ni afinidad de CPU.
- **Citas:**
  - `very-simplified-stack/cognito-backend/app/core/sandbox.py:173-184,190,198,300,305,378,383`
  - `README.md:54`
  - `very-simplified-stack/cognito-backend/docs/BACKLOG.md:197,203`

---

## Seguridad

### 4. ¿Cómo se genera y valida la firma HMAC? ¿Hay un valor por defecto para el secreto? ¿Se comprueba la marca temporal para evitar replay?

- **Estado:** [IMPLEMENTADO]
- **Respuesta breve:**
  - **Generación:** `calculate_signature` genera la firma creando la cadena canónica `f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_sha256}\n{worker_id}"` y aplicando HMAC-SHA256 con el secreto codificado en UTF-8.
  - **Validación:** `verify_cognito_request` calcula el SHA-256 del cuerpo de la petición, comprueba la igualdad con `X-Cognito-Body-SHA256`, e itera los secretos configurados en `SHARED_SECRETS` validando la firma HMAC con `hmac.compare_digest` en tiempo constante.
  - **Valor por defecto para el secreto:**
    - En `cognito-backend`: `COGNITO_WORKER_SECRET` tiene por defecto una cadena vacía `""`.
    - En `cognito-worker`: Al arrancar se lee `COGNITO_WORKER_SECRETS`. **No existe valor por defecto** y la aplicación se detiene inmediatamente con `RuntimeError` si la variable no está configurada.
  - **Marca temporal y Replay Protection:**
    - **Timestamp:** Valida que `abs(now - req_time) <= 300` segundos (5 minutos).
    - **Nonce:** Almacena los nonces procesados en `_SEEN_NONCES`. Si un nonce se repite, rechaza la petición con estado HTTP 401.
- **Citas:**
  - `very-simplified-stack/cognito-backend/app/services/worker_client.py:17-20,27,31-43`
  - `very-simplified-stack/cognito-worker/worker_app/auth.py:11-28,30-81`
  - `very-simplified-stack/cognito-worker/worker_app/main.py:65-71`

---

### 5. ¿Qué endpoints están expuestos vía zrok o nginx y cuáles validan la firma de los webhooks?

- **Estado:** [IMPLEMENTADO] / [NO ENCONTRADO]
- **Respuesta breve:**
  - **Endpoints expuestos vía zrok / nginx:** [IMPLEMENTADO] `nginx-proxy` actúa como proxy inverso exponiendo los servicios del stack en los puertos 80/443 (incluyendo `cognito-backend:8000`, `forgejo:3000`, `n8n:5678`, `authelia:9091`). El contenedor `zrok-tunnel` expone la URL `ZROK_TARGET_URL` (por defecto `http://nginx-proxy:80`) mediante el comando `zrok share public`.
  - **Validación de firmas en webhooks entrantes:** [NO ENCONTRADO EN EL REPO] En `cognito-backend` no existe ningún endpoint receptor de webhooks ni lógica de validación de firmas de webhooks entrantes. La única referencia a webhooks en `cognito-backend` es un componente de exportación saliente de auditoría (`WebhookExporter`). Si se configuran webhooks entrantes en `n8n` o `Forgejo`, su validación es gestionada internamente por esas herramientas.
- **Citas / Ficheros a revisar:**
  - `docker-compose.yml:1650-1675,1855-1875`
  - `very-simplified-stack/scripts/zrok-entrypoint.sh:83`
  - `very-simplified-stack/cognito-backend/app/core/audit.py:84`
  - *Fichero a revisar en caso de integrar webhooks:* `very-simplified-stack/cognito-backend/app/api/routes/`

---

### 6. ¿El `.env` está excluido en `.gitignore`? ¿Hay algún secreto versionado en el historial reciente (`git log -p` sobre ficheros de configuración)?

- **Estado:** [IMPLEMENTADO]
- **Respuesta breve:**
  - **Exclusión en `.gitignore`:** [IMPLEMENTADO] Sí, `.env` y `.env*` están explícitamente excluidos en las líneas 40 y 42 de `.gitignore`.
  - **Secretos versionados en historial:** [IMPLEMENTADO] Existen contraseñas de contingencia o fallback en texto plano dentro de los archivos de configuración versionados en Git, como `POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-admin_password}` y `REDIS_PASSWORD=${REDIS_PASSWORD:-redis_password}` en `very-simplified-stack/docker-compose.yml` y `docker-compose.yml`. En la revisión de commits recientes no se encontraron claves privadas de producción ni tokens en vivo (`sk_live_`).
- **Citas:**
  - `.gitignore:40,42`
  - `very-simplified-stack/docker-compose.yml:32,107`
  - `docker-compose.yml:58,85`

---

### 7. ¿Puede una ruta proporcionada por el usuario salir del directorio de trabajo permitido? Indica la función que valida las rutas o confirms que no existe.

- **Estado:** [IMPLEMENTADO] / [INCOMPLETO]
- **Respuesta breve:**
  - **Función de validación:** La función encargada de validar la contención de rutas dentro del directorio permitido es `is_path_contained` en `very-simplified-stack/cognito-backend/app/core/path_safety.py:3`.
  - **Uso en el código:** Se utiliza en `cognito-worker` para validar el repositorio (`validate_repo_path`) y en las herramientas de modificación del agente (`write_tool.py` y `unified_patch_tool.py`).
  - **Vulnerabilidad de salida de directorio:** En las herramientas de lectura y edición básica (`read_tool.py` y `edit_tool.py`), **no se llama a `is_path_contained`**. Dichas herramientas resuelven la ruta concatenando `Path(context.cwd) / path` y verifican únicamente si la ruta está ignorada por la política de observación (`is_path_ignored`), sin bloquear explícitamente secuencias como `../../etc/passwd` mediante `is_path_contained`.
- **Citas:**
  - `very-simplified-stack/cognito-backend/app/core/path_safety.py:3-23`
  - `very-simplified-stack/cognito-worker/worker_app/main.py:107`
  - `very-simplified-stack/cognito-backend/app/core/tools/write_tool.py:36`
  - `very-simplified-stack/cognito-backend/app/core/tools/unified_patch_tool.py:82`
  - `very-simplified-stack/cognito-backend/app/core/tools/read_tool.py:40`
  - `very-simplified-stack/cognito-backend/app/core/tools/edit_tool.py:36`

---

## Agente y verificación

### 8. ¿Qué pasos de verificación se ejecutan antes de abrir un PR (tests, linters, escaneo de secretos)? Si no existen, dilo explícitamente.

- **Estado:** [IMPLEMENTADO] / [SOLO DOCUMENTADO]
- **Respuesta breve:**
  - **Flujos de CI (`.github/workflows/validate.yml` y `build.yml`):**
    1. Validación de sintaxis en archivos YAML y JSON (`validate-yaml`).
    2. Linter de scripts Shell con ShellCheck (`lint-shell`).
    3. Linter de Dockerfiles con Hadolint (`lint-dockerfile`).
    4. Validación de sintaxis de Docker Compose con `docker compose config` (`validate-compose`).
    5. Linter de archivos Markdown con markdownlint (`lint-markdown`).
    6. Escaneo estático de secretos buscando contraseñas predeterminadas en `.env` y patrones de claves API vivas (`sk_live_`, `pk_live_`) (`security`).
    7. Verificación de sincronización de dependencias y lockfiles con `uv pip compile` (`validate-lockfiles`).
    8. Ejecució de Pytest para componentes externos (`mcp-server/tests/`).
  - **Motor de Verificación Interno (`VerificationEngine`):** Detecta automáticamente comandos de prueba (`pytest` o `npm test`), linter (`flake8` o `npm run lint`) y chequeo de tipos (`mypy` o `npm run typecheck`) según los archivos presentes en el trabajo antes de concluir una tarea.
  - **Aclaración:** No se ejecutan herramientas dedicadas de escaneo dinámico de secretos (como `gitleaks` o `trufflehog`) en la verificación previa a PR del agente.
- **Citas:**
  - `.github/workflows/validate.yml:25,50,70,88,118,142,165`
  - `.github/workflows/build.yml:145`
  - `very-simplified-stack/cognito-worker/worker_app/verification.py:15-32,54-94`

---

### 9. ¿Se guarda algún registro de sesión (prompt, plan, log, resultado)? ¿En qué formato y dónde?

- **Estado:** [IMPLEMENTADO]
- **Respuesta breve:**
  - **Formato y Ubicación de Sesiones:**
    - **Backend Local (por defecto):** Se almacenan en formato JSON Lines (`.jsonl`) y metadatos JSON (`.meta.json`) en `~/.cognito/sessions/<session_id>.jsonl` y `~/.cognito/sessions/<session_id>.meta.json`.
    - **Backend PostgreSQL:** Cuando `COGNITO_STORAGE_BACKEND=postgres` o `postgres_redis`, las sesiones y los mensajes se persisten en las tablas `sessions` y `session_messages` de PostgreSQL.
  - **Formato y Ubicación de Tareas y Planes:**
    - Las tareas, requerimientos, decisiones de enrutamiento, resúmenes de intentos, parches diff y resultados de verificación se guardan en PostgreSQL (tablas `tasks`, `execution_attempts`, `verification_runs`, `approval_requests`) con respaldos en memoria en `TaskStore`.
  - **Auditoría de Aprobaciones:**
    - Se guardan registros estructurados de auditoría de aprobaciones en `~/.cognito/sessions/approval_audit_logs.jsonl` y en el sistema unificado de auditoría.
- **Citas:**
  - `very-simplified-stack/cognito-backend/app/core/session_manager.py:44,98,101,234,367`
  - `very-simplified-stack/cognito-backend/app/services/task_store.py:11-200`
  - `very-simplified-stack/cognito-backend/app/models/db.py:27,62,126,162,192,225`
  - `very-simplified-stack/cognito-backend/app/core/approval.py:45`
  - `very-simplified-stack/cognito-backend/app/core/audit.py:45`

---

### 10. ¿Cómo se decide el escalado a un modelo más potente? ¿Hay límite de coste o de número de llamadas por tarea?

- **Estado:** [IMPLEMENTADO]
- **Respuesta breve:**
  - **Decisión de Escalado:**
    1. **Por error de verificación:** `EscalationService` comprueba la verificación tras cada intento. Si `exit_status != 0` y el fallo se clasifica como `"model_related"`, escala progresivamente en la cadena `local` -> `luna` -> `terra` -> `sol`.
    2. **Por umbral de incertidumbre:** `OllamaClassifier` y `SemanticOrchestrator` calculan la incertidumbre de la subtarea. Si supera el umbral configurado, la redirigen según `ESCALATION_ROUTING` (`fast` -> `qwen3.5:9b`, `general`/`coding`/`analysis` -> `phi4:latest`).
  - **Límite de Coste / Presupuesto de Tokens:**
    - `TokenBudgetManager` controla presupuestos de tokens por nivel (`session`, `user`, `project`, `organization`). Permite establecer `max_tokens` y bloquear o advertir (`hard_limit_action`). Adicionalmente, inyecta un aviso `TokenBudgetReminder` al alcanzar el 80% de la ventana de contexto del modelo.
  - **Límite de número de llamadas por tarea:**
    - El bucle del agente está limitado por `max_turns` (por defecto `10` turnos por ejecución).
    - La cadena de escalado de la tarea soporta hasta 4 intentos máximos (uno por cada tier: `local`, `luna`, `terra`, `sol`).
- **Citas:**
  - `very-simplified-stack/cognito-backend/app/services/escalation_service.py:12,129-158`
  - `very-simplified-stack/cognito-backend/app/services/escalation_routing.py:13-18`
  - `very-simplified-stack/cognito-backend/app/core/token_budget.py:33,39,118,284`
  - `very-simplified-stack/cognito-backend/app/core/agent_loop.py:48,135,523`

---

### 11. ¿Hay alguna aprobación humana antes de fusionar, o el flujo puede llegar a merge automático?

- **Estado:** [IMPLEMENTADO] / [NO ENCONTRADO]
- **Respuesta breve:**
  - **Aprobación Humana de Acciones:** [IMPLEMENTADO] `ApprovalManager` y `ExecPolicy` pausan la ejecución y solicitan aprobación explícita a un operador humano antes de ejecutar comandos o acciones destructivas/sensibles. Las decisiones se registran mediante `POST /v1/ai-agents/agent/approvals/{approval_id}/decide`.
  - **Merge Automático:** [NO ENCONTRADO EN EL REPO] No existe ningún código ni flujo de merge automático de Git (`git merge`) o auto-merge de Pull Requests implementado en la plataforma. Todas las fusiones de código requieren la intervención manual de un operador sobre el repositorio Git.
- **Citas:**
  - `very-simplified-stack/cognito-backend/app/core/approval.py:37,185`
  - `very-simplified-stack/cognito-backend/app/services/policy_engine.py:11`
  - `very-simplified-stack/cognito-backend/app/api/routes/ai_agents.py:429`

---

## Operación

### 12. ¿Qué variables de entorno son obligatorias para arrancar el stack y cuáles tienen valores por defecto?

- **Estado:** [IMPLEMENTADO]
- **Respuesta breve:**
  - **Variables Obligatorias (Sin Valor por Defecto):**
    - En `cognito-worker`: `COGNITO_WORKER_SECRETS` (Lanza `RuntimeError` en `worker_app/main.py` si no está definida o está vacía).
    - En el despliegue interactivo global (`init_env.sh` / `.env.example`): `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `N8N_ENCRYPTION_KEY`, `N8N_RUNNERS_AUTH_TOKEN`, `FORGEJO_DB_PASSWORD`.
  - **Variables con Valores por Defecto en Código:**
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

### 13. ¿Qué tests existen y cómo se ejecutan? ¿Cuál is su cobertura aproximada?

- **Estado:** [IMPLEMENTADO]
- **Respuesta breve:**
  - **Tests existentes:** Existen 359 tests automáticos repartidos en:
    - `very-simplified-stack/cognito-backend/tests/` (345 tests): Pruebas para el bucle del agente, sandbox, gestión de sesiones, políticas de ejecución, cliente worker, presupuesto de tokens, API OpenAI compatible, etc.
    - `very-simplified-stack/cognito-worker/tests/` (14 tests): Pruebas de autenticación HMAC, prevención de replay de nonces, ciclo de vida de worktrees y apagado progresivo (`SIGTERM`).
  - **Cómo se ejecutan:**
    ```bash
    COGNITO_WORKER_SECRETS="test-secret" PYTHONPATH=very-simplified-stack/cognito-backend:very-simplified-stack/cognito-worker pytest very-simplified-stack/cognito-backend/tests/ very-simplified-stack/cognito-worker/tests/
    ```
  - **Cobertura aproximada:** **75% de cobertura general** en los módulos de `cognito-backend` y `cognito-worker` (357 aprobados, 2 omitidos, 0 fallados).
- **Citas:**
  - `very-simplified-stack/cognito-backend/tests/`
  - `very-simplified-stack/cognito-worker/tests/`
  - `.github/workflows/build.yml:145`

---

## Riesgos encontrados (Ordenados por Severidad)

1. **CRÍTICO: Ausencia de validación de contención de ruta (`is_path_contained`) en `read_tool` y `edit_tool` (Path Traversal)**
   - **Fichero:** `very-simplified-stack/cognito-backend/app/core/tools/read_tool.py:40` y `edit_tool.py:36`
   - **Descripción:** A diferencia de `write_tool.py` y `unified_patch_tool.py`, las herramientas de lectura y edición de archivos no invocan la función de seguridad `is_path_contained`. Esto permite que un prompt malicioso intente acceder o editar archivos fuera del directorio de trabajo (ej. `../../etc/passwd`) si la política de observación no contiene reglas explícitas de descarte.

2. **ALTO: Herencia imprevista de variables de entorno y credenciales sensibles dentro de `SandboxedExecutor`**
   - **Fichero:** `very-simplified-stack/cognito-backend/app/core/sandbox.py:300,378`
   - **Descripción:** Al ejecutar subprocesos dentro del sandbox de Bubblewrap, no se limpia la variable de entorno `env` al llamar a `asyncio.create_subprocess_exec`. En consecuencia, el subproceso hereda todo el objeto `os.environ` del proceso padre, exponiendo tokens, claves y secretos configurados en el host.

3. **ALTO: Acumulación indeseada de Worktrees huérfanos sin eliminación automática en tareas fallidas o canceladas**
   - **Fichero:** `very-simplified-stack/cognito-worker/worker_app/worktree.py:186` y `very-simplified-stack/cognito-backend/app/services/escalation_service.py:85`
   - **Descripción:** Cuando una tarea falla o si `cleanup_worktree` detecta cambios sin confirmar con `force=False`, la carpeta del worktree se conserva de forma indefinida en `~/.cognito/worktrees/`. La función de recuperación `recover_orphaned_worktrees` solo ejecuta `git worktree prune`, pero no borra directorios físicamente existentes, pudiendo causar agotamiento de espacio en disco en el worker.

4. **MEDIO: Inexistencia de límites de recursos de hardware (CPU / Memoria) en `SandboxedExecutor`**
   - **Fichero:** `very-simplified-stack/cognito-backend/app/core/sandbox.py:190`
   - **Descripción:** La documentación del proyecto indica que el sandbox restringe el uso de CPU y memoria. Sin embargo, en el código no hay implementación de `cgroups` ni `ulimit`. Un comando ejecutado por el LLM en el sandbox puede saturar la CPU o agotar la memoria RAM de la máquina host.

5. **MEDIO: Contraseñas por defecto / fallback en archivos de configuración versionados en Git**
   - **Fichero:** `very-simplified-stack/docker-compose.yml:32,107` y `docker-compose.yml:58,85`
   - **Descripción:** Se incluyen contraseñas predeterminadas en texto plano para `POSTGRES_PASSWORD` (`admin_password`) y `REDIS_PASSWORD` (`redis_password`). Si un operador despliega la pila sin configurar un archivo `.env` personalizado, los servicios quedarán expuestos con credenciales débiles conocidas.

---

## Preguntas sin respuesta en el repo

1. **Validación de firmas para Webhooks de aplicaciones externas (`n8n`, `Forgejo`):**
   - *Explicación y fichero a revisar:* `cognito-backend` no expone endpoints receptores de webhooks. Para verificar cómo se gestionan y aseguran las firmas de los webhooks entrantes de `Forgejo` o `n8n`, es necesario revisar los archivos de configuración y flujos internos de `n8n/` y la consola de administración de `Forgejo`.
2. **Reglas específicas de auto-merge en servidores Git externos:**
   - *Explicación y fichero a revisar:* El repositorio no contiene bots ni integraciones para la aprobación o fusión automática de Pull Requests. La configuración de fusionado automático y reglas de protección de ramas debe revisarse directamente en la interfaz de administración del servidor Git (`Forgejo` o `GitHub`).
3. **Límites de recursos cgroups/cgroupv2 asignados al servicio `cognito-worker` en el host:**
   - *Explicación y fichero a revisar:* El archivo de servicio `very-simplified-stack/cognito-worker/cognito-worker.service` no define directivas de limitación de recursos (`CPUQuota`, `MemoryMax`). Para conocer los límites aplicados al servicio worker en ejecución real, debe revisarse la configuración del demonio systemd en la máquina host.
