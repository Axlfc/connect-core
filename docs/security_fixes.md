# Documentación de Correcciones de Seguridad (`docs/security_fixes.md`)

Este documento detalla la verificación previo-parche, las correcciones implementadas, las pruebas automáticas asociadas y las guías operativas tras los cambios aplicados en el repositorio `very-simplified-stack/` (`cognito-backend` y `cognito-worker`).

---

## Tabla de Verificación de Hallazgos y Correcciones (Puntos 1 - 9)

| ID / Punto | Descripción del Problema | Estado de Verificación | Fichero y Líneas Cambiadas | Test que lo Cubre | Resumen Antes vs Después |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Regresión Worktrees** | La ocultación del directorio `~` con `--tmpfs` bloquea el acceso a `.git` en worktrees situados bajo `~/.cognito/worktrees/`. | **CONFIRMADO / CORREGIDO** | `app/core/sandbox.py:122-139,271-282` | `test_sandbox_worktree_under_home` | **Antes:** Ocultaba todo `~` e impedía a `git` acceder al gitdir principal.<br>**Después:** Detecta si CWD usa un puntero `.git` a un `gitdir` bajo `~` y lo reexpone vía `--ro-bind`. |
| **2. `--nproc` en prlimit** | `RLIMIT_NPROC` cuenta todos los procesos del mismo UID en el sistema, lo que puede provocar fallos al bifurcar subprocesos si el worker tiene actividad alta. | **CONFIRMADO / CORREGIDO** | `app/core/sandbox.py:82-108` | `test_get_prlimit_prefix_no_nproc` | **Antes:** Se incluía `--nproc=256` en `prlimit`.<br>**Después:** Se eliminó `--nproc` de `get_prlimit_prefix()`, manteniendo `--cpu`, `--as` y `--nofile`. |
| **3. HOME como "/" o inexistente** | Si `HOME` es `"/"` o no existe, `--tmpfs` oculta todo el sistema o causa excepciones. | **CONFIRMADO / CORREGIDO** | `app/core/sandbox.py:257-268` | `test_build_bwrap_args_home_slash_or_nonexistent` | **Antes:** Intentaba aplicar `--tmpfs` incondicionalmente sobre `HOME`.<br>**Después:** Se omite `--tmpfs` si `HOME` es `"/"`, no existe o no es directorio, registrando un aviso. |
| **4. CWD bajo `/tmp`** | Se debe garantizar que el `--bind` del CWD prevalezca sobre `--tmpfs /tmp` cuando CWD esté dentro de `/tmp`. | **CONFIRMADO / CORREGIDO** | `app/core/sandbox.py:249,293-298` | `test_sandbox_cwd_under_tmp_writable` | **Antes:** `--tmpfs /tmp` podía anteponerse sin orden garantizado.<br>**Después:** `--bind cwd cwd` se monta después de `--tmpfs /tmp` en la secuencia de bwrap. |
| **5. Compose Fallbacks Sensibles** | `docker-compose.yml` contenía valores predeterminados en texto plano para variables sensibles (`N8N_TEMP_PASSWORD`, `FORGEJO_SECRET_KEY`, etc.). | **CONFIRMADO / CORREGIDO** | `docker-compose.yml:416,1384,1385,1442`<br>`very-simplified-stack/docker-compose.yml:37,153,156,158` | `test_docker_compose_no_plaintext_sensitive_fallbacks` | **Antes:** `${VAR:-valor_texto_plano}`.<br>**Después:** Reemplazado por la sintaxis obligatoria `${VAR:?error}`. |
| **6. Puertos Publicados en Stack** | `qdrant` y `cognito-backend` exponían puertos en `0.0.0.0` sin restricción de interfaz. | **CONFIRMADO / CORREGIDO** | `very-simplified-stack/docker-compose.yml:59,75` | `test_docker_compose_ports_bound_to_localhost` | **Antes:** `"6333:6333"` y `"8000:8000"`.<br>**Después:** Enlazados a `"127.0.0.1:6333:6333"` y `"127.0.0.1:8000:8000"`. |
| **7. Normalización `protected_files`** | `_normalize_protected_file` usaba `lstrip("./\\")`, eliminando puntos iniciales y convirtiendo `.env` en `env`. | **CONFIRMADO / CORREGIDO** | `app/core/tools/write_tool.py:25-29` | `test_write_tool_protected_file_normalization_does_not_strip_leading_dots` | **Antes:** `lstrip("./\\")` borraba el punto de `.env`.<br>**Después:** Remueve únicamente el prefijo `./` sin modificar puntos en el nombre del fichero. |
| **8. Test Memoria Débil** | `test_sandbox_resource_limits_memory` daba falso positivo si el proceso moría por cualquier causa distinta a `MemoryError`. | **CONFIRMADO / CORREGIDO** | `tests/test_security_sandbox.py:140-155` | `test_sandbox_resource_limits_memory` | **Antes:** Verificaba erróneamente solo captura estricta.<br>**Después:** Aserta que la asignación de 300MB no aparezca en stdout y el proceso falle bajo el límite de 50MB. |
| **9. Documentación Aplicación `prlimit`** | `prlimit` se aplica como prefijo del comando del subproceso fuera del ejecutable bwrap. | **CONFIRMADO / DOCUMENTADO** | `app/core/sandbox.py:326,404` | `test_sandbox_prlimit_inherited_limits` | **Explicación:** `prlimit` establece los límites POSIX de recursos del proceso padre creado por `asyncio.create_subprocess_exec`, los cuales son heredados por el proceso hijo `bwrap` y sus comandos. |

---

## Clasificación de Puntos para el PR

### Puntos Bloqueantes para Merge
1. **Regresión con Worktrees (Punto 1):** Esencial para garantizar que `cognito-worker` pueda realizar operaciones de Git (`git status`, `git commit`) en worktrees efímeros.
2. **Eliminación de `--nproc` (Punto 2):** Evita bloqueos imprevistos por límite de subprocesos a nivel de usuario en servidores con alta carga.
3. **Eliminación de Fallbacks en Docker Compose (Punto 5):** Previene el despliegue con contraseñas conocidas en producción.

### Defensa en Profundidad y Mejoras
- **Punto 3:** Ocultamiento condicional de `HOME` cuando no es `/` ni inexistente.
- **Punto 4:** Garantía de orden de montajes `--tmpfs /tmp` previo a `--bind` de CWD.
- **Punto 6:** Restricción de puertos de `qdrant` y `cognito-backend` a la interfaz `127.0.0.1`.
- **Punto 7:** Corrección de la normalización de prefijos en `write_tool.py`.
- **Punto 8:** Refuerzo de la aserción en las pruebas de límites de memoria.
- **Punto 9:** Documentación de la herencia de límites mediante `prlimit`.

---

## Instrucciones para el Operador

1. **Variables Obligatorias en Docker Compose:**
   Los archivos `docker-compose.yml` ahora exigirán la definición explícita de `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `N8N_TEMP_PASSWORD`, `FORGEJO_SECRET_KEY`, `FORGEJO_INTERNAL_TOKEN` y `FORGEJO_MCP_TOKEN`. Si no están configuradas en el entorno o en `.env`, `docker compose config` o `docker compose up` se detendrán informando la variable faltante.

2. **Acceso a Interfaces Locales:**
   Los servicios `qdrant` (puerto 6333) y `cognito-backend` (puerto 8000) en `very-simplified-stack/docker-compose.yml` ahora escuchan exclusivamente en `127.0.0.1`. Si se requiere acceso desde otra máquina externa, el operador deberá configurar un proxy inverso (`nginx-proxy` o `zrok`).
