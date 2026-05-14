# AUDIT 05: REVERSE PROXY I NGINX
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/05_REVERSE_PROXY_AND_NGINX.zh-cn.md)


**Data:** 2024-07-25
**Analista:** Jules

## 1. Resum de Troballes

| Estat | Àrea | Resum de Troballes |
| :--- | :--- | :--- |
| ✓ | **Integració amb Authelia** | La configuració de `forward auth` per a la integració amb Authelia és **correcta i segura**. L'ús d'un bloc `internal` i la correcta transmissió de headers (`X-Forwarded-*`) segueixen les millors pràctiques. |
| ✓ | **Estructura de Configuració** | L'estructura de configuració que utilitza `vhost.d` per aplicar la protecció per servei és **modular i escalable**, permetent un control granular sobre quins endpoints estan protegits. |
| ✗ | **Falta de Security Headers** | La configuració de Nginx **manca completament de headers de seguretat explícits**. No s'està configurant HSTS, CSP, X-Frame-Options, Permissions-Policy, ni altres headers essencials per a l'"enduriment" (hardening) del proxy. |
| ✗ | **Configuració de SSL/TLS Feble** | No s'especifica una política de SSL/TLS. Això significa que es depèn dels valors per defecte de `nginx-proxy`, que poden permetre l'ús de xifrats (ciphers) febles o versions de TLS obsoletes, exposant la comunicació a possibles atacs de downgrade. |
| ⚠️ | **Sense Rate Limiting** | No hi ha cap configuració de `rate limiting` a nivell del reverse proxy. Això deixa els serveis backend vulnerables a atacs de denegació de servei (DoS) o a intents de força bruta que podrien esgotar els recursos. |

---

## 2. Troballes Detallades

### ✓ El que està bé

1.  **Implementació de Forward Auth:**
    *   El fitxer `nginx-proxy/authelia-location.conf` està perfectament configurat. Utilitza la directiva `internal` per prevenir l'accés extern a l'endpoint de verificació i passa correctament tots els headers necessaris perquè Authelia pugui prendre decisions d'autorització.
    *   Els fitxers a `vhost.d` (ex. `n8n.localhost`) inclouen aquest bloc i configuren la directiva `auth_request` de forma correcta, assegurant que les peticions no autenticades siguin interceptades.

2.  **Modularitat de la Configuració:**
    *   El sistema de `vhost.d` permet aplicar l'autenticació de forma selectiva. Això és flexible i permet, per exemple, que certs endpoints (com webhooks) puguin quedar desprotegits si fos necessari, sense comprometre la seguretat de la resta de l'aplicació.

### ✗ Problemes Trobats

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **RP-01** | **ALT** | **Absència de Headers de Seguretat Crítics** | Sense HSTS (`Strict-Transport-Security`), els navegadors no són forçats a utilitzar HTTPS, obrint la porta a atacs `sslstrip`. Sense `X-Frame-Options` o `Content-Security-Policy: frame-ancestors`, el lloc és vulnerable a atacs de *Clickjacking*. La falta d'una CSP robusta permet atacs de Cross-Site Scripting (XSS). |
| **RP-02** | **MITJÀ** | **Dependència de Configuracions SSL/TLS per Defecte** | No definir explícitament els protocols i ciphers de TLS permesos pot fer que el servidor negociï connexions amb algoritmes febles o insegurs si un client així ho sol·licita. |
| **RP-03** | **MITJÀ** | **Falta de Rate Limiting a l'Edge** | Sense `rate limiting`, un atacant pot realitzar un nombre il·limitat de peticions als serveis backend, ja sigui per intentar endevinar credencials, buscar vulnerabilitats o simplement esgotar els recursos del servidor (CPU, memòria, connexions de base de dades). |

### ⚠️ Avisos/Recomanacions

1.  **Compressió:**
    *   No s'observa una configuració explícita de compressió (Gzip/Brotli). Activar-la pot millorar significativament els temps de càrrega per als usuaris finals.

2.  **Logging Personalitzat:**
    *   El format de log de Nginx és l'estàndard. Es podria personalitzar per incloure més informació útil per a la depuració i l'anàlisi de seguretat, com els temps de resposta de l'`upstream` o els `headers` d'Authelia.

### 🔧 Solucions Suggerides

1.  **Per a RP-01 i RP-02 (Afegir Headers i Hardening de SSL/TLS):**
    *   **Solució:** Crear un nou fitxer de configuració global, per exemple `nginx-proxy/conf.d/hardening.conf`, i afegir les següents directives. Això aplicarà una política de seguretat sòlida a tots els serveis darrere del proxy.
        ```nginx
        # /nginx-proxy/conf.d/hardening.conf

        # --- SSL/TLS Hardening ---
        # Força l'ús de TLS 1.2 i 1.3, i ciphers moderns i segurs.
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;

        # --- Security Headers ---
        # Força HTTPS per 1 any, incloent subdominis.
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

        # Prevé el Clickjacking.
        add_header X-Frame-Options "SAMEORIGIN" always;

        # Prevé que el navegador infereixi el MIME type.
        add_header X-Content-Type-Options "nosniff" always;

        # Activa el filtre XSS dels navegadors.
        add_header X-XSS-Protection "1; mode=block" always;

        # Controla quina informació s'envia al header Referer.
        add_header Referrer-Policy "no-referrer-when-downgrade" always;

        # (Opcional però recomanat) Content Security Policy (CSP) - Requereix ajust fi!
        # Aquesta és una política restrictiva, començar amb alguna cosa més permissiva si causa problemes.
        # add_header Content-Security-Policy "default-src 'self'; script-src 'self'; img-src 'self'; style-src 'self'; object-src 'none';" always;
        ```

2.  **Per a RP-03 (Implementar Rate Limiting):**
    *   **Solució:** Afegir una configuració de `limit_req_zone` al mateix fitxer `hardening.conf` per establir límits globals.
        ```nginx
        # /nginx-proxy/conf.d/hardening.conf (continuació)

        # --- Rate Limiting ---
        # Defineix una zona de memòria per rastrejar IPs. 10m pot emmagatzemar ~160,000 IPs.
        limit_req_zone $binary_remote_addr zone=global_limit:10m rate=10r/s;

        # Aplica el límit a totes les localitzacions.
        limit_req zone=global_limit burst=20 nodelay;
        ```
        *   **Nota:** Aquesta configuració limita a 10 peticions per segon per IP, amb un "burst" de 20. Aquests valors són un punt de partida i s'han d'ajustar segons el trànsit esperat de l'aplicació.
