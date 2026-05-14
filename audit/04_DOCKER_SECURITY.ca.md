# AUDIT 04: SEGURETAT DE DOCKER
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/04_DOCKER_SECURITY.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/04_DOCKER_SECURITY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/04_DOCKER_SECURITY.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/04_DOCKER_SECURITY.zh-cn.md)


**Data:** 2024-07-25
**Analista:** Jules

## 1. Resum de Troballes

| Estat | Àrea | Resum de Troballes |
| :--- | :--- | :--- |
| ✓ | **Aïllament de Xarxa** | L'ús de xarxes de Docker personalitzades (`frontend`, `backend`, `ai`, `monitoring`) amb la majoria configurades com a `internal: true` és una **excel·lent pràctica de seguretat** que limita la comunicació entre serveis. |
| ✓ | **Mínims Privilegis (Parcial)** | La majoria dels serveis utilitzen `cap_drop: - ALL` i `security_opt: - no-new-privileges:true`, cosa que demostra una sòlida comprensió dels principis de seguretat de contenidors. |
| ✗ | **Execució com a Root** | Diversos contenidors crítics, incloent `ollama` i els basats en imatges de NVIDIA (`whisper-stt`), s'executen amb l'**usuari `root`**. Una vulnerabilitat en qualsevol d'aquestes aplicacions atorgaria privilegis d'administrador dins del contenidor. |
| ✗ | **Capacitats de Linux Perilloses** | Múltiples serveis (`postgres`, `forgejo`, `duplicati`) tenen la capacitat `DAC_OVERRIDE` afegida. Aquesta capacitat permet a un procés eludir les comprovacions de permisos de lectura, escriptura i execució de fitxers, soscavant la seguretat del sistema de fitxers. |
| ✗ | **Exposició de la Xarxa del Host** | El servei `fail2ban` està configurat amb `network_mode: host`. Això **trenca completament l'aïllament de xarxa del contenidor**, donant-li accés directe a les interfícies de xarxa del host. Això és extremadament perillós i anul·la molts dels beneficis de seguretat de la containerització. |
| ✗ | **Secrets en Logs** | El `Dockerfile.matrix` conté un script d'entrypoint que **imprimeix els secrets generats (macaroon key, form secret, etc.) als logs del contenidor** en el primer inici. Això exposa credencials crítiques a qualsevol que tingui accés als logs de Docker. |

---

## 2. Troballes Detallades

### ✓ El que està bé

1.  **Principi de Mínims Privilegis Aplicat (en part):**
    *   La majoria dels serveis estan configurats amb `security_opt: [no-new-privileges:true]`, cosa que impedeix que els processos obtinguin privilegis addicionals.
    *   L'ús de `cap_drop: [ALL]` com a configuració per defecte, i després afegir només les capacitats necessàries (`cap_add`), és l'estratègia correcta a seguir.

2.  **Aïllament de Xarxa Robust:**
    *   L'arquitectura de xarxa està molt ben dissenyada. Els serveis de backend no són accessibles des de l'exterior, i la comunicació està segmentada per funció, cosa que limita el moviment lateral d'un atacant.

3.  **Ús d'Usuaris No-Root (en part):**
    *   Serveis com `redis` (`user: "999:999"`), `authelia`, i `n8n` (`user: "${PUID:-1000}:${PGID:-1000}"`) s'executen correctament amb usuaris no privilegiats, reduint significativament el seu risc.

### ✗ Problemes Trobats

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **DS-01** | **CRÍTIC** | **`fail2ban` amb `network_mode: host`** | El contenidor té accés complet a la pila de xarxa del host. Pot sniffejar tot el trànsit, connectar-se a qualsevol servei en `localhost` al host, i interferir amb les regles de tallafoc (firewall) del host. Un compromís d'aquest contenidor és equivalent a un compromís del host a nivell de xarxa. |
| **DS-02** | **CRÍTIC** | **Secrets Exposats als Logs de `matrix-synapse`** | L'script d'entrypoint a `Dockerfile.matrix` imprimeix un bloc de "GENERATED SECRETS" a la sortida estàndard, que és capturada pels logs de Docker. Això fa que secrets de sessió i de federació siguin trivialment accessibles. |
| **DS-03** | **ALT** | **Execució com a `root` en Contenidors Clau** | Els serveis `ollama`, `whisper-stt`, i `kokoro-tts` s'executen com a `root`. Una vulnerabilitat d'execució remota de codi en qualsevol d'aquests serveis donaria a un atacant control total dins del contenidor, amb la capacitat de modificar fitxers, instal·lar programari maliciós i atacar altres serveis a la xarxa. |
| **DS-04** | **ALT** | **Ús de la Capacitat `DAC_OVERRIDE`** | Aquesta capacitat, present a `postgres`, `matrix-postgres`, `forgejo` i `duplicati`, permet a un procés ignorar els permisos de fitxers. Si un atacant compromet un d'aquests contenidors, podria llegir/escriure fitxers als quals normalment no tindria accés, incloent potencialment fitxers de configuració sensibles o dades d'altres usuaris. |
| **DS-05** | **MITJÀ** | **El sòcol (socket) de Docker muntat de forma insegura** | El servei `nginx-proxy` munta el sòcol de Docker (`/var/run/docker.sock`) com a `read-only`. Això és bo, però comprometre `nginx-proxy` encara permetria a un atacant obtenir informació sensible sobre tots els altres contenidors i la configuració del host de Docker. |

---

### ⚠️ Avisos/Recomanacions

1.  **Sistemes de fitxers Read-Only:**
    *   **Recomanació:** Per a contenidors que no necessiten escriure dades en el seu propi sistema de fitxers (a part d'en els volums muntats), considereu afegir l'opció `read_only: true`. Això pot mitigar moltes classes d'atacs que depenen d'escriure fitxers binaris o scripts maliciosos.

2.  **Perfils de Seguretat (AppArmor/Seccomp):**
    *   **Recomanació:** L'ús d' `apparmor=docker-default` és un bon punt de partida. Per a una seguretat encara major, es podrien crear perfils d'AppArmor o Seccomp personalitzats per a cada servei, restringint les crides al sistema que cada aplicació pot realitzar.

---

### 🔧 Solucions Suggerides

1.  **Per a DS-01 (`fail2ban` en `network_mode: host`):**
    *   **Solució:** Aquesta és una configuració difícil de canviar, ja que `fail2ban` necessita modificar les `iptables` del host. La solució més segura és **executar `fail2ban` directament al host**, fora de Docker. Si ha de romandre en un contenidor, s'ha d'investigar l'ús d'un contenidor més especialitzat i "Arrelat" amb eines com `nsenter` per executar ordres en el namespace del host de manera controlada, en lloc d'exposar tota la pila de xarxa.

2.  **Per a DS-02 (Secrets als Logs de Matrix):**
    *   **Solució:** Modificar `/scripts/entrypoint.sh` dins de `Dockerfile.matrix` perquè els secrets es guardin en un fitxer dins del contenidor amb permisos restringits, en lloc d'imprimir-los.
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

3.  **Per a DS-03 (Execució com a `root`):**
    *   **Solució per a `ollama`:** La imatge oficial d' `ollama` ara suporta l'execució com a no-root. S'ha de crear un usuari `ollama` i assegurar-se que els permisos del volum (`/root/.ollama` ha de canviar a `/home/ollama/.ollama`) siguin correctes.
    *   **Solució per a Dockerfiles personalitzats (p. ex., `whisper-stt`):** Afegir els següents passos al final del Dockerfile:
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

4.  **Per a DS-04 (`DAC_OVERRIDE`):**
    *   **Solució:** Investigar per què cada servei necessita aquesta capacitat. Sovint, s'afegeix per solucionar problemes de permisos en els volums muntats. La solució correcta és **arreglar els permisos al host** (utilitzant l'script `setup-permissions.sh` i assegurant que `PUID`/`PGID` coincideixin) en lloc d'atorgar capacitats perilloses. Eliminar `DAC_OVERRIDE` de la secció `cap_add` de tots els serveis.
