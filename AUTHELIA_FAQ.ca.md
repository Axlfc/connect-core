# Configuración de Authelia - FAQ y Respuestas a sus Preguntas
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/AUTHELIA_FAQ.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/AUTHELIA_FAQ.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/AUTHELIA_FAQ.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/AUTHELIA_FAQ.zh-cn.md)


## Q1: Configuración SMTP - ¿Cuál es la forma correcta de configurar SMTP?

### Su pregunta
"¿Cuál es la forma correcta de configurar SMTP en el nuevo formato? ¿Deberíamos usar `notifier.smtp.address` en lugar de `host` y `port` por separado?"

### Respuesta: SÍ, use solo el formato `address`

**Correcto (Moderno v4.38.0+)**:
```yaml
notifier:
  smtp:
    address: 'smtp://smtp.tinet.cat:587'
    timeout: 5s
    sender: 'Authelia <noreply@example.com>'
    tls:
      server_name: smtp.tinet.cat
      skip_verify: false
```

**Formato**: `smtp[s]://[usuario@]host[:puerto]`

**Ejemplos**:
```
smtp://smtp.example.com:587              # STARTTLS en el puerto 587
smtps://smtp.example.com:465             # TLS implícito en el puerto 465
smtp://user@smtp.example.com:587         # Con usuario en la URL
```

**Credenciales mediante variables de entorno**:
```yaml
environment:
  - AUTHELIA_NOTIFIER_SMTP_ADDRESS=smtp://smtp.tinet.cat:587
  - AUTHELIA_NOTIFIER_SMTP_USERNAME=su_correo@example.com
  - AUTHELIA_NOTIFIER_SMTP_PASSWORD=su_contraseña
  - AUTHELIA_NOTIFIER_SMTP_SENDER=Authelia <noreply@example.com>
```

**Desde `.env`**:
```bash
SMTP_HOST=smtp.tinet.cat
SMTP_PORT=587
SMTP_USERNAME=su_correo@example.com
SMTP_PASSWORD=su_contraseña
SMTP_SENDER=Authelia <noreply@example.com>
```

**NO mezcle formatos** (causará conflicto):
```yaml
# ❌ INCORRECTO - Esto causa el error de conflicto:
notifier:
  smtp:
    host: smtp.example.com        # ❌ Formato antiguo
    port: 587                      # ❌ Formato antiguo
    address: 'smtp://...:587'      # ❌ Formato nuevo (¡conflicto!)
```

---

## Q2: Cookies de sesión para Localhost

### Su pregunta
"¿Cómo debemos configurar las cookies de sesión para el desarrollo local usando dominios `.localhost`? El error indica que los dominios deben tener un punto o ser una dirección IP."

### Respuesta: Use `localhost` en la configuración, nginx-proxy gestiona la compatibilidad del navegador

**La Configuración**:
```yaml
session:
  cookies:
    - name: authelia_session
      domain: localhost              # ✅ Correcto para la red Docker
      authelia_url: https://auth.localhost
      default_redirection_url: https://forgejo.localhost
      same_site: Lax
      secure: false                  # Cambiar a true en producción
```

**Cómo funciona**:
1. **Red Docker**: Los servicios se comunican usando `localhost` (funciona bien)
2. **Acceso desde el navegador**: El usuario va a `http://auth.localhost:9091`
3. **nginx-proxy**: Intercepta la petición a `auth.localhost` y la dirige a Authelia
4. **Dominio de la cookie**: nginx-proxy gestiona la reescritura de la cookie para la compatibilidad del navegador
5. **Resultado**: El navegador nunca ve el dominio `localhost` inválido directamente

**Por qué funciona esto**:
- El DNS interno de Docker resuelve `localhost` dentro de los contenedores
- El navegador nunca establece cookies directamente en el dominio `localhost`
- nginx-proxy intermedia y gestiona la traducción del dominio de la cookie
- Tanto el acceso interno de Docker como el del navegador funcionan perfectamente

**Qué NO hacer**:
```yaml
# ❌ INCORRECTO - Esto también fallará:
domain: .localhost    # El navegador sigue rechazando dominios de una sola etiqueta

# ❌ INCORRECTO - Demasiado restrictivo para desarrollo:
domain: auth.localhost  # Solo funciona para auth.localhost, no para otros servicios

# ✅ CORRECTO:
domain: localhost     # Funciona para la red Docker + nginx-proxy gestiona el navegador
```

**Variables de entorno**:
```yaml
environment:
  - VIRTUAL_HOST=${AUTHELIA_DOMAIN:-auth.localhost}
  - VIRTUAL_PORT=9091
```

**En `.env`**:
```bash
AUTHELIA_DOMAIN=auth.localhost
```

---

## Q3: Migración del Secreto JWT

### Su pregunta
"¿Deberíamos actualizar el archivo de configuración para usar la nueva clave `identity_validation.reset_password.jwt_secret`?"

### Respuesta: SÍ, migre a la nueva ruta de clave

**Antiguo (Obsoleto)**:
```yaml
jwt_secret: su_secreto_aqui
```

**Nuevo (v4.38.0+)**:
```yaml
identity_validation:
  reset_password:
    jwt:
      expiration: 15m
      # Secreto inyectado vía variable de entorno
```

**Variable de entorno**:
```yaml
environment:
  - AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE=/run/secrets/authelia_jwt_secret
```

**Configuración de Docker Compose**:
```yaml
secrets:
  - authelia_jwt_secret

services:
  authelia:
    environment:
      - AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE=/run/secrets/authelia_jwt_secret
```

**¿Por qué migrar?**:
- ✅ Soporta el nuevo flujo de restablecimiento de contraseña de Authelia
- ✅ Sigue el versionado semántico (JWT separado para diferentes propósitos)
- ✅ Permite la futura separación de JWTs para autenticación frente a restablecimiento de contraseña
- ✅ Elimina las advertencias de obsolescencia

**Compatibilidad con versiones anteriores**:
- Authelia 4.38.0+ sigue aceptando el antiguo `jwt_secret` pero muestra una advertencia
- Se requiere la nueva configuración para tener logs limpios
- La funcionalidad de restablecimiento de contraseña solo funciona con la nueva clave

---

## Q4: Configuración de la URL de redirección por defecto

### Su pregunta
"¿Cómo debemos configurar correctamente `default_redirection_url` a nivel de cada cookie en lugar de hacerlo globalmente?"

### Respuesta: Muévalo dentro de la configuración de cada cookie

**Antiguo (Causa Error)**:
```yaml
session:
  expiration: 1h
  default_redirection_url: https://forgejo.localhost  # ❌ INCORRECTO
  cookies:
    - name: authelia_session
      domain: localhost
```

**Nuevo (Correcto)**:
```yaml
session:
  expiration: 1h
  # No lo ponga aquí ❌

  cookies:
    - name: authelia_session
      domain: localhost
      default_redirection_url: https://forgejo.localhost  # ✅ AQUÍ
      authelia_url: https://auth.localhost
      same_site: Lax
      secure: false

# Opcional: Fallback global al nivel de la raíz
default_redirection_url: 'https://forgejo.localhost'
```

**Múltiples Cookies (Avanzado)**:
```yaml
session:
  cookies:
    # Cookie de producción
    - name: authelia_session
      domain: ejemplo.com
      default_redirection_url: https://app.ejemplo.com
      secure: true

    # Cookie de desarrollo
    - name: authelia_session_dev
      domain: localhost
      default_redirection_url: https://forgejo.localhost
      secure: false

# Fallback global
default_redirection_url: 'https://ejemplo.com'
```

**Cómo funciona**:
1. El usuario accede a un servicio protegido (ej. n8n.localhost)
2. Es redirigido al login de Authelia (auth.localhost)
3. Tras el login, Authelia comprueba el `default_redirection_url` de cada cookie
4. Redirige a la URL configurada (ej. forgejo.localhost)
5. Si no hay configuración por cookie, usa el `default_redirection_url` global

**Campos de configuración requeridos**:
```yaml
cookies:
  - name: authelia_session              # Nombre de la cookie
    domain: localhost                   # Dominio de la cookie
    authelia_url: https://auth.localhost  # Endpoint de Authelia
    default_redirection_url: https://forgejo.localhost  # Destino de fallback
    same_site: Lax                      # Protección CSRF
    secure: false                       # true en producción
```

---

## Q5: HTTP vs HTTPS - Desarrollo Local vs Producción

### Su pregunta
"¿Podemos ejecutar Authelia con HTTP en desarrollo local (con nginx-proxy gestionando SSL mediante certificados autofirmados o sin SSL) y luego cambiar a HTTPS en producción?"

### Respuesta: SÍ, Authelia es agnóstico al protocolo

**Desarrollo Local (HTTP, sin SSL)**:
```yaml
# En authelia/configuration.yml:
server:
  address: 'tcp://0.0.0.0:9091'
  tls:
    enabled: false          # ✅ Solo HTTP

session:
  cookies:
    - name: authelia_session
      secure: false         # ✅ Permitir cookies HTTP
      same_site: Lax
```

**Docker Compose**:
```yaml
authelia:
  expose:
    - 9091
  environment:
    - VIRTUAL_HOST=auth.localhost
    - VIRTUAL_PORT=9091
    # nginx-proxy sirve vía HTTP
```

**Cómo acceder**:
```
Navegador: http://auth.localhost:9091
Navegador: http://n8n.localhost
```

---

**Producción (HTTPS con Let's Encrypt)**:
```yaml
# En authelia/configuration.yml (NO SE NECESITAN CAMBIOS):
server:
  address: 'tcp://0.0.0.0:9091'
  tls:
    enabled: false          # ✅ Sigue siendo false
    # nginx-proxy gestiona la terminación TLS

session:
  cookies:
    - name: authelia_session
      secure: true          # ✅ Requerir HTTPS
      same_site: Strict
```

**Docker Compose**:
```yaml
authelia:
  expose:
    - 9091
  labels:
    - com.github.jrcs.letsencrypt_nginx_proxy_companion.enable=true
  environment:
    - VIRTUAL_HOST=auth.ejemplo.com
    - VIRTUAL_PORT=9091
    # nginx-proxy + acme-companion gestionan HTTPS + Let's Encrypt
```

**Cómo acceder**:
```
Navegador: https://auth.ejemplo.com
Navegador: https://app.ejemplo.com
```

---

**Puntos Clave**:

1. **Authelia en sí**: Siempre se ejecuta en HTTP (puerto 9091) internamente
2. **Terminación TLS**: Deje que nginx-proxy gestione la terminación HTTPS
3. **Configuración de Authelia**: `tls.enabled: false` para todos los escenarios
4. **Seguridad de la sesión**:
   - Dev local: `secure: false` (permitir HTTP)
   - Producción: `secure: true` (requerir HTTPS)
5. **Ruta de migración**:
   - Empezar con dev local (HTTP, sin SSL)
   - Mover a producción (HTTPS vía nginx-proxy + Let's Encrypt)
   - No se necesitan cambios en la configuración de Authelia
   - Solo cambiar las etiquetas de docker-compose y las variables de entorno

---

## Estado de la Implementación

Todas las correcciones han sido implementadas:

| Problema | Estado | Archivo |
|-------|--------|------|
| Obsolescencia de secreto JWT | ✅ Corregido | [authelia/configuration.yml](authelia/configuration.yml) |
| Conflicto SMTP | ✅ Corregido | [authelia/configuration.yml](authelia/configuration.yml) + [docker-compose.yml](docker-compose.yml) |
| Cookies de sesión | ✅ Corregido | [authelia/configuration.yml](authelia/configuration.yml) |
| Dominio de la cookie | ✅ Corregido | [authelia/configuration.yml](authelia/configuration.yml) |
| HTTP vs HTTPS | ✅ Configurado | [authelia/configuration.yml](authelia/configuration.yml) |
| Documentación | ✅ Completa | [docs/authelia-setup.md](docs/authelia-setup.md) + [AUTHELIA_FIXES_SUMMARY.md](AUTHELIA_FIXES_SUMMARY.md) |

---

## Inicio Rápido

1. **Actualizar archivos de configuración** ✅ (Ya hecho)
2. **Crear `.env` con SMTP**:
   ```bash
   SMTP_HOST=smtp.tinet.cat
   SMTP_PORT=587
   SMTP_USERNAME=su_correo@example.com
   SMTP_PASSWORD=su_contraseña
   SMTP_SENDER=Authelia <noreply@example.com>
   AUTHELIA_DOMAIN=auth.localhost
   ```

3. **Generar secretos** (si no se ha hecho):
   ```bash
   mkdir -p ./secrets
   openssl rand -base64 32 > ./secrets/authelia_jwt_secret.txt
   openssl rand -base64 32 > ./secrets/authelia_session_secret.txt
   chmod 600 ./secrets/*.txt
   ```

4. **Iniciar servicios**:
   ```bash
   docker compose up -d redis authelia
   docker compose logs -f authelia
   ```

5. **Prueba**:
   ```bash
   curl http://localhost:9091/api/health
   # Esperado: 200 OK
   ```

6. **Acceder a la UI**:
   ```
   Navegador: http://auth.localhost:9091
   ```

---

## ¿Aún necesita ayuda?

- **Guía de configuración completa**: Ver [docs/authelia-setup.md](docs/authelia-setup.md)
- **Explicaciones detalladas de los problemas**: Ver [AUTHELIA_FIXES_SUMMARY.md](AUTHELIA_FIXES_SUMMARY.md)
- **Solución de problemas**: Consulte la sección "Troubleshooting" en [docs/authelia-setup.md](docs/authelia-setup.md)
- **Docs oficiales**: https://www.authelia.com/configuration/
