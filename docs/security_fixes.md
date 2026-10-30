# Documentación de Correcciones de Seguridad (`docs/security_fixes.md`)

Este documento detalla la verificación previo-parche, las correcciones implementadas, las pruebas automáticas asociadas y las guías operativas tras los cambios aplicados en el repositorio `very-simplified-stack/` (`cognito-backend` y `cognito-worker`).

---

## Tabla de Verificación de Hallazgos (V1 - V8)

| ID | Hallazgo | Estado de Verificación | Fichero y Líneas Cambiadas | Test de Cobertura | Antes vs Después (Sin Secretos) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **V1** | Herencia imprevista de `os.environ` del host en sandbox | **CONFIRMADO / CORREGIDO** | `app/core/sandbox.py:61-73,197-203,323,401` | `test_sandbox_env_leak_prevention`, `test_build_safe_env` | **Antes:** `asyncio.create_subprocess_exec(*cmd, cwd=...)` heredaba `os.environ`.<br>**Después:** Se pasa `env=build_safe_env()` restringido a `PATH, LANG, LC_ALL, TERM` y `--clearenv` en bwrap. |
| **V2** | Ausencia de límites de recursos de hardware (CPU/MemORIA/NPROC/NOFILE) | **CONFIRMADO / CORREGIDO** | `app/core/sandbox.py:76-111,288-289,313,391` | `test_sandbox_resource_limits_memory` | **Antes:** No se aplicaban restricciones de hardware.<br>**Después:** Se antepone `prlimit` con `--cpu`, `--as`, `--nproc`, `--nofile` configurables por entorno. |
| **V3** | Exposición del directorio `HOME` del usuario en bwrap | **CONFIRMADO / CORREGIDO** | `app/core/sandbox.py:204-218` | `test_sandbox_home_directory_hidden` | **Antes:** `--ro-bind / /` exponía `~/.ssh`, `~/.aws`, `~/.cognito`.<br>**Después:** Se oculta el home con `--tmpfs ~` antes de montar CWD, con opción `COGNITO_SANDBOX_HOME_RO_PATHS`. |
| **V4** | Control de Path Traversal en `read_tool` y `edit_tool` | **CONFIRMADO (MITIGADO) / DEFENSA EN PROFUNDIDAD** | `app/core/path_safety.py:28-50`<br>`read_tool.py:38`<br>`edit_tool.py:38` | `test_read_tool_path_traversal_blocked`, `test_edit_tool_path_traversal_blocked` | **Antes:** `FSObservationPolicy` ya mitigaba el acceso fuera de CWD mediante `.resolve()` e `is_relative_to(cwd)`.<br>**Después:** Se añade la llamada explícita `resolve_in_workspace` como defensa en profundidad. |
| **V5** | Escritura directa no atómica en `edit_tool.py` | **CONFIRMADO / CORREGIDO** | `app/core/tools/edit_tool.py:63-75` | `test_edit_tool_atomic_write_failure_leaves_file_intact` | **Antes:** `open(resolved_target, "w").write(...)` directo.<br>**Después:** Escritura atómica vía `NamedTemporaryFile`, `os.fsync` y `os.replace` con limpieza en fallos. |
| **V6** | Bypass de `protected_files` mediante enlaces simbólicos en `write_tool.py` | **CONFIRMADO / CORREGIDO** | `app/core/tools/write_tool.py:38-48` | `test_write_tool_symlink_to_protected_file_blocked` | **Antes:** Solo comprobaba `if norm_path in context.protected_files`.<br>**Después:** Resuelve el destino real y comprueba `real_rel_path` relativo al CWD contra `protected_files`. |
| **V7** | Proceso zombi tras `proc.kill()` en timeouts de sandbox | **CONFIRMADO / CORREGIDO** | `app/core/sandbox.py:339-342,417-420` | `test_sandbox_timeout_reaps_process` | **Antes:** `proc.kill()` sin reap posterior.<br>**Después:** Se invoca `await proc.wait()` dentro de `try/except` tras el kill. |
| **V8** | Fallback de contraseñas por defecto en texto plano en Docker Compose | **CONFIRMADO / CORREGIDO** | `very-simplified-stack/docker-compose.yml:37,153,156,158`<br>`docker-compose.yml:930,931` | `test_docker_compose_no_plaintext_passwords` | **Antes:** `${POSTGRES_PASSWORD:-admin_password}` y `${REDIS_PASSWORD:-redis_password}`.<br>**Después:** Sintaxis obligatoria `${POSTGRES_PASSWORD:?mensaje}` y `${REDIS_PASSWORD:?mensaje}`. |

---

## Clasificación de Hallazgos

### Fallos Corregidos
1. **Bypass de archivos protegidos en `write_tool.py` via symlinks:** Un enlace simbólico dentro del workspace que apuntase a `.env` permitía sobrescribir archivos protegidos. Ahora se resuelve la ruta real antes de validar contra `protected_files`.
2. **Fuga de credenciales y variables de entorno del host en `SandboxedExecutor`:** Los subprocesos en bwrap heredaban `os.environ`. Se restringió el entorno mediante `build_safe_env()` (`PATH`, `LANG`, `LC_ALL`, `TERM`) y la opción `--clearenv` en bwrap.
3. **Exposición del directorio `HOME` del usuario en `SandboxedExecutor`:** Se ocultó el directorio `~` usando `--tmpfs` antes de montar el CWD.
4. **Ausencia de límites de recursos en el sandbox:** Se introdujeron restricciones de memoria, CPU, subprocesos y descriptores de archivos mediante `prlimit`.
5. **Generación de procesos zombi tras timeout:** Se añadió `await proc.wait()` tras `proc.kill()`.
6. **Escritura directa no atómica en `edit_tool.py`:** Se implementó escritura atómica con archivo temporal, `os.fsync` y `os.replace`.
7. **Contraseñas por defecto en Docker Compose:** Se eliminaron las contraseñas fallback en texto plano sustituyéndolas por `${VAR:?error}`.

### Defensa en Profundidad
1. **Validación explícita de rutas en `read_tool.py` y `edit_tool.py`:**
   Aunque `FSObservationPolicy` ya bloqueaba accesos fuera del workspace invocando `resolve()` e `is_relative_to(cwd)`, se agregó la función helper `resolve_in_workspace` en `app/core/path_safety.py` como capa extra de defensa en profundidad.

### Hallazgos Descartados / No Confirmados
1. **Vulnerabilidad Crítica de Path Traversal en `read_tool` y `edit_tool` (Descartado como crítico):**
   La inspección del código demostró que `FSObservationPolicy.is_path_ignored()` ya capturaba y bloqueaba cualquier intento de escape con `../`, rutas absolutas o enlaces simbólicos dirigidos fuera del workspace al resolver canónicamente la ruta y validar la pertenencia a `cwd`.

---

## Riesgos Residuales y Fuera de Alcance

1. **Límites cgroups/cgroupv2 a nivel de demonio systemd:**
   - *Detalle:* Las restricciones aplicadas mediante `prlimit` actúan a nivel de proceso POSIX. No se han modificado las directivas `CPUQuota` ni `MemoryMax` en `cognito-worker.service`, ya que el aislamiento a nivel de cgroups de Linux requiere permisos administrativos de root en el host.
2. **Reexposición de cachés en el Home del usuario:**
   - *Detalle:* Si los comandos del agente requieren acceder a cachés de dependencias (ej. `~/.cache/pip` o `~/.npm`), no están abiertos por defecto. El operador debe configurar explícitamente `COGNITO_SANDBOX_HOME_RO_PATHS`.

---

## Instrucciones para el Operador

1. **Nuevas Variables de Entorno de Configuración del Sandbox:**
   - `COGNITO_SANDBOX_CPU_SECONDS` (Por defecto: `30` segundos)
   - `COGNITO_SANDBOX_MEMORY_MB` (Por defecto: `2048` MB)
   - `COGNITO_SANDBOX_NPROC` (Por defecto: `256` procesos)
   - `COGNITO_SANDBOX_NOFILE` (Por defecto: `1024` descriptores)
   - `COGNITO_SANDBOX_HOME_RO_PATHS` (Lista separada por comas de rutas de solo lectura bajo `~` a reexponer en bwrap, ej. `/home/user/.cache/pip`).

2. **Requisito de la Herramienta `prlimit`:**
   - El sandbox ahora exige que el binario `prlimit` (paquete `util-linux`) esté instalado en la máquina host/contenedor donde se ejecuta `cognito-backend` o `cognito-worker`.
   - Si `prlimit` no está instalado, `SandboxedExecutor` lanzará una excepción `SandboxUnavailableError` al intentar ejecutar comandos.

3. **Comportamiento de Docker Compose:**
   - Los archivos `docker-compose.yml` ahora fallarán al arrancar (`docker compose up`) si las variables `POSTGRES_PASSWORD` y `REDIS_PASSWORD` no están explícitamente definidas en el archivo `.env` o en las variables de entorno de la sesión.
