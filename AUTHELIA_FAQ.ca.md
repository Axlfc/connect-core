# Configuració d'Authelia - FAQ i Respostes a les vostres preguntes
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/AUTHELIA_FAQ.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/AUTHELIA_FAQ.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/AUTHELIA_FAQ.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/AUTHELIA_FAQ.zh-cn.md)


## Q1: Configuració SMTP - Quina és la forma correcta de configurar l'SMTP?

### La vostra pregunta
"Quina és la forma correcta de configurar l'SMTP en el nou format? Hauríem d'utilitzar `notifier.smtp.address` en lloc d' `host` i `port` per separat?"

### Resposta: SÍ, utilitzeu només el format `address`

**Correcte (Modern v4.38.0+)**:
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

**Format**: `smtp[s]://[usuari@]host[:port]`

**Exemples**:
```
smtp://smtp.example.com:587              # STARTTLS al port 587
smtps://smtp.example.com:465             # TLS implícit al port 465
smtp://user@smtp.example.com:587         # Amb usuari a la URL
```

**Credencials mitjançant variables d'entorn**:
```yaml
environment:
  - AUTHELIA_NOTIFIER_SMTP_ADDRESS=smtp://smtp.tinet.cat:587
  - AUTHELIA_NOTIFIER_SMTP_USERNAME=el_vostre_correu@example.com
  - AUTHELIA_NOTIFIER_SMTP_PASSWORD=la_vostra_contrasenya
  - AUTHELIA_NOTIFIER_SMTP_SENDER=Authelia <noreply@example.com>
```

**Des de `.env`**:
```bash
SMTP_HOST=smtp.tinet.cat
SMTP_PORT=587
SMTP_USERNAME=el_vostre_correu@example.com
SMTP_PASSWORD=la_vostra_contrasenya
SMTP_SENDER=Authelia <noreply@example.com>
```

**NO barregeu formats** (causarà conflicte):
```yaml
# ❌ INCORRECTE - Això causa l'error de conflicte:
notifier:
  smtp:
    host: smtp.example.com        # ❌ Format antic
    port: 587                      # ❌ Format antic
    address: 'smtp://...:587'      # ❌ Format nou (conflicte!)
```

---

## Q2: Cookies de sessió per a Localhost

### La vostra pregunta
"Com hem de configurar les cookies de sessió per al desenvolupament local utilitzant dominis `.localhost`? L'error indica que els dominis han de tenir un punt o ser una adreça IP."

### Resposta: Utilitzeu `localhost` a la configuració, nginx-proxy gestiona la compatibilitat del navegador

**La Configuració**:
```yaml
session:
  cookies:
    - name: authelia_session
      domain: localhost              # ✅ Correcte per a la xarxa Docker
      authelia_url: https://auth.localhost
      default_redirection_url: https://forgejo.localhost
      same_site: Lax
      secure: false                  # Canviar a true en producció
```

**Com funciona**:
1. **Xarxa Docker**: Els serveis es comuniquen utilitzant `localhost` (funciona bé)
2. **Accés des del navegador**: L'usuari va a `http://auth.localhost:9091`
3. **nginx-proxy**: Intercepta la petició a `auth.localhost` i la dirigeix a Authelia
4. **Domini de la cookie**: nginx-proxy gestiona la reescriptura de la cookie per a la compatibilitat del navegador
5. **Resultat**: El navegador mai veu el domini `localhost` invàlid directament

**Per què funciona això**:
- El DNS intern de Docker resol `localhost` dins dels contenidors
- El navegador mai estableix cookies directament al domini `localhost`
- nginx-proxy intermedia i gestiona la traducció del domini de la cookie
- Tant l'accés intern de Docker com el del navegador funcionen perfectament

**Què NO fer**:
```yaml
# ❌ INCORRECTE - Això també fallarà:
domain: .localhost    # El navegador continua rebutjant dominis d'una sola etiqueta

# ❌ INCORRECTE - Massa restrictiu per a desenvolupament:
domain: auth.localhost  # Només funciona per a auth.localhost, no per a altres serveis

# ✅ CORRECTE:
domain: localhost     # Funciona per a la xarxa Docker + nginx-proxy gestiona el navegador
```

**Variables d'entorn**:
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

## Q3: Migració del Secret JWT

### La vostra pregunta
"Hauríem d'actualitzar el fitxer de configuració per utilitzar la nova clau `identity_validation.reset_password.jwt_secret`?"

### Resposta: SÍ, migreu a la nova ruta de clau

**Antic (Obsolet)**:
```yaml
jwt_secret: el_vostre_secret_aqui
```

**Nou (v4.38.0+)**:
```yaml
identity_validation:
  reset_password:
    jwt:
      expiration: 15m
      # Secret injectat via variable d'entorn
```

**Variable d'entorn**:
```yaml
environment:
  - AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE=/run/secrets/authelia_jwt_secret
```

**Configuració de Docker Compose**:
```yaml
secrets:
  - authelia_jwt_secret

services:
  authelia:
    environment:
      - AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE=/run/secrets/authelia_jwt_secret
```

**Per què migrar?**:
- ✅ Suporta el nou flux de restabliment de contrasenya d'Authelia
- ✅ Segueix el versionat semàntic (JWT separat per a diferents propòsits)
- ✅ Permet la futura separació de JWTs per a autenticació enfront de restabliment de contrasenya
- ✅ Elimina els avisos d'obsolescència

**Compatibilitat amb versions anteriors**:
- Authelia 4.38.0+ segueix acceptant l'antic `jwt_secret` però mostra un avís
- Es requereix la nova configuració per tenir logs nets
- La funcionalitat de restabliment de contrasenya només funciona amb la nova clau

---

## Q4: Configuració de la URL de redirecció per defecte

### La vostra pregunta
"Com hem de configurar correctament `default_redirection_url` a nivell de cada cookie en lloc de fer-ho globalment?"

### Resposta: Moveu-ho dins de la configuració de cada cookie

**Antic (Causa Error)**:
```yaml
session:
  expiration: 1h
  default_redirection_url: https://forgejo.localhost  # ❌ INCORRECTE
  cookies:
    - name: authelia_session
      domain: localhost
```

**Nou (Correcte)**:
```yaml
session:
  expiration: 1h
  # No ho poseu aquí ❌

  cookies:
    - name: authelia_session
      domain: localhost
      default_redirection_url: https://forgejo.localhost  # ✅ AQUÍ
      authelia_url: https://auth.localhost
      same_site: Lax
      secure: false

# Opcional: Fallback global al nivell de l'arrel
default_redirection_url: 'https://forgejo.localhost'
```

**Múltiples Cookies (Avançat)**:
```yaml
session:
  cookies:
    # Cookie de producció
    - name: authelia_session
      domain: exemple.com
      default_redirection_url: https://app.exemple.com
      secure: true

    # Cookie de desenvolupament
    - name: authelia_session_dev
      domain: localhost
      default_redirection_url: https://forgejo.localhost
      secure: false

# Fallback global
default_redirection_url: 'https://exemple.com'
```

**Com funciona**:
1. L'usuari accedeix a un servei protegit (ex. n8n.localhost)
2. És redirigit al login d'Authelia (auth.localhost)
3. Després del login, Authelia comprova el `default_redirection_url` de cada cookie
4. Redirigeix a la URL configurada (ex. forgejo.localhost)
5. Si no hi ha configuració per cookie, utilitza el `default_redirection_url` global

**Camps de configuració requerits**:
```yaml
cookies:
  - name: authelia_session              # Nom de la cookie
    domain: localhost                   # Domini de la cookie
    authelia_url: https://auth.localhost  # Endpoint d'Authelia
    default_redirection_url: https://forgejo.localhost  # Destí de fallback
    same_site: Lax                      # Protecció CSRF
    secure: false                       # true en producció
```

---

## Q5: HTTP vs HTTPS - Desenvolupament Local vs Producció

### La vostra pregunta
"Podem executar Authelia amb HTTP en desenvolupament local (amb nginx-proxy gestionant SSL mitjançant certificats autosignats o sense SSL) i després canviar a HTTPS en producció?"

### Resposta: SÍ, Authelia és agnòstic al protocol

**Desenvolupament Local (HTTP, sense SSL)**:
```yaml
# A authelia/configuration.yml:
server:
  address: 'tcp://0.0.0.0:9091'
  tls:
    enabled: false          # ✅ Només HTTP

session:
  cookies:
    - name: authelia_session
      secure: false         # ✅ Permetre cookies HTTP
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
    # nginx-proxy serveix via HTTP
```

**Com accedir**:
```
Navegador: http://auth.localhost:9091
Navegador: http://n8n.localhost
```

---

**Producció (HTTPS amb Let's Encrypt)**:
```yaml
# A authelia/configuration.yml (NO CALEN CANVIS):
server:
  address: 'tcp://0.0.0.0:9091'
  tls:
    enabled: false          # ✅ Segueix sent false
    # nginx-proxy gestiona la terminació TLS

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
    - VIRTUAL_HOST=auth.exemple.com
    - VIRTUAL_PORT=9091
    # nginx-proxy + acme-companion gestionen HTTPS + Let's Encrypt
```

**Com accedir**:
```
Navegador: https://auth.exemple.com
Navegador: https://app.exemple.com
```

---

**Punts Clau**:

1. **Authelia en si**: Sempre s'executa en HTTP (port 9091) internament
2. **Terminació TLS**: Deixeu que nginx-proxy gestioni la terminació HTTPS
3. **Configuració d'Authelia**: `tls.enabled: false` per a tots els escenaris
4. **Seguretat de la sessió**:
   - Dev local: `secure: false` (permetre HTTP)
   - Producció: `secure: true` (requerir HTTPS)
5. **Ruta de migració**:
   - Començar amb dev local (HTTP, sense SSL)
   - Moure a producció (HTTPS via nginx-proxy + Let's Encrypt)
   - No calen canvis a la configuració d'Authelia
   - Només canviar les etiquetes de docker-compose i les variables d'entorn

---

## Estat de la Implementació

Totes les correccions han estat implementades:

| Problema | Estat | Fitxer |
|-------|--------|------|
| Obsolescència de secret JWT | ✅ Corregit | [authelia/configuration.yml](authelia/configuration.yml) |
| Conflicte SMTP | ✅ Corregit | [authelia/configuration.yml](authelia/configuration.yml) + [docker-compose.yml](docker-compose.yml) |
| Cookies de sessió | ✅ Corregit | [authelia/configuration.yml](authelia/configuration.yml) |
| Domini de la cookie | ✅ Corregit | [authelia/configuration.yml](authelia/configuration.yml) |
| HTTP vs HTTPS | ✅ Configurat | [authelia/configuration.yml](authelia/configuration.yml) |
| Documentació | ✅ Completa | [docs/authelia-setup.md](docs/authelia-setup.md) + [AUTHELIA_FIXES_SUMMARY.md](AUTHELIA_FIXES_SUMMARY.md) |

---

## Inici Ràpid

1. **Actualitzar fitxers de configuració** ✅ (Ja fet)
2. **Crear `.env` amb SMTP**:
   ```bash
   SMTP_HOST=smtp.tinet.cat
   SMTP_PORT=587
   SMTP_USERNAME=el_vostre_correu@example.com
   SMTP_PASSWORD=la_vostra_contrasenya
   SMTP_SENDER=Authelia <noreply@example.com>
   AUTHELIA_DOMAIN=auth.localhost
   ```

3. **Generar secrets** (si no s'ha fet):
   ```bash
   mkdir -p ./secrets
   openssl rand -base64 32 > ./secrets/authelia_jwt_secret.txt
   openssl rand -base64 32 > ./secrets/authelia_session_secret.txt
   chmod 600 ./secrets/*.txt
   ```

4. **Iniciar serveis**:
   ```bash
   docker compose up -d redis authelia
   docker compose logs -f authelia
   ```

5. **Prova**:
   ```bash
   curl http://localhost:9091/api/health
   # Esperat: 200 OK
   ```

6. **Accedir a la UI**:
   ```
   Navegador: http://auth.localhost:9091
   ```

---

## Encara necessiteu ajuda?

- **Guia de configuració completa**: Vegeu [docs/authelia-setup.md](docs/authelia-setup.md)
- **Explicacions detallades dels problemes**: Vegeu [AUTHELIA_FIXES_SUMMARY.md](AUTHELIA_FIXES_SUMMARY.md)
- **Solució de problemes**: Consulteu la secció "Troubleshooting" a [docs/authelia-setup.md](docs/authelia-setup.md)
- **Docs oficials**: https://www.authelia.com/configuration/
