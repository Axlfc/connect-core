# AUDIT 07: SEGURETAT DE XARXA I TALLAFOC
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/07_NETWORK_SECURITY.zh-cn.md)


**Data:** 2024-07-25
**Analista:** Jules

## 1. Resum de Troballes

| Estat | Àrea | Resum de Troballes |
| :--- | :--- | :--- |
| ✓ | **Segmentació de Xarxa Interna** | L'arquitectura de xarxa de Docker Compose està **excel·lentment dissenyada**, utilitzant xarxes `internal` per aïllar els serveis de backend i limitar la superfície d'atac interna. |
| ⚠️ | **Configuració de `fail2ban`** | El servei `fail2ban` està implementat, cosa que demostra una intenció de protegir contra atacs de força bruta. Tanmateix, la seva configuració és **massa simplista** i només monitoritza els intents de login fallits a través del log de Nginx. |
| ✗ | **`fail2ban` en `network_mode: host`** | Aquest és un **defecte de disseny de seguretat crític**. Executar `fail2ban` en mode de xarxa d'host trenca l'aïllament del contenidor, atorgant-li accés sense restriccions a les interfícies de xarxa del sistema amfitrió. Un compromís d'aquest contenidor podria comprometre tota la xarxa del host. |
| ✗ | **Falta d'Egress Control** | No hi ha polítiques de xarxa que restringeixin el trànsit de sortida dels contenidors. Si un contenidor és compromès, podria ser utilitzat per descarregar malware, connectar-se a servidors de comandament i control (C2), o atacar altres sistemes a internet sense cap restricció. |
| ✗ | **Exposició de Ports Innecessària** | Múltiples serveis exposen els seus ports directament a les interfícies del host (ex. `postgres` a `127.0.0.1:5432`, `whisper-stt` a `0.0.0.0:9001`). En una arquitectura de microserveis, la comunicació hauria d'ocórrer principalment a través de la xarxa interna de Docker, i només el reverse proxy hauria d'exposar ports externament. |

---

## 2. Troballes Detallades

### ✓ El que està bé

1.  **Aïllament de Serveis per Xarxa:**
    *   La creació de xarxes separades (`frontend`, `backend`, `ai`, `monitoring`) i l'ús d' `internal: true` per a les xarxes que no necessiten accés extern és la implementació correcta del principi de mínim privilegi a nivell de xarxa. Això prevé que un servei compromès al backend (ex. una base de dades) pugui ser accedit directament des de l'exterior.

### ✗ Problemes Trobats

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **N-01** | **CRÍTIC** | **`fail2ban` amb `network_mode: host`** | El contenidor `fail2ban` anul·la l'aïllament de xarxa de Docker. Pot monitoritzar, interferir i manipular el trànsit de xarxa del host. Un atacant que comprometi aquest contenidor podria evadir el tallafoc principal, atacar serveis del host que no estan exposats públicament, i obtenir un punt de suport persistent a la xarxa del host. |
| **N-02** | **ALT** | **Filtres de `fail2ban` Insuficients** | La configuració actual només bloqueja IPs que generen errors 401 en endpoints de login específics. No protegeix contra una àmplia gamma d'atacs comuns, com escaneig de directoris, injecció de SQL, XSS, o atacs de denegació de servei a nivell d'aplicació (capa 7). Proporciona una falsa sensació de seguretat. |
| **N-03** | **MITJÀ** | **Exposició Directa de Ports de Backend** | Serveis com `postgres` i `redis` exposen els seus ports a `127.0.0.1` al host. Tot i que això no és públicament accessible, permet que qualsevol altre procés que s'executi al mateix host (incloent altres contenidors mal configurats) pugui intentar connectar-se directament a la base de dades o al memòria cau (cache), eludint les capes d'aplicació. |
| **N-04** | **MITJÀ** | **Falta de Control de Trànsit de Sortida (Egress)** | Els contenidors poden iniciar connexions sortints a qualsevol destí a internet. Si un atacant aconsegueix executar codi en un contenidor (ex. `ollama`), podria usar-lo per descarregar eines de hacking, exfiltrar dades a un servidor extern, o participar en una botnet. |

### ⚠️ Avisos/Recomanacions

1.  **Visibilitat del Trànsit Intern:**
    *   El trànsit entre contenidors a la mateixa xarxa de Docker no està xifrat (TLS). Per a entorns de molt alta seguretat (ex. compliment de PCI DSS), es podria considerar implementar una malla de serveis (service mesh) com Istio o Linkerd per forçar el xifratge de tot el trànsit intern (mTLS).

### 🔧 Solucions Suggerides

1.  **Per a N-01 i N-02 (Redissenyar l'Estratègia de `fail2ban`):**
    *   **Solució Ideal (Recomanada):** Eliminar el contenidor de `fail2ban`. Instal·lar i configurar `fail2ban` **directament al sistema operatiu del host**. Això li dóna accés legítim i segur als logs i a les `iptables` del host sense trencar el model de seguretat de Docker.
    *   **Solució Alternativa (Si ha de ser en contenidor):**
        1.  Eliminar `network_mode: host`.
        2.  Afegir les capacitats `NET_ADMIN` i `NET_RAW` per permetre la manipulació d' `iptables`.
        3.  Muntar el fitxer de log d' `iptables` del host dins del contenidor perquè pugui veure les seves pròpies accions.
        4.  Expandir massivament els filtres a `filter.d` per incloure regles de `nginx-badbots`, `nginx-noscript`, `nginx-http-auth`, i altres regles predefinides de `fail2ban` per a una protecció més completa.

2.  **Per a N-03 (Limitar Exposició de Ports):**
    *   **Solució:** Revisar cada servei a `docker-compose.yml` i eliminar qualsevol mapatge de `ports` que no sigui estrictament necessari per a l'accés extern (gestionat per `nginx-proxy`) o per a la depuració local. La comunicació entre serveis s'ha de realitzar a través de la xarxa de Docker utilitzant els noms de servei com a DNS (ex. `postgres:5432`).
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

3.  **Per a N-04 (Control d'Egress):**
    *   **Solució:** Crear una xarxa de Docker dedicada per a l'accés a internet i adjuntar només els contenidors que ho necessitin explícitament.
        1.  **Definir una xarxa de sortida a `docker-compose.yml`:**
            ```yaml
            networks:
              egress_allowed:
                driver: bridge
            ```
        2.  **Modificar el tallafoc del host (iptables):** Afegir regles per permetre el trànsit `FORWARD` només des de la subxarxa de la xarxa `egress_allowed` cap a l'exterior, i denegar el `FORWARD` de la resta de xarxes de Docker.
            ```bash
            # Exemple de regla d'iptables (requereix la subxarxa correcta)
            DOCKER_EGRESS_NW="172.x.y.0/24" # Subxarxa de la xarxa egress_allowed
            iptables -A FORWARD -i br-$(docker network ls | grep egress_allowed | awk '{print $1}') -o <external_iface> -j ACCEPT
            iptables -A FORWARD -i docker0 -o <external_iface> -j DROP
            ```
        3.  **Adjuntar contenidors a la xarxa:** Només els contenidors que necessitin accedir a internet (ex. `n8n` per a webhooks) s'afegirien a la xarxa `egress_allowed`.
