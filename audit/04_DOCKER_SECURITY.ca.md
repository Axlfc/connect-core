# AUDIT 04: SEGURIDAD DE DOCKER
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/04_DOCKER_SECURITY.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/04_DOCKER_SECURITY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/04_DOCKER_SECURITY.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/04_DOCKER_SECURITY.zh-cn.md)


**Fecha:** 2024-07-25
**Analista:** Jules

## 1. Resumen de Hallazgos

| Estado | Área | Resumen de Hallazgos |
| :--- | :--- | :--- |
| ✓ | **Aislamiento de Red** | El uso de redes de Docker personalizadas (`frontend`, `backend`, `ai`, `monitoring`) con la mayoría configuradas como `internal: true` es una **excelente práctica de seguridad** que limita la comunicación entre servicios. |
| ✓ | **Mínims Privilegios (Parcial)** | La mayoría de los servicios utilizan `cap_drop: - ALL` y `security_opt: - no-new-privileges:true`, lo que demuestra una sólida comprensión de los principios de seguridad de contenedores. |
| ✗ | **Ejecución como Root** | Varios contenedores críticos, incluyendo `ollama` y los basados en imágenes de NVIDIA (`whisper-stt`), se ejecutan con el **usuario `root`**. Una vulnerabilidad en cualquiera de estas aplicaciones otorgaría privilegios de administrador dentro del contenedor. |
| ✗ | **Capacidades de Linux Peligrosas** | Múltiples servicios (`postgres`, `forgejo`, `duplicati`) tienen la capacidad `DAC_OVERRIDE` añadida. Esta capacidad permite a un proceso eludir las comprobaciones de permisos de lectura, escritura y ejecución de archivos, socavando la seguridad del sistema de archivos. |
| ✗ | **Exposición de la Red del Host** | El servicio `fail2ban` está configurado con `network_mode: host`. Esto **rompe completamente el aislamiento de red del contenedor**, dándole acceso directo a las interfaces de red del host. Esto es extremadamente peligroso y anula muchos de los beneficios de seguridad de la contenedorización. |
| ✗ | **Secretos en Logs** | El `Dockerfile.matrix` contiene un script de entrypoint que **imprime los secretos generados (macaroon key, form secret, etc.) en los logs del contenedor** en el primer inicio. Esto expone credenciales críticas a cualquiera que tenga acceso a los logs de Docker. |

---

## 2. Hallazgos Detallados

### ✓ Lo que está bien

1.  **Principio de Mínims Privilegios Aplicado (en parte):**
    *   La mayoría de los servicios están configurados con `security_opt: [no-new-privileges:true]`, lo que impide que los procesos obtengan privilegios adicionales.
    *   El uso de `cap_drop: [ALL]` como configuración por defecto, y luego añadir solo las capacidades necesarias (`cap_add`), es la estrategia correcta a seguir.

2.  **Aislamiento de Red Robusto:**
    *   La arquitectura de red está muy bien diseñada. Los servicios de backend no son accesibles desde el exterior, y la comunicación está segmentada por función, lo que limita el movimiento lateral de un atacante.

3.  **Ús de Usuarios No-Root (en parte):**
    *   Serveis como `redis` (`user: "999:999"`), `authelia`, y `n8n` (`user: "${PUID:-1000}:${PGID:-1000}"`) se ejecutan correctamente con usuarios no privilegiados, reduciendo significativamente su riesgo.

### ✗ Problemas Encontrados

| ID | Severidad | Problema | Impacto |
| :- | :--- | :--- | :--- |
| **DS-01** | **CRÍTICO** | **`fail2ban` con `network_mode: host`** | El contenedor tiene acceso completo a la pila de red del host. Puede sniffear todo el tráfico, conectarse a cualquier servicio en `localhost` en el host, e interferir con las reglas de firewall del host. Un compromiso de este contenedor es equivalente a un compromiso del host a nivel de red. |
| **DS-02** | **CRÍTICO** | **Secretos Expuestos en Logs de `matrix-synapse`** | El script de entrypoint en `Dockerfile.matrix` imprime un bloque de "GENERATED SECRETS" en la salida estándar, que es capturada por los logs de Docker. Esto hace que secretos de sesión y de federación sean trivialmente accesibles. |
| **DS-03** | **ALTO** | **Ejecución como `root` en Contenedores Clave** | Los servicios `ollama`, `whisper-stt`, y `kokoro-tts` se ejecutan como `root`. Una vulnerabilidad de ejecución remota de código en cualquiera de estos servicios daría a un atacante control total dentro del contenedor, con la capacidad de modificar archivos, instalar software malicioso y atacar otros servicios en la red. |
| **DS-04** | **ALTO** | **Ús de la Capacidad `DAC_OVERRIDE`** | Esta capacidad, presente en `postgres`, `matrix-postgres`, `forgejo` y `duplicati`, permite a un proceso ignorar los permisos de archivos. Si un atacante compromete uno de estos contenedores, podría leer/escribir archivos a los que normalmente no tendría acceso, incluyendo potencialmente archivos de configuración sensibles o datos de otros usuarios. |
| **DS-05** | **MEDIO** | **El socket de Docker montado de forma insegura** | El servicio `nginx-proxy` monta el socket de Docker (`/var/run/docker.sock`) como `read-only`. Esto es bueno, pero comprometer `nginx-proxy` aún permitiría a un atacante obtener información sensible sobre todos los demás contenedores y la configuración del host de Docker. |

### ⚠️ Warnings/Recomendaciones

1.  **Filesystems Read-Only:**
    *   **Recomendación:** Para contenedores que no necesitan escribir datos en su propio sistema de archivos (aparte de en los volúmenes montados), considere añadir la opción `read_only: true`. Esto puede mitigar muchas clases de ataques que dependen de escribir archivos binarios o scripts maliciosos.

2.  **Perfiles de Seguridad (AppArmor/Seccomp):**
    *   **Recomendación:** El uso de `apparmor=docker-default` es un buen punto de partida. Para una seguridad aún mayor, se podrían crear perfiles de AppArmor o Seccomp personalizados para cada servicio, restringiendo las llamadas al sistema que cada aplicación puede realizar.

### 🔧 Soluciones Sugeridas

1.  **Para DS-01 (`fail2ban` en `network_mode: host`):**
    *   **Solució:** Esta es una configuración difícil de cambiar, ya que `fail2ban` necesita modificar las `iptables` del host. La solución más segura es **ejecutar `fail2ban` directamente en el host**, fuera de Docker. Si debe permanecer en un contenedor, se debe investigar el uso de un contenedor más especializado y "Rooteado" con herramientas como `nsenter` para ejecutar comandos en el namespace del host de manera controlada, en lugar de exponer toda la pila de red.

2.  **Para DS-02 (Secretos en Logs de Matrix):**
    *   **Solució:** Modificar `/scripts/entrypoint.sh` dentro de `Dockerfile.matrix` para que los secretos se guarden en un archivo dentro del contenedor con permisos restringidos, en lugar de imprimirlos.
        ```diff
        --- a/Dockerfile.matrix
        +++ b/Dockerfile.matrix
        @@ -242,15 +242,11 @@

         # Display generated secrets (only on first run)
         if [ ! -f "/data/.secrets_displayed" ]; then
-            echo ""
-            echo "=================================================="
-            echo "GENERATED SECRETS (SAVE THESE!):"
-            echo "=================================================="
-            echo "SYNAPSE_REGISTRATION_SHARED_SECRET=${SYNAPSE_REGISTRATION_SHARED_SECRET}"
-            # ... (remove all other echo statements) ...
-            echo "=================================================="
-            echo ""
+            SECRETS_FILE="/data/generated_secrets.log"
+            echo "Saving generated secrets to ${SECRETS_FILE}" > "${SECRETS_FILE}"
+            echo "SYNAPSE_REGISTRATION_SHARED_SECRET=${SYNAPSE_REGISTRATION_SHARED_SECRET}" >> "${SECRETS_FILE}"
+            # ... (append all other secrets to the file) ...
+            chmod 600 "${SECRETS_FILE}"
             touch /data/.secrets_displayed
         fi
         ```

3.  **Para DS-03 (Ejecución como `root`):**
    *   **Solució para `ollama`:** La imagen oficial de `ollama` ahora soporta la ejecución como no-root. Se debe crear un usuario `ollama` y asegurarse de que los permisos del volumen (`/root/.ollama` debe cambiar a `/home/ollama/.ollama`) sean correctos.
    *   **Solució para Dockerfiles personalizados (e.g., `whisper-stt`):** Añadir los siguientes pasos al final del Dockerfile:
        ```dockerfile
        # Create a non-root user
        RUN useradd -ms /bin/bash appuser

        # Ensure correct permissions on the app directory
        RUN chown -R appuser:appuser /app

        # Switch to the non-root user
        USER appuser

        # Adjust command/entrypoint if necessary
        CMD ["python", "/app/server.py"]
        ```

4.  **Para DS-04 (`DAC_OVERRIDE`):**
    *   **Solució:** Investigar por qué cada servicio necesita esta capacidad. A menudo, se añade para solucionar problemas de permisos en los volúmenes montados. La solución correcta es **arreglar los permisos en el host** (usando el script `setup-permissions.sh` y asegurando que `PUID`/`PGID` coincidan) en lugar de otorgar capacidades peligrosas. Eliminar `DAC_OVERRIDE` de la sección `cap_add` de todos los servicios.
