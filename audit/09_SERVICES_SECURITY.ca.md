# AUDIT 09: SERVEIS PRINCIPALS - REVISIÓ PROFUNDA
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/09_SERVICES_SECURITY.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/09_SERVICES_SECURITY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/09_SERVICES_SECURITY.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/09_SERVICES_SECURITY.zh-cn.md)


**Data:** 2024-07-25
**Analista:** Jules

## 1. Resum de Troballes

| Estat | Àrea | Resum de Troballes |
| :--- | :--- | :--- |
| ✗ | **n8n (Automatització)** | **CRÍTIC:** La configuració dels `task-runners` deshabilita completament el sandboxing, permetent l'**execució de codi arbitrari** al contenidor del runner per qualsevol usuari que pugui crear un workflow. |
| ✗ | **Ollama (LLMs)** | L' `ollama-proxy` és un simple proxy de pas **sense cap capa de seguretat**. No implementa rate limiting, control d'accés per API key, ni logging de peticions, depenent exclusivament d'Authelia per a la seva protecció. |
| ⚠️ | **ComfyUI (Imatges)** | L'autenticació nativa està deshabilitada (`WEB_ENABLE_AUTH=false`), creant una **dependència total en Authelia**. Si Authelia fos bypassat, el servei de generació d'imatges quedaria completament exposat i vulnerable a l'abús de recursos. |
| ✗ | **Matrix (Missatgeria)** | **CRÍTIC:** L'script d'entrypoint del contenidor de Matrix **exposa secrets crítics als logs** durant la primera execució. A més, la configuració de registre d'usuaris està habilitada per defecte al `.env.staging`, cosa que podria permetre registres no desitjats. |
| ⚠️ | **Qdrant (Vector DB)** | El servei no té configurada cap clau d'API per a l'accés, cosa que significa que qualsevol servei dins de la mateixa xarxa de Docker (`ai`) pot llegir i escriure a la base de dades vectorial sense autenticació. |

---

## 2. Troballes Detallades

### a) n8n (Workflow Automation)

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **S-n8n-01** | **CRÍTIC** | **Sandboxing Deshabilitat als Runners** | El fitxer `n8n-task-runners.json` configura `NODE_FUNCTION_ALLOW_BUILTIN` i `N8N_RUNNERS_STDLIB_ALLOW` amb `*`. Això permet a un usuari amb accés a n8n usar mòduls com `child_process` o `fs` en un node de "Code", donant-li un shell complet dins del contenidor del runner. Podria exfiltrar dades, atacar altres serveis a la xarxa interna o instal·lar malware. |

#### 🔧 Solució Suggerida (n8n)

*   **Solució Immediata:** Modificar `n8n-task-runners.json` per implementar una política de "deny-list" o "allow-list" estricta. Denegar explícitament l'accés a mòduls perillosos del sistema.
    ```json
    // A n8n-task-runners.json, per al runner de javascript
    "env-overrides": {
        "NODE_FUNCTION_DENY_BUILTIN": "fs,os,child_process,worker_threads,vm",
        "NODE_FUNCTION_ALLOW_EXTERNAL": "axios,moment" // Permetre només mòduls específics
    }
    ```

### b) Ollama (LLMs Locals)

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **S-ollama-01** | **ALT** | **Proxy sense Seguretat Addicional** | L' `ollama-proxy` és un proxy de reenviaments simple. No afegeix valor de seguretat. Si Authelia falla o és mal configurat, no hi ha una segona capa de defensa. Un atacant podria abusar dels models de LLM, consumint recursos de GPU/CPU de forma massiva i sense control. |

#### 🔧 Solució Suggerida (Ollama)

*   **Solució:** Millorar l' `ollama-proxy` perquè actuï com un veritable "API Gateway".
    1.  **Afegir Rate Limiting:** Implementar un middleware a `server.js` (ex. `express-rate-limit`) per limitar el nombre de peticions per IP.
    2.  **Afegir Logging:** Registrar cada petició (IP, endpoint, timestamp) per poder detectar abusos.
    3.  **(Opcional) Autenticació per API Key:** Implementar un sistema d'API keys que els serveis interns (com n8n) hagin d'usar per accedir a Ollama, proporcionant una capa d'autenticació addicional.

### c) ComfyUI (Generació d'Imatges)

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **S-comfy-01** | **MITJÀ** | **Dependència Única d'Authelia** | En deshabilitar l'autenticació nativa de ComfyUI, tota la seguretat recau en la capa perimetral. Això viola el principi de "defensa en profunditat". Un error de configuració a Nginx o Authelia deixaria el servei totalment desprotegit. |

#### 🔧 Solució Suggerida (ComfyUI)

*   **Solució:** Habilitar l'autenticació nativa de ComfyUI com a segona capa de defensa.
    1.  **Modificar `docker-compose.yml`:**
        ```diff
        -      - WEB_ENABLE_AUTH=false
        +      - WEB_ENABLE_AUTH=true
        ```
    2.  **Gestionar Credencials:** Les credencials de ComfyUI (usuari/contrasenya) haurien de ser gestionades a través de Docker Secrets, de la mateixa manera que se suggereix per a altres serveis.

### d) Matrix (Missatgeria)

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **S-matrix-01** | **CRÍTIC** | **Exposició de Secrets als Logs** | Com es detalla a l'**AUDIT 04 (DS-02)**, l'entrypoint del contenidor de Matrix imprimeix secrets de servidor als logs de Docker en la primera arrencada. |
| **S-matrix-02** | **ALT** | **Registre d'Usuaris Obert per Defecte** | La variable `MATRIX_ENABLE_REGISTRATION` està configurada com a `true` al fitxer `.env.staging`. Si aquesta configuració arriba a producció, permetria que qualsevol es registrés al servidor de missatgeria, obrint la porta a spam, abús i consum de recursos. |

#### 🔧 Solució Suggerida (Matrix)

*   **Per a S-matrix-01:** Vegeu la solució detallada a `04_DOCKER_SECURITY.md`.
*   **Per a S-matrix-02:**
    *   **Solució:** Canviar el valor per defecte a `.env.example` i `.env.staging` a `false`. El registre d'usuaris ha de ser una acció explícita i controlada per l'administrador.
        ```diff
        # A .env.example i .env.staging
        - MATRIX_ENABLE_REGISTRATION=true
        + MATRIX_ENABLE_REGISTRATION=false
        ```

### e) Qdrant (Vector Database)

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **S-qdrant-01** | **MITJÀ** | **Accés sense Autenticació a la Xarxa Interna** | Qdrant suporta l'autenticació mitjançant API key, però aquesta no està configurada. Qualsevol contenidor a la xarxa `ai` (compromès o legítim) pot accedir, modificar i eliminar dades de la base de dades vectorial. |

#### 🔧 Solució Suggerida (Qdrant)

*   **Solució:** Habilitar l'autenticació per API key.
    1.  **Generar una API Key:** Usar `openssl rand -hex 32` i guardar-la com un Docker Secret.
    2.  **Modificar `docker-compose.yml` per a Qdrant:**
        ```yaml
        # Al servei qdrant
        secrets:
          - qdrant_api_key
        command: ["./qdrant", "--api-key-file", "/run/secrets/qdrant_api_key"]
        ```
    3.  **Actualitzar Clients:** Configurar els serveis que usen Qdrant (com n8n) perquè enviïn l'API key en les seves peticions.
