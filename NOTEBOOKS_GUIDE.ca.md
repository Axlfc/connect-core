# Notebooks de Jupyter per a provar connect-core
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/NOTEBOOKS_GUIDE.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/NOTEBOOKS_GUIDE.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/NOTEBOOKS_GUIDE.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/NOTEBOOKS_GUIDE.zh-cn.md)


Aquest directori conté notebooks de Jupyter per a provar l'arquitectura d'agents i l'orquestració de connect-core.

## Notebooks disponibles

### 1. `test_agent_router.ipynb` 🔀
**Propòsit:** Proves de l'enrutador d'agents i orquestració multi-agent

**Contingut:**
- ✓ Proves d'enrutament de tasques
- ✓ Orquestració multi-agent
- ✓ Descomposició de tasques
- ✓ Comunicació entre agents

**Requeriments:**
- Mòduls: `AgentRouter`, `MultiAgentOrchestrator`, `TaskDecomposer`

---

### 2. `test_communication.ipynb` 📡
**Propòsit:** Proves de comunicació entre n8n i serveis (Ollama, Qdrant)

**Contingut:**
- ✓ Health checks de serveis
- ✓ Integració amb Ollama (LLM local)
- ✓ Generació de text
- ✓ Qdrant Vector Database
- ✓ Pipeline de comunicació complet

**Requeriments:**
- Docker services: n8n, Ollama, Qdrant
- Llibreries: `requests`

**URLs de serveis:**
- n8n: `http://localhost:5678`
- Ollama: `http://localhost:11434`
- Qdrant: `http://localhost:6333`

---

### 3. `test_task_decomposition.ipynb` 🔧
**Propòsit:** Proves de descomposició de tasques i execució paral·lela

**Contingut:**
- ✓ Descomposició de tasques complexes
- ✓ Execució paral·lela de subtasques
- ✓ Resolució de dependències
- ✓ Síntesi de resultats
- ✓ Anàlisi de rendiment

**Requeriments:**
- Mòduls: `TaskDecomposer`, `ParallelTaskExecutor`, `ResultSynthesizer`
- Llibreries: `concurrent.futures`, `time`

---

### 4. `test_end_to_end.ipynb` 🚀
**Propòsit:** Prova completa de flux de treball amb integració Ollama + Qdrant

**Contingut:**
- **Workflow 1:** Anàlisi de documents amb RAG (Retrieval Augmented Generation)
  - Enrutament de tasques
  - Descomposició de tasques
  - Integració amb Ollama
  - Emmagatzematge a Qdrant
  - Síntesi de resultats
  - Validació de sortida

- **Workflow 2:** Col·laboració multi-agent
  - Simulació de conversa entre agents
  - Flux de missatges
  - Intercanvi d'informació

**Requeriments:**
- Tots els mòduls d'agents
- Serveis: n8n, Ollama, Qdrant
- Llibreries: `requests`, `json`

---

## Com executar els notebooks

### Prerequisits

1. **Iniciar l'stack de Docker:**
```bash
./start.sh
```

2. **Instal·lar Jupyter (si no està instal·lat):**
```bash
pip install jupyter notebook
```

3. **Navegar al directori del projecte:**
```bash
cd /workspaces/connect-core
```

### Executar un notebook específic

```bash
jupyter notebook test_agent_router.ipynb
```

### Executar tots els notebooks en seqüència

```bash
jupyter notebook
# Després obre cada notebook i executa les cel·les
```

### Executar des de VS Code

1. Obre VS Code al directori del projecte
2. Selecciona un fitxer `.ipynb`
3. VS Code detectarà automàticament els notebooks
4. Fes clic a "Run All" per executar totes les cel·les

---

## Estructura dels notebooks

Cada notebook segueix una estructura estàndard:

```
1. Setup/Imports
   └─ Importar mòduls necessaris
   └─ Configurar variables d'entorn

2. Test 1: Component 1
   └─ Verificar funcionament del component
   └─ Mostrar resultats

3. Test 2: Component 2
   └─ Verificar funcionament del component
   └─ Mostrar resultats

... (més tests)

N. Summary
   └─ Resum de tots els tests
   └─ Mètriques finals
```

---

## Variables d'entorn

Els notebooks utilitzen les següents variables d'entorn (amb valors per defecte):

```bash
# .env o en variables de sistema
N8N_BASE_URL=http://localhost:5678
OLLAMA_BASE_URL=http://localhost:11434
QDRANT_BASE_URL=http://localhost:6333
```

---

## Validacions a cada notebook

### `test_agent_router.ipynb`
- ✓ Agents detectats correctament
- ✓ Tasques enrutades als agents apropiats
- ✓ L'orquestració multi-agent funciona
- ✓ Comunicació entre agents establerta

### `test_communication.ipynb`
- ✓ n8n respon als health checks
- ✓ Ollama accessible i models disponibles
- ✓ Qdrant connectat i funcional
- ✓ Pipeline de comunicació complet

### `test_task_decomposition.ipynb`
- ✓ Tasques complexes descomposades correctament
- ✓ Execució paral·lela eficient
- ✓ Dependències resoltes correctament
- ✓ Resultats sintetitzats encertadament

### `test_end_to_end.ipynb`
- ✓ Flux de routing → descomposició → execució
- ✓ Ollama genera respostes vàlides
- ✓ Qdrant emmagatzema resultats
- ✓ Síntesi de resultats correcta
- ✓ Validació de sortida exitosa
- ✓ Multi-agents col·laboren correctament

---

## Resolució de problemes (Troubleshooting)

### Error: "Cannot connect to Docker services"
**Solució:**
```bash
# Verificar que els serveis estiguin corrent
docker compose ps

# Si no estan corrent, iniciar:
./start.sh
```

### Error: "ModuleNotFoundError: No module named 'agents'"
**Solució:**
```bash
# Assegura't d'estar al directori correcte
cd /workspaces/connect-core

# Verifica que la ruta estigui a sys.path
# Hauria d'incloure's al notebook amb: sys.path.insert(0, os.path.abspath('.'))
```

### Ollama: "No models available"
**Solució:**
```bash
# Descarregar models manualment
docker exec ollama ollama pull llama3.2

# O esperar que es descarreguin automàticament
```

### Timeout en requests
**Solució:**
```bash
# Augmentar timeout als requests
# Als notebooks, canviar timeout=5 a timeout=30
```

---

## Propers passos

1. **Executar tots els notebooks en ordre:**
   - `test_agent_router.ipynb` (verifica enrutament)
   - `test_communication.ipynb` (verifica comunicació)
   - `test_task_decomposition.ipynb` (verifica paral·lelització)
   - `test_end_to_end.ipynb` (verifica flux complet)

2. **Monitorar mètriques:**
   - Temps d'execució
   - Ús de recursos (CPU, memòria)
   - Errors i avisos

3. **Documentar resultats:**
   - Guardar outputs dels notebooks
   - Crear informe de proves

4. **Optimitzar basat en resultats:**
   - Ajustar timeouts si cal
   - Optimitzar descomposició de tasques
   - Millorar síntesi de resultats

---

## Enllaços útils

- [Documentació de Jupyter](https://jupyter.readthedocs.io/)
- [Documentació de n8n](https://docs.n8n.io/)
- [GitHub d'Ollama](https://github.com/ollama/ollama)
- [Documentació de Qdrant](https://qdrant.tech/documentation/)

---

**Última actualització:** 2025-12-20
**Versió de connect-core:** Latest
