# Jupyter Notebooks for Testing connect-core
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/NOTEBOOKS_GUIDE.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/NOTEBOOKS_GUIDE.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/NOTEBOOKS_GUIDE.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/NOTEBOOKS_GUIDE.zh-cn.md)


This directory contains Jupyter notebooks to test the agent architecture and orchestration of connect-core.

## Available Notebooks

### 1. `test_agent_router.ipynb` 🔀
**Purpose:** Agent router and multi-agent orchestration testing

**Contents:**
- ✓ Task routing tests
- ✓ Multi-agent orchestration
- ✓ Task decomposition
- ✓ Inter-agent communication

**Requirements:**
- Modules: `AgentRouter`, `MultiAgentOrchestrator`, `TaskDecomposer`

---

### 2. `test_communication.ipynb` 📡
**Purpose:** Communication tests between n8n and services (Ollama, Qdrant)

**Contents:**
- ✓ Service health checks
- ✓ Ollama integration (local LLM)
- ✓ Text generation
- ✓ Qdrant Vector Database
- ✓ Full communication pipeline

**Requirements:**
- Docker services: n8n, Ollama, Qdrant
- Libraries: `requests`

**Service URLs:**
- n8n: `http://localhost:5678`
- Ollama: `http://localhost:11434`
- Qdrant: `http://localhost:6333`

---

### 3. `test_task_decomposition.ipynb` 🔧
**Purpose:** Task decomposition and parallel execution testing

**Contents:**
- ✓ Complex task decomposition
- ✓ Parallel subtask execution
- ✓ Dependency resolution
- ✓ Results synthesis
- ✓ Performance analysis

**Requirements:**
- Modules: `TaskDecomposer`, `ParallelTaskExecutor`, `ResultSynthesizer`
- Libraries: `concurrent.futures`, `time`

---

### 4. `test_end_to_end.ipynb` 🚀
**Purpose:** Complete workflow test with Ollama + Qdrant integration

**Contents:**
- **Workflow 1:** Document analysis with RAG (Retrieval Augmented Generation)
  - Task routing
  - Task decomposition
  - Ollama integration
  - Qdrant storage
  - Results synthesis
  - Output validation

- **Workflow 2:** Multi-agent collaboration
  - Inter-agent conversation simulation
  - Message flow
  - Information exchange

**Requirements:**
- All agent modules
- Services: n8n, Ollama, Qdrant
- Libraries: `requests`, `json`

---

## How to run the notebooks

### Prerequisites

1. **Start the Docker stack:**
```bash
./start.sh
```

2. **Install Jupyter (if not already installed):**
```bash
pip install jupyter notebook
```

3. **Navigate to the project directory:**
```bash
cd /workspaces/connect-core
```

### Run a specific notebook

```bash
jupyter notebook test_agent_router.ipynb
```

### Run all notebooks in sequence

```bash
jupyter notebook
# Then open each notebook and run the cells
```

### Run from VS Code

1. Open VS Code in the project directory
2. Select a `.ipynb` file
3. VS Code will automatically detect the notebooks
4. Click "Run All" to execute all cells

---

## Notebook Structure

Each notebook follows a standard structure:

```
1. Setup/Imports
   └─ Import necessary modules
   └─ Configure environment variables

2. Test 1: Component 1
   └─ Verify component operation
   └─ Show results

3. Test 2: Component 2
   └─ Verify component operation
   └─ Show results

... (more tests)

N. Summary
   └─ Summary of all tests
   └─ Final metrics
```

---

## Environment Variables

The notebooks use the following environment variables (with default values):

```bash
# .env or system variables
N8N_BASE_URL=http://localhost:5678
OLLAMA_BASE_URL=http://localhost:11434
QDRANT_BASE_URL=http://localhost:6333
```

---

## Validations in each notebook

### `test_agent_router.ipynb`
- ✓ Agents correctly detected
- ✓ Tasks routed to appropriate agents
- ✓ Multi-agent orchestration works
- ✓ Inter-agent communication established

### `test_communication.ipynb`
- ✓ n8n responds to health checks
- ✓ Ollama accessible and models available
- ✓ Qdrant connected and functional
- ✓ Full communication pipeline works

### `test_task_decomposition.ipynb`
- ✓ Complex tasks correctly decomposed
- ✓ Efficient parallel execution
- ✓ Dependencies correctly resolved
- ✓ Results accurately synthesized

### `test_end_to_end.ipynb`
- ✓ Routing → decomposition → execution flow works
- ✓ Ollama generates valid responses
- ✓ Qdrant stores results
- ✓ Correct results synthesis
- ✓ Successful output validation
- ✓ Multi-agents collaborate correctly

---

## Troubleshooting

### Error: "Cannot connect to Docker services"
**Solution:**
```bash
# Verify that services are running
docker compose ps

# If not running, start:
./start.sh
```

### Error: "ModuleNotFoundError: No module named 'agents'"
**Solution:**
```bash
# Ensure you are in the correct directory
cd /workspaces/connect-core

# Verify that the path is in sys.path
# Should be included in the notebook with: sys.path.insert(0, os.path.abspath('.'))
```

### Ollama: "No models available"
**Solution:**
```bash
# Download models manually
docker exec ollama ollama pull llama3.2

# Or wait for them to download automatically
```

### Timeout in requests
**Solution:**
```bash
# Increase timeout in requests
# In notebooks, change timeout=5 to timeout=30
```

---

## Next Steps

1. **Run all notebooks in order:**
   - `test_agent_router.ipynb` (verifies routing)
   - `test_communication.ipynb` (verifies communication)
   - `test_task_decomposition.ipynb` (verifies parallelization)
   - `test_end_to_end.ipynb` (verifies full flow)

2. **Monitor metrics:**
   - Execution time
   - Resource usage (CPU, memory)
   - Errors and warnings

3. **Document results:**
   - Save notebook outputs
   - Create test report

4. **Optimize based on results:**
   - Adjust timeouts if necessary
   - Optimize task decomposition
   - Improve results synthesis

---

## Useful Links

- [Jupyter Documentation](https://jupyter.readthedocs.io/)
- [n8n Documentation](https://docs.n8n.io/)
- [Ollama GitHub](https://github.com/ollama/ollama)
- [Qdrant Documentation](https://qdrant.tech/documentation/)

---

**Last update:** 2025-12-20
**connect-core version:** Latest
