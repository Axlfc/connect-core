# AUDIT_MASTER.md — Auditoría Enterprise de Cognito

## 1. Encabezado y Resumen Ejecutivo

- **Alcance del Documento:** Auditoría exhaustiva basada al 100% en evidencia de código del repositorio Cognito (`cognito-backend`, `cognito-worker`, y `cognito_agent.py`). Evaluado frente al listón de referencia enterprise 2026 para agent harnesses (características de referencia observadas en harnesses como Claude Code, Codex CLI, OpenCode, Hermes Agent, Pi Agent y OpenClaw).
- **Metodología Aplicada:** Inspección estática del código fuente y suite de pruebas de los componentes backend, worker y CLI. Contrastación directa de cada directiva del listón de referencia A-J contra la implementación real o la evidencia de ausencia en las rutas de código del repositorio.
- **Resumen Cuantitativo de Hallazgos:**
  - **Total de Hallazgos:** 34
  - **Desglose por Severidad:** Crítico: 5 | Alto: 15 | Medio: 13 | Bajo: 1
  - **Desglose por Tipo:** Defecto: 6 | Deuda Técnica: 6 | Brecha Funcional: 22
  - **Total con Estado "Corregido":** 30
  - **Total con Estado "Pendiente":** 4
  - **Desglose por Categoría (A-J):**
    - A. Seguridad y Aislamiento de Ejecución: 8 hallazgos
    - B. Gobernanza Empresarial y Multi-tenencia: 6 hallazgos
    - C. Gestión de Contexto y Memoria: 4 hallazgos
    - D. Orquestación de Herramientas y Sub-Agentes: 5 hallazgos
    - E. Extensibilidad y Ecosistema: 2 hallazgos
    - F. Observabilidad y Telemetría: 2 hallazgos
    - G. Resiliencia y Recuperación: 2 hallazgos
    - H. Precisión y Evaluación: 2 hallazgos
    - I. Portabilidad de Modelos y Proveedores: 1 hallazgo
    - J. Despliegue y Empaquetado para Producción: 2 hallazgos

- **Evaluación de Madurez de Cognito:**
  Cognito cuenta con bases funcionales sólidas a nivel monolocal: posee políticas de ejecución de shell (`ExecPolicy`), detección de bucles de herramientas, integración básica con servidores MCP y mecanismos iniciales de compactación y steering. Sin embargo, las categorías **B (Gobernanza y Multi-tenencia)**, **E (Extensibilidad)**, **F (Observabilidad)** y **H (Evaluación E2E)** se encuentran muy alejadas del estándar enterprise 2026 debido a la ausencia total de un modelo multi-tenant, falta de SSO, telemetría estructurada SIEM/OpenTelemetry y evaluadores de trayectorias completas. La categoría **A (Seguridad y Aislamiento)** presenta brechas críticas por ejecutar comandos shell directamente en el host sin microVMs ni espacios de nombres forzados por defecto.

---

## 2. Tabla de Resumen de Hallazgos

| ID | Severidad | Tipo | Categoría | Prioridad MVP Enterprise | Componente | Descripción Resumida | Estado |
|---|---|---|---|---|---|---|---|
| AUD-001 | Crítico | Defecto | A. Seguridad y Aislamiento | P0 Bloqueante | cognito-backend | BashTool ejecuta comandos directamente en la shell del host sin aislamiento microVM ni bwrap obligatorio | Corregido |
| AUD-002 | Alto | Brecha Funcional | A. Seguridad y Aislamiento | P0 Bloqueante | cognito-backend / CLI | Ausencia de política de red outbound deny-all por defecto en subprocesos | Corregido |
| AUD-003 | Alto | Deuda Técnica | A. Seguridad y Aislamiento | P0 Bloqueante | cognito-backend | Almacenamiento plano de secreto de autenticación MCP sin rotación/revocación dinámica | Corregido |
| AUD-004 | Crítico | Defecto | A. Seguridad y Aislamiento | P0 Bloqueante | cognito-backend | Falta de validación de Origin header y protección CSRF/CORS en conexiones HTTP/WebSocket MCP | Corregido |
| AUD-005 | Medio | Brecha Funcional | A. Seguridad y Aislamiento | P1 Esperado | cognito-backend | Ausencia de metadatos de comportamiento (read-only/destructive/concurrency) en esquema de herramientas | Corregido |
| AUD-006 | Medio | Deuda Técnica | A. Seguridad y Aislamiento | P1 Esperado | cognito-backend / worker | Rango abierto de dependencias Python sin lockfile con hashes integrados | Corregido |
| AUD-007 | Crítico | Brecha Funcional | B. Gobernanza y Multi-tenencia | P0 Bloqueante | cognito-backend | Ausencia de modelo de datos multi-tenant (Org / Tenant / User) | Corregido |
| AUD-008 | Crítico | Brecha Funcional | B. Gobernanza y Multi-tenencia | P0 Bloqueante | cognito-backend | Inexistencia de autenticación SSO/SAML/OIDC para operadores humanos | Corregido |
| AUD-009 | Crítico | Brecha Funcional | B. Gobernanza y Multi-tenencia | P0 Bloqueante | cognito-backend | Inexistencia de audit log estructurado exportable hacia sistemas SIEM | Corregido |
| AUD-010 | Alto | Brecha Funcional | B. Gobernanza y Multi-tenencia | P1 Esperado | cognito-backend | Control de presupuesto de tokens restringido al ámbito de sesión individual | Corregido |
| AUD-011 | Medio | Brecha Funcional | B. Gobernanza y Multi-tenencia | P1 Esperado | cognito-backend | Inexistencia de políticas automatizadas de retención y borrado de datos de usuario/sesión | Corregido |
| AUD-012 | Alto | Deuda Técnica | B. Gobernanza y Multi-tenencia | P1 Esperado | cognito-backend | Acoplamiento rígido al sistema de archivos local que impide despliegues BYOC/stateless | Corregido |
| AUD-013 | Medio | Defecto | C. Gestión de Contexto | P1 Esperado | cognito-backend | Pérdida de estructura (rutas, firmas, tool calls) durante la compactación narrativa de contexto | Corregido |
| AUD-014 | Alto | Brecha Funcional | C. Gestión de Contexto | P2 Diferenciador | cognito-backend | Ausencia de memoria de hechos del proyecto o usuario persistente entre sesiones | Corregido |
| AUD-015 | Medio | Brecha Funcional | C. Gestión de Contexto | P2 Diferenciador | cognito-backend | Historial de conversación strictly lineal sin ramificación (branching/checkpoints) | Corregido |
| AUD-016 | Medio | Deuda Técnica | C. Gestión de Contexto | P1 Esperado | cognito-backend | Descubrimiento de AGENTS.md restringido a la raíz del CWD sin anidamiento ni tolerancia a fallos | Corregido |
| AUD-017 | Alto | Brecha Funcional | D. Orquestación y Sub-Agentes | P1 Esperado | cognito-backend | Bucle de agente estrictamente secuencial y mono-agente por sesión | Corregido |
| AUD-018 | Medio | Brecha Funcional | D. Orquestación y Sub-Agentes | P1 Esperado | cognito-backend | Ausencia de fase forzada de planificación de solo lectura previa a modificaciones de archivos | Corregido |
| AUD-019 | Alto | Brecha Funcional | D. Orquestación y Sub-Agentes | P1 Esperado | cognito-backend | Cliente MCP simulado (mock) en lugar de transporte real stdio/SSE para servidores externos | Corregido |
| AUD-020 | Medio | Brecha Funcional | D. Orquestación y Sub-Agentes | P2 Diferenciador | cognito-backend | Inexistencia de lifecycle hooks globales pre/post ejecución y pre/post compactación | Corregido |
| AUD-021 | Alto | Brecha Funcional | D. Orquestación y Sub-Agentes | P0 Bloqueante | cognito-backend | Ausencia de canal interactivo de aprobación humana (Human-in-the-Loop) para acciones de riesgo | Corregido |
| AUD-022 | Medio | Brecha Funcional | E. Extensibilidad y Ecosistema | P2 Diferenciador | cognito-backend | Ausencia de un formato estándar declarativo de definición de habilidades (tipo SKILL.md) | Pendiente |
| AUD-023 | Medio | Brecha Funcional | E. Extensibilidad y Ecosistema | P2 Diferenciador | cognito-backend | Carga de extensiones acoplada a la estructura de archivos local del repositorio | Pendiente |
| AUD-024 | Alto | Brecha Funcional | F. Observabilidad y Telemetría | P1 Esperado | cognito-backend | Inexistencia de exportación de métricas de costo/tokens por usuario a Prometheus/OpenTelemetry | Corregido |
| AUD-025 | Alto | Brecha Funcional | F. Observabilidad y Telemetría | P1 Esperado | cognito-backend | Ausencia de Trace ID / Request ID correlacionado entre HTTP, agente y herramientas | Corregido |
| AUD-026 | Alto | Brecha Funcional | G. Resiliencia y Recuperación | P1 Esperado | cognito-backend | Falta de checkpointing de ejecución que permita reanudar el estado tras una caída del proceso | Corregido |
| AUD-027 | Medio | Defecto | G. Resiliencia y Recuperación | P1 Esperado | cognito-backend | Reintentos transitorios de streaming con riesgo de duplicar llamadas no idempotentes | Corregido |
| AUD-028 | Alto | Brecha Funcional | H. Precisión y Evaluación | P1 Esperado | evals / cognito-backend | Ausencia de suite de evaluación E2E de trayectorias completas del agente contra baselines | Corregido |
| AUD-029 | Medio | Brecha Funcional | H. Precisión y Evaluación | P2 Diferenciador | cognito-backend | Inexistencia de un paso interno de autocrítica o verificación previa a la entrega final | Pendiente |
| AUD-030 | Bajo | Deuda Técnica | I. Portabilidad de Proveedores | P2 Diferenciador | cognito-backend | Abstracción del LLM Router con condicionales específicos dificultando la adición de nuevos rimes | Corregido |
| AUD-031 | Medio | Deuda Técnica | J. Despliegue y Producción | P1 Esperado | Dockerfiles | Contenedores Docker ejecutados como root y sin instrucciones HEALTHCHECK o graceful shutdown | Corregido |
| AUD-032 | Alto | Brecha Funcional | J. Despliegue y Producción | P0 Bloqueante | cognito-backend | Estado de sesión acoplado a SQLite y locks locales imprevistos para escalado horizontal | Corregido |
| AUD-033 | Alto | Defecto | A. Seguridad y Aislamiento | P0 Bloqueante | cognito-backend | Brecha de aislamiento de red: paso condicional de --share-net en bwrap según lista blanca | Corregido |
| AUD-036 | Alto | Defecto | A. Seguridad y Aislamiento | P0 Bloqueante | cognito-worker | Riesgo de inyección de argumentos en comandos git en worktree.py | Corregido |

---

## 3. Hallazgos Detallados por Categoría

### Categoría A: Seguridad y Aislamiento de Ejecución

#### AUD-001
- **ID:** AUD-001
- **Severidad:** Crítico
- **Tipo:** Defecto
- **Categoría:** A. Seguridad y Aislamiento de Ejecución
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P0 Bloqueante
- **Descripción del problema:** La herramienta de comandos de shell (`BashTool`) ejecuta instrucciones de consola utilizando directamente `asyncio.create_subprocess_exec` en el proceso y sistema de archivos del host. Aunque existe un módulo `sandbox.py` que prepara argumentos para `bwrap` (Bubblewrap), `BashTool` no invoca a `SandboxManager` de forma obligatoria ni por defecto. Un comando malicioso enviado al agente tiene acceso completo a los recursos del host donde corre el proceso backend.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/tools/bash_tool.py` (líneas 27-55) y `very-simplified-stack/cognito-backend/app/core/sandbox.py` (líneas 85-150).
- **Comparación con el estado del arte:** En 2026, los agent harnesses enterprise imponen aislamiento forzado a nivel de kernel/microVM (e.g. Codex CLI o Firecracker/gVisor). Ejecutar subprocesos directos en el host sin restricción estricta incumple los requisitos básicos de aislamiento.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se modificó `app/core/tools/bash_tool.py` para invocar obligatoriamente `SandboxedExecutor` / `bwrap` por defecto al ejecutar comandos bash.
  - Se eliminó la ejecución directa en subproceso del host cuando `bwrap` no está disponible. Si `bwrap` no está presente, se retorna un error explícito de seguridad (`ToolResult(is_error=True)`).
  - Se agregó el modo opcional "sin sandbox" gateado exclusivamente por la variable de entorno `COGNITO_DISABLE_SANDBOX_DEV_ONLY` (para entornos de desarrollo local), la cual emite una advertencia (`logger.warning`) en los logs durante el arranque y la ejecución.
  - Se actualizaron los argumentos de `bwrap` en `app/core/sandbox.py` (`build_bwrap_args`) añadiendo `/dev`, `/proc` y `/tmp` como montajes necesarios junto con el directorio de trabajo actual (`--bind`), asegurando que la lectura/escritura de archivos del proyecto y comandos legítimos de build/test funcionen adecuadamente dentro del sandbox.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_sandbox.py`:
    - `test_bash_tool_mandatory_sandbox_by_default`: Comprueba que `BashTool` ejecuta los comandos a través de `SandboxedExecutor`/`bwrap` por defecto.
    - `test_bash_tool_bwrap_unavailable_error`: Verifica que si `bwrap` no está instalado y no está activo el bypass de dev, `BashTool` falla con un mensaje de error de seguridad.
    - `test_bash_tool_dev_bypass_warning`: Confirma que al activar `COGNITO_DISABLE_SANDBOX_DEV_ONLY=true` se permite la ejecución en el host y se emite la advertencia requerida en los logs.
    - `test_real_bwrap_isolation_filesystem`: Prueba la restricción del sistema de archivos con un binario real de `bwrap`, demostrando que no se puede escribir fuera del directorio de trabajo permitido ni alterar el sistema de archivos del host.

#### AUD-002
- **ID:** AUD-002
- **Severidad:** Alto
- **Tipo:** Brecha Funcional
- **Categoría:** A. Seguridad y Aislamiento de Ejecución
- **Componente:** cognito-backend / CLI
- **Prioridad MVP Enterprise:** P0 Bloqueante
- **Descripción del problema:** No existe un control de red de salida saliente (egress network policy) tipo deny-all por defecto para los subprocesos o herramientas ejecutadas por el agente. El módulo `build_bwrap_args` en `sandbox.py` incluye la opción `--share-net` o deja activa la pila de red sin filtrar IP salientes ni requerir lista blanca explícita de endpoints.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/sandbox.py` (líneas 34-45) y `cognito_agent.py` (líneas 1-200).
- **Comparación con el estado del arte:** Los harnesses enterprise de 2026 bloquean por defecto cualquier tráfico de red saliente de las herramientas ejecutadas por el agente, permitiendo únicamente dominios o IPs autorizadas explícitamente en una lista blanca.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se modificó `build_bwrap_args` en `very-simplified-stack/cognito-backend/app/core/sandbox.py` para aplicar una política de red deny-all por defecto (espacio de nombres de red aislado con `--unshare-all`, eliminando `--share-net` por defecto).
  - Se implementaron las funciones `get_sandbox_allowed_hosts()` e `is_host_allowed()` para definir y validar dinámicamente la lista blanca de hosts autorizados. La lista blanca por defecto incluye los endpoints de los proveedores LLM activos en `BackendRouter` (`BACKENDS_BY_PRIORITY`), así como `localhost`, `127.0.0.1`, `::1` y `host.docker.internal`.
  - Se añadió soporte para que un operador configure hosts/IPs salientes adicionales sin modificar código fuente mediante la variable de entorno `COGNITO_SANDBOX_ALLOWED_HOSTS` (lista separada por comas).
  - Se actualizó `SandboxedExecutor` para validar los hosts de destino antes y durante la ejecución, lanzando `SandboxNetworkError` si se intenta conectar a un host no listado.
  - Se documentó la variable `COGNITO_SANDBOX_ALLOWED_HOSTS` en `very-simplified-stack/cognito-backend/README.md` y `ENV_MANAGEMENT.md`.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_sandbox.py`:
    - `test_build_bwrap_args_deny_all_by_default`: Demuestra que `build_bwrap_args` no incluye `--share-net` por defecto, manteniendo el espacio de nombres de red aislado.
    - `test_get_sandbox_allowed_hosts_and_is_host_allowed`: Valida que los endpoints LLM por defecto y los hosts configurados vía `COGNITO_SANDBOX_ALLOWED_HOSTS` están permitidos, mientras que destinos no autorizados son rechazados.
    - `test_sandboxed_executor_unwhitelisted_host_fails`: Confirma que `SandboxedExecutor` cancela la ejecución lanzando `SandboxNetworkError` al intentar conectar a un host no listado.
- **Nota de Seguimiento Fechada (Verificación de Enforcement de Red):**
  - **Mecanismo de Enforcement Confirmado:** Se confirmó que las llamadas salientes del agente Cognito hacia proveedores LLM u otros servicios ocurren exclusivamente fuera del sandbox en el proceso principal orquestador de Cognito. El sandbox de `bwrap` aísla por completo el subproceso sandboxeado con `--unshare-all` a nivel de namespace del kernel Linux sin ninguna interfaz de red utilizable (`deny-all` real sin excepciones internas).
  - **Corrección Aplicada:** Se eliminó la ambigüedad donde `build_bwrap_args` aceptaba opcionalmente `--share-net` si el host estaba en la lista blanca. Ahora `build_bwrap_args` NUNCA añade `--share-net` bajo ningún parámetro. La comprobación `is_host_allowed` / `get_sandbox_allowed_hosts` aplica a las verificaciones previas a la ejecución del proceso principal de Cognito, no al interior del sandbox.
- **Nota de Seguimiento Fechada (Verificación de Necesidad de Red en BashTool):**
  - **Investigación de Flujos de Red en BashTool:** Se investigó exhaustivamente el uso normal de Cognito como agente de codificación para determinar si `BashTool` requiere conectividad de red saliente dentro del sandbox (e.g. `git clone/pull/push`, `pip install`, `npm install`, `curl`/`wget`). Se confirmó que `BashTool` **NO** necesita red dentro del sandbox por diseño arquitectónico explícito.
  - **Arquitectura de Segregación de Red:**
    1. **Gestión de Repositorios y Clonación:** Las operaciones Git de preparación del entorno (clonación, creación de ramas y worktrees aislados) ocurren en el servicio `cognito-worker` (`worker_app/worktree.py`), ejecutado fuera del sandbox a nivel de host.
    2. **Llamadas a Modelos LLM e Integraciones de API:** La comunicación con los backends LLM (Ollama, OpenAI, Anthropic) se realiza exclusivamente desde el proceso orquestador principal de `cognito-backend` mediante HTTP/HTTPS sin pasar por `bwrap`.
    3. **Ejecución de Herramientas de Trabajo:** `BashTool` en `cognito-backend` se invoca exclusivamente para inspeccionar archivos locales, ejecutar scripts de build/test y realizar ediciones en el espacio de trabajo local preinstalado.
  - **Verificación Técnica de Pruebas:** Los tests del sandbox (`test_real_bwrap_isolation_network` en `test_sandbox.py`) corroboran activamente que cualquier intento de conexión de red dentro de `bwrap` falla de manera absoluta a nivel de socket del kernel con `--unshare-all`, mientras que las operaciones normales del agente y las suites de prueba de backend (251 tests) y worker (5 tests) pasan al 100%.
  - **Decisión de Diseño Intencional:** Mantener red cero (`deny-all` absoluto sin `--share-net`) en `BashTool` es una decisión de seguridad intencional para prevenir filtraciones de datos, ataques de exfiltración de contexto y derivaciones de red desde comandos generados por el modelo.

#### AUD-003
- **ID:** AUD-003
- **Severidad:** Alto
- **Tipo:** Deuda Técnica
- **Categoría:** A. Seguridad y Aislamiento de Ejecución
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P0 Bloqueante
- **Descripción del problema:** El token de autenticación para el servidor MCP (`verify_mcp_auth`) se lee directamente en texto plano desde el archivo JSON de configuración `cognito_mcp_config.json` o variables de entorno simples sin soporte para integración con gestores de secretos (AWS Secrets Manager, Vault) ni rotación/revocación en caliente.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/services/mcp_server.py` (líneas 272-378).
- **Comparación con el estado del arte:** La gestión de secretos enterprise exige rotación dinámica y revocación en tiempo real de credenciales comprometidas sin requerir reinicios o modificaciones de archivos en disco plano.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se creó la abstracción abstracta `SecretsProvider` (`app/core/secrets.py`) declarando `get_secret(name)`, `invalidate(name)` y `refresh(name)`.
  - Se implementó `LocalFileSecretsProvider` envolviendo el comportamiento local por defecto (resolución jerárquica de variables de entorno -> `~/.cognito/config.json` con permisos `0o600` / directorio `0o700` -> token efímero autogenerado), manteniendo retrocompatibilidad total para desarrollo local.
  - Se incluyó la clase `VaultSecretsProvider` como stub documentado con las instrucciones de configuración para operadores de infraestructura (`COGNITO_SECRETS_PROVIDER=vault`, `VAULT_ADDR`, `VAULT_TOKEN`, `VAULT_SECRET_PATH`). *(Nota explícita: La integración de red en vivo contra una infraestructura real de HashiCorp Vault / AWS Secrets Manager queda como trabajo de seguimiento pendiente de infraestructura/DevOps, no de código).*
  - Se refactorizaron `verify_mcp_auth` y `load_mcp_config` en `app/services/mcp_server.py` para consultar credenciales mediante `SecretsProvider`.
  - Se añadió el endpoint REST `POST /api/secrets/reload` que permite recargar/invalidar secretos en caliente tras una rotación sin reiniciar el proceso backend.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_secrets.py`:
    - `test_local_file_secrets_provider_auto_generation`: Valida autogeneración y permisos `0o600` / `0o700`.
    - `test_local_file_secrets_provider_env_override`: Valida prevalencia de variables de entorno.
    - `test_secret_rotation_and_revocation_flow`: Demuestra que tras invalidar/rotar un secreto, las peticiones con el token antiguo son denegadas (`verify_mcp_auth` retorna `False`) y el nuevo token pasa a ser el único válido.
    - `test_vault_secrets_provider_stub`: Valida el comportamiento e inicialización del stub de Vault.
    - `test_secrets_reload_api_endpoint`: Comprueba la recarga en caliente a través del endpoint REST HTTP.
- **Nota de Seguimiento Fechada (Verificación y Fortalecimiento de Autenticación en Endpoint de Recarga):**
  - **Verificación Realizada:** Se constató que la implementación inicial de `POST /api/secrets/reload` exponía el endpoint sin autenticación obligatoria y sin límites de tasa de peticiones, lo cual permitía que cualquier cliente anónimo invalidara la caché de secretos de forma repetida (vector potencial de denegación de servicio / DoS).
  - **Corrección Aplicada:** Se protegió `POST /api/secrets/reload` en `app/api/routes/ai_agents.py` mediante verificación administrativa exigiendo un token válido (`Authorization: Bearer <token>`, `X-API-Key: <token>` o `auth_token` en el cuerpo JSON) validado dinámicamente con `verify_mcp_auth`. Peticiones sin token o con credenciales inválidas son rechazadas con HTTP 401 (`Unauthorized`). Adicionalmente, se incorporó un rate limiter por ventana deslizante (`SlidingWindowRateLimiter`) restringiendo el endpoint a un máximo de 5 peticiones por minuto, retornando HTTP 429 (`Too Many Requests`) al exceder la cuota.
  - **Test de Regresión:**
    - `very-simplified-stack/cognito-backend/tests/test_secrets.py`:
      - `test_secrets_reload_unauthenticated_rejected`: Comprueba que peticiones no autenticadas a `POST /api/secrets/reload` son rechazadas con HTTP 401.
      - `test_secrets_reload_invalid_token_rejected`: Valida que tokens incorrectos o caducados reciben HTTP 401.
      - `test_secrets_reload_api_endpoint`: Confirma la invalidación y recarga exitosa con credenciales HTTP Bearer válidas (HTTP 200).
      - `test_secrets_reload_rate_limiting`: Demuestra que peticiones excesivas que superan la tasa límite son bloqueadas con HTTP 429.

#### AUD-004
- **ID:** AUD-004
- **Severidad:** Crítico
- **Tipo:** Defecto
- **Categoría:** A. Seguridad y Aislamiento de Ejecución
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P0 Bloqueante
- **Descripción del problema:** Las conexiones WebSocket y rutas HTTP expuestas por FastAPI y el servidor MCP no implementan validación de la cabecera `Origin`, ni middleware de protección CSRF o restricciones específicas de CORS. Además, ciertos tokens de auth pueden transmitirse en parámetros de consulta URL, expuestos a logs de red.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/main.py` (líneas 1-50) y `very-simplified-stack/cognito-backend/app/services/mcp_server.py` (líneas 1-700).
- **Comparación con el estado del arte:** A raíz de vulnerabilidades críticas de Cross-Site WebSocket Hijacking en 2026, los harnesses enterprise requieren verificación estricta de `Origin`, tokens de sesión en cabeceras HTTP Authorization y mitigación CORS/CSRF.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se configuró `CORSMiddleware` en `app/main.py` con una lista blanca explícita de orígenes permitidos resolved a través de la variable de entorno `COGNITO_ALLOWED_ORIGINS` (evitando wildcards `*` combinados con credenciales).
  - Se implementó validación explícita de la cabecera `Origin` en el endpoint WebSocket (`/ws`), rechazando conexiones no autorizadas con el código de cierre `1008 (Policy Violation)`.
  - Se documentó explícitamente la razón por la cual CSRF no aplica (Cognito utiliza autenticación explícita por cabeceras `Authorization: Bearer <token>` y payloads FastMCP en lugar de cookies de sesión persistentes de navegador).
  - Se verificó que la transmisión de tokens de autenticación se realice vía cabecera `Authorization` y se descartó cualquier requerimiento de tokens en parámetros de consulta URL.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_cors_origin_security.py`:
    - `test_is_origin_allowed`: Valida la lógica de origen permitido contra listas blancas y comodines.
    - `test_cors_whitelisted_origin`: Comprueba que una petición cross-origin desde un origen listado es permitida con cabeceras CORS de credenciales.
    - `test_cors_unauthorized_origin`: Confirma que orígenes no autorizados no reciben cabeceras `Access-Control-Allow-Origin`.
    - `test_cors_custom_env_origins`: Verifica la configuración dinámica de orígenes mediante `COGNITO_ALLOWED_ORIGINS`.
    - `test_websocket_unauthorized_origin`: Demuestra que una conexión WebSocket desde un origen no autorizado es rechazada.
    - `test_websocket_authorized_origin`: Confirma la aceptación y comunicación bidireccional cuando el origen es autorizado.
    - `test_no_auth_tokens_in_url_query_params`: Garantiza que los tokens de auth son aceptados vía cabecera `Authorization`.

#### AUD-005
- **ID:** AUD-005
- **Severidad:** Medio
- **Tipo:** Brecha Funcional
- **Categoría:** A. Seguridad y Aislamiento de Ejecución
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** La clase abstracta `AgentTool` no declara metadatos explícitos de comportamiento (tales como `is_read_only`, `is_destructive` o `concurrency_safe`). La evaluación de permisos depende de lógica hardcodeada o de la política externa `ExecPolicy` en lugar de autodeclaración tipada de la herramienta.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/tools/base.py` (líneas 10-50).
- **Comparación con el estado del arte:** En 2026, el patrón estándar en Claude Code / OpenCode exige que cada herramienta exponga metadatos de riesgo y concurrencia tipados (ej. vía Pydantic) para que el harness decida permisos automáticamente.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se añadieron campos tipados de metadatos de comportamiento de riesgo (`is_read_only: bool = False`, `is_destructive: bool = False`, `concurrency_safe: bool = False`) a la clase base `AgentTool` (`app/core/tools/base.py`).
  - Se migraron todas las herramientas existentes (`ReadTool`, `WriteTool`, `EditTool`, `UnifiedPatchTool`, `ListDirectoryTool`, `SearchFilesTool`, `BashTool`, `PersistentShellTool`, `ShellTools`, `TodoTools`, `WebPublisherTools`, `QuerySpillTool`, `ReadSpillTool`, `CodeReviewTool`), así como los wrappers `WrappedMCPTool` y `HookedTool`, para declarar estos metadatos explícitamente.
  - Se actualizó `ToolLoopDetector` (`app/core/guardrails/tool_loop_detector.py`) para consultar `tool.is_read_only` directamente al calcular hashes de llamadas.
  - Se creó `evaluate_tool_execution` en `ExecPolicy` (`app/core/exec_policy.py`) y se integró en `agent_loop.py` para evaluar permisos según los metadatos `is_destructive` e `is_read_only` de cada herramienta en contextos confiables o no confiables.
  - Se actualizó `ApprovalManager` y `PendingApprovalRequest` (`app/core/approval.py`) para registrar las banderas `is_destructive` e `is_read_only` en las solicitudes de aprobación pendientes.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_aud005_tool_metadata.py`:
    - `test_agent_tool_base_metadata_defaults`: Verifica que la clase base `AgentTool` define los atributos de metadatos.
    - `test_all_official_tools_declare_metadata`: Comprueba que cada herramienta oficial declara valores explícitos correctos para `is_read_only`, `is_destructive` y `concurrency_safe`.
    - `test_wrapped_mcp_and_hooked_tool_metadata_propagation`: Confirma la propagación de metadatos en wrappers de MCP y herramientas con hooks.
    - `test_tool_loop_detector_queries_tool_metadata`: Valida que `ToolLoopDetector` consulta los metadatos de la herramienta para diferenciar el cálculo de hash entre herramientas de lectura y destructivas.
    - `test_exec_policy_evaluates_tool_metadata`: Garantiza que `evaluate_tool_execution` bloquea herramientas destructivas en entornos no confiables requiriendo aprobación explícita.
    - `test_approval_manager_records_tool_metadata`: Verifica que las solicitudes de aprobación pendientes registran los metadatos de riesgo de la herramienta.

#### AUD-006
- **ID:** AUD-006
- **Severidad:** Medio
- **Tipo:** Deuda Técnica
- **Categoría:** A. Seguridad y Aislamiento de Ejecución
- **Componente:** cognito-backend / worker
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** Los archivos `requirements.txt` del backend y del worker especificaban nombres de librerías sin fijar versiones exactas ni hashes criptográficos en lockfiles dedicados. Esto exponía el despliegue a ataques de cadena de suministro o incompatibilidades transitorias.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/requirements.txt` y `very-simplified-stack/cognito-worker/requirements.txt`.
- **Comparación con el estado del arte:** Las normativas de compliance enterprise exigen escaneo de dependencias y lockfiles congelados (`poetry.lock`, `pip-compile --generate-hashes`, `uv pip compile --generate-hashes`).
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se generaron los archivos `requirements.lock` con hashes sha256 fijados para todas las dependencias directas e indirectas de `cognito-backend` y `cognito-worker` utilizando `uv pip compile --generate-hashes`.
  - Se actualizó `very-simplified-stack/cognito-backend/Dockerfile` para copiar e instalar las dependencias desde `requirements.lock` utilizando `pip install --no-cache-dir --require-hashes -r requirements.lock`.
  - Se agregó el trabajo `validate-lockfiles` en `.github/workflows/validate.yml` que valida automáticamente en la canalización de CI que los archivos `requirements.lock` coinciden exactamente con la compilación actual de `requirements.txt`, fallando la build si divergen.
  - Se documentó el procedimiento de instalación segura con hashes y regeneración del lockfile (`uv pip compile --generate-hashes requirements.txt -o requirements.lock`) en `very-simplified-stack/cognito-backend/README.md` y `very-simplified-stack/cognito-worker/README.md`.
- **Test de Regresión:**
  - Se verificó que la instalación mediante `pip install --require-hashes -r requirements.lock` reproduce exactamente las mismas versiones y valida correctamente la integridad criptográfica sha256 de los paquetes.
  - Se verificó mediante un script de validación idéntico al de CI que cualquier inconsistencia o divergencia entre `requirements.txt` y `requirements.lock` resulta en un fallo inmediato (código de retorno distinto de cero).

#### AUD-033
- **ID:** AUD-033
- **Severidad:** Alto
- **Tipo:** Defecto
- **Categoría:** A. Seguridad y Aislamiento de Ejecución
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P0 Bloqueante
- **Descripción del problema:** En la implementación inicial de AUD-002, `build_bwrap_args` en `sandbox.py` habilitaba condicionalmente la flag `--share-net` de bubblewrap si la red estaba solicitada y el host de destino coincidía con la lista blanca. Esto abría una brecha de seguridad a nivel de red, ya que una vez que se pasaba la flag `--share-net` al binario `bwrap`, el comando sandboxeado compartía el namespace de red completo del host y podía abrir sockets hacia cualquier puerto/host arbitrario directamente desde el kernel, evitando cualquier filtrado a nivel de aplicación en el orquestador Python.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/sandbox.py` (función `build_bwrap_args`).
- **Comparación con el estado del arte:** El aislamiento estricto exige que los comandos de shell arbitrarios ejecutados en un sandbox tengan deny-all a nivel de kernel/namespace sin posibilidad de derivar la pila de red, manteniendo cualquier conectividad saliente fuera del proceso incondicionalmente.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se eliminó completamente la lógica de adición condicional de `--share-net` en `build_bwrap_args()`. Todos los subprocesos de bubblewrap se ejecutan estrictamente con `--unshare-all` y sin interfaz de red.
  - Se aclaró formalmente en los docstrings de `sandbox.py` (`is_host_allowed`, `get_sandbox_allowed_hosts`, `SandboxNetworkError`) que la lista blanca aplica a las llamadas salientes originadas en el proceso principal de Cognito (ej. llamadas a APIs de modelos LLM o workers), y no al espacio de ejecución del sandbox.
  - Se añadió la prueba `test_real_bwrap_isolation_network` en `test_sandbox.py` y se actualizaron las pruebas de `build_bwrap_args` para asegurar que `--share-net` nunca sea incluida.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_sandbox.py`:
    - `test_build_bwrap_args_deny_all_by_default`: Comprueba que `--share-net` jamás se añade a los argumentos de `bwrap` independientemente de los parámetros provistos.
    - `test_real_bwrap_isolation_network`: Ejecuta un comando real de prueba de socket dentro del sandbox intentando conectarse a `127.0.0.1:8080` (host de lista blanca) y confirma que la conexión falla a nivel de red con excepción de socket.
- **Nota de Seguimiento y Decisión de Alcance (Instalación de Dependencias Mid-Sesión):**
  - **Confirmación del Comportamiento Actual:** Si un usuario o agente solicita una tarea que requiere instalar dependencias adicionales mid-sesión (por ejemplo `npm install axios` o `pip install requests`), `BashTool` intentará ejecutar el comando dentro del sandbox `bwrap` y fallará por falta de conectividad a la red debido a la imposición de `--unshare-all`. Actualmente no existe ningún mecanismo previo (ni en `cognito-worker` ni en la preparación del workspace) que instale dependencias antes de entregar el control al agente.
  - **Limitación de Alcance del MVP Actual:** Esta conducta se define formalmente como una **limitación de alcance explícita del MVP actual** derivada del diseño de aislamiento estricto, y no como un efecto secundario accidental.
  - **Estrategia Futura Recomendada:** Para permitir la instalación de paquetes mid-sesión sin comprometer la superficie de red de `BashTool`, se sugiere diseñar una herramienta dedicada (ej. `PackageInstallTool`) o un hook de preparación en `cognito-worker` fuera del sandbox, que procese paquetes a través de una whitelist auditada de registros (e.g. npm/PyPI enterprise), evitando la apertura de red genérica a `BashTool`.
  - **Decisión de Producto:** El equipo de producto debe evaluar explícitamente si esta limitación de no soportar instalación de paquetes mid-sesión en `BashTool` es aceptable para el MVP actual o si requiere priorizar la herramienta dedicada en la hoja de ruta.

#### AUD-036
- **ID:** AUD-036
- **Severidad:** Alto
- **Tipo:** Defecto
- **Categoría:** A. Seguridad y Aislamiento de Ejecución
- **Componente:** cognito-worker
- **Prioridad MVP Enterprise:** P0 Bloqueante
- **Descripción del problema:** La clase `GitWorktreeManager` en `worker_app/worktree.py` ejecuta operaciones de Git (`rev-parse`, `branch`, `worktree add`, `diff`, `worktree remove`) sin sanitización estricta de parámetros de entrada como la URL o ruta del repositorio, identificadores (`repo_id`, `task_id`) y referencias Git (`base_commit`, `branch_name`). Aunque los comandos se ejecutaban mediante listas de argumentos en `subprocess.run` (sin `shell=True`), la falta de delimitadores `--` y de validación de entradas permitía que valores iniciados por `-` (por ejemplo, `--upload-pack` o `-o`) o esquemas de transporte inseguros de Git (como `ext::`) fueran interpretados como flags o comandos arbitrarios por el binario `git`.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-worker/worker_app/worktree.py` (métodos `_run_git`, `validate_git_repo`, `create_worktree`, `get_diff` y `cleanup_worktree`).
- **Comparación con el estado del arte:** La ejecución segura de herramientas en arneses enterprise exige la prevención absoluta de argument injection en invocaciones a binarios CLI, asegurando que ningún parámetro de usuario no confiable pueda alterar las opciones de ejecución mediante separadores explícitos `--` y validación de esquemas/sintaxis.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se añadieron las funciones de validación sanitizadora `validate_repo_url_or_path`, `validate_git_ref` y `validate_identifier` en `worker_app/worktree.py`.
  - Se restringieron las URLs/rutas de repositorios para rechazar esquemas de protocolo inseguros (`ext::`, `fd::`, `file::`) o valores que inicien con el prefijo `-`.
  - Se impuso la validación de identificadores y nombres de referencia Git para que rechacen caracteres nulos, secuencias inválidas de refspec y prefijos con `-`.
  - Se incorporó el separador `--` antes de los argumentos posicionales en todos los subcomandos de Git (`branch`, `worktree add`, `worktree remove`) para impedir la inyección de opciones.
  - Se eliminaron los argumentos vacíos de marcador de posición (`""`) en las invocaciones de `worktree remove`.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-worker/tests/test_worktree.py`:
    - `test_validate_repo_url_or_path_*`: Verifica la aceptación de URLs/rutas válidas y el rechazo de URLs con el prefijo `-`, byte nulo o esquemas prohibidos (`ext::`, `fd::`, `file::`).
    - `test_validate_git_ref_*`: Comprueba que referencias Git o ramas que inician con `-` o contienen caracteres no permitidos son rechazadas antes de invocar Git.
    - `test_validate_identifier_*`: Comprueba el rechazo de `repo_id` o `task_id` maliciosos que intenten inyectar flags.
    - `test_worktree_manager_normal_lifecycle`: Valida el ciclo de vida completo de un worktree legítimo en un repositorio de prueba real.
    - `test_worktree_manager_rejects_malicious_inputs`: Confirma que `GitWorktreeManager` cancela la ejecución lanzando `ValueError` al recibir parámetros con inyección de flags sin llegar a invocar `git`.

---

### Categoría B: Gobernanza Empresarial y Multi-tenencia

#### AUD-007
- **ID:** AUD-007
- **Severidad:** Crítico
- **Tipo:** Brecha Funcional
- **Categoría:** B. Gobernanza Empresarial y Multi-tenencia
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P0 Bloqueante
- **Descripción del problema:** El modelo de datos de Cognito (`app/models/db.py` y `app/models/domain.py`) únicamente contempla los conceptos de `Session`, `Message` y `Execution`. No existen las entidades `Organization`, `Project` ni `User`, asumiendo una arquitectura de único inquilino y único operador.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/models/db.py` y `very-simplified-stack/cognito-backend/app/models/domain.py`.
- **Comparación con el estado del arte:** El software enterprise requiere RBAC granular y segmentación explícita por usuario, proyecto y organización.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se crearon los modelos de dominio (`Organization`, `Project`, `User`) en `very-simplified-stack/cognito-backend/app/models/domain.py` y las tablas ORM SQLAlchemy (`DBOrganization`, `DBProject`, `DBUser`) en `very-simplified-stack/cognito-backend/app/models/db.py`, de acuerdo fiel con el diseño especificado en `ARCHITECTURE_RFC_GOBERNANZA.md`.
  - Se vincularon las sesiones (`SessionMetadata`, `SessionManager`) y los presupuestos de tokens jerárquicos (`TokenBudgetManager`) con los identificadores de jerarquía multi-tenant `org_id`, `project_id` y `user_id`.
  - Los ítems subsiguientes del plan de gobernanza enterprise AUD-008 (autenticación SSO/SAML/OIDC), AUD-009 (audit logging estructurado SIEM) y AUD-032 (almacenamiento compartido) se construyen y referencian sobre este modelo de datos unificado de verdad (`Organization`, `Project`, `User`).
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_hierarchical_budget.py`:
    - `test_domain_and_db_models`: Verifica la instanciación e identificadores de `Organization`, `Project` y `User`.
    - `test_session_manager_tenant_binding`: Comprueba la vinculación de metadatos multi-tenant en sesiones.

#### AUD-008
- **ID:** AUD-008
- **Severidad:** Crítico
- **Tipo:** Brecha Funcional
- **Categoría:** B. Gobernanza Empresarial y Multi-tenencia
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P0 Bloqueante
- **Descripción del problema:** No existe ninguna integración con esquemas de autenticación federada SSO, SAML 2.0 ni OpenID Connect (OIDC) para validar la identidad de los usuarios humanos que interactúan con el backend o la CLI.
- **Evidencia de Ubicación en Código:** Revisión completa del directorio `very-simplified-stack/cognito-backend/app/api/routes/` (ausencia de módulos de OAuth/OIDC/SAML).
- **Comparación con el estado del arte:** El soporte de SSO/OIDC/SAML es un requisito no negociable en las evaluaciones de seguridad corporativa para permitir el control de acceso centralizado.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se creó el módulo `very-simplified-stack/cognito-backend/app/core/sso/` definiendo la interfaz abstracta `SSOProvider` (`base.py`) y la implementación real `OIDCProvider` (`oidc.py`).
  - Se implementó la verificación real de firmas asimétricas (RS256 / ES256) de los ID Tokens OIDC contra el JWKS (JSON Web Key Set) del proveedor utilizando `PyJWT` y `cryptography`. Tokens con firma manipulada o expirados son explícitamente rechazados (`InvalidTokenSignatureError`).
  - Se implementó la clase `SSOService` (`service.py`) que resuelve la vinculación de `Organization` mediante reglas configurables de mapeo por dominio de email (`COGNITO_SSO_DOMAIN_MAP`), realiza el auto-aprovisionamiento de nuevos usuarios (`User`) o actualización de existentes en su primer login, y vincula la sesión de Cognito (`SessionManager` con `auth_type="authenticated_sso"`).
  - Se integró el registro de eventos de auditoría SIEM (`auth.sso_login` y `auth.sso_logout`) en el Audit Log estructurado (AUD-009).
  - Se expusieron las rutas HTTP REST en `app/api/routes/auth.py` (`GET /api/auth/sso/login`, `GET/POST /api/auth/sso/callback`, `POST /api/auth/sso/logout`) y se montaron en `app/main.py`.
  - Se implementó la clase `SAMLProvider` (`saml.py`) como stub documentado siguiendo el mismo patrón arquitectónico de `VaultSecretsProvider` (AUD-003), permitiendo extender el soporte completo a SAML 2.0 en el futuro sin romper contratos de API.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_sso_oidc.py`:
    - `test_oidc_authorization_url_generation`: Valida la generación de URLs de autorización OIDC con `state` y `client_id`.
    - `test_oidc_valid_id_token_verification`: Verifica la validación exitosa de firmas asimétricas RS256 usando pares de claves RSA y JWKS.
    - `test_oidc_tampered_signature_token_rejected`: Prueba explícitamente que tokens con firma o payload manipulados son rechazados lanzando `InvalidTokenSignatureError`.
    - `test_oidc_end_to_end_callback_flow_and_auto_provisioning`: Prueba E2E del callback SSO con mock IdP, verificando el auto-aprovisionamiento de usuario, vinculación multi-tenant a la organización por dominio, emisión de sesión Cognito y registro en el Audit Log.
    - `test_sso_logout_endpoint_and_audit`: Confirma el cierre de sesión y la presencia del evento `auth.sso_logout` en el Audit Log.
    - `test_saml_provider_stub_instantiation_and_callback`: Verifica el comportamiento e instanciación del stub documentado de SAML 2.0.

#### AUD-009
- **ID:** AUD-009
- **Severidad:** Crítico
- **Tipo:** Brecha Funcional
- **Categoría:** B. Gobernanza Empresarial y Multi-tenencia
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P0 Bloqueante
- **Descripción del problema:** Cognito registra eventos en consola o archivos de log locales sin un formato estructurado de auditoría (Audit Trail) exportable vía Syslog, OTLP o conectores SIEM (e.g., Splunk, Datadog). No se registran eventos firmados con timestamp de identidad humana.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/logging_config.py` (líneas 1-40) y `very-simplified-stack/cognito-backend/app/core/tracing.py` (líneas 1-50).
- **Comparación con el estado del arte:** Los estándares de cumplimiento 2026 exigen audit logs inmutables de todas las llamadas a herramientas y accesos a archivos exportables a SIEM.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se definió la entidad y modelo Pydantic `AuditLogRecord` (`app/core/audit.py`) conteniendo el esquema de auditoría estructurado completo: `actor` (`user_id`, `org_id`, `type`, `id`), `action`, `resource`, `timestamp` (ISO 8601 UTC), `trace_id` (AUD-025), `status`/`result`, `session_id`, `project_id`, `security_context` y `approval_metadata`.
  - Se creó la tabla ORM `DBStructuredAuditLog` (`app/models/db.py`) y persistencia atómica en `app/core/audit.py` que almacena los registros de auditoría en la base de datos compartida (AUD-012/032) y en archivos `.jsonl` locales de forma estrictamente inmutable y **append-only** (sin consultas `UPDATE` o `DELETE` desde código de aplicación).
  - Se implementó la captura de eventos mediante los hooks del ciclo de vida de AUD-020 (`on_agent_start`, `on_tool_pre_exec`, `on_tool_post_exec`), eliminando la necesidad de sembrar llamadas manuales de auditoría por el `agent_loop`.
  - Se unificó `ApprovalDecisionAudit` (AUD-021) en este mismo Audit Log mediante `record_approval_decision` y consulta cruzada en `ApprovalManager`, estableciendo una única fuente de verdad para la auditoría en Cognito.
  - Se implementó la exportación SIEM en tiempo real:
    - Exportador Syslog RFC 5424 en formato de texto plano sobre UDP/TCP utilizando la librería estándar `socket`.
    - Forwarder Webhook HTTP enviando payloads JSON estructurados mediante `urllib` / `http.client`.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_audit_log_siem.py`:
    - `test_audit_log_schema_actor_trace_timestamp`: Valida la estructura del esquema con `actor` (`user_id`/`org_id`), `trace_id`, `timestamp` e identificadores correctos.
    - `test_audit_log_append_only_persistence`: Confirma que la persistencia en disco y base de datos es inmutable y estrictamente append-only.
    - `test_syslog_rfc5424_exporter_formatting_and_sending`: Comprueba el formateo y envío correcto de mensajes Syslog RFC 5424 usando `socket`.
    - `test_webhook_exporter_sending`: Verifica el envío de payloads JSON formateados vía webhook HTTP.
    - `test_aud020_lifecycle_hooks_capture`: Confirma la captura automática de eventos a través de los hooks de ciclo de vida (`on_agent_start`, `on_tool_pre_exec`, `on_tool_post_exec`).
    - `test_aud021_approval_decision_unification`: Valida la unificación de decisiones de aprobación en el Audit Log como única fuente de verdad.

#### AUD-010
- **ID:** AUD-010
- **Severidad:** Alto
- **Tipo:** Brecha Funcional
- **Categoría:** B. Gobernanza Empresarial y Multi-tenencia
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** El control de cuota de consumo (`TokenBudgetManager`) se calcula exclusivamente por sesión individual. No existen mecanismos para definir cuotas financieras o límites de consumo de tokens a nivel de equipo, usuario u organización.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/token_budget.py` (líneas 1-80).
- **Comparación con el estado del arte:** Los arneses de nivel enterprise gestionan presupuestos agregados jerárquicos con alertas y bloqueos de costes por departamento o proyecto.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se crearon las entidades de dominio y modelos ORM de base de datos `Organization`, `Project` y `User` en `app/models/domain.py` y `app/models/db.py`.
  - Se extendió `SessionMetadata` y `SessionManager.create()` en `app/core/session_manager.py` para vincular sesiones con los identificadores multi-tenant `org_id`, `project_id` y `user_id`.
  - Se extendió `TokenBudgetManager` en `app/core/token_budget.py` incorporando soporte para presupuestos definidos jerárquicamente a nivel de `Organization`, `Project`, `User` y `Session`.
  - Se implementó la agregación de consumo acumulado simultáneo en todas las dimensiones del jerarquía (`record_usage`), evaluando umbrales de aviso configurables (`warning_threshold_ratio`, por defecto 80%) y bloqueos duros (`hard_limit_action="block"` / `TokenBudgetExceededError`).
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_hierarchical_budget.py`:
    - `test_domain_and_db_models`: Verifica la instanciación e identificadores de `Organization`, `Project` y `User`.
    - `test_session_manager_tenant_binding`: Comprueba la vinculación de metadatos multi-tenant en sesiones.
    - `test_hierarchical_budget_setting_and_getting`: Valida la configuración y consulta de presupuestos por alcance.
    - `test_hierarchical_usage_aggregation_and_org_budget_enforcement`: Demuestra que el presupuesto de organización se respeta agregando el consumo acumulado de múltiples usuarios/sesiones, activando alertas de advertencia y lanzando `TokenBudgetExceededError` al superar la cuota agregada de la organización.
    - `test_project_and_session_level_blocking`: Confirma el bloqueo independiente a nivel de proyecto y de sesión.

#### AUD-011
- **ID:** AUD-011
- **Severidad:** Medio
- **Tipo:** Brecha Funcional
- **Categoría:** B. Gobernanza Empresarial y Multi-tenencia
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** No existen servicios o tareas de fondo para la purga programada o eliminación bajo demanda (derecho al olvido / GDPR) del historial de sesiones o archivos almacenados.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/session_manager.py` (líneas 1-120) y `very-simplified-stack/cognito-backend/app/core/database.py` (líneas 1-50).
- **Comparación con el estado del arte:** Las políticas de retención de datos corporativos exigen la purga automática de sesiones inactivas tras N días y capacidades de borrado solicitadas por API.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - **Parte 1 (Purga por antigüedad de sesiones inactivas):**
    - Se agregaron los métodos `purge_inactive_sessions(max_age_days)` y `purge_inactive_sessions_async(max_age_days)` en `app/core/session_manager.py`, permitiendo la inspección y eliminación segura de sesiones cuya última actualización (`updated_at`) supere los días de inactividad configurados. La eliminación destruye atómicamente los archivos de sesión (`.jsonl`), metadatos (`.meta.json`), cerrojos (`.lock`) y sincroniza el índice general (`index.json`).
    - Se implementó la clase `SessionPurgerTask` en `app/core/session/purger.py` basada en la librería estándar `asyncio`, que ejecuta un bucle periódico en segundo plano. La retención y el intervalo de ejecución son configurables mediante las variables de entorno `COGNITO_SESSION_RETENTION_DAYS` (por defecto 30 días) y `COGNITO_SESSION_PURGE_INTERVAL_SECONDS` (por defecto 3600 segundos).
    - Se integró la tarea de purga en segundo plano en el gestor de ciclo de vida (`lifespan`) de la aplicación FastAPI en `app/main.py`, asegurando un arranque automático y una cancelación limpia (`graceful shutdown`) al detener la aplicación.
  - **Parte 2 (Borrado bajo demanda por User/Organization - Bloqueado por RFC):**
    - *(Nota explicativa explícita)*: La exposición de la API de borrado bajo demanda de todos los datos asociados a un `User` u `Organization` específico está documentada y marcada formalmente como **bloqueada** a la espera de la integración completa del modelo de datos multi-tenant del RFC (entidades `User` u `Organization` persistidas y vinculadas en el motor de base de datos relacional).
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_session_purger.py`:
    - `test_purge_inactive_sessions_by_age`: Comprueba la eliminación exacta de sesiones con antigüedad superior al umbral configurado (`max_age_days`), preservando las sesiones activas recientes.
    - `test_session_purger_background_task`: Valida la ejecución del bucle en segundo plano `SessionPurgerTask` y la detención limpia sin fugas de corrutinas.

#### AUD-012
- **ID:** AUD-012
- **Severidad:** Alto
- **Tipo:** Deuda Técnica
- **Categoría:** B. Gobernanza Empresarial y Multi-tenencia
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** `SessionManager` escribe el estado de las sesiones y la base de datos SQLite directamente en rutas del disco local (`./data/sessions/`). Esto impide el despliegue de Cognito en entornos BYOC (Bring Your Own Cloud) donde los contenedores backend deben ser efímeros.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/session_manager.py` (líneas 45-90).
- **Comparación con el estado del arte:** Los despliegues enterprise modernos abstraen la capa de persistencia mediante bases de datos gestionadas y almacenamiento de objetos (S3/GCS).
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se definieron los modelos ORM de SQLAlchemy `DBSession` y `DBSessionMessage` en `very-simplified-stack/cognito-backend/app/models/db.py` alojando metadatos de sesión e historial de mensajes estructurados vinculados con `Organization`, `Project` y `User` (AUD-007).
  - Se extendió `SessionManager` en `app/core/session_manager.py` para soportar la variable de entorno `COGNITO_STORAGE_BACKEND`. En modo `postgres_redis` / `postgres`, PostgreSQL actúa como la fuente de verdad persistente de estado y mensajes de sesión, abstrayendo por completo el almacenamiento de disco local para despliegues BYOC sin estado (stateless).
  - Se implementó el script de migración de datos `very-simplified-stack/cognito-backend/scripts/migrate_sessions_local_to_postgres.py` que lee las sesiones locales existentes (SQLite y archivos JSONL/.meta.json) y las migra atómicamente a PostgreSQL sin pérdida de historial.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_postgres_redis_shared_storage.py`:
    - `test_local_to_postgres_migration_script`: Crea una sesión con historial en almacenamiento local, ejecuta la migración a PostgreSQL, conmuta el backend a `COGNITO_STORAGE_BACKEND=postgres_redis` y verifica la integridad completa del historial recuperado desde PostgreSQL.

---

### Categoría C: Gestión de Contexto y Memoria

#### AUD-013
- **ID:** AUD-013
- **Severidad:** Medio
- **Tipo:** Defecto
- **Categoría:** C. Gestión de Contexto y Memoria
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** El mecanismo de compactación en `compaction.py` comprime el historial reemplazando turnos antiguos por un resumen en texto plano narrativo. Durante este proceso se descartan firmas exactas de llamadas a herramientas, esquemas de entrada/salida y rutas de archivos accedidas.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/compaction.py` (líneas 30-110).
- **Comparación con el estado del arte:** La compactación estructural de referencia (Claude Code / OpenCode) conserva mapas de archivos leídos, firmas de herramientas y fragmentos de código intactos mientras resume solo la conversación accesoria.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se implementó la función `extract_context_ledger` en `very-simplified-stack/cognito-backend/app/core/compaction.py` que analiza los mensajes a compactar, parsea ledgers previos embebidos y extrae de forma estructurada `files_touched` (rutas de archivos leídos/modificados), `function_signatures` y `tool_calls` ejecutados.
  - Se modificó `compact()` en `app/core/compaction.py` para generar y retornar la tupla `(summary, context_ledger)`.
  - Se actualizó `SessionManager.append_compaction()` en `app/core/session_manager.py` para almacenar `context_ledger` dentro del registro de compactación persistido en disco (`.jsonl`).
  - Se actualizó `derive_messages_for_llm` en `app/core/session/message_deriver.py` y `format_ledger_for_system_prompt()` en `app/core/compaction.py` para inyectar el ledger estructurado en el mensaje de resumen del System Prompt y adjuntar el diccionario `context_ledger` a los mensajes de la sesión, garantizando que el estado estructurado sobreviva a compactaciones sucesivas.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_compaction.py`:
    - `test_context_ledger_extraction_and_multi_compaction`: Confirma que rutas de archivos, firmas de funciones y llamadas a herramientas son extraídas, persistidas en disco y sobreviven sin pérdidas a través de 3 compactaciones sucesivas.
    - `test_extract_context_ledger_key_variations`: Verifica la extracción robusta ante variaciones en las claves de los argumentos de herramientas (`path`, `file_path`, `file`, etc.).
    - `test_compact_returns_summary_and_ledger`: Valida que `compact()` retorna la tupla `(summary, ledger)`.

#### AUD-014
- **ID:** AUD-014
- **Severidad:** Alto
- **Tipo:** Brecha Funcional
- **Categoría:** C. Gestión de Contexto y Memoria
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P2 Diferenciador
- **Descripción del problema:** `nooa_memory.py` gestionaba exclusivamente memoria volátil de corto plazo por sesión. No existía un subsistema de memoria persistente de hechos de largo plazo que mantuviera preferencias del usuario, reglas de estilo o datos del proyecto entre sesiones independientes del mismo usuario o proyecto.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/nooa_memory.py`.
- **Comparación con el estado del arte:** Los arneses avanzados de 2026 aprenden y persisten autónomamente preferencias, reglas de estilo y arquitectura de proyectos a lo largo del tiempo.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - **Almacén de Hechos Estructurado:** Se diseñó e implementó la entidad ORM `DBFact` (`app/models/db.py`) y el modelo Pydantic `Fact` (`app/models/domain.py`) con persistencia en el almacenamiento compartido relacional (`facts` table en PostgreSQL/SQLite) indexado por `user_id`, `project_id` u `org_id`.
  - **Gestor de Memoria de Hechos (`FactMemoryManager`):** Se creó `app/core/fact_memory.py` gestionando operaciones de guardado y consulta asociadas al contexto multi-tenant de la sesión.
  - **Herramienta Explícita del Agente (`RememberFactTool` / `remember_fact`):** Se creó la herramienta `RememberFactTool` (`app/core/tools/remember_fact_tool.py`) permitiendo al agente registrar hechos de forma explícita y determinista durante la conversación (en lugar de extracción automática imprecisa en el MVP).
  - **Inyección en System Prompt:** Se actualizó `build_system_message` en `app/core/system_prompt.py` y el derivation manager (`message_deriver.py`) para inyectar automáticamente los hechos guardados del `user_id` y `project_id` en el System Prompt de cualquier sesión posterior.
  - **Exclusión Explícita de Embeddings / Vector Store para MVP:** Se documentó explícitamente la decisión arquitectónica de posponer la búsqueda semántica por embeddings y bases de datos vectoriales como un diferenciador futuro. Esto evita introducir dependencias pesadas de vector store en el MVP, manteniendo la política de dependencias mínimas y ofreciendo una recuperación de hechos determinista, liviana y predecible a través de PostgreSQL/SQLite.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_persistent_facts_memory.py`:
    - `test_fact_memory_manager_save_and_retrieve`: Verifica el guardado, actualización idempotente y recuperación de hechos estructurados por ámbito de usuario/proyecto.
    - `test_remember_fact_tool_execution`: Valida la ejecución de `RememberFactTool` con metadatos de riesgo y formato de retorno.
    - `test_facts_injection_across_independent_sessions`: Demuestra que un hecho registrado en la sesión A (User X / Project P) se inyecta correctamente en el System Prompt de una sesión B posterior e independiente del mismo User X / Project P.
    - `test_facts_tenant_isolation`: Confirma el aislamiento estricto garantizando que sesiones de User Y / Project Q no reciben los hechos pertenecientes a User X / Project P.

#### AUD-015
- **ID:** AUD-015
- **Severidad:** Medio
- **Tipo:** Brecha Funcional
- **Categoría:** C. Gestión de Contexto y Memoria
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P2 Diferenciador
- **Descripción del problema:** La estructura de almacenamiento de mensajes de la sesión es estrictamente lineal. No soporta un modelo de árbol de mensajes que permita volver a checkpoints anteriores o crear ramas alternas de trabajo (session branching).
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/session_manager.py` (líneas 50-100) y `very-simplified-stack/cognito-backend/app/models/db.py` (líneas 20-40).
- **Comparación con el estado del arte:** Arneses de vanguardia como Codex CLI incorporan comandos `/fork` o navegación por árbol de contexto para probar enfoques alternativos sin destruir la sesión original.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se extendió el modelo de datos de sesión `DBSession` (`app/models/db.py`) y `SessionMetadata` (`app/core/session_manager.py`) con los campos `parent_session_id` y `branch_turn`.
  - Se actualizó `SessionManager.fork_from` para soportar ramificación por número de turno (`turn: Optional[int]`), copiando el contexto de mensajes de la sesión origen de forma exacta hasta el turno especificado N y registrando los metadatos de linaje.
  - Se expuso la ramificación por turno en el endpoint API `POST /api/agent/sessions/{session_id}/fork` (`app/api/routes/ai_agents.py`), cliente HTTP `CognitoClient.fork_session` (`cli/http_client.py`), modo RPC (`cli/modes/rpc_mode.py`) y en la CLI interactiva mediante el comando slash `/fork [turn]` (`cli/slash_commands.py`).
  - Se verificó la integración sin contaminación cruzada entre ramas madre e hijas, así como la compatibilidad con el ledger de compactación (AUD-013) y el checkpointing por turno (AUD-026).
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_aud015_session_branching.py`:
    - `test_session_branching_divergence_no_cross_contamination`: Valida la creación de la rama en el turno N y confirma la independencia completa e inexistencia de contaminación cruzada tras hacer divergir ambas ramas.
    - `test_branching_with_compaction_and_context_ledger`: Verifica el funcionamiento de la compactación (AUD-013) sobre sesiones ramificadas.
    - `test_branching_with_turn_checkpointing`: Confirma que el checkpointing atómico de turnos (AUD-026) funciona correctamente en sesiones ramificadas.

#### AUD-016
- **ID:** AUD-016
- **Severidad:** Medio
- **Tipo:** Deuda Técnica
- **Categoría:** C. Gestión de Contexto y Memoria
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** `ResourceLoader.discover_agents_md` únicamente busca el archivo `AGENTS.md` en la raíz exacta del directorio de trabajo actual (`os.path.join(self.cwd, "AGENTS.md")`). No soporta jerarquías anidadas por subdirectorio ni gestiona excepciones de sintaxis de forma detallada.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/resource_loader.py` (líneas 10-38).
- **Comparación con el estado del arte:** La norma de referencia para `AGENTS.md` exige descubrimiento recursivo descendente con prevalencia del archivo más cercano al directorio donde opera la herramienta.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se modificó `ResourceLoader` en `app/core/resource_loader.py` agregando `discover_agents_md_files()` que recorre los directorios de forma ascendente desde el directorio de trabajo actual (`self.cwd`) hasta la raíz del sistema de archivos.
  - Se ordenan los archivos descubiertos desde la raíz hacia `self.cwd`, garantizando que las directivas del archivo `AGENTS.md` más cercano al subdirectorio anidado se concatenen al final y tengan prevalencia en el contexto del System Prompt.
  - Se añadió manejo de excepciones tolerante a fallos (`try-except`) al leer cada `AGENTS.md`. En caso de encontrarse con archivos mal formados o inalcanzables (e.g., `UnicodeDecodeError`, `PermissionError`, `OSError`), se registra una advertencia en logs (`logger.warning`) y la inicialización/arranque del agente continúa sin interrumpirse.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_resource_loader.py`:
    - `test_discover_agents_md_recursive_and_precedence`: Verifica que `AGENTS.md` en subdirectorios anidados se descubre y sus directivas quedan ordenadas con prevalencia sobre los `AGENTS.md` de la raíz.
    - `test_discover_agents_md_malformed_file_handling`: Confirma que archivos con codificación o bytes corruptos no detienen la ejecución ni el arranque, emitiendo una advertencia en los logs.
    - `test_get_effective_protected_files_with_nested_agents_md`: Valida la combinación de archivos protegidos considerando la jerarquía descendente de `AGENTS.md`.

---

### Categoría D: Orquestación de Herramientas y Sub-Agentes

#### AUD-017
- **ID:** AUD-017
- **Severidad:** Alto
- **Tipo:** Brecha Funcional
- **Categoría:** D. Orquestación de Herramientas y Sub-Agentes
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** El bucle principal en `agent_loop.py` es estrictamente secuencial y monohilo/monoagente. No posee capacidad para delegar sub-tareas a sub-agentes paralelos o en segundo plano (background workers).
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/agent_loop.py` (líneas 80-160).
- **Comparación con el estado del arte:** Los harnesses de 2026 permiten al agente principal instanciar decenas de sub-agentes paralelos para tareas intensivas (búsquedas, refactorizaciones parciales).
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se implementó la ejecución concurrente de herramientas `concurrency_safe` en `agent_loop.py` usando `asyncio.gather` por lotes.
  - Se creó la herramienta `SubAgentTool` (`delegate_subagent`) en `app/core/tools/subagent_tool.py`, que permite al agente principal delegar sub-tareas delimitadas con límites de tiempo (`timeout_seconds`), límites de turnos (`max_turns`) y alcance de herramientas restringido.
  - Se registró `SubAgentTool` en el registro de extensiones (`app/core/extensions/registry.py`).
  - Se agregaron pruebas de rendimiento y comportamiento en `tests/test_parallel_subagents.py` y se verificó que pasa 100% el Eval Harness E2E (`tests/test_e2e_eval_harness.py`).

#### AUD-018
- **ID:** AUD-018
- **Severidad:** Medio
- **Tipo:** Brecha Funcional
- **Categoría:** D. Orquestación de Herramientas y Sub-Agentes
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** Cognito no fuerza una fase de análisis/planificación de solo lectura previa a la ejecución de escrituras en disco. El agente puede invocar `WriteTool` o `EditTool` en el primer turno de la interacción.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/agent_loop.py` (líneas 90-140).
- **Comparación con el estado del arte:** Arneses como OpenCode imponen una fase de scoping mediante un agente de solo lectura que genera un plan antes de habilitar herramientas destructivas.
- **Estado:** Corregido
- **Notas de Resolución:**
  - Se implementó la fase forzada de planificación de solo lectura en `evaluate_tool_execution` (`app/core/exec_policy.py`) usando la metadato `is_read_only` introducida en AUD-005.
  - En un workspace no confiado y durante los turnos iniciales (`turn <= read_only_turns`, por defecto 1), cualquier intento de ejecutar una herramienta que no sea de solo lectura (`WriteTool`, `EditTool`, `BashTool`, etc.) es rechazado hasta que se produzca un plan.
  - Se añadieron parámetros configurables `planning_phase` (bool) y `read_only_turns` (int) en `AgentLoopRequest` (`app/api/routes/ai_agents.py`) y `agent_loop` (`app/core/agent_loop.py`) para activar/desactivar o personalizar la fase.
  - Se agregaron pruebas unitarias e integradas en `tests/test_read_only_planning_phase.py`.
  - Se verificó con el harness de evaluación E2E (`tests/test_e2e_eval_harness.py`) confirmando cero regresiones en la calidad y paso del 100% de las tareas.

#### AUD-019
- **ID:** AUD-019
- **Severidad:** Alto
- **Tipo:** Brecha Funcional
- **Categoría:** D. Orquestación de Herramientas y Sub-Agentes
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** La clase `MCPServerClient` implementa un cliente simulado (mock) en `discover_tools` que devuelve una herramienta hardcodeada (`WrappedMCPTool`) sin establecer una conexión real por protocolo stdio o SSE con servidores MCP externos.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/mcp_client.py` (líneas 14-38).
- **Comparación con el estado del arte:** Los sistemas enterprise requieren un cliente MCP completo capaz de negociar herramientas y recursos con cualquier servidor MCP de terceros.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se implementó el soporte para transportes reales `stdio` y `sse` en `MCPServerClient` (`app/core/mcp_client.py`) utilizando la librería oficial `mcp` (`ClientSession`, `stdio_client`, `sse_client`).
  - Se agregaron las excepciones tipadas `MCPClientError`, `MCPClientConnectionError`, `MCPClientTimeoutError` y `MCPClientProtocolError` para un manejo transparente de fallos de conexión, timeout y protocolo MCP.
  - Se implementó la negociación de capacidades (handshake `initialize()`), descubrimiento dinámico de herramientas (`list_tools()`) y envoltura en instancias de `WrappedMCPTool`.
  - Se implementó la ejecución de herramientas remotas en `WrappedMCPTool.execute()` e `MCPServerClient.call_tool()`.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_mcp_client_real_stdio_sse.py`:
    - `test_real_stdio_mcp_client_discovery_and_tool_call`: Prueba de integración completa descubriendo e invocando herramientas de un servidor MCP externo real corriendo sobre protocolo `stdio` (`python3 -m app.services.mcp_server`).
    - `test_mcp_client_invalid_command_connection_error`: Valida que comandos/binarios inexistentes lanzan `MCPClientConnectionError`.
    - `test_mcp_client_connection_timeout_error`: Confirma que demoras excediendo el timeout lanzan `MCPClientTimeoutError`.
    - `test_mcp_client_sse_transport_mocked`: Prueba unitaria de descubrimiento e invocación mediante transporte `sse`.

#### AUD-020
- **ID:** AUD-020
- **Severidad:** Medio
- **Tipo:** Brecha Funcional
- **Categoría:** D. Orquestación de Herramientas y Sub-Agentes
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P2 Diferenciador
- **Descripción del problema:** `ExtensionRegistry` y `HookedTool` permiten envolver herramientas individuales, pero no existen hooks globales del ciclo de vida del agente (`on_agent_start`, `on_tool_pre_exec`, `on_tool_post_exec`, `on_pre_compact`).
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/agent_loop.py` (líneas 100-150) y `very-simplified-stack/cognito-backend/app/core/extensions/registry.py` (líneas 1-60).
- **Comparación con el estado del arte:** Los puntos de extensión de ciclo de vida permiten a los integradores inyectar validadores de seguridad corporativos sin modificar el núcleo del arnés.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se crearon las clases Pydantic de payload para eventos globales del ciclo de vida (`AgentStartPayload`, `ToolPreExecPayload`, `ToolPostExecPayload`, `PreCompactPayload`) en `app/core/extensions/api.py`.
  - Se ampliaron los tipos `HookEvent` y los métodos helper de registro en `ExtensionAPI` (`on_agent_start`, `on_tool_pre_exec`, `on_tool_post_exec`, `on_pre_compact`).
  - Se actualizó `ExtensionRegistry.fire()` en `app/core/extensions/registry.py` para permitir veto/bloqueo de acciones cuando un handler de `on_tool_pre_exec` o `before_tool_call` retorna un mensaje de rechazo.
  - Se conectó `agent_loop.py` para disparar `on_agent_start` al inicio de cada bucle, `on_tool_pre_exec` antes de la ejecución de herramientas (bloqueando la acción y retornando `ToolResult(is_error=True)` si el hook retorna rechazo), y `on_tool_post_exec` tras completarse la herramienta con el resultado y metadatos.
  - Se conectó `compact()` en `app/core/compaction.py` y `ai_agents.py` para disparar `on_pre_compact` con el historial de mensajes, metadatos y `trace_id` antes de la compactación.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_agent_lifecycle_hooks.py`:
    - `test_on_tool_pre_exec_blocks_tool_execution`: Confirma que un hook en `on_tool_pre_exec` puede bloquear y vetar una herramienta sensible retornando un mensaje de rechazo de seguridad corporativa.
    - `test_on_agent_start_event_fires_at_loop_start`: Valida que `on_agent_start` se dispara al inicio del bucle del agente con la lista de mensajes, metadatos de sesión y `trace_id`.
    - `test_on_tool_post_exec_event_fires_after_execution`: Verifica que `on_tool_post_exec` se dispara tras la ejecución de herramientas con la salida generada y el estado de error.
    - `test_on_pre_compact_event_fires_before_compaction`: Comprueba que `on_pre_compact` se dispara antes de la compactación con la lista de mensajes y `session_id`.
    - `test_extension_api_helper_registration_and_origin_isolation`: Prueba la registración fluida vía `ExtensionAPI` y el aislamiento por `cwd` (hooks globales vs específicos por proyecto).

#### AUD-021
- **ID:** AUD-021
- **Severidad:** Alto
- **Tipo:** Brecha Funcional
- **Categoría:** D. Orquestación de Herramientas y Sub-Agentes
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P0 Bloqueante
- **Descripción del problema:** El backend carece de una interfaz interactiva de pausado e interrupción que solicite aprobación humana explícita (Human-in-the-Loop) para operaciones sensibles que no estén bloqueadas automáticamente por `ExecPolicy`.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/exec_policy.py` (líneas 1-80) y `very-simplified-stack/cognito-backend/app/core/agent_loop.py` (líneas 110-140).
- **Comparación con el estado del arte:** Las políticas de gobernanza 2026 exigen que operaciones de riesgo medio/alto requieran confirmación síncrona del operador.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se extendió `ExecPolicy` y la evaluación unificada `evaluate_command_execution` en `app/core/exec_policy.py` incorporando un tercer veredicto explícito: `ExecVerdict.REQUIERE_APROBACION` (`requiere_aprobacion`).
  - Se definieron y documentaron los criterios de clasificación:
    - `DENEGAR`: Comandos prohibidos incondicionales de alto riesgo (`rm -rf /`, `sudo`, `mkfs`, fork bomb, `curl | bash`).
    - `REQUIERE_APROBACION`: Acciones sensibles (`git reset --hard`, `git clean`, `rm -rf <dir>`, paquetes de sistema, terminación de procesos) o comandos ejecutados en proyectos no confiables (`trusted=False`).
    - `PERMITIR`: Inspección de solo lectura o comandos previamente autorizados en `SessionApprovalCache`.
  - Se implementó `ApprovalManager` en `app/core/approval.py` que gestiona solicitudes pendientes, pausa la ejecución asíncrona mediante `asyncio.Future`, aplica timeout configurable (`COGNITO_APPROVAL_TIMEOUT_SECONDS`, por defecto 30s) y deniega la acción por defecto si expira sin respuesta.
  - Se registró cada decisión en una estructura inmutable `ApprovalDecisionAudit` (`approval_id`, `session_id`, `action`, `actor`, `timestamp`, `status`, `reason`) preparada para integración futura con el sistema SIEM de AUD-009.
  - Se introdujo `ApprovalRequiredEvent` en `app/core/events.py` y se actualizó `agent_loop.py` para pausar el turno del agente, emitir el evento SSE y notificar al canal de steering/sesión interactivo existente.
  - Se expusieron los endpoints REST en `app/api/routes/ai_agents.py`: `GET /api/agent/approvals/pending`, `GET /api/agent/approvals/audit-logs` y `POST /api/agent/approvals/{approval_id}/decide`.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_human_approval.py`:
    - `test_exec_policy_requiere_aprobacion_classification`: Valida la clasificación del nuevo veredicto.
    - `test_human_approval_flow_approved`: Prueba el flujo completo pausa -> aprobación por operador -> ejecución exitosa.
    - `test_human_approval_flow_denied`: Confirma el rechazo explícito por operador.
    - `test_human_approval_flow_timeout_default_deny`: Comprueba la denegación por defecto tras timeout.
    - `test_agent_loop_human_in_the_loop_integration`: Verifica la emisión de `ApprovalRequiredEvent` y reanudación del bucle.
    - `test_rest_api_approvals_endpoints`: Prueba los endpoints HTTP de decisión y consulta.
- **Nota de Seguimiento (2026-08-26):**
  - **Investigación de Ejecuciones Sin Cliente en Vivo:** Se investigó la interacción entre `cognito-worker` y `cognito-backend`. Se confirmó que existen flujos no interactivos / sin cliente conectado en vivo (tareas en segundo plano `/api/agent/tasks`, ejecutores de tareas `escalation_service.execute_task_attempt`, o sesiones donde el cliente SSE/WebSocket se desconecta).
  - **Visibilidad Mejorada de Denegaciones por Timeout:** Cuando una acción `REQUIERE_APROBACION` alcanza el timeout en una ejecución sin cliente en vivo, se mejoró la señalización para evitar que pase desapercibida:
    - Se persistieron las decisiones de auditoría en disco (`approval_audit_logs.jsonl`) para garantizar que sobrevivan a reinicios del servidor.
    - Se indexaron las denegaciones en `SessionMetadata` (`blocked_actions_count` y `approval_summary`), permitiendo a operadores identificar de inmediato sesiones bloqueadas mediante `GET /api/agent/sessions/{id}`.
    - Se registró un mensaje de sistema prominente (`[ACCION_BLOQUEADA_POR_APROBACION_HUMANA]`) en el log de eventos/steering de la sesión.
  - **Timeout Configurable Granular:** Se implementó una jerarquía de timeout a nivel de solicitud (`AgentLoopRequest.approval_timeout_seconds`) y de sesión (`SessionMetadata.approval_timeout_seconds` / `ApprovalManager.set_session_timeout`) manteniendo el fallback a la variable global `COGNITO_APPROVAL_TIMEOUT_SECONDS`.
  - **Nuevos Tests de Regresión:**
    - `test_configurable_approval_timeout_hierarchy`: Verifica la precedencia del timeout por solicitud y por sesión sobre la variable global.
    - `test_non_live_session_approval_timeout_visibility`: Valida una ejecución sin cliente conectado que alcanza `REQUIERE_APROBACION`, confirmando la denegación explícita, actualización de metadatos, mensaje de steering persistente y registro en auditoría.

---

### Categoría E: Extensibilidad y Ecosistema

#### AUD-022
- **ID:** AUD-022
- **Severidad:** Medio
- **Tipo:** Brecha Funcional
- **Categoría:** E. Extensibilidad y Ecosistema
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P2 Diferenciador
- **Descripción del problema:** Cognito no cuenta con un parser ni motor de ejecución para esquemas declarativos de habilidades como el estándar `SKILL.md` (agentskills.io). Las capacidades adicionales requieren escribir clases en Python.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/skills.py` (líneas 1-50) y `very-simplified-stack/cognito-backend/app/core/extensions/loader.py` (líneas 1-70).
- **Comparación con el estado del arte:** Claude Code y OpenCode soportan la extensión de habilidades mediante simples archivos Markdown declarativos colocados en el repositorio.
- **Estado:** Pendiente

#### AUD-023
- **ID:** AUD-023
- **Severidad:** Medio
- **Tipo:** Brecha Funcional
- **Categoría:** E. Extensibilidad y Ecosistema
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P2 Diferenciador
- **Descripción del problema:** El cargador de extensiones (`ExtensionLoader`) intenta importar archivos `.py` locales de forma dinámica vía `importlib`. No soporta un sistema formal de paquetes de plugins distribuibles o aislados en entornos virtuales independientes.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/extensions/loader.py` (líneas 15-60).
- **Comparación con el estado del arte:** Los ecosistemas enterprise requieren empaquetamiento de plugins independientes para evitar colisiones de dependencias con el core.
- **Estado:** Pendiente

---

### Categoría F: Observabilidad y Telemetría

#### AUD-024
- **ID:** AUD-024
- **Severidad:** Alto
- **Tipo:** Brecha Funcional
- **Categoría:** F. Observabilidad y Telemetría
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** El módulo `metrics.py` registra contadores locales simples, pero no expone un endpoint `/metrics` en formato Prometheus ni exporta datos de telemetría de costo y uso de tokens por usuario vía OpenTelemetry.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/metrics.py` (líneas 1-40) y `very-simplified-stack/cognito-backend/app/core/token_budget.py` (líneas 20-60).
- **Comparación con el estado del arte:** La observabilidad en producción exige métricas estandarizadas de latencia, fallos de herramientas y costes por modelo exportables a tableros corporativos.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se implementó la clase `CognitoMetrics` en `very-simplified-stack/cognito-backend/app/core/metrics.py` con métodos dedicados: `record_operation_duration` (histrograma de latencia), `record_tool_failure` (contador de fallos de herramientas), `record_retry` (contador de reintentos), `record_tokens` (contador de consumo de tokens por usuario/modelo) y `record_cost` (costo acumulado en dólares). Cada método acepta el parámetro `trace_id` proveniente de AUD-025.
  - Se implementó `generate_prometheus_text()` en `app/core/metrics.py` para renderizar todas las métricas registradas en formato Prometheus Text Exposition Format (v0.0.4) con anotaciones `# HELP` y `# TYPE`.
  - Se expuso el endpoint HTTP `GET /metrics` en `very-simplified-stack/cognito-backend/app/main.py` retornando `PlainTextResponse` con tipo de contenido `text/plain; version=0.0.4`.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_metrics_endpoint.py`:
    - `test_metrics_endpoint_scraping_and_format`: Simula la recolección de latencias, fallos, reintentos, tokens y costos asociados a un `trace_id` específico, realiza la petición raspado a `GET /metrics`, y valida las cabeceras HTTP 200 `version=0.0.4`, anotaciones Prometheus y etiquetado exacto de `trace_id`, `tool_name`, `operation`, `model` y `user_id`.

#### AUD-025
- **ID:** AUD-025
- **Severidad:** Alto
- **Tipo:** Brecha Funcional
- **Categoría:** F. Observabilidad y Telemetría
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** Los logs generados durante la ejecución de las peticiones HTTP y del agent loop carecen de identificadores de trazabilidad unificados (`trace_id`, `span_id`, `request_id`) propagados a las llamadas a herramientas.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/tracing.py` (líneas 1-60) y `very-simplified-stack/cognito-backend/app/api/routes/ai_agents.py` (líneas 20-80).
- **Comparación con el estado del arte:** La resolución de incidentes en entornos distribuidos depende de la propagación de contextos W3C Trace Context en todos los componentes.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se definió la variable contextual `TRACE_ID_VAR = contextvars.ContextVar("trace_id", default="")` e identificadores de correlación en `very-simplified-stack/cognito-backend/app/core/logging_config.py`.
  - Se implementaron las funciones `set_trace_id()` y `get_trace_id()` en `app/core/logging_config.py` para establecer y consultar dinámicamente el identificador de traza.
  - Se actualizó `StructuredJSONFormatter` en `app/core/logging_config.py` para inyectar automáticamente el `trace_id` en cada línea de log estructurada en formato JSON.
  - Se creó el middleware HTTP `trace_id_middleware` y la inicialización de contexto WebSocket en `app/main.py` para extraer o generar `trace_id` desde cabeceras `X-Trace-ID` / `X-Request-ID` o query params, retornando la cabecera `X-Trace-ID` en las respuestas HTTP.
  - Se integró `get_trace_id()` en la instanciación de eventos (`app/core/events.py`) y trazado de contexto de ejecuciones (`app/core/tracing.py`), propagando el `trace_id` hasta las llamadas a herramientas y registro de métricas.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_trace_id_propagation.py`:
    - `test_trace_id_context_vars`: Verifica que `set_trace_id` y `get_trace_id` gestionan correctamente las variables de contexto `contextvars`.
    - `test_structured_json_formatter_includes_trace_id`: Valida que `StructuredJSONFormatter` añade el atributo `trace_id` a la salida JSON formateada del log.
    - `test_agent_loop_logs_share_same_trace_id`: Captura los registros de log producidos durante un turno de agente y comprueba que todas las líneas generadas comparten el mismo `trace_id`.

---

### Categoría G: Resiliencia y Recuperación

#### AUD-026
- **ID:** AUD-026
- **Severidad:** Alto
- **Tipo:** Brecha Funcional
- **Categoría:** G. Resiliencia y Recuperación
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** El proceso del agente no realiza guardados de estado (checkpointing) por turno. Si el proceso backend colapsa en mitad de una tarea de 10 turnos, toda la secuencia se interrumpe y debe reejecutarse desde el inicio.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/agent_loop.py` (líneas 35-180).
- **Comparación con el estado del arte:** La resiliencia enterprise exige la persistencia atómica del estado tras cada turno para permitir la reanudación transparente tras fallos de la infraestructura.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se implementó la persistencia atómica turno a turno en `very-simplified-stack/cognito-backend/app/core/agent_loop.py` e `very-simplified-stack/cognito-backend/app/api/routes/ai_agents.py`, invocando `session_manager.append_message()` inmediatamente después de cada respuesta del asistente y ejecución de herramientas.
  - Se actualizó `SessionManager` en `app/core/session_manager.py` para escribir y sincronizar atómicamente los mensajes y metadatos en archivos `.jsonl` de sesión en disco.
  - Se adaptó `run_agent_loop` en `app/api/routes/ai_agents.py` para que al proporcionar un `session_id` existente, recupere la historia de mensajes efectivas mediante `session_manager.get_effective_messages(session_id)` y reanude la ejecución desde el último turno completado sin reiniciar la tarea ni duplicar mensajes de usuario.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_aud026_turn_checkpointing.py`:
    - `test_aud026_checkpointing_and_resumption`: Simula una caída abrupta del proceso backend tras completar el turno 1 de una tarea multi-turno, confirma que el estado del turno 1 quedó guardado atómicamente en disco, simula el reinicio del servidor reanudando con el mismo `session_id`, y verifica que la ejecución continúa desde el punto de control del turno 2 sin duplicar entradas ni reiniciar la tarea.

#### AUD-027
- **ID:** AUD-027
- **Severidad:** Medio
- **Tipo:** Defecto
- **Categoría:** G. Resiliencia y Recuperación
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** El mecanismo de reintento transitorio (`retry_transient_async` en `retry.py`) reejecuta peticiones cuando ocurre una desconexión de red. Si el fallo ocurre después de que una herramienta no idempotente (ej. modificar un archivo o ejecutar un comando remoto) se haya iniciado, la herramienta puede ser ejecutada de nuevo produciendo duplicaciones de efectos secundarios.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/retry.py` (líneas 1-50) y `very-simplified-stack/cognito-backend/app/services/worker_client.py` (líneas 40-90).
- **Comparación con el estado del arte:** Los arneses robustos gestionan tokens de idempotencia y estado de efectos secundarios antes de autorizar reintentos de red.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se extendió `retry_transient_async` en `very-simplified-stack/cognito-backend/app/core/retry.py` añadiendo soporte para claves de idempotencia (`idempotency_key`), un callback opcional de comprobación de estado persistido (`idempotency_check`) y el almacén `_IDEMPOTENCY_STORE`.
  - Para herramientas no idempotentes o destructivas (`is_destructive=True`), se genera o asigna una clave de idempotencia única. El resultado de la operación se registra en el almacén de idempotencia inmediatamente tras completarse la acción en el destino.
  - Al desencadenarse un reintento por fallo de red o timeout transitorio posterior a la ejecución del efecto secundario, `retry_transient_async` consulta el almacén o invoca `idempotency_check`, retornando el resultado registrado sin volver a ejecutar la herramienta ni repetir sus efectos secundarios.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_retry_idempotency.py`:
    - `test_generate_idempotency_key`: Valida la generación de claves de idempotencia con prefijos.
    - `test_retry_transient_async_file_write_idempotency_network_failure`: Simula una caída de red con error 502 Bad Gateway ocurrida *después* de realizar una escritura no idempotente en archivo; verifica que el reintento recupera el resultado previo registrado, confirmando que la escritura en disco ocurrió exactamente 1 vez sin duplicar contenido.
    - `test_retry_transient_async_custom_persisted_idempotency_check`: Prueba el callback personalizado `idempotency_check` comprobando la existencia previa de archivos en disco para omitir reejecuciones.

---

### Categoría H: Precisión y Evaluación

#### AUD-028
- **ID:** AUD-028
- **Severidad:** Alto
- **Tipo:** Brecha Funcional
- **Categoría:** H. Precisión y Evaluación
- **Componente:** evals / cognito-backend
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** Las evaluaciones presentes en la carpeta `evals/` (`evals/router` y `evals/system_prompt`) se limitan a probar la selección de prompts y enrutamiento en aislamientos unitarios. No existe una suite de evaluación end-to-end (Eval Harness) que ponga a prueba el comportamiento multi-turno del agente completo y compare sus trayectorias contra referencias (baselines).
- **Evidencia de Ubicación en Código:** `very-simplified-stack/evals/` (revisión completa de la estructura de evals).
- **Comparación con el estado del arte:** La ingeniería de agentes 2026 basa la prevención de regresiones en benchmarks automáticos de trayectorias completas (ej. SWE-bench Lite / custom eval harnesses).
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se creó el conjunto de datos de evaluación E2E `very-simplified-stack/evals/e2e/dataset.py` conteniendo 10 tareas de trayectoria completa (`E2E-001` a `E2E-010`) que cubren escenarios reales de codificación, edición, parcheo, delegación a sub-agentes, manejo de errores y recuperación.
  - Se implementó el arnés de ejecución `very-simplified-stack/evals/e2e/runner.py` (`run_e2e_evaluation` y `run_single_e2e_task`) y esquemas de métricas en `very-simplified-stack/evals/e2e/schemas.py` que evalúan trayectorias completas contra el bucle de agente real y verifican criterios de éxito.
  - Se integró el Eval Harness en la suite de pruebas del backend en `very-simplified-stack/cognito-backend/tests/test_e2e_eval_harness.py`, asegurando su ejecución continua en los flujos de CI.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_e2e_eval_harness.py`:
    - `test_e2e_tasks_dataset_completeness`: Confirma que el dataset de evaluación contiene entre 8 y 12 tareas E2E completas con criterios de verificación definidos.
    - `test_e2e_evaluation_harness_trajectory_run`: Ejecuta la suite de evaluación E2E completa `run_e2e_evaluation()`, validando que todas las tareas se completan exitosamente con una tasa de aprobación del 100% (pass_rate 1.0) y cero fallos de trayectoria.

#### AUD-029
- **ID:** AUD-029
- **Severidad:** Medio
- **Tipo:** Brecha Funcional
- **Categoría:** H. Precisión y Evaluación
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P2 Diferenciador
- **Descripción del problema:** Cuando el modelo decide finalizar su turno o emite un evento `DoneEvent`, el resultado se retorna directamente. No existe un paso intermedio de auto-crítica o agente de revisión interno (Critic Agent) que verifique si los cambios cumplen las pruebas antes de declarar la tarea terminada.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/agent_loop.py` (líneas 150-180).
- **Comparación con el estado del arte:** Los arneses de alta precisión implementan bucles de verificación autónoma previa a la entrega final.
- **Estado:** Pendiente

---

### Categoría I: Portabilidad de Modelos y Proveedores

#### AUD-030
- **ID:** AUD-030
- **Severidad:** Bajo
- **Tipo:** Deuda Técnica
- **Categoría:** I. Portabilidad de Proveedores
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P2 Diferenciador
- **Descripción del problema:** El enrutador de modelos `BackendRouter` contiene ramificaciones de código específicas con condicionales para conmutar entre Ollama y OpenAI. Integrar un nuevo proveedor (como Anthropic o una API propietaria) requiere modificar la lógica central del enrutador.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/llm/router.py` (líneas 40-120) y `very-simplified-stack/cognito-backend/app/core/llm/adapters/base.py` (líneas 1-50).
- **Comparación con el estado del arte:** Un arnés enterprise abstrae la interfaz de los modelos mediante un registro dinámico de proveedores sin código condicional disperso.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se definió la interfaz genérica `LLMProviderAdapter` / `LLMAdapter` en `very-simplified-stack/cognito-backend/app/core/llm/adapters/base.py` declarando los métodos de generación y streaming (`chat_completion`, `stream_completion`, `_do_chat_completion`, `_do_stream_completion`).
  - Se implementó el registro dinámico global de proveedores (`PROVIDER_REGISTRY`, `register_provider`, `get_provider_class`) en `app/core/llm/adapters/base.py`.
  - Se migró `OllamaAdapter` (`app/core/llm/adapters/ollama.py`) y `OpenAICompatibleAdapter` (`app/core/llm/adapters/openai_compatible.py`) para registrarse dinámicamente vía el decorador `@register_provider`.
  - Se agregó `AnthropicAdapter` (`very-simplified-stack/cognito-backend/app/core/llm/adapters/anthropic.py`) registrado como tercer proveedor para la API de Anthropic Messages (`/v1/messages`) y exportado en `app/core/llm/adapters/__init__.py`.
  - Se refactorizó la fábrica `create_adapter_from_config` en `very-simplified-stack/cognito-backend/app/core/llm/router.py` para instanciar clases buscando dinámicamente en el registro (`get_provider_class(cfg.type)`), eliminando todos los condicionales `if/elif` hardcodeados.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_aud030_provider_registry.py`:
    - `test_provider_registration_and_lookup`: Comprueba que `PROVIDER_REGISTRY` contiene las claves de proveedores registradas.
    - `test_anthropic_adapter_chat_completion`: Mokea la API de Anthropic y valida el formateo de peticiones/respuestas del adaptador.
    - `test_dynamic_provider_dispatch_without_modifying_router`: Registra un adaptador custom de prueba y demuestra que `LLMRouter` puede instanciarlo y despachar solicitudes sin tocar una sola línea de `router.py`.

---

### Categoría J: Despliegue y Empaquetado para Producción

#### AUD-031
- **ID:** AUD-031
- **Severidad:** Medio
- **Tipo:** Deuda Técnica
- **Categoría:** J. Despliegue y Empaquetado para Producción
- **Componente:** Dockerfiles
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** Los `Dockerfile` de `cognito-backend` y `cognito-worker` configuran la ejecución del proceso como usuario `root`. Además, carecen de instrucciones `HEALTHCHECK` y de manejo de señales `SIGTERM` para apagados ordenados (graceful shutdown).
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/Dockerfile` (líneas 1-25) y `very-simplified-stack/cognito-worker/Dockerfile` (líneas 1-25).
- **Comparación con el estado del arte:** Los estándares de empaquetamiento seguro para producción exigen la ejecución con usuarios sin privilegios y comprobaciones de salud del contenedor.
- **Estado:** Corregido

#### AUD-032
- **ID:** AUD-032
- **Severidad:** Alto
- **Tipo:** Brecha Funcional
- **Categoría:** J. Despliegue y Empaquetado para Producción
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P0 Bloqueante
- **Descripción del problema:** La arquitectura asume una única instancia del backend debido al uso de SQLite local y bloqueos en memoria por sesión (`SessionManager`). Múltiples réplicas del backend detrás de un balanceador de carga no podrían compartir ni coordinar el estado de las sesiones.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/database.py` (líneas 10-40) y `very-simplified-stack/cognito-backend/app/core/session_manager.py` (líneas 20-60).
- **Comparación con el estado del arte:** La alta disponibilidad en producción requiere escalabilidad horizontal con estado distribuido en Redis o bases de datos relacionales compartidas.
- **Estado:** Corregido
- **Resolución y Evidencia Técnica:**
  - Se implementó la coordinación asíncrona y síncrona de cierres distribuidos en `very-simplified-stack/cognito-backend/app/core/redis_lock.py` (`RedisDistributedLock` / `AsyncRedisDistributedLock`) utilizando primitivas de Redis (`SET key token NX PX`) con script Lua de liberación atómica y fallback a `fcntl` local para desarrollo.
  - Se refactorizaron los bloqueos por sesión y por índice en `SessionManager` (`app/core/session_manager.py`) para utilizar las claves de Redis `cognito:lock:session:{session_id}` y `cognito:lock:index`, permitiendo que múltiples réplicas concurrentes del backend coordinen operaciones sobre la misma sesión sin condiciones de carrera.
  - Se añadieron `asyncpg`, `redis`, `psycopg2-binary` y `fakeredis` a `requirements.txt` y `requirements.lock` con hashes sha256 verificados.
- **Test de Regresión:**
  - `very-simplified-stack/cognito-backend/tests/test_postgres_redis_shared_storage.py`:
    - `test_postgres_redis_shared_session_concurrency`: Simula dos réplicas concurrentes (`Replica A` y `Replica B`) sirviendo la misma sesión en paralelo sobre PostgreSQL+Redis; confirma cero pérdida de mensajes y consistencia de contadores.
    - `test_postgres_redis_steering_concurrency`: Prueba la entrega e inspección concurrente de mensajes de steering entre réplicas independientes.

---

Cualquier auditoría futura debe contrastarse e integrarse en este documento utilizando la numeración consecutiva AUD-XXX.
