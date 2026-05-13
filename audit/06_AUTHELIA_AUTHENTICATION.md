# AUDIT 06: AUTHELIA - AUTENTICACIÓN Y AUTORIZACIÓN
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.en.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.zh-cn.md)


**Fecha:** 2024-07-25
**Analista:** Jules

## 1. Resumen de Hallazgos

| Estado | Área | Resumen de Hallazgos |
| :--- | :--- | :--- |
| ✓ | **Integración y SSO** | La configuración de Authelia como un proveedor de `forward auth` para Nginx está **correctamente implementada**. El flujo de Single Sign-On (SSO) es conceptualmente sólido. |
| ✓ | **Política de Acceso** | La política de `default_policy: deny` es la **mejor práctica de seguridad**, forzando a que cada servicio deba ser explícitamente autorizado. Las reglas por dominio son claras y fáciles de gestionar. |
| ✗ | **Política de Contraseñas (Hashing)** | La configuración del algoritmo de hash `argon2id` es **críticamente débil**, utilizando solo `iterations: 1`. Esto hace que los hashes de contraseña almacenados sean vulnerables a ataques de cracking offline a alta velocidad. |
| ✗ | **Seguridad de la Sesión** | La cookie de sesión está configurada con `secure: false`, un parámetro **solo para desarrollo**. En producción, esto permitiría que la cookie de sesión se transmita sin cifrar sobre HTTP, exponiéndola a ataques de secuestro de sesión (session hijacking). |
| ⚠️ | **Backend de Almacenamiento** | El sistema utiliza una base de datos SQLite local para el almacenamiento. Aunque es funcional, no se recomienda para entornos de producción con alta concurrencia o que requieran alta disponibilidad. |
| ⚠️ | **Gestión de Secretos** | El password del usuario `admin` se carga desde una variable de entorno (`AUTHELIA_ADMIN_PASSWORD`), lo que perpetúa la estrategia de gestión de secretos inconsistente y menos segura identificada en el **AUDIT 02**. |

---

## 2. Hallazgos Detallados

### ✓ Lo que está bien

1.  **Modelo de Confianza Cero (Zero Trust):**
    *   La política de `access_control.default_policy: deny` es excelente. Asegura que ningún servicio nuevo sea expuesto accidentalmente sin una regla de autorización explícita.

2.  **Protección Anti-Fuerza Bruta:**
    *   La sección `regulation` está configurada con valores razonables (`max_retries: 3`, `ban_time: 15m`). Esto proporciona una primera línea de defensa efectiva contra ataques de adivinación de contraseñas en línea.

3.  **Gestión de Secretos de Sesión:**
    *   Los secretos de sesión y JWT de Authelia se gestionan correctamente a través de Docker Secrets (`AUTHELIA_SESSION_SECRET_FILE`, `AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE`), la forma más segura de manejar este tipo de credenciales.

### ✗ Problemas Encontrados

| ID | Severidad | Problema | Impacto |
| :- | :--- | :--- | :--- |
| **A-01** | **CRÍTICO** | **Hashing de Contraseñas Débil** | La configuración `password.iterations: 1` para `argon2id` es peligrosamente baja. Argon2id está diseñado para ser computacionalmente intensivo. Con 1 iteración, un atacante que obtenga el archivo `users_database.yml` podría crackear las contraseñas miles de veces más rápido de lo esperado, haciendo trivial la recuperación de contraseñas débiles. |
| **A-02** | **CRÍTICO** | **Cookie de Sesión Insegura** | La configuración `cookies.secure: false` indica al navegador que puede enviar la cookie de sesión sobre conexiones HTTP no cifradas. Si por alguna razón (ej. un ataque de `sslstrip`) un usuario se conecta por HTTP, su cookie de sesión sería interceptada, permitiendo a un atacante tomar control total de su cuenta. |
| **A-03** | **MEDIO** | **Duración Excesiva de "Recordarme"** | La sesión de `remember_me_duration` está configurada en `1y` (un año). Si la sesión de un usuario es comprometida, el atacante tendría acceso potencial durante un año completo, incluso si el usuario no inicia sesión activamente. |

### ⚠️ Warnings/Recomendaciones

1.  **Backend de Producción:**
    *   **Recomendación:** Para un entorno de producción, migrar el `storage` de Authelia de SQLite a una base de datos más robusta como PostgreSQL. Esto mejora el rendimiento, la concurrencia y la fiabilidad. Authelia puede usar la misma instancia de Postgres que ya está en el stack (con una base de datos separada).

2.  **Documentación de Authelia:**
    *   El proyecto contiene múltiples archivos `AUTHELIA_*.md`. Sería beneficioso consolidarlos en una única guía dentro del directorio `/docs` o `/audit` para clarificar la arquitectura de autenticación y las decisiones de diseño.

### 🔧 Soluciones Sugeridas

1.  **Para A-01 (Fortalecer Hashing - CRÍTICO):**
    *   **Solución:** Incrementar el número de iteraciones en `authelia/configuration.yml` a un valor seguro. El valor recomendado por Authelia es `2`, pero `3` o `4` ofrecen un balance aún mejor entre seguridad y rendimiento.
        ```diff
        --- a/authelia/configuration.yml
        +++ b/authelia/configuration.yml
        @@ -60,7 +60,7 @@
     path: /config/users_database.yml
     password:
       algorithm: argon2id
-      iterations: 1
+      iterations: 3
       salt_length: 16
       parallelism: 8
       memory: 64
        ```
    *   **Importante:** Después de aplicar este cambio, todas las contraseñas de usuario existentes deberán ser reseteadas para que se vuelvan a hashear con la nueva configuración.

2.  **Para A-02 (Asegurar Cookie de Sesión - CRÍTICO):**
    *   **Solución:** Cambiar el valor de `secure` a `true` en la configuración de la cookie. Esto debe hacerse antes de cualquier despliegue en un entorno que utilice HTTPS.
        ```diff
        --- a/authelia/configuration.yml
        +++ b/authelia/configuration.yml
        @@ -40,7 +40,7 @@
       authelia_url: https://auth.localhost
       default_redirection_url: https://forgejo.localhost
       same_site: Lax
-      secure: false  # Set to true in production with HTTPS
+      secure: true
        ```

3.  **Para A-03 (Reducir Duración de Sesión):**
    *   **Solución:** Reducir el valor de `remember_me_duration` a un periodo más conservador, como `1M` (un mes) o `14d` (dos semanas), para limitar la ventana de exposición en caso de compromiso de la sesión.
        ```diff
        --- a/authelia/configuration.yml
        +++ b/authelia/configuration.yml
        @@ -32,7 +32,7 @@
   # session.secret is provided via AUTHELIA_SESSION_SECRET_FILE
   expiration: 1h
   inactivity: 5m
-  remember_me_duration: 1y
+  remember_me_duration: 30d
   # Per-cookie configuration for local development with .localhost domains
   cookies:
     - name: authelia_session
        ```
