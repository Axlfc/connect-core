# AUDIT 02: GESTIÓ DE VARIABLES D'ENTORN I CONFIGURACIÓ
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/02_ENVIRONMENT_AND_CONFIGURATION.zh-cn.md)


**Data:** 2024-07-25
**Analista:** Jules

## 1. Resum de Troballes

| Estat | Àrea | Resum de Troballes |
| :--- | :--- | :--- |
| ✓ | **Generació de Secrets** | Els scripts d'inicialització (`init_env.sh`) utilitzen mètodes criptogràficament segurs (`openssl rand`) per generar secrets, la qual cosa és una pràctica excel·lent. |
| ✓ | **Protecció de Fitxers** | El fitxer `.gitignore` està configurat correctament per excloure `secrets/` i `.env*`, prevenint l'exposició accidental de credencials al repositori. |
| ⚠️ | **Metodologia Mixta** | El projecte utilitza dos mètodes per a la gestió de secrets simultàniament: **Docker Secrets** (segur) i **variables d'entorn a través de `.env`** (menys segur). Aquesta inconsistència és la font principal de risc. |
| ✗ | **Exposició Potencial** | Secrets crítics com `POSTGRES_PASSWORD` i `REDIS_PASSWORD` s'injecten als contenidors com a variables d'entorn, cosa que els fa visibles a través de `docker inspect`, logs i potencialment en eines de monitoratge. |
| ✗ | **Validació d'Entrades** | Els scripts de shell, tot i que robustos, no validen exhaustivament les entrades de l'usuari en mode interactiu, la qual cosa podria permetre la injecció de caràcters maliciosos al fitxer `.env`. |

---

## 2. Troballes Detallades

### ✓ El que està bé

1.  **Generació Segura de Secrets:**
    *   L'script `init_env.sh` utilitza `openssl rand` com a mètode principal per a la creació de contrasenyes i claus. Aquesta és la millor pràctica industrial per generar valors aleatoris segurs.

2.  **Maneig de Fitxers `.env.example`:**
    *   L'script `generate_env_example.sh` és notablement intel·ligent. Identifica variables sensibles per patrons (`PASSWORD`, `KEY`, `TOKEN`, etc.) i les buida, mentre preserva valors de configuració no sensibles. Això assegura que el fitxer d'exemple sigui segur i útil.

3.  **Ús Parcial de Docker Secrets:**
    *   El `docker-compose.yml` defineix un bloc de `secrets:` i els utilitza correctament en diversos serveis (per exemple, `authelia`, `n8n-import`). Això demostra coneixement de la forma correcta de gestionar secrets a Docker.
    *   **Exemple (servei `authelia`):**
        ```yaml
        secrets:
          - authelia_jwt_secret
          - authelia_session_secret
        environment:
          - AUTHELIA_IDENTITY_VALIDATION_RESET_PASSWORD_JWT_SECRET_FILE=/run/secrets/authelia_jwt_secret
          - AUTHELIA_SESSION_SECRET_FILE=/run/secrets/authelia_session_secret
        ```
    *   Aquest mètode és segur perquè el secret es munta com un fitxer a `/run/secrets/` dins del contenidor i mai s'exposa com una variable d'entorn.

### ✗ Problemes Trobats

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **C-01** | **ALT** | **Ús de Variables d'Entorn per a Secrets Crítics** | El servei principal de `postgres` i `redis` reben les seves contrasenyes a través de variables d'entorn carregades des del fitxer `.env`. Un atacant amb accés al host de Docker podria extreure aquestes credencials amb l'ordre `docker inspect postgres`. |
| **C-02** | **MITJÀ** | **Inconsistència en la Gestió de Secrets** | El projecte utilitza Docker Secrets per a alguns serveis (Authelia) però variables d'entorn per a d'altres (Postgres, Redis). Aquesta falta d'un estàndard únic augmenta la complexitat, el risc d'error humà i la superfície d'atac. |
| **C-03** | **BAIX** | **Visualització de Secrets a la Consola** | `init_env.sh` mostra una part del secret generat a la consola. Tot i que és una part truncada, això podria exposar el secret a l'historial del shell (`.bash_history`) o a observadors. |

---

### ⚠️ Avisos/Recomanacions

1.  **Documentació d'`ENV_MANAGEMENT.md`:**
    *   El fitxer `ENV_MANAGEMENT.md` existeix però podria ser més explícit sobre l'estratègia de secrets. Hauria d'explicar *per què* es prefereix Docker Secrets i advertir sobre els riscos d'utilitzar variables d'entorn per a dades sensibles.

2.  **Enduriment (Hardening) d'Scripts de Shell:**
    *   Els scripts `init_env.sh` i `generate_env_example.sh` són complexos. Una bona pràctica seria afegir `set -o pipefail` a l'inici per assegurar que els pipelines fallin si una ordre intermèdia falla.

---

### 🔧 Solucions Suggerides

1.  **Per a C-01 i C-02 (Unificar en Docker Secrets - CRÍTIC):**
    *   **Pas 1: Modificar `docker-compose.yml`:**
        *   Reconfigurar tots els serveis que actualment usen variables d'entorn per a secrets perquè usin Docker Secrets.
        *   **Exemple per al servei `postgres`:**
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
    *   **Pas 2: Actualitzar `init_env.sh`:**
        *   Modificar l'script perquè, en lloc d'escriure `POSTGRES_PASSWORD=valor_secret` al `.env`, creï el fitxer corresponent al directori `secrets/`.
            ```bash
            # A init_env.sh, en lloc de sed:
            echo "$new_value" > secrets/postgres_password.txt
            chmod 600 secrets/postgres_password.txt
            # I eliminar la variable del .env
            sed -i '/^POSTGRES_PASSWORD=/d' "$TARGET_FILE"
            ```
        *   Això centralitza tots els secrets en un únic lloc (`/secrets`) gestionat amb els permisos correctes.

2.  **Per a C-03 (Visualització de Secrets):**
    *   **Solució:** Modificar `init_env.sh` per no mostrar el valor generat a la consola. Simplement informar a l'usuari que s'ha generat i guardat un valor.
        ```diff
        --- a/init_env.sh
        +++ b/init_env.sh
        @@ -145,7 +145,7 @@
             echo ""
             echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
             echo -e "${BLUE}Variable:${NC} $var"
-            echo -e "${BLUE}Valor generat:${NC} ${new_value:0:20}...${new_value: -10}"
+            echo -e "${BLUE}Valor generat:${NC} [OCULT PER SEGURETAT]"
             echo -n "Vols utilitzar aquest valor? (S/n/personalitzar): "
             read -r response
         ```
