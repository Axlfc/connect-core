# AUDIT 07: SEGURIDAD DE RED Y FIREWALL
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.zh-cn.md)


**Fecha:** 2024-07-25
**Analista:** Jules

## 1. Resumen de Hallazgos

| Estado | Área | Resumen de Hallazgos |
| :--- | :--- | :--- |
| ✓ | **Segmentación de Red Interna** | La arquitectura de red de Docker Compose está **excelentemente diseñada**, utilizando redes `internal` para aislar los servicios de backend y limitar la superficie de ataque interna. |
| ⚠️ | **Configuración de `fail2ban`** | El servicio `fail2ban` está implementado, lo que demuestra una intención de proteger contra ataques de fuerza bruta. Sin embargo, su configuración es **demasiado simplista** y solo monitorea los intentos de login fallidos a través del log de Nginx. |
| ✗ | **`fail2ban` en `network_mode: host`** | Este es un **defecto de diseño de seguridad crítico**. Ejecutar `fail2ban` en modo de red de host rompe el aislamiento del contenedor, otorgándole acceso sin restricciones a las interfaces de red del sistema anfitrión. Un compromiso de este contenedor podría comprometer toda la red del host. |
| ✗ | **Falta de Egress Control** | No hay políticas de red que restrinjan el tráfico de salida de los contenedores. Si un contenedor es comprometido, podría ser utilizado para descargar malware, conectarse a servidores de comando y control (C2), o atacar otros sistemas en internet sin ninguna restricción. |
| ✗ | **Exposición de Ports Innecesaria** | Múltiples servicios exponen sus puertos directamente a las interfaces del host (ej. `postgres` en `127.0.0.1:5432`, `whisper-stt` en `0.0.0.0:9001`). En una arquitectura de microservicios, la comunicación debería ocurrir principalmente a través de la red interna de Docker, y solo el reverse proxy debería exponer puertos externamente. |

---

## 2. Hallazgos Detallados

### ✓ Lo que está bien

1.  **Aislamiento de Serveis por Red:**
    *   La creación de redes separadas (`frontend`, `backend`, `ai`, `monitoring`) y el uso de `internal: true` para las redes que no necesitan acceso externo es la implementación correcta del principio de mínimo privilegio a nivel de red. Esto previene que un servicio comprometido en el backend (ej. una base de datos) pueda ser accedido directamente desde el exterior.

### ✗ Problemas Encontrados

| ID | Severidad | Problema | Impacto |
| :- | :--- | :--- | :--- |
| **N-01** | **CRÍTICO** | **`fail2ban` con `network_mode: host`** | El contenedor `fail2ban` anula el aislamiento de red de Docker. Puede monitorear, interferir y manipular el tráfico de red del host. Un atacante que comprometa este contenedor podría evadir el firewall principal, atacar servicios del host que no están expuestos públicamente, y obtener un punto de apoyo persistente en la red del host. |
| **N-02** | **ALTO** | **Filtros de `fail2ban` Insuficientes** | La configuración actual solo bloquea IPs que generan errores 401 en endpoints de login específicos. No protege contra una amplia gama de ataques comunes, como escaneo de directorios, inyección de SQL, XSS, o ataques de denegación de servicio a nivel de aplicación (capa 7). Proporciona una falsa sensación de seguridad. |
| **N-03** | **MEDIO** | **Exposición Directa de Ports de Backend** | Serveis como `postgres` y `redis` exponen sus puertos a `127.0.0.1` en el host. Aunque esto no es públicamente accesible, permite que cualquier otro proceso que se ejecute en el mismo host (incluyendo otros contenedores mal configurados) pueda intentar conectarse directamente a la base de datos o al caché, eludiendo las capas de aplicación. |
| **N-04** | **MEDIO** | **Falta de Control de Tráfico de Salida (Egress)** | Los contenedores pueden iniciar conexiones salientes a cualquier destino en internet. Si un atacante logra ejecutar código en un contenedor (ej. `ollama`), podría usarlo para descargar herramientas de hacking, exfiltrar datos a un servidor externo, o participar en una botnet. |

### ⚠️ Warnings/Recomendaciones

1.  **Visibilidad del Tráfico Interno:**
    *   El tráfico entre contenedores en la misma red de Docker no está cifrado (TLS). Para entornos de muy alta seguridad (ej. cumplimiento de PCI DSS), se podría considerar implementar una malla de servicios (service mesh) como Istio o Linkerd para forzar el cifrado de todo el tráfico interno (mTLS).

### 🔧 Soluciones Sugeridas

1.  **Para N-01 y N-02 (Rediseñar la Estrategia de `fail2ban`):**
    *   **Solució Ideal (Recomendada):** Eliminar el contenedor de `fail2ban`. Instalar y configurar `fail2ban` **directamente en el sistema operativo del host**. Esto le da acceso legítimo y seguro a los logs y a las `iptables` del host sin romper el modelo de seguridad de Docker.
    *   **Solució Alternativa (Si debe ser en contenedor):**
        1.  Eliminar `network_mode: host`.
        2.  Añadir las capacidades `NET_ADMIN` y `NET_RAW` para permitir la manipulación de `iptables`.
        3.  Montar el archivo de log de `iptables` del host dentro del contenedor para que pueda ver sus propias acciones.
        4.  Expandir masivamente los filtros en `filter.d` para incluir reglas de `nginx-badbots`, `nginx-noscript`, `nginx-http-auth`, y otras reglas predefinidas de `fail2ban` para una protección más completa.

2.  **Para N-03 (Limitar Exposición de Ports):**
    *   **Solució:** Revisar cada servicio en `docker-compose.yml` y eliminar cualquier mapeo de `ports` que no sea estrictamente necesario para el acceso externo (gestionado por `nginx-proxy`) o para la depuración local. La comunicación entre servicios debe realizarse a través de la red de Docker utilizando los nombres de servicio como DNS (ej. `postgres:5432`).
        ```diff
        --- a/docker-compose.yml
        +++ b/docker-compose.yml
        @@ -140,8 +140,6 @@
         hostname: postgres
         container_name: postgres
         networks:
           - backend
         restart: unless-stopped
-        ports:
-          - "127.0.0.1:5432:5432"
         secrets:
           - postgres_password
           - postgres_user
        ```

3.  **Para N-04 (Control de Egress):**
    *   **Solució:** Crear una red de Docker dedicada para el acceso a internet y adjuntar solo a los contenedores que lo necesiten explícitamente.
        1.  **Definir una red de salida en `docker-compose.yml`:**
            ```yaml
            networks:
              egress_allowed:
                driver: bridge
            ```
        2.  **Modificar el firewall del host (iptables):** Añadir reglas para permitir el tráfico `FORWARD` solo desde la subred de la red `egress_allowed` hacia el exterior, y denegar el `FORWARD` del resto de redes de Docker.
            ```bash
            # Ejemplo de regla de iptables (requiere la subred correcta)
            DOCKER_EGRESS_NW="172.x.y.0/24" # Subred de la red egress_allowed
            iptables -A FORWARD -i br-$(docker network ls | grep egress_allowed | awk '{print $1}') -o <external_iface> -j ACCEPT
            iptables -A FORWARD -i docker0 -o <external_iface> -j DROP
            ```
        3.  **Adjuntar contenedores a la red:** Solo los contenedores que necesiten acceder a internet (ej. `n8n` para webhooks) se añadirían a la red `egress_allowed`.
