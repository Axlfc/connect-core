# Análisis de Riesgos de Nuevas Funcionalidades

Este documento analiza los riesgos de seguridad y operación asociados a las nuevas funcionalidades propuestas, evaluando los permisos requeridos, el aislamiento de red y credenciales, el impacto de fallos repetitivos y la suficiencia de los controles actuales.

---

## 1. Permisos adicionales necesarios en el Worker o el Sandbox

- **Verificación visual con navegador (Playwright):**
  - **Permisos requeridos:** En el contenedor o proceso de `cognito-worker`, se requiere instalar binarios de Chromium/WebKit y dependencias del sistema de Linux (ej. `libgbm1`, `libnss3`, `libasound2`). En el sandbox `SandboxedExecutor`, ejecutar Playwright requiere acceso al sistema de archivos `/tmp` e interproceso. [VERIFICADO EN CÓDIGO]
  - **Riesgos:** Si el navegador dentro del sandbox intenta abrir sockets de red para renderizar recursos remotos, tropezará con el aislamiento estricto `--unshare-all` de Bubblewrap en `SandboxedExecutor`. Si para permitir Playwright se desactiva el aislamiento de red o se agrega la opción `--share-net`, el proceso del navegador ganará acceso completo a la red. [VERIFICADO EN CÓDIGO]

- **Memoria por repositorio:**
  - **Permisos requeridos:** Requiere permisos de lectura/escritura sobre las colecciones de Qdrant y las tablas de hechos en PostgreSQL (`models/db.py`). No requiere permisos elevados a nivel del sistema operativo. [VERIFICADO EN CÓDIGO]

- **Tareas recurrentes:**
  - **Permisos requeridos:** El proceso de `cognito-backend` requiere permisos para ejecutar un hilo/proceso en segundo plano (scheduler) y mantener conexiones persistentes con PostgreSQL y Redis. [VERIFICADO EN CÓDIGO]

- **Revisión del plan y Reintentos automáticos:**
  - **Permisos requeridos:** No requieren permisos adicionales del sistema operativo; utilizan las estructuras existentes en `TaskStore` y `ApprovalManager`. [VERIFICADO EN CÓDIGO]

---

## 2. Aislamiento de Red y Credenciales del Host en Navegadores y Pruebas Frontend

- **Aislamiento de red:**
  - `SandboxedExecutor` aplica aislamiento total de red en el kernel mediante Bubblewrap `--unshare-all` sin `--share-net` (`app/core/sandbox.py:173`). [VERIFICADO EN CÓDIGO]
  - Si un test de frontend o Playwright se ejecuta dentro de `SandboxedExecutor`, **no podrá acceder a Internet ni a red local** para descargar assets, CDNs o consultar APIs externas. [VERIFICADO EN CÓDIGO]
  - Si para permitir pruebas de frontend se ejecuta Playwright fuera del sandbox o se pasa una excepción de red, el navegador podrá realizar peticiones salientes a cualquier IP o servicio de la red local. [SUPOSICIÓN]

- **Acceso a credenciales del host:**
  - Al crear subprocesos en `SandboxedExecutor`, no se limita el parámetro `env` en `asyncio.create_subprocess_exec` (`sandbox.py:300,378`), heredando `os.environ`. [VERIFICADO EN CÓDIGO]
  - Si el entorno del host contiene tokens, claves API o contraseñas, cualquier test de frontend o script ejecutado dentro del sandbox tiene capacidad técnica de leer dichas variables de entorno. [VERIFICADO EN CÓDIGO]

---

## 3. Impacto de Reintentos Automáticos en Fallos Costosos

- **Escenario de fallo repetitivo:**
  - Si un test falla debido a un error en el propio entorno (ej. falta una dependencia en el sistema o una API externa está caída) y el sistema ejecuta reintentos automáticos, el agente repetirá llamadas costosas al LLM en cada intento. [VERIFICADO EN CÓDIGO]
- **Coste de Tokens y Llamadas:**
  - En la cadena de escalado actual (`local` -> `luna` -> `terra` -> `sol`), cada reintento utiliza un modelo progresivamente más grande y costoso (`escalation_service.py:12`). Un bucle de reintentos sin acotar puede agotar la cuota de tokens. [VERIFICADO EN CÓDIGO]
- **Mecanismos de mitigación:**
  - `TokenBudgetManager` (`app/core/token_budget.py:39`) rastrea el consumo de tokens y puede bloquear la ejecución si se excede `max_tokens`. [VERIFICADO EN CÓDIGO]
  - `VerificationEngine.classify_failure` (`worker_app/verification.py:34`) clasifica los fallos como `environmental`, `model_related`, `policy_related` o `requirement_related`. Si la falla se clasifica como `environmental`, se evita el escalado innecesario de modelo. [VERIFICADO EN CÓDIGO]

---

## 4. Evaluación de los Controles Actuales

Actualmente existen cuatro controles principales en el repositorio:

1. **`ApprovalManager` (`app/core/approval.py:37`):**
   - *Estado actual:* Pausa la ejecución para solicitar aprobación humana en acciones sensibles. [VERIFICADO EN CÓDIGO]
   - *Suficiencia:* **Insuficiente por sí solo para el plan inicial.** Actualmente las acciones leídas no requieren aprobación previa y el agente puede modificar varios archivos antes de pedir aprobación en comandos de shell. [VERIFICADO EN CÓDIGO]

2. **`ExecPolicy` (`app/services/policy_engine.py:11`):**
   - *Estado actual:* Filtra comandos shell permitidos, prohibidos o que requieren aprobación previa. [VERIFICADO EN CÓDIGO]
   - *Suficiencia:* **Suficiente para ejecución de comandos shell**, pero no restringe las operaciones de lectura de archivos mediante `read_tool`. [VERIFICADO EN CÓDIGO]

3. **`TokenBudgetManager` (`app/core/token_budget.py:39`):**
   - *Estado actual:* Controla el presupuesto de tokens acumulado a nivel de sesión, usuario, proyecto u organización. [VERIFICADO EN CÓDIGO]
   - *Suficiencia:* **Suficiente para prevenir consumo descontrolado de tokens** en reintentos automáticos, siempre que se configuren valores `max_tokens` razonables por sesión. [VERIFICADO EN CÓDIGO]

4. **`SandboxedExecutor` (`app/core/sandbox.py:190`):**
   - *Estado actual:* Aísla la ejecución mediante Bubblewrap (`bwrap`) sin acceso a red (`--unshare-all`). [VERIFICADO EN CÓDIGO]
   - *Suficiencia:* **Insuficiente en el aislamiento de credenciales y límites de hardware.** Hereda `os.environ` del host y no aplica restricciones de CPU ni memoria RAM. [VERIFICADO EN CÓDIGO]

---

## Resumen de Suficiencia de Controles por Funcionalidad Propuesta

| Funcionalidad Propuesta | Controles Existentes | ¿Son Suficientes Hoy? | Medidas Adicionales Requeridas |
| :--- | :--- | :--- | :--- |
| **Revisión de Plan** | `ApprovalManager` | **Insuficiente** | Bloquear herramientas de edición (`write`/`edit`/`patch`) en la fase de planificación hasta recibir la aprobación del plan. [SUPOSICIÓN] |
| **Verificación Frontend (Playwright)** | `SandboxedExecutor` | **Insuficiente** | Limpiar `env` al invocar subprocesos y definir políticas de red controladas si se requieren conexiones locales. [SUPOSICIÓN] |
| **Reintentos Automáticos** | `TokenBudgetManager`, `VerificationEngine` | **Suficiente** | Configurar límites estrictos de `max_tokens` y acotar a un máximo de 3 reintentos por tarea. [VERIFICADO EN CÓDIGO] |
| **Memoria por Repositorio** | `QdrantMemoryService`, `NooaMemory` | **Insuficiente** | Introducir filtrado obligatorio por `repo_id` en las consultas vectoriales e inyectar el parámetro `enable_repo_memory`. [SUPOSICIÓN] |
| **Tareas Recurrentes** | `ApprovalManager` | **Suficiente** | Exigir aprobación humana obligatoria en `ApprovalManager` antes de cada disparo recurrente. [SUPOSICIÓN] |
