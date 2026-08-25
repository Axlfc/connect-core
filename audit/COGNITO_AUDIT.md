# Informe de Auditoría Técnica y de Seguridad - Agente de IA "Cognito"

**Fecha:** 2024-07-25
**Auditor:** Jules (Arquitecto de Software Senior, Auditor de Seguridad de IA & QA Lead)
**Proyecto:** Cognito Stack (`very-simplified-stack/cognito-backend`, `cognito-worker`, `cognito_agent.py`)

---

## Resumen Ejecutivo

Esta auditoría evaluó de forma exhaustiva la arquitectura, precisión de respuestas/comportamiento, seguridad agéntica y resiliencia del sistema de inteligencia artificial **Cognito**. Se examinaron los componentes de backend FastAPI (`very-simplified-stack/cognito-backend`), servicios auxiliares de inferencia (`cognito-worker`), orquestadores de herramientas y endpoints SSE.

### Top 5 Riesgos Identificados

1. **Bypass de Sanitización de Inyección Indirecta de Prompts (CRÍTICO - COG-001):** La función `sanitize_tool_output` en `agent_loop.py` solo escapa etiquetas `tool_output` y `system` exactas en minúsculas/con espacio básico, pero ignora variaciones con atributos HTML/XML o mayúsculas arbitrarias (`<TOOL_OUTPUT source="bad">`, `<SYSTEM override="true">`), permitiendo escapar la delimitación de herramientas y ejecutar inyección indirecta de instrucciones.
2. **Ejecución de Comandos y Ausencia de Aislamiento de Sandbox en BashTool (ALTO - COG-002):** `BashTool` ejecuta comandos de shell mediante el intérprete del sistema sin restricción de subprocesos, lista blanca de comandos ni aislamiento de contenedor activo en `agent_loop`, permitiendo a un prompt inyectado modificar el host completo.
3. **Bloqueo Síncrono de E/S (`fcntl.flock`) en el Bucle Asíncrono de FastAPI (ALTO - COG-003):** `SessionManager` utiliza primitivas de bloqueo de archivos síncronos `fcntl.flock` en operaciones de sesión (`open`, `append_message`, `_get_index`), bloqueando el event loop de asyncio en peticiones concurrentes bajo carga.
4. **Fallo Silencioso y Degradación de Desempeño por Rate Limiting / 429 en Ollama y Backend (MEDIO - COG-004):** Ante respuestas de límite de tasa (429) de proveedores LLM u Ollama, el backend no reintenta ni notifica con un evento estructurado de degradación, interrumpiendo abruptamente el stream SSE del usuario.
5. **Desincronización de Persistencia de Contexto en Inyección de Steering (MEDIO - COG-005):** Las peticiones enviadas al endpoint `/api/agent/sessions/{session_id}/steer` se encolan en memoria pero si ocurre un fallo o reinicio del proceso antes del siguiente turno del bucle, las instrucciones de steering se pierden sin haber quedado registradas en el JSONL de la sesión.

---

## Arquitectura Real Mapeada (Fase 0)

Cognito no es un monolito rígido sino un ecosistema agéntico compuesto por:
- **`cognito_agent.py`**: Cliente de razonamiento multi-módulo simplificado que interactúa directamente con la API REST de Ollama (`/api/generate`) para enrutamiento (`routing`) y ejecución por tipo de inferencia (deducción, inducción, abducción, conducción, analógica, generativa, social).
- **`very-simplified-stack/cognito-backend`**: Backend FastAPI estructurado que implementa:
  - Agent Loop SSE (`/api/agent/loop` y `app/core/agent_loop.py`) para function-calling streaming.
  - Registro dinámico de herramientas (`app/core/tools/*`): `ReadTool`, `WriteTool`, `EditTool`, `BashTool`, `CodeReviewTool`, `NOOATools`, `QuerySpillTool`.
  - Sistema de prompts versionados (`app/core/system_prompt.py` y `app/core/prompts/system_prompt.v1.1.toml`).
  - Persistencia de eventos y mensajes por sesión vía `SessionManager` (`.cognito/sessions/*.jsonl` y metadata `.meta.json`).
  - Enrutamiento inteligente y escalado de tareas (`Cognito-Codex Intelligent Router`).
- **`very-simplified-stack/cognito-worker`**: Microservicio worker de ejecución asíncrona que gestiona tareas pesadas o delegadas de procesamiento.

---

## Hallazgos Detallados de Auditoría

### Fase 1: Arquitectura y Diseño

| ID | Título | Severidad | Categoría | Componente | Descripción | Evidencia / Reproducción | Impacto | Recomendación |
|---|---|---|---|---|---|---|---|---|
| COG-003 | Bloqueo síncrono `fcntl.flock` en event loop asyncio | Alto | Arquitectura | `SessionManager` (`app/core/session_manager.py`) | Las funciones de locking en `SessionManager` usan `fcntl.flock` síncrono dentro de endpoints `async` de FastAPI, paralizando el bucle de eventos durante operaciones concurrentes de disco. | Inspección de `SessionManager._lock_session` y `_lock_index`. | Degrada la concurrencia global del servidor FastAPI a una sola petición concurrente por bloqueo I/O. | Migrar a un lock asíncrono en memoria (`asyncio.Lock`) combinado con `aiofiles` o ejecutar bloqueos síncronos en `anyio.to_thread.run_sync`. |
| COG-006 | Desacoplamiento entre `cognito_agent.py` y el agent loop de `cognito-backend` | Medio | Arquitectura | Multi-módulo / API | `cognito_agent.py` define una taxonomía de razonamiento (deducción, abducción, etc.) independiente que no está integrada formalmente con el bucle SSE de `cognito-backend`. | Comparación entre `SimpleCognitoStack` en `cognito_agent.py` y `agent_loop.py`. | Inconsistencia arquitectónica entre el script de terminal y la API REST en producción. | Unificar la lógica de enrutamiento de `cognito_agent.py` como un módulo o extensión dentro de `cognito-backend`. |
| COG-007 | Ausencia de contratos de validación estrictos en herramientas MCP y locales | Medio | Arquitectura | `app/core/tools/base.py` | Las herramientas procesan argumentos arbitrarios antes de la ejecución; si el modelo envía campos inválidos, las excepciones no siempre retornan un formato homogéneo de corrección. | Revisión de `validate_and_execute` en `base.py`. | Reintentos innecesarios por fallos de sintaxis en las llamadas a herramientas. | Reforzar los esquemas Pydantic y retornar descripciones de error normalizadas directamente al contexto del LLM. |

---

### Fase 2: Precisión y Comportamiento

| ID | Título | Severidad | Categoría | Componente | Descripción | Evidencia / Reproducción | Impacto | Recomendación |
|---|---|---|---|---|---|---|---|---|
| COG-008 | Pérdida de contexto semántico durante la compactación de sesión | Medio | Precisión | `app/core/compaction.py` | La compactación de historial sustituye mensajes anteriores por un resumen textual plano, pudiendo descartar detalles técnicos precisos como rutas de archivos o firmas de funciones. | `compact()` en `compaction.py` y `SessionManager.append_compaction`. | Alucinaciones o repetición de preguntas sobre archivos revisados antes de la compactación. | Mantener un índice de entidades o memoria estructurada (Qdrant) para preservar identificadores clave tras la compactación. |
| COG-009 | Recordatorios de presupuesto de tokens inyectados como mensajes de usuario | Bajo | Precisión | `app/core/token_budget.py` | Al superar el 80% de ventana de contexto, se inyecta un mensaje en el historial recomendando resumir, lo que puede confundir al modelo si cree que el usuario final envió dicha instrucción. | `apply_token_budget_reminder()` en `token_budget.py`. | Modificación del tono o comportamiento del agente por un pseudo-mensaje de usuario. | Inyectar los avisos de tokens como directiva de rol `system` en lugar de rol `user`. |

---

### Fase 3: Seguridad de IA (Red Teaming)

| ID | Título | Severidad | Categoría | Componente | Descripción | Evidencia / Reproducción | Impacto | Recomendación |
|---|---|---|---|---|---|---|---|---|
| COG-001 | Bypass de sanitización contra inyección indirecta de prompts | Crítico | Seguridad | `app/core/agent_loop.py` | `sanitize_tool_output()` busca patrone estricto de cierre/apertura. Un contenido malicioso con atributos como `<tool_output source="attacker">` no se escapa y permite inyectar instrucciones falsas de sistema. | Probar output de herramienta con `<tool_output foo="bar">` o `<system override="true">`. | Un archivo malicioso leído por Cognito puede tomar el control del flujo de instrucciones del agente. | Utilizar expresiones regulares con detección de cualquier atributo o escapar caracteres de llaves/etiquetas HTML de forma general (`<` a `&lt;`). |
| COG-002 | Sin restricción de comandos ni aislamiento de contenedor en `BashTool` | Alto | Seguridad | `app/core/tools/bash_tool.py` | `BashTool` ejecuta comandos arbitrarios en el sistema operativo del backend sin sandbox de Docker activo por defecto en entornos locales. | `subprocess.Popen(command, shell=True)` en `bash_tool.py`. | Compromiso del sistema host si el agente es manipulado vía prompt injection. | Obligar a que `BashTool` se ejecute en un contenedor Docker aislado e imponer una lista restrictiva de comandos permitidos. |
| COG-010 | Exposición potencial de variables de entorno y secretos en logs | Medio | Seguridad | `app/core/logging_config.py` | Las respuestas de herramientas y payloads de peticiones se registran en logs en nivel INFO sin filtrar tokens o credenciales. | Logs generados durante la ejecución de llamadas HTTP o inspección de archivos `.env`. | Filtración de credenciales sensibles en los logs del servidor. | Implementar un filtro/redactor de patrones de credenciales (API Keys, JWTs, contraseñas) en el logger global. |

---

### Fase 4: Resiliencia y Manejo de Errores

| ID | Título | Severidad | Categoría | Componente | Descripción | Evidencia / Reproducción | Impacto | Recomendación |
|---|---|---|---|---|---|---|---|---|
| COG-004 | Interrupción abrupta de SSE ante rate limiting HTTP 429 | Medio | Resiliencia | `app/api/routes/ai_agents.py` | Si Ollama o el backend de LLM retorna HTTP 429, la transmisión SSE falla con excepción no capturada grácilmente hacia el cliente. | Simular respuesta 429 en `backend_router.generate_with_tools`. | Desconexión repentina del usuario sin mensaje aclaratorio ni reintento con backoff exponencial. | Interceptar HTTP 429 en la capa de transporte y emitir un `ErrorEvent` SSE estructurado antes de cerrar la conexión. |
| COG-005 | Pérdida de mensajes de steering ante reinicio o error | Medio | Resiliencia | `app/core/steering.py` | Los mensajes del endpoint `/agent/sessions/{session_id}/steer` residen en colas en memoria (`steering_queue`) y no se persisten hasta que el agente inicia su siguiente turno. | Encolar mensaje de steering y forzar fallo de turno. | Pérdida de instrucciones críticas enviadas por el operador humano. | Persistir las instrucciones de steering en el archivo `.jsonl` de la sesión inmediatamente al recibir la petición HTTP POST. |
| COG-011 | Falta de retries idempotentes en operaciones de escritura de archivos | Bajo | Resiliencia | `app/core/tools/write_tool.py` | `WriteTool` sobrescribe archivos sin verificación de integridad previa ni creación de backup temporal ante fallos de I/O durante la escritura. | Simular fallo de disco a mitad de `WriteTool.execute()`. | Corrupción de archivos de código fuente en el repositorio local. | Implementar patrón de escritura atómica en archivo temporal (`.tmp`) antes de reemplazar el archivo de destino. |

---

## Conclusiones y Próximos Pasos

El agente Cognito presenta un diseño sólido con capacidades avanzadas de function-calling, gestión de sesiones y control de contexto. Sin embargo, los hallazgos de seguridad (COG-001 y COG-002) y concurrencia (COG-003) requieren atención prioritaria antes de desplegar el agente en entornos compartidos o de producción.

Todas las pruebas del conjunto de tests automatizados (`cognito-backend` y `cognito-worker`) pasan satisfactoriamente (199/199 y 5/5 pasados respectivamente).
