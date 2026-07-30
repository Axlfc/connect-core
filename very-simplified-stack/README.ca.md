# 🧠 Very Simplified AI Stack — Stack d'Intel·ligència Artificial Simplificat
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](README.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](README.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](README.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](README.zh-cn.md)

Aquesta és una versió refinada i "extremadament simplificada" de l'AI Stack. Està dissenyada per a usuaris que volen les capacitats de base d'orquestració de la IA i eines cognitives locals, però s'estimen més executar els seus LLMs (com Ollama) de manera externa o en una altra màquina dedicada de l'host.

El nucli d'aquest stack simplificat es centra en l'**Agent Cognito (Cognito Agent)**, el qual integra de manera nativa el paradigma **NOOA (NVIDIA-labs Object Oriented Agents)** i les 5 fases del Roadmap d'AGI.

---

## 🚀 Què Inclou?

- **PostgreSQL**: Base de dades relacional amb extensió vectorial integrada (`pgvector`).
- **Qdrant**: Base de dades vectorial d'alt rendiment per a cerca semàntica i RAG.
- **Redis**: Servidor de memòria cache ultra-ràpid per a la gestió de sessions d'IA.
- **Forgejo**: Servidor Git self-hosted per gestionar el teu codi, repositoris i webhooks.
- **ComfyUI**: Generació d'imatges avançada amb suport natiu d'Stable Diffusion.
- **Voice Services**: Integració de Whisper (STT), Kokoro (TTS) i Demucs (separació d'àudio).
- **Voice Gateway**: API unificada i pasarel·la per simplificar tasques de processament de veu.
- **Nginx Proxy & zrok**: Servidor proxy i tunelització segura per a webhooks públics.
- **Cognito Backend (`cognito-backend`)**: Pla de control intel·ligent, enrutador multi-model d'IA (Ollama, Codex) i orquestrador del bucle de l'agent.
- **Cognito Worker (`cognito-worker`)**: Component d'execució segura del costat de l'host que realitza aïllament de repositoris (`git worktree`), compilació i verificació de canvis.

---

## ❌ Què s'ha eliminat?

Per mantenir l'stack el més lleuger i àgil possible, s'han descartat:
- **Obsidian**: Gestor de base de coneixement local.
- **Drupal**: Capa CMS / experimentació web de UI.
- **Monitoreig**: Servidors Prometheus, Grafana, Alertmanager, etc.
- **Eines de suport**: LibreTranslate, LanguageTool, Duplicati, Uptime Kuma.

---

## 🤖 L'Agent Cognito i la seva Arquitectura

La intel·ligència de l'stack està distribuïda en dos components natius sumament robustos:

### 1. Pla de Control: `cognito-backend`
El backend (desenvolupat en FastAPI) actua com el cervell de l'orquestrador:
- **Bucle d'Agent (SSE)**: Exposa l'endpoint `/api/agent/loop` que executa raonament interactiu i crides asíncrones a eines del sistema.
- **Metaclase NOOAMeta**: Permet definir classes d'agent on els mètodes buits especificats únicament amb l'el·lipsi (`...`) s'emboliquen automàticament en crides estructurades de LLM, respectant els contractes de tipus Pydantic de manera estricta.
- **Visibilitat Selectiva**: Oculta mètodes i atributs marcats amb `@hidden` o guió baix del context del LLM.
- **Compactat Automàtic**: Redueix l'historial de la conversa mitjançant resums de context en calent per no saturar la finestra de tokens.
- **Escalat Adaptatiu per Incertesa**: Si el model actual genera una subtasca amb alta entropia de Shannon (incertesa), l'orquestrador la escala automàticament a un model de major rang (com ara GPT-4o o Claude) per garantir la qualitat.

### 2. Capa d'Execució Segura: `cognito-worker`
El worker (desenvolupat en Python amb uvicorn) corre del costat de l'host de manera segura:
- **Aïllament amb Git Worktree**: Clonat segur de repositoris en directoris temporals per validar pegats i proves sense col·lidir amb la branca de treball activa de l'usuari.
- **Signatura Criptogràfica HMAC**: Totes les comunicacions entre el backend i el worker se signen i validen mitjançant un secret HMAC compartit per prevenir modificacions o atacs de tipus replay.
- **Sandboxing SandboxExecutor**: Executa codi generat pel LLM en un entorn aïllat aplicant límits estrictes de recursos de maquinari i temps d'espera (timeouts).

---

## 🛠️ Instal·lació i Arrencada

> **Nota**: Aquest stack assumeix que tens [Ollama](https://ollama.com/) executant-se de manera externa (per exemple, a l'host o en un altre servidor). Per defecte, està preconfigurat per connectar-se a `http://host.docker.internal:11434`.

### Pas 1: Configurar Variables d'Entorn
Copia la plantilla i configura les teves claus i contrasenyes secretes al fitxer `.env`:
```bash
cp .env.example .env
nano .env
```
Assegura't d'apuntar les variables `OLLAMA_API_URL` i `OLLAMA_URL` cap al teu endpoint d'Ollama corresponent.

### Pas 2: Arrancar els Contenidors
Selecciona l'ordre adequada segons el maquinari del teu servidor o màquina:

- **Mode CPU (Sense GPU)**:
  ```bash
  docker compose --profile cpu --profile voice-cpu up -d
  ```

- **Mode GPU NVIDIA**:
  ```bash
  docker compose --profile gpu-nvidia --profile voice up -d
  ```

- **Amb Tunelització Pública (zrok)**:
  Afegeix `--profile zrok` a qualsevol de les instruccions anteriors.

### Pas 3: Arrancar el Cognito Worker a l'Host (Opcional per a l'agent)
Per configurar el component d'execució segura en segon pla del costat de l'host:
```bash
cd cognito-worker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn worker_app.main:app --host 0.0.0.0 --port 8001
```

---

## 💡 Què Podem Fer amb Això?

Una vegada aixecat l'stack, tens un entorn cognitiu de desenvolupament extremadament potent per a:

1. **Crear i Instanciar Agents Autònoms**:
   Utilitza l'API de `cognito-backend` o la CLI interactiva en Python (`python -m cli.cognito_cli`) per dialogar amb el teu repositori, permetent a l'agent llegir, editar, escriure fitxers o executar comandes bash de manera autònoma amb total seguretat i control de trust.
2. **Executar fluxos d'AGI de 5 fases**:
   Utilitza el mòdul `agents/` per descompondre tasques complexes (fase 1: Chain-of-Thought), validar sortides amb auto-iteració i feedback en calent (fase 2: Self-Evaluation), aprendre d'execucions passades (fase 3: Memory & Learning), coordinar equips amb l'enrutador intel·ligent d'agents (fase 4) i optimitzar recursos (fase 5).
3. **Fluxos RAG i Cerca Semàntica**:
   Injecta documents, models d'amenaça o guies d'arquitectura locals a Qdrant, permetent als teus agents consultar i respondre preguntes complexes amb context en temps real.
4. **Processament de Veu Local**:
   Converteix text a veu d'alta qualitat amb Kokoro, transcriu àudios amb Whisper o separa pistes amb Demucs mitjançant la pasarel·la de veu unificada.
