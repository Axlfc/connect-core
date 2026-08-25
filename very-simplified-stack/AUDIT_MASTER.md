# Documento Maestro de Auditoría Cognito (`AUDIT_MASTER.md`)

Este documento constituye el registro persistente, unificado y reconciliado de todos los hallazgos de auditoría de seguridad, arquitectura, precisión y resiliencia en los componentes `cognito-backend` y `cognito-worker`.

Cualquier auditoría futura debe contrastarse e integrarse en este documento utilizando la numeración consecutiva `AUD-XXX`.

---

## Resumen de Estado de Hallazgos

| ID | Severidad | Categoría | Componente | Descripción Resumida | Estado |
|---|---|---|---|---|---|
| **AUD-001** | Crítico | Seguridad | `cognito-backend` | Delimitador `<tool_output>` falsificable por contenido inyectado | **Corregido** (Fix de aislamiento dinámico con UUID/nonce por turno) |
| **AUD-002** | Alto | Precisión/Arquitectura | `cognito-backend` | Pérdida de mensajes intermedios e inyección de system prompt en compactación | **Corregido** |
| **AUD-003** | Alto | Seguridad | `cognito-backend` | Modo `COGNITO_MCP_INSECURE_DEV` desactivaba auth globalmente | **Corregido** |
| **AUD-004** | Alto | Arquitectura | `cognito-backend` | Contención de rendimiento y bloqueo del event loop de FastAPI por `fcntl.flock` síncrono | **Corregido** (Locks por sesión + Ejecución off-thread en AnyIO) |
| **AUD-005** | Medio | Resiliencia | `cognito-backend` | Interrupción de streaming por errores HTTP 429/transitorios en `generate_with_tools` | **Corregido** (Integrado `retry_transient_stream` en `BackendRouter`) |
| **AUD-006** | Bajo | Precisión | `cognito-backend` | Falsos positivos del detector de bucles en herramientas de solo lectura | **Corregido** |
| **AUD-007** | Medio | Seguridad | `cognito-worker` | Clave por defecto hardcodeada en `cognito-worker` | **Corregido** |
| **AUD-008** | Medio | Arquitectura/Precisión | `cognito-backend` | System prompt sin versionar | **Corregido** |
| **AUD-009** | Crítico | Seguridad | `cognito-backend` | Bypass de `ExecPolicy` en `shell_run` | **Corregido** |
| **AUD-010** | Alto | Seguridad | `cognito-backend` | `shell_policy.py` desconectado en tiempo de ejecución | **Corregido** |
| **AUD-011** | Alto | Seguridad | `cognito-worker` / `cognito-backend` | Ejecución de `BashTool` sin sandbox de contenedor ni lista blanca | **Pendiente (Documentado)** |
| **AUD-012** | Medio | Resiliencia | `cognito-backend` | Pérdida de mensajes de steering por almacenarse únicamente en cola en memoria | **Pendiente (Documentado)** |
| **AUD-013** | Medio | Precisión | `cognito-backend` | Pérdida de detalle semántico (rutas de archivo, firmas) durante compactación | **Pendiente (Documentado)** |
| **AUD-014** | Bajo | Precisión | `cognito-backend` | Recordatorios de presupuesto de tokens inyectados con rol `user` en vez de `system` | **Pendiente (Documentado)** |
| **AUD-015** | Bajo | Resiliencia | `cognito-backend` | Ausencia de escritura atómica en `WriteTool`, sin backup ante fallo de I/O | **Pendiente (Documentado)** |
| **AUD-016** | Medio | Arquitectura | `cognito-backend` | Desacoplamiento entre `cognito_agent.py` y el agent loop de `cognito-backend` | **Pendiente (Documentado)** |
| **AUD-017** | Medio | Arquitectura | `cognito-backend` | Falta de contratos de validación estrictos en herramientas MCP/locales | **Pendiente (Documentado)** |

---

## Hallazgos Reconciliados (AUD-001 a AUD-010)

### AUD-001: Delimitador `<tool_output>` falsificable por contenido de herramientas
- **Severidad**: Crítico
- **Categoría**: Seguridad
- **Componente**: `cognito-backend` (`app/core/agent_loop.py`)
- **Descripción**: El formato de retorno de herramientas utilizaba la etiqueta fija `<tool_output source="...">`. Un intento de inyección indirecta dentro de un archivo de texto o salida de comando que contuviera la secuencia literal `</tool_output>` podía cerrar el bloque prematuramente e inyectar instrucciones directas con rol de sistema o usuario. La función previa `sanitize_tool_output()` basada en expresiones regulares sólo filtraba nombres de etiquetas exactos y en minúsculas, resultando inherentemente incompleta contra variaciones de etiquetas XML u otros atributos.
- **Resolución**: Se sustituye el delimitador estático adivinable por un token único impredecible por turno (UUID/nonce por ejecución de turno), p. ej. `<tool_output_{nonce} source="...">...</tool_output_{nonce}>`. De este modo, cualquier etiqueta `</tool_output>` inyectada en el contenido de la herramienta no coincide con el token del turno y es tratada como datos planos no confiables.

### AUD-002: Pérdida de mensajes intermedios y falta de system prompt en compactación
- **Severidad**: Alto
- **Categoría**: Precisión / Arquitectura
- **Componente**: `cognito-backend` (`app/core/session_manager.py`, `app/core/session/message_deriver.py`)
- **Descripción**: Al resumir o compactar el historial de una sesión (`compact()`), las versiones iniciales descartaban mensajes intercalados y omitían la reinyección en caliente del System Prompt actualizado en la cabecera del contexto derivado para la siguiente llamada del LLM.
- **Resolución**: Verificado contra el código actual. `SessionManager.get_effective_messages` y `derive_messages_for_llm` preservan la estructura del log de eventos, calculan las líneas cubiertas por el resumen de compactación e inyectan dinámicamente el System Prompt (`build_system_message`) en la posición inicial.

### AUD-003: Modo `COGNITO_MCP_INSECURE_DEV` desactivaba auth globalmente
- **Severidad**: Alto
- **Categoría**: Seguridad
- **Componente**: `cognito-backend` (`app/services/mcp_server.py`)
- **Descripción**: La variable de entorno `COGNITO_MCP_INSECURE_DEV` omitía por completo la comprobación de claves/tokens de autorización para todos los clientes MCP, exponiendo endpoints sensibles sin autenticación.
- **Resolución**: Verificado contra el código actual. `COGNITO_MCP_INSECURE_DEV` únicamente emite advertencias de log en entorno de desarrollo, pero el servidor valida estrictamente los tokens HMAC y las credenciales efímeras configuradas.

### AUD-004: Contención de rendimiento y bloqueo del event loop por `fcntl.flock` síncrono
- **Severidad**: Alto
- **Categoría**: Arquitectura
- **Componente**: `cognito-backend` (`app/core/session_manager.py`)
- **Descripción**: La sincronización del índice y de los archivos de sesión dependía originalmente de un lock global en `index.json`. Además, el uso síncrono de `fcntl.flock` directamente dentro de funciones asíncronas de FastAPI/SessionManager bloqueaba por completo el Event Loop de asyncio durante el tiempo que la operación de I/O retenía el cerrojo.
- **Resolución**: Se aplicó una arquitectura de metadatos segmentados por sesión (`<session_id>.meta.json`) eliminando el bloqueo global sobre `index.json`. Adicionalmente, se envuelven las operaciones de archivo con bloqueo síncrono en ejecutores asíncronos en hilos (`anyio.to_thread.run_sync` / thread pool), previniendo cualquier bloqueo del event loop principal del servidor.

### AUD-005: Interrupción de streaming por errores HTTP 429/transitorios en `generate_with_tools`
- **Severidad**: Medio
- **Categoría**: Resiliencia
- **Componente**: `cognito-backend` (`app/services/backend_router.py`, `app/api/routes/ai_agents.py`)
- **Descripción**: Aunque `BackendClient.generate_stream` contaba con `retry_transient_stream`, la ruta principal del Agent Loop (`/agent/loop` consumida por `ai_agents.py`) llamaba a `BackendRouter.generate_with_tools`, la cual iteraba directamente sobre la respuesta del cliente sin la protección de `retry_transient_stream`. Como resultado, un error HTTP 429 (Rate Limit) o de red intermitente de Ollama/OpenAI interrumpía el stream SSE de forma abrupta.
- **Resolución**: Se integra `retry_transient_stream` en `BackendRouter.generate_with_tools` garantizando la re-intento transparente y el backoff exponencial ante errores transitorios durante el streaming de herramientas.

### AUD-006: Falsos positivos del detector de bucles en herramientas de solo lectura
- **Severidad**: Bajo
- **Categoría**: Precisión
- **Componente**: `cognito-backend` (`app/core/guardrails/tool_loop_detector.py`)
- **Descripción**: `ToolLoopDetector` activaba alertas y bloqueaba ejecuciones al detectar múltiples llamadas a herramientas de inspección o lectura (p. ej., `read`, `dir`, `search`), que legítimamente se invocan repetidamente durante la exploración del repositorio.
- **Resolución**: Verificado contra el código actual. El detector de bucles excluye herramientas de solo lectura y únicamente supervisa herramientas con efectos secundarios (mutadoras) o secuencias idénticas continuas con exactamente los mismos argumentos de entrada.

### AUD-007: Clave por defecto hardcodeada en `cognito-worker`
- **Severidad**: Medio
- **Categoría**: Seguridad
- **Componente**: `cognito-worker` (`worker_app/main.py`)
- **Descripción**: `cognito-worker` contenía una clave HMAC por defecto para autenticar peticiones si no se proporcionaba la variable de entorno correspondiente.
- **Resolución**: Verificado contra el código actual. `worker_app/main.py` requiere obligatoriamente `COGNITO_WORKER_SECRETS` y falla de inmediato en el arranque si no está configurado.

### AUD-008: System prompt sin versionar
- **Severidad**: Medio
- **Categoría**: Arquitectura / Precisión
- **Componente**: `cognito-backend` (`app/core/system_prompt.py`, `app/core/prompts/`)
- **Descripción**: El system prompt estaba definido de manera implícita o estática sin un sistema de versionado estructurado que permitiese evaluar y retrotraer cambios.
- **Resolución**: Verificado contra el código actual. Se cuenta con soporte para archivos de definición TOML versionados (p. ej., `system_prompt.v1.1.toml`), selector de versión por variable de entorno `COGNITO_SYSTEM_PROMPT_VERSION` y suite de evals en `evals/system_prompt/`.

### AUD-009: Bypass de `ExecPolicy` en `shell_run`
- **Severidad**: Crítico
- **Categoría**: Seguridad
- **Componente**: `cognito-backend` (`app/core/tools/nooa_tools.py`)
- **Descripción**: La herramienta `shell_run` ejecutaba comandos recibidos sin validar previamente los permisos de `ExecPolicy`, permitiendo la ejecución no autorizada de comandos destructivos.
- **Resolución**: Verificado contra el código actual. `ShellTools` (`shell_run`) valida todos los comandos mediante `exec_policy.py` antes de cualquier ejecución.

### AUD-010: `shell_policy.py` desconectado en tiempo de ejecución
- **Severidad**: Alto
- **Categoría**: Seguridad
- **Componente**: `cognito-backend` (`app/core/exec_policy.py`, `app/core/shell_policy.py`)
- **Descripción**: `shell_policy.py` implementaba reglas de seguridad granulares pero sus funciones no eran invocadas por la canalización principal de `exec_policy.py`.
- **Resolución**: Verificado contra el código actual. `exec_policy.py` importa e invoca dinámicamente `evaluate_shell_command_policy` de `shell_policy.py`.

---

## Hallazgos Nuevos (AUD-011 a AUD-017)

### AUD-011: Ejecución de `BashTool` sin sandbox de contenedor ni lista blanca
- **Severidad**: Alto
- **Categoría**: Seguridad
- **Componente**: `cognito-backend` (`app/core/tools/bash_tool.py`), `cognito-worker`
- **Descripción**: `BashTool` ejecuta comandos directamente en el sistema operativo del host sin aislamiento mediante contenedores (Docker/Landlock) ni una lista blanca de comandos estrictamente permitidos, exponiendo el entorno host a ejecuciones arbitrarias no sandboxeadas.
- **Estado**: Pendiente (Documentado sin fix todavía).

### AUD-012: Pérdida de mensajes de steering ante fallos de proceso
- **Severidad**: Medio
- **Categoría**: Resiliencia
- **Componente**: `cognito-backend` (`app/api/routes/ai_agents.py`, `app/core/steering.py`)
- **Descripción**: Los mensajes de direccionamiento e interacción en tiempo real enviados vía `/api/agent/sessions/{session_id}/steer` se almacenan en colas en memoria (`asyncio.Queue`). Si el proceso del backend se reinicia o sufre un fallo repentino antes del siguiente turno del bucle, dichos mensajes se pierden de forma irrecuperable sin haber sido persistidos en el log de la sesión.
- **Estado**: Pendiente (Documentado sin fix todavía).

### AUD-013: Pérdida de detalle semántico durante la compactación de contexto
- **Severidad**: Medio
- **Categoría**: Precisión
- **Componente**: `cognito-backend` (`app/core/compaction.py`)
- **Descripción**: El proceso de compactación de historial genera resúmenes de texto plano que omiten metadatos estructurales clave, como rutas de archivos leídos/modificados, firmas de funciones involucradas y llamadas a herramientas anteriores (más allá de la pérdida de mensajes intermedios ya corregida en AUD-002), degradando la precisión del modelo en tareas de refactorización largas.
- **Estado**: Pendiente (Documentado sin fix todavía).

### AUD-014: Recordatorios de presupuesto de tokens inyectados con rol `user` en lugar de `system`
- **Severidad**: Bajo
- **Categoría**: Precisión
- **Componente**: `cognito-backend` (`app/core/token_budget.py`)
- **Descripción**: Las advertencias o recordatorios de consumo del presupuesto de tokens (`TokenBudgetReminder`) se insertan en la conversación con el rol `"user"` en lugar del rol `"system"`. Esto altera la semántica de la conversación y puede confundir al modelo atribuyendo instrucciones operativas de infraestructura a las entradas del usuario.
- **Estado**: Pendiente (Documentado sin fix todavía).

### AUD-015: Ausencia de escritura atómica en `WriteTool` sin copia de respaldo ante fallos de I/O
- **Severidad**: Bajo
- **Categoría**: Resiliencia
- **Componente**: `cognito-backend` (`app/core/tools/write_tool.py`)
- **Descripción**: `WriteTool` sobrescribe archivos en disco mediante operaciones de apertura y escritura directas (`open(path, "w")`) sin escribir primero en un archivo temporal ni crear copias de seguridad (backups). Si se produce una interrupción de I/O o un fallo de proceso a mitad de la escritura, el archivo destino queda truncado o corrupto.
- **Estado**: Pendiente (Documentado sin fix todavía).

### AUD-016: Desacoplamiento entre `cognito_agent.py` y el agent loop de `cognito-backend`
- **Severidad**: Medio
- **Categoría**: Arquitectura
- **Componente**: Raíz del repositorio (`cognito_agent.py`), `cognito-backend` (`app/core/agent_loop.py`)
- **Descripción**: El script CLI `cognito_agent.py` mantiene su propia lógica y flujo de orquestación divergente respecto al bucle estándar `agent_loop` de `cognito-backend`, generando duplicación de código y comportamientos inconsistentes en el manejo de herramientas y sesiones.
- **Estado**: Pendiente (Solo documentar).

### AUD-017: Falta de contratos de validación estrictos en herramientas MCP y locales
- **Severidad**: Medio
- **Categoría**: Arquitectura
- **Componente**: `cognito-backend` (`app/core/tools/`), `app/services/mcp_server.py`
- **Descripción**: Las herramientas locales y del protocolo MCP carecen de esquemas de validación estrictos para sus parámetros de entrada y tipos de retorno, permitiendo que argumentos mal formados o tipos incompatibles pasen a la fase de ejecución sin un rechazo temprano estructurado.
- **Estado**: Pendiente (Solo documentar).
