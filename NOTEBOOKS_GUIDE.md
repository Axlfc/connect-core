# Jupyter Notebooks for Testing cognito-stack
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/cognito-stack/blob/master/NOTEBOOKS_GUIDE.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/NOTEBOOKS_GUIDE.en.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/cognito-stack/blob/master/NOTEBOOKS_GUIDE.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/NOTEBOOKS_GUIDE.zh-cn.md)


Este directorio contiene notebooks de Jupyter para probar la arquitectura de agentes y la orquestación de cognito-stack.

## Notebooks disponibles

### 1. `test_agent_router.ipynb` 🔀
**Propósito:** Pruebas del enrutador de agentes y orquestación multi-agente

**Contenido:**
- ✓ Pruebas de enrutamiento de tareas
- ✓ Orquestación multi-agente
- ✓ Descomposición de tareas
- ✓ Comunicación entre agentes

**Requerimientos:**
- Módulos: `AgentRouter`, `MultiAgentOrchestrator`, `TaskDecomposer`

---

### 2. `test_communication.ipynb` 📡
**Propósito:** Pruebas de comunicación entre n8n y servicios (Ollama, Qdrant)

**Contenido:**
- ✓ Health checks de servicios
- ✓ Integración con Ollama (LLM local)
- ✓ Generación de texto
- ✓ Qdrant Vector Database
- ✓ Pipeline de comunicación completo

**Requerimientos:**
- Docker services: n8n, Ollama, Qdrant
- Librerías: `requests`

**URLs de servicios:**
- n8n: `http://localhost:5678`
- Ollama: `http://localhost:11434`
- Qdrant: `http://localhost:6333`

---

### 3. `test_task_decomposition.ipynb` 🔧
**Propósito:** Pruebas de descomposición de tareas y ejecución paralela

**Contenido:**
- ✓ Descomposición de tareas complejas
- ✓ Ejecución paralela de subtareas
- ✓ Resolución de dependencias
- ✓ Síntesis de resultados
- ✓ Análisis de performance

**Requerimientos:**
- Módulos: `TaskDecomposer`, `ParallelTaskExecutor`, `ResultSynthesizer`
- Librerías: `concurrent.futures`, `time`

---

### 4. `test_end_to_end.ipynb` 🚀
**Propósito:** Prueba completa de flujo de trabajo con integración Ollama + Qdrant

**Contenido:**
- **Workflow 1:** Análisis de documentos con RAG (Retrieval Augmented Generation)
  - Enrutamiento de tareas
  - Descomposición de tareas
  - Integración con Ollama
  - Almacenamiento en Qdrant
  - Síntesis de resultados
  - Validación de salida

- **Workflow 2:** Colaboración multi-agente
  - Simulación de conversación entre agentes
  - Flujo de mensajes
  - Intercambio de información

**Requerimientos:**
- Todos los módulos de agentes
- Servicios: n8n, Ollama, Qdrant
- Librerías: `requests`, `json`

---

## Cómo ejecutar los notebooks

### Prerrequisitos

1. **Iniciar el stack de Docker:**
```bash
./start.sh
```

2. **Instalar Jupyter (si no está instalado):**
```bash
pip install jupyter notebook
```

3. **Navegar al directorio del proyecto:**
```bash
cd /workspaces/cognito-stack
```

### Ejecutar un notebook específico

```bash
jupyter notebook test_agent_router.ipynb
```

### Ejecutar todos los notebooks en secuencia

```bash
jupyter notebook
# Luego abre cada notebook y ejecuta las celdas
```

### Ejecutar desde VS Code

1. Abre VS Code en el directorio del proyecto
2. Selecciona un archivo `.ipynb`
3. VS Code detectará automáticamente los notebooks
4. Haz clic en "Run All" para ejecutar todas las celdas

---

## Estructura de los notebooks

Cada notebook sigue una estructura estándar:

```
1. Setup/Imports
   └─ Importar módulos necesarios
   └─ Configurar variables de entorno

2. Test 1: Component 1
   └─ Verificar funcionamiento del componente
   └─ Mostrar resultados

3. Test 2: Component 2
   └─ Verificar funcionamiento del componente
   └─ Mostrar resultados

... (más tests)

N. Summary
   └─ Resumen de todos los tests
   └─ Métricas finales
```

---

## Variables de entorno

Los notebooks usan las siguientes variables de entorno (con valores por defecto):

```bash
# .env o en variables de sistema
N8N_BASE_URL=http://localhost:5678
OLLAMA_BASE_URL=http://localhost:11434
QDRANT_BASE_URL=http://localhost:6333
```

---

## Validaciones en cada notebook

### `test_agent_router.ipynb`
- ✓ Agentes detectados correctamente
- ✓ Tareas enrutadas a agentes apropiados
- ✓ Orquestación multi-agente funciona
- ✓ Comunicación entre agentes establecida

### `test_communication.ipynb`
- ✓ n8n responde a health checks
- ✓ Ollama accesible y modelos disponibles
- ✓ Qdrant conectado y funcional
- ✓ Pipeline de comunicación completo

### `test_task_decomposition.ipynb`
- ✓ Tareas complejas descompuestas correctamente
- ✓ Ejecución paralela eficiente
- ✓ Dependencias resueltas correctamente
- ✓ Resultados sintetizados acertadamente

### `test_end_to_end.ipynb`
- ✓ Flujo de routing → decomposición → ejecución
- ✓ Ollama genera respuestas válidas
- ✓ Qdrant almacena resultados
- ✓ Síntesis de resultados correcta
- ✓ Validación de salida exitosa
- ✓ Multi-agentes colaboran correctamente

---

## Troubleshooting

### Error: "Cannot connect to Docker services"
**Solución:**
```bash
# Verificar que los servicios estén corriendo
docker compose ps

# Si no están corriendo, iniciar:
./start.sh
```

### Error: "ModuleNotFoundError: No module named 'agents'"
**Solución:**
```bash
# Asegúrate de estar en el directorio correcto
cd /workspaces/cognito-stack

# Verifica que la ruta esté en sys.path
# Debería incluirse en el notebook con: sys.path.insert(0, os.path.abspath('.'))
```

### Ollama: "No models available"
**Solución:**
```bash
# Descargar modelos manualmente
docker exec ollama ollama pull llama3.2

# O esperar a que se descarguen automáticamente
```

### Timeout en requests
**Solución:**
```bash
# Aumentar timeout en los requests
# En los notebooks, cambiar timeout=5 a timeout=30
```

---

## Próximos pasos

1. **Ejecutar todos los notebooks en orden:**
   - `test_agent_router.ipynb` (verifica enrutamiento)
   - `test_communication.ipynb` (verifica comunicación)
   - `test_task_decomposition.ipynb` (verifica paralelización)
   - `test_end_to_end.ipynb` (verifica flujo completo)

2. **Monitorear métricas:**
   - Tiempo de ejecución
   - Uso de recursos (CPU, memoria)
   - Errores y advertencias

3. **Documentar resultados:**
   - Guardar outputs de los notebooks
   - Crear reporte de pruebas

4. **Optimizar basado en resultados:**
   - Ajustar timeouts si es necesario
   - Optimizar descomposición de tareas
   - Mejorar síntesis de resultados

---

## Links útiles

- [Jupyter Documentation](https://jupyter.readthedocs.io/)
- [n8n Documentation](https://docs.n8n.io/)
- [Ollama GitHub](https://github.com/ollama/ollama)
- [Qdrant Documentation](https://qdrant.tech/documentation/)

---

**Última actualización:** 2025-12-20
**Versión de cognito-stack:** Latest
