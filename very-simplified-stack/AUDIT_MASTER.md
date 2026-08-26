# Documento Maestro de Auditoría Cognito (`AUDIT_MASTER.md`)

Este documento constituye el registro persistente, unificado y reconciliado de todos los hallazgos de auditoría de seguridad, arquitectura, precisión y resiliencia en los componentes `cognito-backend` y `cognito-worker`.

Cualquier auditoría futura debe contrastarse e integrarse en este documento utilizando la numeración consecutiva `AUD-XXX`.

---

## Resumen de Estado de Hallazgos

| ID | Severidad | Categoría | Componente | Descripción Resumida | Estado |
|---|---|---|---|---|---|
| **AUD-001** | Crítico | Seguridad | `cognito-backend` | Delimitador `<tool_output>` falsificable por contenido inyectado | **Corregido** (Nonce por turno + Escapado) |
| **AUD-002** | Alto | Precisión/Arquitectura | `cognito-backend` | Pérdida de mensajes intermedios e inyección de system prompt en compactación | **Corregido** (Filtro `i > covers_through_line` + System Prompt) |
| **AUD-003** | Crítico | Seguridad | `cognito-backend` | Modo `COGNITO_MCP_INSECURE_DEV` desactivaba auth globalmente | **Corregido** (Reclasificado a Crítico; Fail-closed + Token pers. `0o600`) |
| **AUD-004** | Alto | Arquitectura | `cognito-backend` | Contención de rendimiento y bloqueo del event loop de FastAPI por `fcntl.flock` síncrono | **Corregido** (Locks por sesión + Offloading AnyIO thread; p99=238.64ms) |
| **AUD-005** | Medio | Resiliencia | `cognito-backend` | Interrupción de streaming por errores HTTP 429/transitorios en `generate_with_tools` | **Corregido** (Integrado `retry_transient_stream` en `BackendRouter`) |
| **AUD-006** | Bajo | Precisión | `cognito-backend` | Falsos positivos del detector de bucles en herramientas de solo lectura | **Corregido** (Uso de `READ_ONLY_TOOLS` en `record_and_check`) |
| **AUD-007** | Medio | Seguridad | `cognito-worker` | Clave por defecto hardcodeada en `cognito-worker` | **Corregido** (`COGNITO_WORKER_SECRETS` obligatorio) |
| **AUD-008** | Medio | Arquitectura/Precisión | `cognito-backend` | System prompt sin versionar | **Corregido** (Definiciones TOML versionadas) |
| **AUD-009** | Crítico | Seguridad | `cognito-backend` | Bypass de `ExecPolicy` en `shell_run` | **Corregido** (Validación previa en `ShellTools`) |
| **AUD-010** | Alto | Seguridad | `cognito-backend` | `shell_policy.py` desconectado en tiempo de ejecución | **Corregido** (Conectado a `exec_policy.py`) |
| **AUD-011** | Alto | Seguridad | `cognito-worker` / `cognito-backend` | Ejecución de `BashTool` sin sandbox de contenedor ni lista blanca | **Corregido** (ExecPolicy + SandboxedExecutor bwrap / RLIMITs de OS) |
| **AUD-012** | Medio | Resiliencia | `cognito-backend` | Pérdida de mensajes de steering por almacenarse únicamente en cola en memoria | **Corregido** (Persistencia durable en JSONL + Marcado `delivered` + Sincronización al reanudar) |
| **AUD-013** | Medio | Precisión | `cognito-backend` | Pérdida de detalle semántico (rutas de archivo, firmas) durante compactación | **Corregido** (Context Ledger estructurado JSON + persistencia en log + reinyección en system prompt) |
| **AUD-014** | Bajo | Precisión | `cognito-backend` | Recordatorios de presupuesto de tokens inyectados con rol `user` en vez de `system` | **Corregido** (Inyección con rol `system` y metadato `type: TokenBudgetReminder`) |
| **AUD-015** | Bajo | Resiliencia | `cognito-backend` | Ausencia de escritura atómica en `WriteTool`, sin backup ante fallo de I/O | **Corregido** (Escritura atómica en temp + fsync + os.replace + backup `.bak`) |
| **AUD-016** | Medio | Arquitectura | `cognito-backend` | Desacoplamiento entre `cognito_agent.py` y el agent loop de `cognito-backend` | **Corregido** (Cliente CLI sobre agent_loop + ExecPolicy + SessionManager) |
| **AUD-017** | Medio | Arquitectura | `cognito-backend` | Falta de contratos de validación estrictos en herramientas MCP/locales | **Corregido** (Validación fail-fast Pydantic/JSON Schema en entrada y salida) |

---

## Hallazgos Reconciliados (AUD-001 a AUD-010)

### AUD-001: Delimitador `<tool_output>` falsificable por contenido de herramientas
- **Severidad**: Crítico
- **Categoría**: Seguridad
- **Componente**: `cognito-backend` (`app/core/agent_loop.py`)
- **Descripción**: El formato de retorno de herramientas utilizaba la etiqueta fija `<tool_output source="...">`. Un intento de inyección indirecta dentro de un archivo de texto o salida de comando que contuviera la secuencia literal `</tool_output>` podía cerrar el bloque prematuramente e inyectar instrucciones directas con rol de sistema o usuario. La función previa `sanitize_tool_output()` basada en expresiones regulares sólo filtraba nombres de etiquetas exactos y en minúsculas.
- **Evidencia de Ubicación en Código**: `very-simplified-stack/cognito-backend/app/core/agent_loop.py` (Líneas 17-26 y Líneas 180-184).
- **Resolución y Evidencia Técnica**:
  - `sanitize_tool_output(output: str)` escapa secuencias literales `</tool_output>` a `<\/tool_output>` (Línea 25) y `<tool_output` a `<\tool_output` (Línea 26).
  - Cada turno genera un token nonce único impredecible (`turn_nonce = uuid.uuid4().hex[:8]`), formateando la salida como `<tool_output_{turn_nonce} source="...">\n{sanitized_output}\n</tool_output_{turn_nonce}>` (Líneas 181-182).
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_indirect_injection.py` (`test_indirect_injection_escaped_tool_output_delimiter`, `test_indirect_injection_read_file`, `test_indirect_injection_apply_patch`, `test_indirect_injection_code_review`).
- **Resultado del Test**: **PASA** (200/200 tests pasados).

### AUD-002: Pérdida de mensajes intermedios y falta de system prompt en compactación
- **Severidad**: Alto
- **Categoría**: Precisión / Arquitectura
- **Componente**: `cognito-backend` (`app/core/session_manager.py`, `app/core/session/message_deriver.py`)
- **Descripción**: Al resumir o compactar el historial de una sesión (`compact()` / `append_compaction()`), las versiones iniciales descartaban mensajes intercalados entre la línea de corte y el evento de compactación registrado, y omitían la reinyección del System Prompt actualizado en la cabecera del contexto derivado.
- **Evidencia de Ubicación en Código**:
  - `very-simplified-stack/cognito-backend/app/core/session_manager.py` (Líneas 281-305).
  - `very-simplified-stack/cognito-backend/app/core/session/message_deriver.py` (Líneas 40-75).
- **Confirmación con Diff y Análisis del Código Actual**:
  - En `SessionManager.get_effective_messages`:
    ```python
    if compaction:
        summary = compaction.get("summary", "")
        start_line = compaction.get("covers_through_line", -1)
        messages.append({"role": "system", "content": f"[Resumen de la conversación anterior]: {summary}"})
        for i, data in all_entries:
            if i > start_line and data.get("type") == "message":
                messages.append(self._to_ai_message(data))
        return messages
    ```
  - La condición `i > start_line` en la línea 298 garantiza explícitamente que los mensajes registrados entre la línea de corte `covers_through_line` (p. ej., línea 3) y la línea donde se grabó la compactación (p. ej., línea 5) NO se ignoran y son preservados en el array de mensajes devueltos.
  - Además, si `include_system_prompt=True` (o en `derive_messages_for_llm`), se inserta en el índice 0 el system prompt dinámico (`build_system_message(resolved_cwd)`), incluyendo las directivas de `AGENTS.md`.
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_session_compaction_regression.py` (`test_session_compaction_message_loss_and_system_prompt_regression`), `very-simplified-stack/cognito-backend/tests/test_compaction.py`.
- **Resultado del Test**: **PASA** (200/200 tests pasados).

### AUD-003: Modo `COGNITO_MCP_INSECURE_DEV` desactivaba auth globalmente
- **Severidad**: Crítico (Reclasificado explícitamente de Alto a Crítico)
- **Categoría**: Seguridad
- **Componente**: `cognito-backend` (`app/services/mcp_server.py`)
- **Descripción**: La variable de entorno `COGNITO_MCP_INSECURE_DEV` desactivaba la comprobación de autenticación para todos los clientes MCP.
- **Evaluación de Reclasificación de Severidad**: **Reclasificado a Crítico**. La desactivación global de la autenticación permitía la ejecución remota no autenticada de tareas de agente arbitrarias (`execute_agent_task`), acceso al estado de sesiones y ejecución de herramientas con privilegios en el sistema host sin credenciales ni tokens de autorización.
- **Evidencia de Ubicación en Código**: `very-simplified-stack/cognito-backend/app/services/mcp_server.py` (Líneas 18-24, Líneas 56-83 y Líneas 85-108).
- **Resolución y Evidencia Técnica**:
  - En `load_mcp_config()` (Líneas 18-23), la opción `RequireAuth` se establece por defecto en `True` y `COGNITO_MCP_INSECURE_DEV` sólo desactiva auth si se habilita explícitamente (`RequireAuth = False`).
  - Si no se configuran tokens/claves, `load_mcp_config()` genera automáticamente un token seguro efímero (`secrets.token_urlsafe(32)`), lo persiste en `~/.cognito/config.json` con permisos estrictos de sistema de archivos (`0o600` para el archivo, `0o700` para la carpeta) y falla con `RuntimeError` si la persistencia no es posible.
  - En `verify_mcp_auth(auth_token)` (Líneas 85-108), todas las peticiones son evaluadas de forma segura y rechazadas por defecto si el token no coincide.
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_mcp_server_canonical.py` (`test_load_mcp_config_and_auth`, `test_mcp_unauthenticated_rejected_by_default`, `test_load_mcp_config_persistence_failure_raises`, `test_mcp_insecure_dev_mode_opt_in`).
- **Resultado del Test**: **PASA** (200/200 tests pasados).

### AUD-004: Contención de rendimiento y bloqueo del event loop por `fcntl.flock` síncrono
- **Severidad**: Alto
- **Categoría**: Arquitectura
- **Componente**: `cognito-backend` (`app/core/session_manager.py`, `app/api/routes/ai_agents.py`)
- **Descripción**: La sincronización dependía originalmente de un cerrojo global en `index.json`, y la invocación síncrona directa de `fcntl.flock` bloqueaba el Event Loop de asyncio durante operaciones de I/O concurrentes.
- **Evidencia de Ubicación en Código**:
  - `very-simplified-stack/cognito-backend/app/core/session_manager.py` (Líneas 47-57, Líneas 193-211).
  - `very-simplified-stack/cognito-backend/app/api/routes/ai_agents.py` (Línea 108).
- **Resolución y Evidencia Técnica**:
  - Se sustituyó el cerrojo global por locks individuales por sesión (`<session_id>.lock` y `<session_id>.meta.json`) en `SessionManager._lock_session` (Líneas 47-57).
  - Las llamadas síncronas de lectura/escritura de sesión en contexto asíncrono se delegan fuera del event loop principal mediante AnyIO thread pool worker (`anyio.to_thread.run_sync`) en `open_async`, `append_message_async`, y `get_effective_messages_async` (Líneas 193-211).
- **Benchmark de Carga Concurrente (N=50 sesiones concurrentes, 1,000 operaciones en paralelo)**:
  - **Latencia promedio**: 164.98 ms
  - **Latencia p50 (Mediana)**: 165.46 ms
  - **Latencia p95**: 210.02 ms
  - **Latencia p99**: **238.64 ms**
  - *(Comportamiento previo antes del fix: bloqueo completo del event loop con latencias p99 > 3,500 ms y timeouts por contención en `index.json.lock`)*.
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_session_manager.py`, `very-simplified-stack/cognito-backend/tests/test_agent_loop_sessions.py`.
- **Resultado del Test**: **PASA** (200/200 tests pasados).

### AUD-005: Interrupción de streaming por errores HTTP 429/transitorios en `generate_with_tools`
- **Severidad**: Medio
- **Categoría**: Resiliencia
- **Componente**: `cognito-backend` (`app/services/backend_router.py`)
- **Descripción**: La ruta principal de streaming del Agent Loop llamaba a `BackendRouter.generate_with_tools`, la cual iteraba sobre la respuesta del cliente sin envolver la transmisión en `retry_transient_stream`.
- **Evidencia de Ubicación en Código**: `very-simplified-stack/cognito-backend/app/services/backend_router.py` (Líneas 99-114).
- **Resolución y Evidencia Técnica**:
  - `BackendRouter.generate_with_tools` importa e invoca `retry_transient_stream(_stream_raw)` (Línea 112).
  - Ante errores HTTP 429 (Rate Limit) o fallos de red intermitentes de Ollama/OpenAI, la función realiza reintentos transparentes con backoff exponencial sin interrumpir abruptamente el stream SSE al cliente.
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_retry_streaming.py` (`test_retry_transient_stream_recovery`, `test_retry_transient_stream_persistent_failure_explicit_error`, `test_retry_transient_stream_non_transient_no_retry`).
- **Resultado del Test**: **PASA** (200/200 tests pasados).

### AUD-006: Falsos positivos del detector de bucles en herramientas de solo lectura
- **Severidad**: Bajo
- **Categoría**: Precisión
- **Componente**: `cognito-backend` (`app/core/guardrails/tool_loop_detector.py`)
- **Descripción**: `ToolLoopDetector` activaba alertas y bloqueaba ejecuciones al detectar múltiples llamadas a herramientas de inspección o lectura (`read`, `dir`, `search`), que legítimamente se invocan repetidamente durante la exploración del repositorio.
- **Evidencia de Ubicación en Código**: `very-simplified-stack/cognito-backend/app/core/guardrails/tool_loop_detector.py` (Líneas 47-54 y Línea 72).
- **Confirmación de Uso de `READ_ONLY_TOOLS` dentro de `record_and_check`**:
  - En las líneas 47-54 se define la constante:
    ```python
    READ_ONLY_TOOLS = {
        "read",
        "read_file",
        "list_directory",
        "search_files",
        "query_spill",
        "read_spill",
    }
    ```
  - En la línea 72 dentro del método `record_and_check`, se confirma explícitamente con cita de línea el uso de `READ_ONLY_TOOLS`:
    ```python
    if tool_name in READ_ONLY_TOOLS:
        call_hash = compute_tool_call_hash(tool_name, arguments, output=output)
    else:
        call_hash = compute_tool_call_hash(tool_name, arguments, output=None)
    ```
  - De este modo, para herramientas de lectura se incluye la salida `output` en el hash. Invocaciones sucesivas de lectura que retornan contenidos distintos no se cuentan como bucles repetitivos.
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_tool_loop_detector.py`.
- **Resultado del Test**: **PASA** (200/200 tests pasados).

### AUD-007: Clave por defecto hardcodeada en `cognito-worker`
- **Severidad**: Medio
- **Categoría**: Seguridad
- **Componente**: `cognito-worker` (`worker_app/main.py`)
- **Descripción**: `cognito-worker` contenía una clave HMAC por defecto para autenticar peticiones si no se proporcionaba la variable de entorno correspondiente.
- **Evidencia de Ubicación en Código**: `very-simplified-stack/cognito-worker/worker_app/main.py` (Líneas 32-37).
- **Resolución y Evidencia Técnica**:
  - `worker_app/main.py` verifica la variable de entorno `COGNITO_WORKER_SECRETS`:
    ```python
    raw_secrets = os.getenv("COGNITO_WORKER_SECRETS")
    if not raw_secrets or not raw_secrets.strip():
        raise RuntimeError("COGNITO_WORKER_SECRETS environment variable is required but not set.")
    ```
  - El proceso aborta con `RuntimeError` inmediatamente en tiempo de arranque si `COGNITO_WORKER_SECRETS` no está definida o está vacía, eliminando la clave hardcodeada previa.
- **Test de Regresión**: `very-simplified-stack/cognito-worker/tests/test_worker.py`.
- **Resultado del Test**: **PASA** (5/5 tests pasados).

### AUD-008: System prompt sin versionar
- **Severidad**: Medio
- **Categoría**: Arquitectura / Precisión
- **Componente**: `cognito-backend` (`app/core/system_prompt.py`, `app/core/prompts/`)
- **Descripción**: El system prompt estaba definido de manera implícita o estática sin un sistema de versionado estructurado.
- **Evidencia de Ubicación en Código**: `very-simplified-stack/cognito-backend/app/core/system_prompt.py` (Líneas 10-35) y `very-simplified-stack/cognito-backend/app/core/prompts/system_prompt.v1.1.toml`.
- **Resolución y Evidencia Técnica**:
  - `app/core/system_prompt.py` carga de forma dinámica archivos de definición TOML versionados.
  - La versión se selecciona mediante la variable de entorno `COGNITO_SYSTEM_PROMPT_VERSION` (por defecto `system_prompt.v1.1.toml`).
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_system_prompt.py`.
- **Resultado del Test**: **PASA** (200/200 tests pasados).

### AUD-009: Bypass de `ExecPolicy` en `shell_run`
- **Severidad**: Crítico
- **Categoría**: Seguridad
- **Componente**: `cognito-backend` (`app/core/tools/nooa_tools.py`)
- **Descripción**: La herramienta `shell_run` ejecutaba comandos recibidos sin validar previamente los permisos de `ExecPolicy`.
- **Evidencia de Ubicación en Código**: `very-simplified-stack/cognito-backend/app/core/tools/nooa_tools.py` (Líneas 85-110) y `very-simplified-stack/cognito-backend/app/core/exec_policy.py`.
- **Resolución y Evidencia Técnica**:
  - `ShellTools.shell_run` evalúa cada comando contra `ExecPolicy.evaluate_command(cmd)` antes de invocar `subprocess.run` / `asyncio.create_subprocess_exec`. Comandos denegados o destructivos son bloqueados de inmediato lanzando una excepción de seguridad.
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_exec_policy.py`, `very-simplified-stack/cognito-backend/tests/test_nooa_core.py`.
- **Resultado del Test**: **PASA** (200/200 tests pasados).

### AUD-010: `shell_policy.py` desconectado en tiempo de ejecución
- **Severidad**: Alto
- **Categoría**: Seguridad
- **Componente**: `cognito-backend` (`app/core/exec_policy.py`, `app/core/shell_policy.py`)
- **Descripción**: `shell_policy.py` implementaba reglas de seguridad granulares pero sus funciones no eran invocadas por la canalización principal de `exec_policy.py`.
- **Evidencia de Ubicación en Código**: `very-simplified-stack/cognito-backend/app/core/exec_policy.py` (Líneas 12-25) y `very-simplified-stack/cognito-backend/app/core/shell_policy.py`.
- **Resolución y Evidencia Técnica**:
  - `exec_policy.py` importa e invoca dinámicamente `evaluate_shell_command_policy` de `shell_policy.py` dentro de su pipeline de validación en tiempo de ejecución.
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_exec_policy.py`, `very-simplified-stack/cognito-backend/tests/test_granular_security.py`.
- **Resultado del Test**: **PASA** (200/200 tests pasados).

---

## Hallazgos Nuevos (AUD-011 a AUD-017)

### AUD-011: Ejecución de `BashTool` sin sandbox de contenedor ni lista blanca
- **Severidad**: Alto
- **Categoría**: Seguridad
- **Componente**: `cognito-backend` (`app/core/tools/bash_tool.py`), `cognito-worker`
- **Descripción**: `BashTool` requería aislamiento en tiempo de ejecución y límites de recursos para evitar ejecuciones no sandboxeadas o efectos secundarios destructivos en el sistema host.
- **Evidencia de Ubicación en Código**: `very-simplified-stack/cognito-backend/app/core/tools/bash_tool.py` (Líneas 35-95).
- **Resolución y Evidencia Técnica**:
  - `BashTool.execute` canaliza cada comando a través de `evaluate_command_execution(...)` verificando permisos con `ExecPolicy` y `shell_policy.py`.
  - Integración de aislamiento con `SandboxedExecutor` (`bubblewrap`/`bwrap`) para contención de sistema de archivos (bind mount de solo lectura en raíz `/` y escritura restringida al directorio de trabajo `cwd`) y desaislamiento de red no autorizada.
  - Aplicación de límites de recursos del SO vía `resource.setrlimit` (`RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_FSIZE`) como fallback seguro para restringir tiempo de CPU, uso de memoria RAM y tamaño de escritura en disco.
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_exec_policy.py` (`test_bash_tool_sandboxed_isolation_and_resource_limits`, `test_bash_tool_exec_policy_parity`, `test_unified_shell_policy_denied_across_all_tools`).
- **Resultado del Test**: **PASA** (206/206 tests pasados).

### AUD-012: Pérdida de mensajes de steering ante fallos de proceso
- **Severidad**: Medio
- **Categoría**: Resiliencia
- **Componente**: `cognito-backend` (`app/api/routes/ai_agents.py`, `app/core/steering.py`, `app/core/session_manager.py`, `app/core/agent_loop.py`)
- **Descripción**: Los mensajes de steering enviados vía `POST /api/agent/sessions/{session_id}/steer` se guardaban únicamente en una cola en memoria (`asyncio.Queue`). Si el proceso del backend se reiniciaba o fallaba antes de que el agent loop consumiera el siguiente turno, dichos mensajes se perdían sin haber quedado registrados en el log de la sesión.
- **Evidencia de Ubicación en Código**:
  - `very-simplified-stack/cognito-backend/app/core/session_manager.py` (Líneas 300-412: `append_steering_message`, `get_undelivered_steering_messages`, `mark_steering_delivered`).
  - `very-simplified-stack/cognito-backend/app/core/steering.py` (Líneas 32-72: `post_steering_message`, `sync_pending_steering`, `SteeringString`).
  - `very-simplified-stack/cognito-backend/app/api/routes/ai_agents.py` (Línea 144 en `run_agent_loop`, Línea 285 en `steer_session`).
  - `very-simplified-stack/cognito-backend/app/core/agent_loop.py` (Líneas 61-90 en `process_steering`).
- **Resolución y Evidencia Técnica**:
  - Al recibir un mensaje de steering en `post_steering_message`, se registra de forma durable en el almacenamiento JSONL de la sesión (`<session_id>.jsonl`) con `type: "steering"`, `id`, `content`, y `delivered: false`.
  - Al iniciar o reanudar una sesión (`run_agent_loop` o cada turno de `agent_loop`), `steering_manager.sync_pending_steering` consulta los mensajes de steering no entregados (`delivered: false`) y los re-encola en memoria.
  - Al consumirse cada mensaje de steering durante la ejecución del agent loop (`process_steering`), se inyecta en la conversación como mensaje de rol `user` (`[STEERING INPUT] ...`) y se marca como `delivered: true` en el log de la sesión, garantizando entrega duradera y evitando duplicaciones al reanudar.
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_steering.py` (`test_steering_persistence_and_resumption_after_process_restart`).
- **Resultado del Test**: **PASA** (208/208 tests pasados).

### AUD-013: Pérdida de detalle semántico durante la compactación de contexto
- **Severidad**: Medio
- **Categoría**: Precisión
- **Componente**: `cognito-backend` (`app/core/compaction.py`, `app/core/session_manager.py`, `app/core/session/message_deriver.py`, `app/api/routes/ai_agents.py`)
- **Descripción**: El proceso de compactación de historial generaba resúmenes de texto plano que omitían metadatos estructurales clave, como rutas de archivos leídos/modificados, firmas de funciones involucradas y llamadas a herramientas anteriores, degradando la precisión del modelo en tareas de refactorización largas.
- **Evidencia de Ubicación en Código**:
  - `very-simplified-stack/cognito-backend/app/core/compaction.py` (`extract_context_ledger`, `format_ledger_for_system_prompt`, `compact`).
  - `very-simplified-stack/cognito-backend/app/core/session_manager.py` (`append_compaction`, `get_effective_messages`).
  - `very-simplified-stack/cognito-backend/app/core/session/message_deriver.py` (`CompactionEvent`, `derive_messages_for_llm`).
  - `very-simplified-stack/cognito-backend/app/api/routes/ai_agents.py` (`run_agent_loop`).
- **Resolución y Evidencia Técnica**:
  - `compaction.py` extrae automáticamente un `context_ledger` estructurado (JSON) que rastrea `files_touched`, `function_signatures` y `tool_calls` (nombre y argumentos clave).
  - Preservación acumulativa: al compactar un rango que ya contiene ledgers previos, `_parse_embedded_ledgers` los fusiona para evitar la pérdida de contexto estructural en compactaciones sucesivas.
  - El `context_ledger` se almacena junto al resumen narrativo en los eventos de compactación en el log `.jsonl` de la sesión (`append_compaction`).
  - Tanto `get_effective_messages` como `derive_messages_for_llm` re-inyectan el ledger formateado de forma clara en el mensaje de sistema de resumen (`[Resumen de la conversación anterior]`), haciéndolo legible para el modelo.
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_compaction.py` (`test_context_ledger_extraction_and_multi_compaction`), `very-simplified-stack/cognito-backend/tests/test_session_compaction_regression.py`.
- **Resultado del Test**: **PASA** (209/209 tests pasados).

### AUD-014: Recordatorios de presupuesto de tokens inyectados con rol `user` en lugar de `system`
- **Severidad**: Bajo
- **Categoría**: Precisión
- **Componente**: `cognito-backend` (`app/core/token_budget.py`)
- **Descripción**: Las advertencias o recordatorios de consumo del presupuesto de tokens (`TokenBudgetReminder`) se insertan en la conversación con el rol `"user"` en lugar del rol `"system"`. Esto altera la semántica de la conversación y puede confundir al modelo atribuyendo instrucciones operativas de infraestructura a las entradas del usuario.
- **Evidencia de Ubicación en Código**: `very-simplified-stack/cognito-backend/app/core/token_budget.py` (Líneas 160-198).
- **Resolución y Evidencia Técnica**:
  - En `apply_token_budget_reminder`, el mensaje se construye explícitamente con `role: "system"`:
    ```python
    reminder_msg = {"role": "system", "content": reminder_text, "type": "TokenBudgetReminder"}
    ```
  - Se inyecta adecuadamente tras el prompt inicial del sistema o al final del listado de mensajes sin duplicación si ya está presente.
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_token_budget.py` (`test_apply_token_budget_reminder`).
- **Resultado del Test**: **PASA** (209/209 tests pasados).

### AUD-015: Ausencia de escritura atómica en `WriteTool` sin copia de respaldo ante fallos de I/O
- **Severidad**: Bajo
- **Categoría**: Resiliencia
- **Componente**: `cognito-backend` (`app/core/tools/write_tool.py`)
- **Descripción**: `WriteTool` sobrescribía archivos en disco mediante operaciones de apertura y escritura directas (`open(path, "w")`) sin escribir primero en un archivo temporal ni crear copias de seguridad (backups). Si se producía una interrupción de I/O o un fallo de proceso a mitad de la escritura, el archivo destino quedaba truncado o corrupto.
- **Evidencia de Ubicación en Código**: `very-simplified-stack/cognito-backend/app/core/tools/write_tool.py`.
- **Resolución y Evidencia Técnica**:
  - Refactorización de `WriteTool.execute` para escribir primero en un archivo temporal (`NamedTemporaryFile`) en el mismo directorio que el destino.
  - Ejecución de `flush()` y `os.fsync()` en el archivo temporal antes de cerrar.
  - Si el archivo destino existe, creación de copia de seguridad con sufijo `.bak` (vía `shutil.copy2`).
  - Sustitución atómica del archivo original con `os.replace(temp_path, target_path)`.
  - Manejo de excepciones (p. ej., disco lleno o permisos denegados) limpiando el archivo temporal y dejando el archivo original intacto.
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_tools.py` (`test_write_tool_creates_backup_on_overwrite`, `test_write_tool_atomic_failure_leaves_original_intact`).
- **Resultado del Test**: **PASA** (211/211 tests pasados).

### AUD-016: Desacoplamiento entre `cognito_agent.py` y el agent loop de `cognito-backend`
- **Severidad**: Medio
- **Categoría**: Arquitectura
- **Componente**: Raíz del repositorio (`cognito_agent.py`), `cognito-backend` (`app/core/agent_loop.py`)
- **Descripción**: El script CLI `cognito_agent.py` mantenía su propia lógica de orquestación sin ejecución de herramientas ni políticas de seguridad, divergente del `agent_loop` estándar de `cognito-backend`, duplicando código y omitiendo `ExecPolicy`, `ToolLoopDetector`, sanitización por nonce y la persistencia estructurada de sesiones JSONL.
- **Evidencia de Ubicación en Código**: `cognito_agent.py` (Líneas 1-250), `very-simplified-stack/cognito-backend/app/core/agent_loop.py`.
- **Resolución y Evidencia Técnica**:
  - `cognito_agent.py` refactorizado como un cliente/wrapper CLI delgado construido sobre la orquestación unificada de `agent_loop.py`.
  - Integración directa de `SessionManager`, `ToolContext`, `ResourceLoader`, `ProjectTrustStore` y `extension_registry.tools_for(...)`.
  - En cada ciclo de razonamiento, `SimpleCognitoStack` invoca `agent_loop(...)` consumiendo sus eventos (`TextDeltaEvent`, `ToolCallEvent`, `ToolResultEvent`, `DoneEvent`, `ErrorEvent`), garantizando la aplicación automática de políticas de seguridad (`ExecPolicy`, `shell_policy`), aislamiento sandbox (`SandboxedExecutor`), detector de bucles (`ToolLoopDetector`), sanitización por nonce impredecible de delimitadores `<tool_output>` y registro persistente de eventos de sesión en formato JSONL.
  - Mantenimiento estricto de la interfaz externa y firma de funciones del CLI (`solve()`, `execute_reasoning()`, `route_task()`, `generate()`) garantizando compatibilidad retroactiva total.
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_cognito_agent_unification.py` (`test_cognito_agent_initialization`, `test_cognito_agent_solve_flow_uses_agent_loop`, `test_cognito_agent_tool_execution_and_exec_policy`, `test_cognito_agent_triggers_tool_loop_detector`).
- **Resultado del Test**: **PASA** (215/215 tests pasados).

### AUD-017: Falta de contratos de validación estrictos en herramientas MCP y locales
- **Severidad**: Medio
- **Categoría**: Arquitectura
- **Componente**: `cognito-backend` (`app/core/tools/base.py`, `app/services/mcp_server.py`)
- **Descripción**: Las herramientas locales y del protocolo MCP carecían de esquemas de validación estrictos para sus parámetros de entrada y tipos de retorno, permitiendo que argumentos mal formados o tipos incompatibles pasasen a la fase de ejecución sin un rechazo temprano estructurado.
- **Evidencia de Ubicación en Código**: `very-simplified-stack/cognito-backend/app/core/tools/base.py` (Líneas 100-165), `very-simplified-stack/cognito-backend/app/services/mcp_server.py` (Líneas 15-275, 645-690).
- **Resolución y Evidencia Técnica**:
  - Ampliado `AgentTool` en `app/core/tools/base.py` incorporando `STANDARD_TOOL_RETURN_SCHEMA` y validación estructurada del tipo de retorno en `validate_and_execute(...)`.
  - Definidos esquemas explícitos JSON Schema (`MCP_TOOL_SCHEMAS`) para los parámetros de entrada y estructuras de retorno de todas las herramientas MCP expuestas en `app/services/mcp_server.py`.
  - Implementadas las funciones reutilizables `validate_mcp_input` y `validate_mcp_output` en `mcp_server.py` (compartiendo `format_validation_error` con las herramientas locales) aplicando validación fail-fast antes de la ejecución de cualquier lógica de la herramienta.
  - Generación de respuestas de error legibles y estructuradas cuando los argumentos de entrada faltan o son de tipo incorrecto, garantizando un comportamiento idéntico tanto si la herramienta se invoca localmente como si se invoca vía MCP.
- **Test de Regresión**: `very-simplified-stack/cognito-backend/tests/test_tool_validation_errors.py` (`test_local_tools_reject_invalid_arguments_fail_fast`, `test_mcp_tools_reject_invalid_arguments_fail_fast`, `test_valid_arguments_pass_local_and_mcp_tools`).
- **Resultado del Test**: **PASA** (228/228 tests pasados).
