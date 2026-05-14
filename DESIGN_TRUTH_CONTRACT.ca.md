# 📋 Design Truth Contract - Testing Framework de connect-core
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/DESIGN_TRUTH_CONTRACT.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/DESIGN_TRUTH_CONTRACT.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/DESIGN_TRUTH_CONTRACT.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/[ORGANIZATION]/connect-core/blob/master/DESIGN_TRUTH_CONTRACT.zh-cn.md)


**Versió:** 1.0
**Data:** 2025-12-20
**Estat:** Actiu
**Última actualització:** 2025-12-20

---

## 1. Requisits de l'Arquitectura Core

### 1.1 Orquestració Multi-Agent ✅
**Must Have:** Els agents treballen junts en harmonia
- [x] Enrutament d'agents basat en el tipus de tasca
- [x] Comunicació entre agents
- [x] Distribució de tasques
- [x] Síntesi de resultats
- [ ] Priorització d'agents
- [ ] Balanceig de càrrega
- [ ] Tolerància a fallades

### 1.2 Integració amb LLM ✅
**Must Have:** Ollama funciona de forma fiable
- [x] Comprovació de disponibilitat del model
- [x] Generació de text
- [x] Gestió de prompts
- [x] Validació de respostes
- [ ] Comptatge de tokens
- [ ] Gestió de context
- [ ] Capacitat de fine-tuning

### 1.3 Base de Dades Vectorial ✅
**Must Have:** Qdrant per a embeddings
- [x] Gestió de col·leccions
- [x] Emmagatzematge de vectors
- [x] Cerca per similitud
- [x] Recuperació de dades
- [ ] Optimització d'índexs
- [ ] Operacions d'esborrat
- [ ] Operacions per lot (batch)

### 1.4 Orquestració de Workflows ✅
**Must Have:** Integració amb n8n
- [x] Comunicació via Webhook
- [x] Disparament (triggering) de tasques
- [x] Gestió de resultats
- [x] Gestió d'errors
- [ ] Programació de workflows (scheduling)
- [ ] Lògica condicional
- [ ] Gestió de bucles (loops)

---

## 2. Testing de Components d'Agents

### 2.1 Agents Crítics

#### AgentRouter 🔀
**Estat:** Necessita testing exhaustiu
```
Propòsit: Enrutar tasques als agents apropiats
Tests Necessaris:
  □ Enrutar tasques d'anàlisi
  □ Enrutar tasques de generació
  □ Enrutar tasques de processament
  □ Gestionar tipus de tasques desconeguts
  □ Rendiment sota càrrega
```

#### ChainOfThoughtAgent 🧠
**Estat:** Necessita testing
```
Propòsit: Raonament estratègic
Tests Necessaris:
  □ Generar cadenes de raonament
  □ Validar flux lògic
  □ Mètriques de rendiment
  □ Gestió d'errors
```

#### IterativeAgent 🔄
**Estat:** Necessita testing
```
Propòsit: Refinament iteratiu
Tests Necessaris:
  □ Execució multi-pas
  □ Seguiment de millores
  □ Detecció de convergència
  □ Ús de recursos
```

#### ResultSynthesizer 🔗
**Estat:** Testejat parcialment
```
Propòsit: Combinar sortides d'agents
Tests Necessaris:
  □ Combinar resultats heterogenis
  □ Gestionar dades faltants
  □ Estandardització de format
  □ Mètriques de qualitat
```

#### OutputValidator ✅
**Estat:** Necessita testing
```
Propòsit: Validar sortides
Tests Necessaris:
  □ Validació d'esquema
  □ Validació de contingut
  □ Comprovació de format
  □ Verificació de consistència
```

### 2.2 Agents de Suport

#### TaskDecomposer 📦
- [x] Desglossar tasques complexes
- [ ] Anàlisi de dependències
- [ ] Optimització
- [ ] Assignació de recursos

#### ParallelTaskExecutor ⚡
- [ ] Execució concurrent
- [ ] Gestió de dependències
- [ ] Recuperació d'errors
- [ ] Optimització del rendiment

#### MemoryManager 🧠
- [ ] Emmagatzematge de context
- [ ] Eficiència en la recuperació
- [ ] Gestió de mida
- [ ] Neteja de memòria cau (cache)

#### ModelRouter 🛣️
- [ ] Selecció de model
- [ ] Comparació de rendiment
- [ ] Optimització de costos
- [ ] Aparellament de capacitats

---

## 3. Requisits d'Integration Testing

### 3.1 n8n ↔ Agents
**CAL TESTEJAR:**
```
□ Webhook → Enrutament d'agents
□ Paràmetres de tasca → Entrada de l'agent
□ Sortida de l'agent → Formateig de resposta
□ Gestió d'errors
□ Gestió de timeouts
```

### 3.2 Agents ↔ Ollama
**CAL TESTEJAR:**
```
□ Càrrega de models
□ Formateig de prompts
□ Parseig de respostes
□ Gestió de tokens
□ Models de reserva (fallback)
```

### 3.3 Agents ↔ Qdrant
**CAL TESTEJAR:**
```
□ Generació d'embeddings
□ Emmagatzematge de vectors
□ Cerca per similitud
□ Gestió de col·leccions
□ Persistència de dades
```

### 3.4 Pipeline Complet
**CAL TESTEJAR:**
```
n8n Webhook
    ↓
AgentRouter
    ↓
TaskDecomposer
    ↓
Execució Paral·lela
    ↓
Ollama (trucades LLM)
    ↓
Qdrant (Emmagatzematge)
    ↓
ResultSynthesizer
    ↓
OutputValidator
    ↓
Resposta n8n
```

---

## 4. Estat Actual dels Notebooks

### ✅ El que tenim
1. **test_agent_router.ipynb**
   - Tests bàsics d'enrutament
   - Assignació de tasques
   - Detecció d'agents

2. **test_communication.ipynb**
   - Health checks de serveis
   - Integració amb Ollama
   - Operacions bàsiques de Qdrant
   - Resum del pipeline

3. **test_task_decomposition.ipynb**
   - Desglossament de tasques
   - Execució paral·lela
   - Resolució de dependències

4. **test_end_to_end.ipynb**
   - Workflow d'anàlisi de documents
   - Col·laboració multi-agent
   - Patró RAG

### ❌ El que necessitem (Must Have)

1. **test_agent_components.ipynb** ⭐ CRITICAL
   - Testejar cada agent individualment
   - Verificar contractes de components
   - Mesurar rendiment

2. **test_integration_n8n_agents.ipynb** ⭐ CRITICAL
   - Comunicació n8n → Agent
   - Flux petició/resposta
   - Escenaris d'error

3. **test_llm_pipeline.ipynb** ⭐ CRITICAL
   - Integració amb Ollama
   - Gestió de prompts
   - Validació de respostes
   - Gestió de tokens

4. **test_rag_system.ipynb** ⭐ CRITICAL
   - Workflow RAG de principi a fi
   - Generació d'embeddings
   - Precisió en la recuperació
   - Ús del context

5. **test_agent_reliability.ipynb** ⭐ CRITICAL
   - Recuperació d'errors
   - Gestió de timeouts
   - Mecanismes de reintent
   - Degradació controlada

6. **test_performance_benchmarks.ipynb** ⭐ IMPORTANT
   - Mesurament de rendiment (throughput)
   - Anàlisi de latència
   - Perfilat de recursos
   - Tests d'escalabilitat

7. **test_concurrent_workflows.ipynb** ⭐ IMPORTANT
   - Execució de tasques en paral·lel
   - Contenció de recursos
   - Gestió de cues
   - Balanç de càrrega

8. **test_data_persistence.ipynb** ⭐ IMPORTANT
   - Gestió d'estat
   - Recuperació de dades
   - Comprovacions de consistència
   - Procediments de recuperació

---

## 5. Patró de Disseny de Notebooks

### Estructura de la Plantilla
```
1. Configuració i Imports
   └─ Inicialitzar serveis
   └─ Configurar logging
   └─ Carregar credencials

2. Comprovació de Prerequisits
   └─ Salut dels serveis
   └─ Dependències llestes
   └─ Dades disponibles

3. Suites de Test
   └─ Unit tests
   └─ Integration tests
   └─ Stress tests
   └─ Casos límit (edge cases)

4. Validació
   └─ Condicions d'asserció (assert)
   └─ Mesurament de mètriques
   └─ Documentació de resultats

5. Neteja i Resum
   └─ Neteja de recursos
   └─ Generació d'informes
   └─ Següents passos
```

---

## 6. Estratègia d'Execució de Tests

### Fase 1: Testing de Components (Setmana 1)
```
1. test_agent_components.ipynb
2. test_llm_pipeline.ipynb
3. test_integration_n8n_agents.ipynb
```

### Fase 2: Integration Testing (Setmana 2)
```
4. test_rag_system.ipynb
5. test_agent_reliability.ipynb
6. test_concurrent_workflows.ipynb
```

### Fase 3: Rendiment i Escala (Setmana 3)
```
7. test_performance_benchmarks.ipynb
8. test_data_persistence.ipynb
9. Validació end-to-end
```

---

## 7. Criteris d'Èxit

### Per a cada Notebook
- ✅ Tots els tests passen
- ✅ Sense excepcions no gestionades
- ✅ Rendiment dins dels objectius
- ✅ Resultats reproduïbles
- ✅ Documentació completa

### Sistema Global
- ✅ Els components funcionen individualment
- ✅ Els components s'integren correctament
- ✅ El sistema escala de forma fiable
- ✅ Rendiment acceptable
- ✅ Els mecanismes de recuperació funcionen

---

## 8. Checklist de Validació

### Abans de fusionar (merge) el codi:
- [ ] Passen els tests de components
- [ ] Passen els tests d'integració
- [ ] Benchmarks de rendiment acceptables
- [ ] Sense fugues de memòria (memory leaks)
- [ ] Gestió d'errors testejada
- [ ] Casos límit coberts
- [ ] Documentació actualitzada

### Abans de producció:
- [ ] Tots els tests dels notebooks passen
- [ ] Tests de càrrega exitosos
- [ ] Escenaris de fallada gestionats
- [ ] Seguretat revisada
- [ ] Rendiment optimitzat
- [ ] Monitorització en marxa

---

## 9. Mètriques a Seguir

### Rendiment
- Temps d'execució de tasques
- Latència de resposta dels agents
- Ús de memòria
- Utilització de CPU
- I/O de xarxa

### Fiabilitat
- Taxa d'èxit per agent
- Temps de recuperació d'errors
- Temps d'activitat del sistema (uptime)
- Consistència de dades
- Finalització de transaccions

### Qualitat
- Cobertura de tests
- Taxa de detecció de bugs
- Puntuació de qualitat del codi
- Completesa de la documentació
- Satisfacció de l'usuari

---

## 10. Full de Ruta (Roadmap)

### Estat Actual 📊
```
Completat: ████░░░░░░░░░░░░░░ 20%
En Progrés: ░░░░░░░░░░░░░░░░░░ 0%
Planificat: ██████████████░░░░ 80%
```

### Properes Accions
1. **Crear test_agent_components.ipynb** ⭐
2. **Crear test_integration_n8n_agents.ipynb** ⭐
3. **Crear test_llm_pipeline.ipynb** ⭐
4. **Crear test_rag_system.ipynb** ⭐
5. **Crear test_agent_reliability.ipynb** ⭐
6. **Crear test_performance_benchmarks.ipynb**
7. **Crear test_concurrent_workflows.ipynb**
8. **Crear test_data_persistence.ipynb**
9. Executar tests de la Fase 1
10. Analitzar i optimitzar

---

## Resum

**Notebooks actuals (4):** ✅ Bona base
- Proporcionen cobertura de testing bàsica
- Validen els fluxos de comunicació
- Testegen la descomposició i síntesi

**Notebooks faltants (5 Crítics + 3 Importants):**
- Necessiten testing detallat de components d'agents
- Necessiten validació d'integració amb n8n
- Necessiten verificació del pipeline de LLM
- Necessiten validació del sistema RAG
- Necessiten testing de fiabilitat
- Necessiten benchmarks de rendiment

**Avaluació Global:** 📊
- **30% completat** - Testing d'infraestructura bàsica acabat
- **70% restant** - Crític: testing de components i integració

---

**Veritat de Disseny:** El sistema és arquitectònicament sòlid, però necessitem
un testing exhaustiu de:
1. Comportament individual dels agents
2. Comunicació entre agents
3. Fiabilitat de la integració amb LLM
4. Precisió del sistema RAG
5. Tolerància a fallades del sistema

Una vegada validats, podrem passar a producció amb confiança.

---

**Creat per:** GitHub Copilot
**Propòsit:** Assegurar la qualitat i fiabilitat del sistema
**Vàlid fins a:** Canvis en l'arquitectura del sistema
