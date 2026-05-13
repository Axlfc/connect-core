# AUDIT 05: REVERSE PROXY Y NGINX
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.ca.md)


**Fecha:** 2024-07-25
**Analista:** Jules

## 1. Resumen de Hallazgos

| Estado | Área | Resumen de Hallazgos |
| :--- | :--- | :--- |
| ✓ | **Integración con Authelia** | La configuración de `forward auth` para la integración con Authelia es **correcta y segura**. El uso de un bloque `internal` y la correcta transmisión de headers (`X-Forwarded-*`) siguen las mejores prácticas. |
| ✓ | **Estructura de Configuración** | La estructura de configuración que utiliza `vhost.d` para aplicar la protección por servicio es **modular y escalable**, permitiendo un control granular sobre qué endpoints están protegidos. |
| ✗ | **Falta de Security Headers** | La configuración de Nginx **carece por completo de headers de seguridad explícitos**. No se está configurando HSTS, CSP, X-Frame-Options, Permissions-Policy, ni otros headers esenciales para el "hardening" del proxy. |
| ✗ | **Configuración de SSL/TLS Débil** | No se especifica una política de SSL/TLS. Esto significa que se depende de los valores por defecto de `nginx-proxy`, que pueden permitir el uso de ciphers débiles o versiones de TLS obsoletas, exponiendo la comunicación a posibles ataques de downgrade. |
| ⚠️ | **Sin Rate Limiting** | No hay ninguna configuración de `rate limiting` a nivel del reverse proxy. Esto deja a los servicios backend vulnerables a ataques de denegación de servicio (DoS) o a intentos de fuerza bruta que podrían agotar los recursos. |

---

## 2. Hallazgos Detallados

### ✓ Lo que está bien

1.  **Implementación de Forward Auth:**
    *   El archivo `nginx-proxy/authelia-location.conf` está perfectamente configurado. Utiliza la directiva `internal` para prevenir el acceso externo al endpoint de verificación y pasa correctamente todos los headers necesarios para que Authelia pueda tomar decisiones de autorización.
    *   Los archivos en `vhost.d` (ej. `n8n.localhost`) incluyen este bloque y configuran la directiva `auth_request` de forma correcta, asegurando que las peticiones no autenticadas sean interceptadas.

2.  **Modularidad de la Configuración:**
    *   El sistema de `vhost.d` permite aplicar la autenticación de forma selectiva. Esto es flexible y permite, por ejemplo, que ciertos endpoints (como webhooks) puedan quedar desprotegidos si fuera necesario, sin comprometer la seguridad del resto de la aplicación.

### ✗ Problemas Encontrados

| ID | Severidad | Problema | Impacto |
| :- | :--- | :--- | :--- |
| **RP-01** | **ALTO** | **Ausencia de Headers de Seguridad Críticos** | Sin HSTS (`Strict-Transport-Security`), los navegadores no son forzados a usar HTTPS, abriendo la puerta a ataques `sslstrip`. Sin `X-Frame-Options` o `Content-Security-Policy: frame-ancestors`, el sitio es vulnerable a ataques de *Clickjacking*. La falta de una CSP robusta permite ataques de Cross-Site Scripting (XSS). |
| **RP-02** | **MEDIO** | **Dependencia de Configuraciones SSL/TLS por Defecto** | No definir explícitamente los protocolos y ciphers de TLS permitidos puede hacer que el servidor negocie conexiones con algoritmos débiles o inseguros si un cliente así lo solicita. |
| **RP-03** | **MEDIO** | **Falta de Rate Limiting en el Edge** | Sin `rate limiting`, un atacante puede realizar un número ilimitado de peticiones a los servicios backend, ya sea para intentar adivinar credenciales, buscar vulnerabilidades o simplemente agotar los recursos del servidor (CPU, memoria, conexiones de base de datos). |

### ⚠️ Warnings/Recomendaciones

1.  **Compresión:**
    *   No se observa una configuración explícita de compresión (Gzip/Brotli). Activarla puede mejorar significativamente los tiempos de carga para los usuarios finales.

2.  **Logging Personalizado:**
    *   El formato de log de Nginx es el estándar. Se podría personalizar para incluir más información útil para la depuración y el análisis de seguridad, como los tiempos de respuesta del `upstream` o los `headers` de Authelia.

### 🔧 Soluciones Sugeridas

1.  **Para RP-01 y RP-02 (Añadir Headers y Hardening de SSL/TLS):**
    *   **解决方案:** Crear un nuevo archivo de configuración global, por ejemplo `nginx-proxy/conf.d/hardening.conf`, y añadir las siguientes directivas. Esto aplicará una política de seguridad sólida a todos los servicios detrás del proxy.
        ```nginx
        # /nginx-proxy/conf.d/hardening.conf

        # --- SSL/TLS Hardening ---
        # Fuerza el uso de TLS 1.2 y 1.3, y ciphers modernos y seguros.
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;

        # --- Security Headers ---
        # Fuerza HTTPS por 1 año, incluyendo subdominios.
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

        # Previene el Clickjacking.
        add_header X-Frame-Options "SAMEORIGIN" always;

        # Previene que el navegador infiera el MIME type.
        add_header X-Content-Type-Options "nosniff" always;

        # Activa el filtro XSS de los navegadores.
        add_header X-XSS-Protection "1; mode=block" always;

        # Controla qué información se envía en el header Referer.
        add_header Referrer-Policy "no-referrer-when-downgrade" always;

        # (Opcional pero recomendado) Content Security Policy (CSP) - ¡Requiere ajuste fino!
        # Esta es una política restrictiva, empezar con algo más permisivo si causa problemas.
        # add_header Content-Security-Policy "default-src 'self'; script-src 'self'; img-src 'self'; style-src 'self'; object-src 'none';" always;
        ```

2.  **Para RP-03 (Implementar Rate Limiting):**
    *   **解决方案:** Añadir una configuración de `limit_req_zone` en el mismo archivo `hardening.conf` para establecer límites globales.
        ```nginx
        # /nginx-proxy/conf.d/hardening.conf (continuación)

        # --- Rate Limiting ---
        # Define una zona de memoria para rastrear IPs. 10m puede almacenar ~160,000 IPs.
        limit_req_zone $binary_remote_addr zone=global_limit:10m rate=10r/s;

        # Aplica el límite a todas las localizaciones.
        limit_req zone=global_limit burst=20 nodelay;
        ```
        *   **Nota:** Esta configuración limita a 10 peticiones por segundo por IP, con un "burst" de 20. Estos valores son un punto de partida y deben ser ajustados según el tráfico esperado de la aplicación.
