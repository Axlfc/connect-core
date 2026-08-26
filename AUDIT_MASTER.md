# AUDIT_MASTER.md — Auditoría Enterprise de Cognito

## 1. Encabezado y Resumen Ejecutivo

- **Alcance del Documento:** Auditoría exhaustiva basada al 100% en evidencia de código del repositorio Cognito (`cognito-backend`, `cognito-worker`, y `cognito_agent.py`). Evaluado frente al listón de referencia enterprise 2026 para agent harnesses (características de referencia observadas en harnesses como Claude Code, Codex CLI, OpenCode, Hermes Agent, Pi Agent y OpenClaw).
- **Metodología Aplicada:** Inspección estática del código fuente y suite de pruebas de los componentes backend, worker y CLI. Contrastación directa de cada directiva del listón de referencia A-J contra la implementación real o la evidencia de ausencia en las rutas de código del repositorio.
- **Resumen Cuantitativo de Hallazgos:**
  - **Total de Hallazgos:** 32
  - **Desglose por Severidad:** Crítico: 6 | Alto: 12 | Medio: 10 | Bajo: 4
  - **Desglose por Tipo:** Defecto: 4 | Deuda Técnica: 9 | Brecha Funcional: 19
  - **Desglose por Categoría (A-J):**
    - A. Seguridad y Aislamiento de Ejecución: 6 hallazgos
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
| AUD-001 | Crítico | Defecto | A. Seguridad y Aislamiento | P0 Bloqueante | cognito-backend | BashTool ejecuta comandos directamente en la shell del host sin aislamiento microVM ni bwrap obligatorio | Pendiente |
| AUD-002 | Alto | Brecha Funcional | A. Seguridad y Aislamiento | P0 Bloqueante | cognito-backend / CLI | Ausencia de política de red outbound deny-all por defecto en subprocesos | Pendiente |
| AUD-003 | Alto | Deuda Técnica | A. Seguridad y Aislamiento | P0 Bloqueante | cognito-backend | Almacenamiento plano de secreto de autenticación MCP sin rotación/revocación dinámica | Pendiente |
| AUD-004 | Crítico | Defecto | A. Seguridad y Aislamiento | P0 Bloqueante | cognito-backend | Falta de validación de Origin header y protección CSRF/CORS en conexiones HTTP/WebSocket MCP | Pendiente |
| AUD-005 | Medio | Brecha Funcional | A. Seguridad y Aislamiento | P1 Esperado | cognito-backend | Ausencia de metadatos de comportamiento (read-only/destructive/concurrency) en esquema de herramientas | Pendiente |
| AUD-006 | Medio | Deuda Técnica | A. Seguridad y Aislamiento | P1 Esperado | cognito-backend / worker | Rango abierto de dependencias Python sin lockfile con hashes integrados | Pendiente |
| AUD-007 | Crítico | Brecha Funcional | B. Gobernanza y Multi-tenencia | P0 Bloqueante | cognito-backend | Ausencia de modelo de datos multi-tenant (Org / Tenant / User) | Pendiente |
| AUD-008 | Crítico | Brecha Funcional | B. Gobernanza y Multi-tenencia | P0 Bloqueante | cognito-backend | Inexistencia de autenticación SSO/SAML/OIDC para operadores humanos | Pendiente |
| AUD-009 | Crítico | Brecha Funcional | B. Gobernanza y Multi-tenencia | P0 Bloqueante | cognito-backend | Inexistencia de audit log estructurado exportable hacia sistemas SIEM | Pendiente |
| AUD-010 | Alto | Brecha Funcional | B. Gobernanza y Multi-tenencia | P1 Esperado | cognito-backend | Control de presupuesto de tokens restringido al ámbito de sesión individual | Pendiente |
| AUD-011 | Medio | Brecha Funcional | B. Gobernanza y Multi-tenencia | P1 Esperado | cognito-backend | Inexistencia de políticas automatizadas de retención y borrado de datos de usuario/sesión | Pendiente |
| AUD-012 | Alto | Deuda Técnica | B. Gobernanza y Multi-tenencia | P1 Esperado | cognito-backend | Acoplamiento rígido al sistema de archivos local que impide despliegues BYOC/stateless | Pendiente |
| AUD-013 | Medio | Defecto | C. Gestión de Contexto | P1 Esperado | cognito-backend | Pérdida de estructura (rutas, firmas, tool calls) durante la compactación narrativa de contexto | Pendiente |
| AUD-014 | Alto | Brecha Funcional | C. Gestión de Contexto | P2 Diferenciador | cognito-backend | Ausencia de memoria de hechos del proyecto o usuario persistente entre sesiones | Pendiente |
| AUD-015 | Medio | Brecha Funcional | C. Gestión de Contexto | P2 Diferenciador | cognito-backend | Historial de conversación estrictamente lineal sin ramificación (branching/checkpoints) | Pendiente |
| AUD-016 | Medio | Deuda Técnica | C. Gestión de Contexto | P1 Esperado | cognito-backend | Descubrimiento de AGENTS.md restringido a la raíz del CWD sin anidamiento ni tolerancia a fallos | Pendiente |
| AUD-017 | Alto | Brecha Funcional | D. Orquestación y Sub-Agentes | P1 Esperado | cognito-backend | Bucle de agente estrictamente secuencial y mono-agente por sesión | Pendiente |
| AUD-018 | Medio | Brecha Funcional | D. Orquestación y Sub-Agentes | P1 Esperado | cognito-backend | Ausencia de fase forzada de planificación de solo lectura previa a modificaciones de archivos | Pendiente |
| AUD-019 | Alto | Brecha Funcional | D. Orquestación y Sub-Agentes | P1 Esperado | cognito-backend | Cliente MCP simulado (mock) en lugar de transporte real stdio/SSE para servidores externos | Pendiente |
| AUD-020 | Medio | Brecha Funcional | D. Orquestación y Sub-Agentes | P2 Diferenciador | cognito-backend | Inexistencia de lifecycle hooks globales pre/post ejecución y pre/post compactación | Pendiente |
| AUD-021 | Alto | Brecha Funcional | D. Orquestación y Sub-Agentes | P0 Bloqueante | cognito-backend | Ausencia de canal interactivo de aprobación humana (Human-in-the-Loop) para acciones de riesgo | Pendiente |
| AUD-022 | Medio | Brecha Funcional | E. Extensibilidad y Ecosistema | P2 Diferenciador | cognito-backend | Ausencia de un formato estándar declarativo de definición de habilidades (tipo SKILL.md) | Pendiente |
| AUD-023 | Medio | Brecha Funcional | E. Extensibilidad y Ecosistema | P2 Diferenciador | cognito-backend | Carga de extensiones acoplada a la estructura de archivos local del repositorio | Pendiente |
| AUD-024 | Alto | Brecha Funcional | F. Observabilidad y Telemetría | P1 Esperado | cognito-backend | Inexistencia de exportación de métricas de costo/tokens por usuario a Prometheus/OpenTelemetry | Pendiente |
| AUD-025 | Alto | Brecha Funcional | F. Observabilidad y Telemetría | P1 Esperado | cognito-backend | Ausencia de Trace ID / Request ID correlacionado entre HTTP, agente y herramientas | Pendiente |
| AUD-026 | Alto | Brecha Funcional | G. Resiliencia y Recuperación | P1 Esperado | cognito-backend | Falta de checkpointing de ejecución que permita reanudar el estado tras una caída del proceso | Pendiente |
| AUD-027 | Medio | Defecto | G. Resiliencia y Recuperación | P1 Esperado | cognito-backend | Reintentos transitorios de streaming con riesgo de duplicar llamadas no idempotentes | Pendiente |
| AUD-028 | Alto | Brecha Funcional | H. Precisión y Evaluación | P1 Esperado | evals / cognito-backend | Ausencia de suite de evaluación E2E de trayectorias completas del agente contra baselines | Pendiente |
| AUD-029 | Medio | Brecha Funcional | H. Precisión y Evaluación | P2 Diferenciador | cognito-backend | Inexistencia de un paso interno de autocrítica o verificación previa a la entrega final | Pendiente |
| AUD-030 | Bajo | Deuda Técnica | I. Portabilidad de Proveedores | P2 Diferenciador | cognito-backend | Abstracción del LLM Router con condicionales específicos dificultando la adición de nuevos rimes | Pendiente |
| AUD-031 | Medio | Deuda Técnica | J. Despliegue y Producción | P1 Esperado | Dockerfiles | Contenedores Docker ejecutados como root y sin instrucciones HEALTHCHECK o graceful shutdown | Pendiente |
| AUD-032 | Alto | Brecha Funcional | J. Despliegue y Producción | P0 Bloqueante | cognito-backend | Estado de sesión acoplado a SQLite y locks locales imprevistos para escalado horizontal | Pendiente |

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
- **Estado:** Pendiente

#### AUD-002
- **ID:** AUD-002
- **Severidad:** Alto
- **Tipo:** Brecha Funcional
- **Categoría:** A. Seguridad y Aislamiento de Ejecución
- **Componente:** cognito-backend / CLI
- **Prioridad MVP Enterprise:** P0 Bloqueante
- **Descripción del problema:** No existe un control de red de salida saliente (egress network policy) tipo deny-all por defecto para los subprocesos o herramientas ejecutadas por el agente. El módulo `build_bwrap_args` en `sandbox.py` incluye la opción `--share-net` o deja activa la pila de red sin filtrar IP salientes ni requerir lista blanca explícita de endpoints.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/sandbox.py` (líneas 34-45) y `cognito_agent.py` (líneas 1-200).
- **Comparación con el estado del arte:** Los arneses enterprise de 2026 bloquean por defecto cualquier tráfico de red saliente de las herramientas ejecutadas por el agente, permitiendo únicamente dominios o IPs autorizadas explícitamente en una lista blanca.
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

#### AUD-006
- **ID:** AUD-006
- **Severidad:** Medio
- **Tipo:** Deuda Técnica
- **Categoría:** A. Seguridad y Aislamiento de Ejecución
- **Componente:** cognito-backend / worker
- **Prioridad MVP Enterprise:** P1 Esperado
- **Descripción del problema:** Los archivos `requirements.txt` del backend y del worker especifican nombres de librerías sin fijar versiones exactas con hashes cryptographic (lockfiles). Esto expone el despliegue a ataques de cadena de suministro o incompatibilidades transitorias.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/requirements.txt` (líneas 1-6) y `very-simplified-stack/cognito-worker/requirements.txt` (líneas 1-6).
- **Comparación con el estado del arte:** Las normativas de compliance enterprise exigen escaneo de dependencias y lockfiles congelados (`poetry.lock`, `pip-compile --generate-hashes`).
- **Estado:** Pendiente

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
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/models/db.py` (líneas 1-60) y `very-simplified-stack/cognito-backend/app/models/domain.py` (líneas 1-50).
- **Comparación con el estado del arte:** El software enterprise requiere RBAC granular y segmentación explícita por usuario, proyecto y organización.
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

#### AUD-014
- **ID:** AUD-014
- **Severidad:** Alto
- **Tipo:** Brecha Funcional
- **Categoría:** C. Gestión de Contexto y Memoria
- **Componente:** cognito-backend
- **Prioridad MVP Enterprise:** P2 Diferenciador
- **Descripción del problema:** `nooa_memory.py` gestiona memoria volátil de corto plazo por sesión. No existe un subsistema de memoria persistente de largo plazo (ej. vector store o archivo de hechos) que mantenga el conocimiento aprendido sobre el usuario o el proyecto entre sesiones independientes.
- **Evidencia de Ubicación en Código:** `very-simplified-stack/cognito-backend/app/core/nooa_memory.py` (líneas 1-60).
- **Comparación con el estado del arte:** Los arneses avanzados de 2026 aprenden y persisten autónomamente preferencias, reglas de estilo y arquitectura de proyectos a lo largo del tiempo.
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

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
- **Estado:** Pendiente

---

Cualquier auditoría futura debe contrastarse e integrarse en este documento utilizando la numeración consecutiva AUD-XXX.
