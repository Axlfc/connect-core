# AUDIT 06: AUTHELIA - AUTENTICACIÓ I AUTORITZACIÓ
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/06_AUTHELIA_AUTHENTICATION.zh-cn.md)


**Data:** 2024-07-25
**Analista:** Jules

## 1. Resum de Troballes

| Estat | Àrea | Resum de Troballes |
| :--- | :--- | :--- |
| ✓ | **Integració i SSO** | La configuració d'Authelia com un proveïdor de `forward auth` per a Nginx està **correctament implementada**. El flux de Single Sign-On (SSO) és conceptualment sòlid. |
| ✓ | **Política d'Accés** | La política de `default_policy: deny` és la **millor pràctica de seguretat**, forçant que cada servei hagi de ser explícitament autoritzat. Les regles per domini són clares i fàcils de gestionar. |
| ✗ | **Política de Contrasenyes (Hashing)** | La configuració de l'algoritme de hash `argon2id` és **críticament feble**, utilitzant només `iterations: 1`. Això fa que els hashes de contrasenya emmagatzemats siguin vulnerables a atacs de cracking offline a alta velocitat. |
| ✗ | **Seguretat de la Sessió** | La cookie de sessió està configurada amb `secure: false`, un paràmetre **només per a desenvolupament**. En producció, això permetria que la cookie de sessió es transmetés sense xifrar sobre HTTP, exposant-la a atacs de segrest de sessió (session hijacking). |
| ⚠️ | **Backend d'Emmagatzematge** | El sistema utilitza una base de dades SQLite local per a l'emmagatzematge. Tot i que és funcional, no es recomana per a entorns de producció amb alta concurrència o que requereixin alta disponibilitat. |
| ⚠️ | **Gestió de Secrets** | El password de l'usuari `admin` es carrega des d'una variable d'entorn (`AUTHELIA_ADMIN_PASSWORD`), cosa que perpetua l'estratègia de gestió de secrets inconsistent i menys segura identificada a l'**AUDIT 02**. |

---

## 2. Troballes Detallades

### ✓ El que està bé

1.  **Model de Confiança Zero (Zero Trust):**
    *   La política d' `access_control.default_policy: deny` és excel·lent. Assegura que cap servei nou sigui exposat accidentalment sense una regla d'autorització explícita.

2.  **Protecció Anti-Força Bruta:**
    *   La secció `regulation` està configurada amb valors raonables (`max_retries: 3`, `ban_time: 15m`). Això proporciona una primera línia de defensa efectiva contra atacs d'endevinació de contrasenyes en línia.

3.  **Gestió de Secrets de Sessió:**
    *   Els secrets de sessió i JWT d'Authelia es gestionen correctament a través de Docker Secrets (`AUTHELIA_SESSION_SECRET_FILE`, `AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE`), la forma més segura de manejar aquest tipus de credencials.

### ✗ Problemes Trobats

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **A-01** | **CRÍTIC** | **Hashing de Contrasenyes Feble** | La configuració `password.iterations: 1` per a `argon2id` és perillosament baixa. Argon2id està dissenyat per ser computacionalment intensiu. Amb 1 iteració, un atacant que obtingui el fitxer `users_database.yml` podria crackejar les contrasenyes milers de vegades més ràpid del que s'esperava, fent trivial la recuperació de contrasenyes febles. |
| **A-02** | **CRÍTIC** | **Cookie de Sessió Insegura** | La configuració `cookies.secure: false` indica al navegador que pot enviar la cookie de sessió sobre connexions HTTP no xifrades. Si per alguna raó (ex. un atac de `sslstrip`) un usuari es connecta per HTTP, la seva cookie de sessió seria interceptada, permetent a un atacant prendre el control total del seu compte. |
| **A-03** | **MITJÀ** | **Durada Excessiva de "Recorda'm"** | La sessió de `remember_me_duration` està configurada en `1y` (un any). Si la sessió d'un usuari és compromesa, l'atacant tindria accés potencial durant un any sencer, fins i tot si l'usuari no inicia sessió activament. |

---

### ⚠️ Avisos/Recomanacions

1.  **Backend de Producció:**
    *   **Recomanació:** Per a un entorn de producció, migrar l'`storage` d'Authelia de SQLite a una base de dades més robusta com PostgreSQL. Això millora el rendiment, la concurrència i la fiabilitat. Authelia pot usar la mateixa instància de Postgres que ja està a l'stack (amb una base de dades separada).

2.  **Documentació d'Authelia:**
    *   El projecte conté múltiples fitxers `AUTHELIA_*.md`. Seria beneficiós consolidar-los en una única guia dins del directori `/docs` o `/audit` per aclarir l'arquitectura d'autenticació i les decisions de disseny.

---

### 🔧 Solucions Suggerides

1.  **Per a A-01 (Enfortir Hashing - CRÍTIC):**
    *   **Solució:** Incrementar el nombre d'iteracions a `authelia/configuration.yml` a un valor segur. El valor recomanat per Authelia és `2`, però `3` o `4` ofereixen un balanç encara millor entre seguretat i rendiment.
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
    *   **Important:** Després d'aplicar aquest canvi, totes les contrasenyes d'usuari existents hauran de ser resetejades perquè es tornin a hashejar amb la nova configuració.

2.  **Per a A-02 (Assegurar Cookie de Sessió - CRÍTIC):**
    *   **Solució:** Canviar el valor de `secure` a `true` en la configuració de la cookie. Això s'ha de fer abans de qualsevol desplegament en un entorn que utilitzi HTTPS.
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

3.  **Per a A-03 (Reduir Durada de Sessió):**
    *   **Solució:** Reduir el valor de `remember_me_duration` a un període més conservador, com `1M` (un mes) o `14d` (dues setmanes), per limitar la finestra d'exposició en cas de compromís de la sessió.
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
