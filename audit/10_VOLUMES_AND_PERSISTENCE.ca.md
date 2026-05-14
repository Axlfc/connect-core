# AUDIT 10: GESTIÓ DE VOLUMS I PERSISTÈNCIA
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/10_VOLUMES_AND_PERSISTENCE.zh-cn.md)


**Data:** 2024-07-25
**Analista:** Jules

## 1. Resum de Troballes

| Estat | Àrea | Resum de Troballes |
| :--- | :--- | :--- |
| ✓ | **Estratègia de Persistència** | L'estratègia d'utilitzar volums amb nom de Docker per a totes les dades d'estat (`postgres_storage`, `n8n_storage`, etc.) és **correcta i robusta**. Separa el cicle de vida de les dades del dels contenidors. |
| ✓ | **Intenció de Backup** | La presència d'un servei `duplicati` i un `duplicati-job-template.json` demostra una **clara intenció d'implementar backups**, la qual cosa és fonamental per a la resiliència de les dades. |
| ⚠️ | **Permisos de Volums** | L'script `inspect_volumes.sh` requereix `sudo` per calcular la mida dels volums (`du -sh`). Això suggereix que els permisos dels directoris de volums al host poden no estar correctament alineats amb els usuaris del sistema, cosa que podria portar a problemes de permisos en temps d'execució. |
| ✗ | **Estratègia de Backup No Implementada** | El sistema **manca d'una estratègia de backup automatitzada i funcional**. El `duplicati-job-template.json` és només una plantilla; no hi ha cap script o mecanisme que configuri automàticament el treball de backup a Duplicati, deixant el procés enterament manual i propens a errors. |
| ✗ | **Sense Procediments de Recuperació (Recovery)** | No existeix un procediment de recuperació de desastres documentat o provat. Les úniques referències a la restauració són ordres de `docker` a la sortida d' `inspect_volumes.sh`, la qual cosa és **insuficient per a un entorn de producció**. |

---

## 2. Troballes Detallades

### ✓ El que està bé

1.  **Ús de Volums amb Nom:**
    *   El `docker-compose.yml` defineix explícitament volums amb nom per a cada servei amb estat. Aquesta és una millor pràctica en comparació amb els muntatges de `bind` per a dades, ja que els volums són gestionats pel motor de Docker i són més portables i fàcils de manejar.

2.  **Plantilla de Backup Ben Definida:**
    *   El fitxer `backups/duplicati-job-template.json` defineix un treball de backup sòlid:
        *   **Fonts Clares:** Identifica correctament els directoris clau a protegir (`./shared`, `./data`, `./models`).
        *   **Xifratge Habilitat:** Especifica `encryption-module: aes`, la qual cosa és crucial per a la seguretat dels backups.
        *   **Programació Diària:** El `Schedule: "@daily"` és un punt de partida raonable per a la majoria dels casos d'ús.

### ✗ Problemes Trobats

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **V-01** | **ALT** | **Procés de Backup Manual** | No hi ha automatització per configurar Duplicati. Un administrador ha de: 1) Iniciar l'stack. 2) Accedir a la UI de Duplicati. 3) Crear un nou treball de backup. 4) Configurar el destí. 5) Configurar la frase de pas (passphrase) de xifratge. 6) Seleccionar els directoris font. Aquest procés manual és propens a errors de configuració i pot ser fàcilment oblidat. |
| **V-02** | **ALT** | **Absència de Pla de Recuperació de Desastres** | Si el servidor host falla catastròficament, no hi ha una guia pas a pas que descrigui com restaurar els serveis i les dades en un nou host. Això augmenta significativament el Temps de Recuperació (RTO) i el risc de pèrdua de dades si la restauració es realitza incorrectament. |
| **V-03** | **MITJÀ** | **Potencials Problemes de Permisos en Volums** | El fet que es necessiti `sudo` per inspeccionar la mida dels volums a l'script de diagnòstic és un "code smell". Indica que els UID/GID dels processos dins dels contenidors podrien no coincidir amb la propietat dels fitxers al host, una causa comuna d'errors de "permís denegat" en producció. |

---

### ⚠️ Avisos/Recomanacions

1.  **Backup de Bases de Dades:**
    *   El backup actual es basa a copiar els fitxers del volum de la base de dades (`postgres_storage`). Això es coneix com un backup "en fred" o de sistema de fitxers. Per garantir la consistència de les dades, la millor pràctica és utilitzar eines específiques de la base de dades com `pg_dump`. El backup actual podria capturar la base de dades en un estat inconsistent si s'hi està escrivint durant el procés.

2.  **Proves de Restauració:**
    *   Un pla de backup no està complet fins que el procés de restauració ha estat provat. No hi ha evidència que s'hagin realitzat proves de restauració.

---

### 🔧 Solucions Suggerides

1.  **Per a V-01 (Automatitzar la Configuració de Duplicati):**
    *   **Solució:** Crear un script d'inicialització per a Duplicati.
        1.  **Crear un Script (`scripts/init_duplicati.sh`):** Aquest script utilitzaria l'API de Duplicati o la seva CLI (`duplicati-cli`) per configurar el treball de backup automàticament en la primera arrencada.
        2.  **Lògica de l'Script:**
            *   Esperar que l'API de Duplicati estigui disponible.
            *   Llegir variables d'entorn (ex. `DUPLICATI_DESTINATION`, `DUPLICATI_PASSPHRASE`) del fitxer `.env`.
            *   Utilitzar `sed` o una eina similar per reemplaçar els marcadors de posició (placeholders) a `duplicati-job-template.json`.
            *   Fer un `POST` del JSON resultant a l'endpoint de l'API de Duplicati per crear/actualitzar el treball.
        3.  **Executar l'Script:** Executar aquest script com un servei de `docker-compose` que s'executa una vegada a l'inici, o com a part de l'script `start.sh`.

2.  **Per a V-02 (Crear un Pla de Recuperació):**
    *   **Solució:** Crear un document `DISASTER_RECOVERY.md`.
        *   **Contingut del Document:**
            *   **Requisits Previs:** (ex. nou host amb Docker instal·lat).
            *   **Pas 1: Restaurar Backups:** Instruccions detallades sobre com usar la UI o CLI de Duplicati per restaurar les dades des de l'emmagatzematge de destí a un directori temporal.
            *   **Pas 2: Re-inicialitzar l'Stack:** Com clonar el repositori, executar `init_env.sh` i `setup-permissions.sh`.
            *   **Pas 3: Importar Dades Restaurades:** Ordres `docker cp` o de muntatge de volums per moure les dades restaurades als nous volums de Docker.
            *   **Pas 4: Verificació:** Com verificar que els serveis s'han iniciat correctament i que les dades estan intactes.
        *   **Proves:** Aquest procediment ha de ser provat almenys una vegada per garantir que funciona com s'espera.

3.  **Per a V-03 (Solucionar Permisos):**
    *   **Solució:** Expandir i fer complir l'ús de `setup-permissions.sh`.
        *   Assegurar-se que l'script `setup-permissions.sh` crea els directoris al host per a **tots** els volums que ho necessitin, no només per als logs.
        *   Utilitzar les variables `PUID` i `PGID` del fitxer `.env` de forma consistent en tots els serveis de `docker-compose.yml` i a l'script `setup-permissions.sh` perquè els permisos coincideixin.
