# AUDIT 12: VOICE GATEWAY I SERVEIS ESPECIALITZATS
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/12_VOICE_GATEWAY.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/12_VOICE_GATEWAY.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/12_VOICE_GATEWAY.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/audit/12_VOICE_GATEWAY.zh-cn.md)


**Data:** 2024-07-25
**Analista:** Jules

## 1. Resum de Troballes

| Estat | Àrea | Resum de Troballes |
| :--- | :--- | :--- |
| ✓ | **Arquitectura Neta** | El Voice Gateway és un microservei ben dissenyat que segueix les millors pràctiques de FastAPI. Actua com un orquestrador desacoblat per als serveis de STT, LLM i TTS. |
| ✓ | **Configuració Segura** | Tota la configuració, incloent URLs de serveis i la contrasenya de Redis, es gestiona correctament a través de variables d'entorn, evitant credencials hardcodejades. |
| ✓ | **Gestió d'Errors** | El codi gestiona adequadament els errors de xarxa i d'estat HTTP dels serveis downstream, retornant codis d'estat HTTP apropiats (503 Service Unavailable, etc.). |
| ✗ | **Falta de Validació d'Entrades** | **CRÍTIC:** L'endpoint de transcripció (`/v1/audio/transcriptions`) **no valida la mida del fitxer d'àudio pujat**. Un atacant podria pujar un fitxer d'àudio maliciosament gran, esgotant la memòria i els recursos de CPU del gateway i del servei Whisper, provocant una denegació de servei. |
| ⚠️ | **Sense Timeouts Agressius** | Tot i que el client HTTP té un timeout general de 120 segons, les peticions individuals als serveis d'IA (que poden trigar molt) no tenen timeouts més curts i específics, cosa que podria deixar connexions obertes durant molt de temps. |
| ⚠️ | **CORS Massa Permissiu** | La política de CORS està configurada per a `allow_origins=["*"]`, cosa que permet que qualsevol lloc web a internet realitzi peticions al gateway. Tot i que el gateway està protegit per Authelia, aquesta és una configuració massa permissiva per a producció. |

---

## 2. Troballes Detallades

### ✓ El que està bé

1.  **Codi Asíncron i Eficient:**
    *   L'ús de `FastAPI` juntament amb `httpx.AsyncClient` assegura que el gateway sigui no bloquejant i pugui gestionar múltiples peticions concurrents de manera eficient.

2.  **Capa de Caching:**
    *   La implementació d'un memòria cau (cache) a Redis per a les peticions de Text-to-Speech (TTS) és una excel·lent optimització. Redueix la càrrega al servei Kokoro (que consumeix molta GPU) i millora dràsticament els temps de resposta per a frases comunes.

3.  **Compatibilitat amb API d'OpenAI:**
    *   Els endpoints (`/v1/audio/transcriptions`, `/v1/audio/speech`) imiten l'estructura de l'API d'OpenAI, cosa que facilita la integració amb clients i eines existents.

### ✗ Problemes Trobats

| ID | Severitat | Problema | Impacte |
| :- | :--- | :--- | :--- |
| **VG-01** | **CRÍTIC** | **Pujada de Fitxers Sense Límit de Mida** | L'endpoint `create_transcription` llegeix el fitxer d'àudio completament en memòria (`await file.read()`) sense verificar-ne la mida primer. Un atacant pot enviar un fitxer de diversos gigabytes, cosa que causarà un error de `MemoryError` i bloquejarà el procés del servidor, fent-lo inaccessible per a altres usuaris (Denegació de Servei). |
| **VG-02** | **MITJÀ** | **CORS Obert (`*`)** | Permetre orígens `*` és una mala pràctica en producció. Tot i que Authelia bloqueja l'accés no autenticat, això encara podria permetre certs tipus d'atacs (com CSRF en navegadors antics) i no segueix el principi de mínim privilegi. |

---

### ⚠️ Avisos/Recomanacions

1.  **Seguretat de WebSockets:**
    *   El servei actual no utilitza WebSockets, però si s'afegissin en el futur per a streaming en temps real, seria crucial implementar una validació de l'origen (`Origin`) i rate limiting als missatges per prevenir abusos.

2.  **Gestió de Dades d'Àudio:**
    *   Les dades d'àudio es processen en memòria i en fitxers temporals. Tot i que això és funcional, no hi ha una política explícita de neteja o retenció. S'ha d'assegurar que els fitxers temporals s'eliminin sempre, fins i tot en cas d'error. El codi actual (`os.unlink(tmp_path)`) és bo, però podria ser més robust si estigués en un bloc `finally`.

3.  **Informació als Logs:**
    *   El `config.py` imprimeix les URLs dels serveis interns als logs en iniciar. Tot i que útil per a la depuració, en un entorn de producció, això podria ser considerat una fuga d'informació menor sobre l'arquitectura interna.

---

### 🔧 Solucions Suggerides

1.  **Per a VG-01 (Validar Mida de Pujada - CRÍTIC):**
    *   **Solució:** Modificar l'endpoint `create_transcription` per validar la mida del fitxer abans de llegir-lo en memòria.
        ```python
        # A main.py, dins de create_transcription
        import config

        # ...

        # Llegir el contingut del fitxer a trossos per verificar la mida
        # sense carregar-ho tot en memòria de cop.
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

        size = 0
        chunks = []
        async for chunk in file.file:
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413, detail=f"File size exceeds the limit of {MAX_FILE_SIZE / 1024 / 1024} MB"
                )
            chunks.append(chunk)

        content = b"".join(chunks)

        # Ara el 'content' és segur d'utilitzar
        files = {"audio_file": (file.filename, content, file.content_type)}
        response = await client.post(
            f"{config.WHISPER_URL}/asr",
            files=files,
            params={"output": "json"}
        )
        # ... resta de la funció
        ```
    *   El `MAX_FILE_SIZE` hauria de ser configurable a través de `config.py`.

2.  **Per a VG-02 (Restringir CORS):**
    *   **Solució:** Modificar la configuració de CORS a `main.py` perquè només permeti els dominis de les aplicacions frontend que necessiten accedir al gateway.
        ```python
        # A main.py

        # Llegir els orígens permesos des d'una variable d'entorn
        ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")

        app.add_middleware(
            CORSMiddleware,
            allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["https://n8n.localhost", "https://app.localhost"],
            allow_credentials=True,
            allow_methods=["GET", "POST"], # Ser explícit
            allow_headers=["Authorization", "Content-Type"], # Ser explícit
        )
        ```
