# AUDIT 03: ANÀLISI DE DOCKER I CONTAINERITZACIÓ
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/03_DOCKER_CONTAINERIZATION.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/03_DOCKER_CONTAINERIZATION.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/03_DOCKER_CONTAINERIZATION.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/03_DOCKER_CONTAINERIZATION.zh-cn.md)


**Data:** 2024-07-25
**Analista:** Jules

## 1. Resum de Troballes

| Estat | Àrea | Resum de Troballes |
| :--- | :--- | :--- |
| ✓ | **Orquestració** | El fitxer `docker-compose.yml` està **ben estructurat**, utilitzant àncores de YAML, perfils i xarxes segmentades de manera efectiva. Demostra un disseny d'arquitectura sòlid. |
| ✓ | **Healthchecks** | La majoria dels serveis crítics implementen `healthchecks`, una pràctica excel·lent que assegura un ordre d'inici correcte i millora la resiliència de l'stack. |
| ⚠️ | **Optimització d'Imatges** | Els Dockerfiles personalitzats són funcionals però **manquen d'optimitzacions clau**. No utilitzen builds multi-etapa, cosa que resulta en imatges més grans del necessari que contenen eines de compilació no requerides en temps d'execució. |
| ✗ | **Dependències No Fixades** | L'ús generalitzat de l'etiqueta `:latest` a `docker-compose.yml` i als Dockerfiles és un **risc crític per a l'estabilitat i la seguretat**. Això porta a builds no reproduïbles i a la introducció inesperada de canvis disruptius. |
| ✗ | **Falta de Límits de Recursos** | La gran majoria dels serveis no tenen límits de CPU o memòria definits a la secció `deploy.resources`. Això crea un risc que un sol servei consumeixi tots els recursos del host, provocant una denegació de servei per a tot l'stack. |
| ✗ | **Inconsistències i Malas Pràctiques** | S'observen diverses males pràctiques, com la instal·lació de dependències amb `apt-get` sense netejar la memòria cau (cache), i la clonació de repositoris `git` des de branques `master` en lloc d'etiquetes o commits específics. |

---

## 2. Troballes Detallades

### ✓ El que està bé

1.  **Estructura de `docker-compose.yml`:**
    *   L'ús d'àncores de YAML (ex. `x-ollama: &service-ollama`) per definir serveis base és excel·lent per a la mantenibilitat i redueix la duplicació de codi.
    *   La segmentació de la xarxa en `frontend`, `backend`, `ai` i `monitoring` (amb les últimes tres marcades com a `internal: true`) és una implementació de seguretat de xarxa de llibre de text, aïllant efectivament els serveis.
    *   L'ús de perfils (`cpu`, `gpu-nvidia`, `monitoring`, etc.) permet un control granular sobre quins serveis s'inicien, adaptant l'stack a diferents entorns de maquinari.

2.  **Definició de Healthchecks:**
    *   Serveis com `postgres`, `redis`, `n8n`, i `authelia` tenen `healthchecks` ben definits. Això és crucial per a la directiva `depends_on.condition: service_healthy`, que prevé que els serveis dependents s'inicien abans que les seves dependències estiguin llestes.

3.  **Maneig de Volums:**
    *   L'estratègia de volums és clara, utilitzant volums amb nom de Docker per a la persistència de dades (ex. `postgres_storage`) i muntatges de tipus `bind` per a la configuració (ex. `./authelia:/config`), la qual cosa és una pràctica estàndard i robusta.

### ✗ Problemes Trobats

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **D-01** | **CRÍTIC** | **Ús de l'etiqueta `:latest`** | Múltiples serveis (`qdrant`, `ollama`, `authelia`, `libretranslate`, `languagetool`, etc.) i Dockerfiles (`Dockerfile.comfyui`) usen `:latest`. Això trenca la reproduïabilitat dels builds. Una actualització a la imatge remota pot trencar l'aplicació sense previ avís o introduir una vulnerabilitat. |
| **D-02** | **ALT** | **Absència de Límits de Recursos** | La majoria dels serveis no tenen una secció `deploy.resources` amb `limits`. Un procés amb fugues de memòria o un pic de CPU en un servei (ex. `ollama` processant una sol·licitud complexa) podria fer caure tot el servidor host. |
| **D-03** | **ALT** | **Builds No Reproduïbles als Dockerfiles** | `Dockerfile.comfyui` instal·la dependències de PyTorch des d'un URL `nightly` i clona repositoris de git des de la branca `master`. Això significa que construir la mateixa imatge en dos moments diferents pot resultar en dues imatges completament diferents, amb diferents versions i funcionalitats. |
| **D-04** | **MITJÀ** | **Imatges Inflades (Bloated Images)** | Dockerfiles com `Dockerfile.runners` instal·len paquets de compilació (`gcc`, `g++`, `build-base`) però no els eliminen. Això augmenta innecessàriament la mida de la imatge final i, per tant, la superfície d'atac. |
| **D-05** | **MITJÀ** | **Falta de Neteja de Memòria Cau d'APT** | En diversos Dockerfiles, s'executen ordres `apt-get install` sense `&& rm -rf /var/lib/apt/lists/*` a la mateixa capa `RUN`. Això deixa dades de memòria cau innecessàries en una capa de la imatge, augmentant-ne la mida. |

### ⚠️ Avisos/Recomanacions

1.  **Versionat de la Configuració de Compose:**
    *   El `docker-compose.yml` és de la versió "3.8". Tot i que és funcional, considereu actualitzar a l'especificació més recent de `compose` per aprofitar noves característiques en el futur.

2.  **Claredat als Ports Exposats:**
    *   Alguns serveis exposen ports només a `127.0.0.1` (ex. `postgres`), la qual cosa és una bona pràctica de seguretat. No obstant això, d'altres els exposen a `0.0.0.0` (ex. `whisper-stt`). Es recomana afegir comentaris que justifiquin per què un port ha d'estar obert a totes les interfícies per evitar confusions.

### 🔧 Solucions Suggerides

1.  **Per a D-01 (Fixar Versions - CRÍTIC):**
    *   **Solució:** Realitzar una auditoria de cada servei que usa `:latest` i reemplaçar-lo amb una etiqueta de versió específica i estable.
        ```diff
        --- a/docker-compose.yml
        +++ b/docker-compose.yml
        @@ -201,7 +201,7 @@
         # QDRANT - Vector Database
         # ========================================
         qdrant:
        -  image: qdrant/qdrant:latest
        +  image: qdrant/qdrant:v1.9.0  # O la versió estable més recent
           hostname: qdrant
           container_name: qdrant
           networks:
        ```

2.  **Per a D-02 (Afegir Límits de Recursos):**
    *   **Solució:** Afegir una secció `deploy.resources` a cada servei, definint `limits` i `reservations` raonables. Aquests valors s'han d'ajustar en funció de proves de càrrega, però un punt de partida és essencial.
        ```diff
        --- a/docker-compose.yml
        +++ b/docker-compose.yml
        @@ -216,6 +216,12 @@
           test: ["CMD-SHELL", "bash -c ':> /dev/tcp/localhost/6333' || exit 1"]
           interval: 5s
           timeout: 5s
           retries: 3
        +  deploy:
        +    resources:
        +      limits:
        +        cpus: '2.0'
        +        memory: 4G
        +      reservations:
        +        memory: 512M
         ```

3.  **Per a D-03 (Builds Reproduïbles):**
    *   **Solució per a `Dockerfile.comfyui`:**
        *   Fixar la versió de la imatge base (`ghcr.io/ai-dock/comfyui:v1.2.3`).
        *   Descarregar les dependències de PyTorch, verificar-ne els checksums (SHA256), i després instal·lar-les.
        *   En clonar repositoris de `git`, usar `git clone --branch v1.0.0` o `git checkout <commit-hash>` en lloc de clonar des de `master`.

4.  **Per a D-04 i D-05 (Optimitzar Imatges):**
    *   **Solució:** Utilitzar builds multi-etapa i combinar ordres `RUN` per reduir el nombre de capes i netejar artefactes de compilació.
        ```dockerfile
        # Exemple per a Dockerfile.runners

        # Etapa 1: Build
        FROM n8nio/runners:1.121.0 as builder
        USER root
        RUN apk add --no-cache gcc g++ musl-dev python3-dev build-base
        RUN python3 -m venv /home/runner/custom-venv
        # ... instal·lar totes les dependències amb pip ...

        # Etapa 2: Final
        FROM n8nio/runners:1.121.0
        USER root
        # Copiar només el venv de l'etapa de build
        COPY --from=builder /home/runner/custom-venv /home/runner/custom-venv
        COPY n8n-task-runners.json /etc/n8n-task-runners.json
        # Assegurar permisos i canviar d'usuari
        RUN chown -R runner:runner /home/runner/custom-venv
        USER runner
        ENV PATH="/home/runner/custom-venv/bin:$PATH"
        ```
