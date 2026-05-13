# AUDIT 02: GESTIÓN DE VARIABLES DE ENTORNO Y CONFIGURACIÓN
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.ca.md)


**Fecha:** 2024-07-25
**Analista:** Jules

## 1. Resumen de Hallazgos

| Estado | Área | Resumen de Hallazgos |
| :--- | :--- | :--- |
| ✓ | **Generación de Secretos** | Los scripts de inicialización (`init_env.sh`) utilizan métodos criptográficamente seguros (`openssl rand`) para generar secretos, lo cual es una práctica excelente. |
| ✓ | **Protección de Archivos** | El archivo `.gitignore` está configurado correctamente para excluir `secrets/` y `.env*`, previniendo la exposición accidental de credenciales en el repositorio. |
| ⚠️ | **Metodología Mixta** | El proyecto utiliza dos métodos para la gestión de secretos simultáneamente: **Docker Secrets** (seguro) y **variables de entorno a través de `.env`** (menos seguro). Esta inconsistencia es la principal fuente de riesgo. |
| ✗ | **Exposición Potencial** | Secretos críticos como `POSTGRES_PASSWORD` y `REDIS_PASSWORD` se inyectan en los contenedores como variables de entorno, lo que los hace visibles a través de `docker inspect`, logs y potencialmente en herramientas de monitoreo. |
| ✗ | **Validación de Entradas** | Los scripts de shell, aunque robustos, no validan exhaustivamente las entradas del usuario en modo interactivo, lo que podría permitir la inyección de caracteres maliciosos en el archivo `.env`. |

---

## 2. Hallazgos Detallados

### ✓ Lo que está bien

1.  **Generación Segura de Secretos:**
    *   El script `init_env.sh` utiliza `openssl rand` como método principal para la creación de contraseñas y claves. Esta es la mejor práctica industrial para generar valores aleatorios seguros.

2.  **Manejo de Archivos `.env.example`:**
    *   El script `generate_env_example.sh` es notablemente inteligente. Identifica variables sensibles por patrones (`PASSWORD`, `KEY`, `TOKEN`, etc.) y las vacía, mientras preserva valores de configuración no sensibles. Esto asegura que el archivo de ejemplo sea seguro y útil.

3.  **使用 Parcial de Docker Secrets:**
    *   El `docker-compose.yml` define un bloque de `secrets:` y los utiliza correctamente en varios servicios (por ejemplo, `authelia`, `n8n-import`). Esto demuestra conocimiento de la forma correcta de manejar secretos en Docker.
    *   **Ejemplo (`authelia` service):**
        ```yaml
        secrets:
          - authelia_jwt_secret
          - authelia_session_secret
        environment:
          - AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE=/run/secrets/authelia_jwt_secret
          - AUTHELIA_SESSION_SECRET_FILE=/run/secrets/authelia_session_secret
        ```
    *   Este método es seguro porque el secreto se monta como un archivo en `/run/secrets/` dentro del contenedor y nunca se expone como una variable de entorno.

### ✗ Problemas Encontrados

| ID | Severidad | Problema | Impacto |
| :- | :--- | :--- | :--- |
| **C-01** | **ALTO** | **使用 de Variables de Entorno para Secretos Críticos** | El servicio principal de `postgres` y `redis` reciben sus contraseñas a través de variables de entorno cargadas desde el archivo `.env`. Un atacante con acceso al host de Docker podría extraer estas credenciales con el comando `docker inspect postgres`. |
| **C-02** | **MEDIO** | **Inconsistencia en la Gestión de Secretos** | El proyecto utiliza Docker Secrets para algunos servicios (Authelia) pero variables de entorno para otros (Postgres, Redis). Esta falta de un estándar único aumenta la complejidad, el riesgo de error humano y la superficie de ataque. |
| **C-03** | **BAJO** | **Visualización de Secretos en Consola** | `init_env.sh` muestra una porción del secreto generado en la consola. Aunque es una porción truncada, esto podría exponer el secreto al historial del shell (`.bash_history`) o a observadores. |

### ⚠️ Warnings/Recomendaciones

1.  **Documentación de `ENV_MANAGEMENT.md`:**
    *   El archivo `ENV_MANAGEMENT.md` existe pero podría ser más explícito sobre la estrategia de secretos. Debería explicar *por qué* se prefiere Docker Secrets y advertir sobre los riesgos de usar variables de entorno para datos sensibles.

2.  **Hardening de Scripts de Shell:**
    *   Los scripts `init_env.sh` y `generate_env_example.sh` son complejos. Una buena práctica sería añadir `set -o pipefail` al inicio para asegurar que los pipelines fallen si un comando intermedio falla.

### 🔧 Soluciones Sugeridas

1.  **Para C-01 y C-02 (Unificar en Docker Secrets - CRÍTICO):**
    *   **Paso 1: Modificar `docker-compose.yml`:**
        *   Reconfigurar todos los servicios que actualmente usan variables de entorno para secretos para que usen Docker Secrets.
        *   **Ejemplo para el servicio `postgres`:**
            ```diff
            --- a/docker-compose.yml
            +++ b/docker-compose.yml
            @@ -143,8 +143,10 @@
             restart: unless-stopped
             ports:
               - "127.0.0.1:5432:5432"
-            environment:
-              - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
+            secrets:
+              - postgres_password
+            environment:
+              - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
               - POSTGRES_USER=${POSTGRES_USER}
               - POSTGRES_DB=${POSTGRES_DB}
               - PGDATA=/var/lib/postgresql/data/pgdata
            ```
    *   **Paso 2: Actualizar `init_env.sh`:**
        *   Modificar el script para que, en lugar de escribir `POSTGRES_PASSWORD=valor_secreto` en el `.env`, cree el archivo correspondiente en el directorio `secrets/`.
            ```bash
            # En init_env.sh, en lugar de sed:
            echo "$new_value" > secrets/postgres_password.txt
            chmod 600 secrets/postgres_password.txt
            # Y eliminar la variable del .env
            sed -i '/^POSTGRES_PASSWORD=/d' "$TARGET_FILE"
            ```
        *   Esto centraliza todos los secretos en un único lugar (`/secrets`) gestionado con los permisos correctos.

2.  **Para C-03 (Visualización de Secretos):**
    *   **解决方案:** Modificar `init_env.sh` para no mostrar el valor generado en la consola. Simplemente informar al usuario que se ha generado y guardado un valor.
        ```diff
        --- a/init_env.sh
        +++ b/init_env.sh
        @@ -145,7 +145,7 @@
             echo ""
             echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
             echo -e "${BLUE}Variable:${NC} $var"
-            echo -e "${BLUE}Valor generado:${NC} ${new_value:0:20}...${new_value: -10}"
+            echo -e "${BLUE}Valor generado:${NC} [OCULTO POR SEGURIDAD]"
             echo -n "¿Usar este valor? (S/n/personalizar): "
             read -r response
         ```
