# BACKLOG DE TAREAS - FRAMEWORK NOOA (NVIDIA-labs Object Oriented Agents)

Este backlog representa la descomposición estructurada y secuencial de las **30 features fundamentales** del framework **NOOA**, diseñadas para ser incorporadas programáticamente al backlog de desarrollo del repositorio de `cognito agent` en `very-simplified-stack`.

Las tareas están ordenadas lógicamente respetando su grafo de dependencias técnicas (desde la configuración base y abstracciones de modelos, hasta estrategias interactivas complejas, observabilidad y benchmarking).

---

## ÍNDICE DE TAREAS POR ORDEN DE IMPLEMENTACIÓN

| ID | Título del Ticket | Categoría | Prioridad | Dependencias | Componente |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **NOOA-01** | [Configuración] Sistema de configuración por capas | Configuración | **Alta** | Ninguna | `nooa-framework` |
| **NOOA-02** | [LLM Integration] UnifiedLLM sobre litellm | LLM Integration | **Alta** | NOOA-01 | `nooa-framework` |
| **NOOA-03** | [LLM Integration] Resiliencia, reintentos y HTTP | LLM Integration | **Alta** | NOOA-02 | `nooa-framework` |
| **NOOA-04** | [Paradigma Core] Contratos tipados y salidas Pydantic | Paradigma Core | **Alta** | Ninguna | `nooa-framework` |
| **NOOA-05** | [Testing LLM] Clientes fake/replay para pruebas deterministas | Testing LLM | **Alta** | NOOA-02 | `nooa-framework` |
| **NOOA-06** | [Paradigma Core] Metaclase de detección de métodos de generación | Paradigma Core | **Alta** | NOOA-02, NOOA-04 | `nooa-framework` |
| **NOOA-07** | [Paradigma Core] Sistema de visibilidad selectiva (`@hidden`, `_private`) | Paradigma Core | **Alta** | Ninguna | `nooa-framework` |
| **NOOA-08** | [Memoria corta] EventManager: registro de eventos | Memoria corta | **Alta** | Ninguna | `nooa-framework` |
| **NOOA-09** | [Contexto] Sistema de ContextBlocks/DynamicContext | Contexto | **Alta** | Ninguna | `nooa-framework` |
| **NOOA-10** | [Documentación dinámica] AgentDoc: firmas y docstrings para LLM | Documentación dinámica | **Media** | NOOA-07 | `nooa-framework` |
| **NOOA-11** | [Seguridad] SandboxedExecutor: límites, timeouts y Landlock | Seguridad | **Alta** | Ninguna | `cognito-worker` |
| **NOOA-12** | [Runtime] ActorRuntime: orquestación de ciclo de vida | Runtime | **Alta** | NOOA-06, NOOA-08, NOOA-09 | `nooa-framework` |
| **NOOA-13** | [Runtime] Estrategia Predict: un solo turno | Runtime | **Alta** | NOOA-12 | `nooa-framework` |
| **NOOA-14** | [Runtime] Estrategia CodeAct: REPL interactivo | Runtime | **Alta** | NOOA-11, NOOA-12 | `cognito-worker` |
| **NOOA-15** | [Tools] Toolset incorporado: ShellTools, TodoTools y Web | Tools | **Media** | NOOA-11 | `cognito-worker` |
| **NOOA-16** | [Skills] Sistema de Skills basado en `SKILL.md` | Skills | **Media** | NOOA-09 | `nooa-framework` |
| **NOOA-17** | [Integraciones externas] Soporte MCP (Model Context Protocol) | Integraciones externas | **Media** | NOOA-12 | `nooa-framework` |
| **NOOA-18** | [Memoria largo plazo] nooa-memory: SQLite + vectoriales | Memoria largo plazo | **Media** | NOOA-08 | `nooa-framework` |
| **NOOA-19** | [Observabilidad] Tracing OpenInference/OpenTelemetry | Observabilidad | **Alta** | NOOA-12 | `nooa-framework` |
| **NOOA-20** | [Observabilidad] Scrubbing automático de secretos en trazas | Observabilidad | **Media** | NOOA-19 | `nooa-framework` |
| **NOOA-21** | [Observabilidad] Gestión de sesiones de trazas | Observabilidad | **Media** | NOOA-19 | `nooa-framework` |
| **NOOA-22** | [Interoperabilidad] Exportación ATIF (Agent Trajectory Format) | Interoperabilidad | **Media** | NOOA-19 | `nooa-framework` |
| **NOOA-23** | [Dev Tooling] Trace Viewer (FastAPI/React) | Dev Tooling | **Baja** | NOOA-21 | `cognito-backend` |
| **NOOA-24** | [Análisis] TraceExplorer: agente analizador de trazas | Análisis | **Baja** | NOOA-19 | `nooa-framework` |
| **NOOA-25** | [CLI] nooa-cli: comandos init, eject y autocompletado | CLI | **Media** | NOOA-01 | `nooa-framework` |
| **NOOA-26** | [Evaluación] eval_pipeline: evaluaciones batch YAML | Evaluación | **Media** | NOOA-12 | `nooa-framework` |
| **NOOA-27** | [Evaluación externa] Harbor Adapter: SWE-bench y Terminal-Bench | Evaluación externa | **Baja** | NOOA-26 | `cognito-worker` |
| **NOOA-28** | [Benchmarking] nooa-bench: BenchAgent y Runner concurrente | Benchmarking | **Baja** | NOOA-26 | `nooa-framework` |
| **NOOA-29** | [Calidad] Infraestructura de testing (QA) y pipeline CI/CD | Calidad | **Alta** | Ninguna | `nooa-framework` |
| **NOOA-30** | [Ejemplos] Tutoriales rápidos e implementación ARC-AGI-3 | Ejemplos | **Baja** | NOOA-13, NOOA-14 | `nooa-framework` |

---

## DETALLE TÉCNICO DE LOS TICKETS

### NOOA-01: [Configuración] Sistema de configuración por capas: ExecutionConfig, ModelConfig, StrategyConfig, TruncationConfig (resolución jerárquica)
- **Categoría**: Configuración
- **Prioridad**: Alta (Core)
- **Componente**: `nooa-framework`
- **Dependencias**: Ninguna
- **Descripción**:
  Diseñar e implementar un sistema unificado y jerárquico de configuración para el framework que permita combinar opciones globales, específicas del modelo, de la estrategia y parámetros de truncado de contexto. El sistema debe resolver la configuración con el siguiente orden de precedencia (cascada): Archivo de configuración local (nooa.json / pyproject.toml) -> Variables de Entorno -> Configuración por defecto de la aplicación.
- **Criterios de Aceptación**:
  - Definición de modelos Pydantic v2 para ExecutionConfig, ModelConfig, StrategyConfig y TruncationConfig.
  - Implementación de una clase ConfigurationManager que resuelva de manera jerárquica las configuraciones superpuestas.
  - Soporte para cargar la configuración desde un archivo nooa.json o sección [tool.nooa] de pyproject.toml.
  - Pruebas unitarias que verifiquen el orden de precedencia estricto de la resolución en cascada.

---

### NOOA-02: [LLM Integration] UnifiedLLM sobre litellm: interfaz multi-proveedor con registry de modelos/alias
- **Categoría**: LLM Integration
- **Prioridad**: Alta (Core)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-01
- **Descripción**:
  Implementar la interfaz centralizada UnifiedLLM que sirva como envoltorio genérico sobre la librería litellm. Debe proveer una API homogénea e interoperable para interactuar con múltiples proveedores de LLM (Ollama, OpenAI, Anthropic, etc.) y gestionar un registro (registry) global de modelos y alias simplificados.
- **Criterios de Aceptación**:
  - Clase UnifiedLLM con métodos asíncronos para generación simple y en streaming que exponga una interfaz consistente.
  - Soporte para un diccionario de alias que traduzca identificadores lógicos (p. ej., 'codex.local') a modelos específicos en el proveedor.
  - Cobertura de pruebas unitarias usando mocks para llamadas de múltiples proveedores.
  - Integración del Registry de modelos permitiendo añadir nuevos modelos dinámicamente.

---

### NOOA-03: [LLM Integration] Resiliencia: reintentos y gestión de configuración HTTP
- **Categoría**: LLM Integration
- **Prioridad**: Alta (Core)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-02
- **Descripción**:
  Añadir una capa robusta de resiliencia y tolerancia a fallos sobre la interfaz UnifiedLLM. Esto incluye políticas de reintento exponencial (exponential backoff) para errores de Rate Limiting (HTTP 429), errores temporales del servidor (HTTP 5xx), gestión de timeouts personalizados, y límites de concurrencia en llamadas salientes.
- **Criterios de Aceptación**:
  - Configuración de reintentos mediante la librería tenacity asociada a UnifiedLLM.
  - Manejo controlado de excepciones de red y timeouts, lanzando excepciones de dominio claras.
  - Configuración parametrizable de backoff exponencial, jitter y número máximo de intentos.
  - Pruebas que simulen fallos intermitentes de red para comprobar que la lógica de reintento se ejecuta correctamente.

---

### NOOA-04: [Paradigma Core] Contratos tipados: enforcement de salida estructurada vía anotaciones de tipo (incl. Pydantic)
- **Categoría**: Paradigma Core
- **Prioridad**: Alta (Core)
- **Componente**: `nooa-framework`
- **Dependencias**: Ninguna
- **Descripción**:
  Diseñar e implementar el motor de enforcement de tipos para salidas estructuradas. Al declarar tipos de retorno (incluyendo modelos Pydantic y tipos primitivos de Python) en los métodos de generación del agente, el framework debe garantizar que la salida del LLM se valide y se convierta al tipo especificado de manera estricta.
- **Criterios de Aceptación**:
  - Capacidad de extraer firmas de tipo de Python y convertirlas dinámicamente a esquemas JSON para inyectar en las llamadas de API de LLM.
  - Mecanismo de re-intento de parsing automático de JSON cuando la salida no cumple con el esquema definido.
  - Lanzamiento de errores estructurados de validación si el LLM falla persistentemente en cumplir con el contrato.
  - Pruebas unitarias con modelos de Pydantic complejos (incluyendo tipos anidados y opcionales).

---

### NOOA-05: [Testing LLM] Clientes fake/replay para pruebas deterministas sin costo de API
- **Categoría**: Testing LLM
- **Prioridad**: Alta (Soporte)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-02
- **Descripción**:
  Implementar un sistema de clientes 'Fake/Replay' para facilitar pruebas deterministas y reproducibles de agentes sin realizar llamadas reales a APIs de LLM. Debe permitir pre-registrar respuestas simuladas y grabar ejecuciones interactivas reales en archivos JSONL (replays) para su posterior reproducción.
- **Criterios de Aceptación**:
  - Implementación de FakeLLMClient que herede de la interfaz de UnifiedLLM.
  - Capacidad de cargar cassettes/archivos de replay para simular una secuencia exacta de interacciones LLM.
  - Modo de grabación que registre las respuestas reales en un archivo cuando esté habilitado.
  - Pruebas de integración de un mini-agente que use el cliente Fake y demuestre determinismo absoluto.

---

### NOOA-06: [Paradigma Core] Metaclase de detección de métodos de generación (`...`) vs métodos deterministas, con wrapping automático a ejecución LLM
- **Categoría**: Paradigma Core
- **Prioridad**: Alta (Core)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-02, NOOA-04
- **Descripción**:
  Crear la metaclase core de NOOA que inspeccione la clase del Agente al instanciarse. Debe distinguir entre métodos deterministas convencionales (con implementación en código) y métodos de generación especificados únicamente con el elipsis (`...`). Los métodos de generación deben ser envueltos (wrapped) automáticamente para transformarse en llamadas asíncronas de LLM.
- **Criterios de Aceptación**:
  - Metaclase NOOAMeta que herede de type.
  - Detección automática de métodos cuyo cuerpo es únicamente el elipsis (`...`) o un docstring sin código.
  - Generación automática del wrapper que recupera el contexto, instancia UnifiedLLM y procesa la solicitud del LLM en base a la firma y tipo de salida.
  - Pruebas unitarias de clases que implementan NOOAMeta demostrando la conversión exitosa de métodos elípticos a llamadas LLM estructuradas.

---

### NOOA-07: [Paradigma Core] Sistema de visibilidad selectiva (`@hidden`, convención `_private`) para controlar qué ve el LLM del entorno Python
- **Categoría**: Paradigma Core
- **Prioridad**: Alta (Core)
- **Componente**: `nooa-framework`
- **Dependencias**: Ninguna
- **Descripción**:
  Desarrollar un decorador @hidden y un sistema de filtros basados en convenciones de nomenclatura (como el prefijo de guión bajo `_`) para ocultar de manera selectiva métodos, atributos o propiedades de la clase del agente de la vista del LLM en los prompts y catálogos de herramientas.
- **Criterios de Aceptación**:
  - Implementación del decorador @hidden.
  - Implementación de un analizador de contexto que filtre los métodos y atributos del Agente, excluyendo aquellos decorados o que comiencen con guión bajo.
  - Pruebas de que los métodos privados u ocultos con @hidden no aparezcan en la interfaz de herramientas expuesta.

---

### NOOA-08: [Memoria corta] EventManager: registro secuencial de eventos como memoria de corto plazo
- **Categoría**: Memoria corta
- **Prioridad**: Alta (Core)
- **Componente**: `nooa-framework`
- **Dependencias**: Ninguna
- **Descripción**:
  Implementar el gestor secuencial de eventos EventManager para actuar como el registro cronológico del agente durante la ejecución de sus tareas. Este componente es el núcleo de la memoria de corto plazo, registrando trazas, llamadas a herramientas, pensamientos de LLM y observaciones del entorno en un log ordenado e inmutable.
- **Criterios de Aceptación**:
  - Clase EventManager que mantenga una lista secuencial de objetos de tipo Event.
  - Soporte para persistencia en memoria y persistencia opcional serializada en disco (JSONL ordenado por tiempo).
  - Métodos para consultar eventos recientes, filtrar por tipo de evento y resumir eventos pasados.
  - Cobertura de pruebas que garanticen la consistencia de los eventos ante inserciones concurrentes.

---

### NOOA-09: [Contexto] Sistema de ContextBlocks/DynamicContext: inyección de datos vivos en el prompt (XML/Markdown según proveedor)
- **Categoría**: Contexto
- **Prioridad**: Alta (Core)
- **Componente**: `nooa-framework`
- **Dependencias**: Ninguna
- **Descripción**:
  Desarrollar un sistema de inyección dinámica de datos vivos en el prompt conocido como ContextBlocks. Permite registrar funciones o fuentes de datos que se evalúan en caliente al enviar un prompt al LLM, formateando el resultado en XML o Markdown adaptado según los requisitos de cada proveedor de modelos.
- **Criterios de Aceptación**:
  - Clase ContextBlock y DynamicContextManager para definir e inyectar datos vivos.
  - Soporte de formateadores automáticos para XML (tipo <block name='sys_info'>...</block>) y Markdown estructurado.
  - Integración fluida que garantice la inyección en el prompt justo antes de la llamada de UnifiedLLM.
  - Pruebas de inyección dinámica simulando un cambio de contexto en caliente.

---

### NOOA-10: [Documentación dinámica] AgentDoc: generación automática de documentación de API a partir de firmas y docstrings para el contexto del LLM
- **Categoría**: Documentación dinámica
- **Prioridad**: Media (Soporte)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-07
- **Descripción**:
  Implementar el motor AgentDoc para generar dinámicamente documentación legible por máquinas y humanos a partir de las firmas, anotaciones de tipo y docstrings de los métodos expuestos de un Agente. Esta documentación se inyecta en el prompt del LLM para que este entienda su propio ecosistema de herramientas y métodos de generación.
- **Criterios de Aceptación**:
  - Clase AgentDocGenerator que use introspección de Python (módulo inspect) para analizar clases de agente.
  - Respeto absoluto a la visibilidad selectiva (no documentar elementos decorados con @hidden o privados).
  - Formateo de salida personalizable (Markdown, JSON Schema o texto plano estructurado).
  - Pruebas unitarias de inspección y aserciones de que el contenido coincide con el docstring real.

---

### NOOA-11: [Seguridad] SandboxedExecutor: aislamiento de ejecución en proceso worker, límites de recursos, timeouts, restricciones de filesystem (Landlock)
- **Categoría**: Seguridad
- **Prioridad**: Alta (Core)
- **Componente**: `cognito-worker`
- **Dependencias**: Ninguna
- **Descripción**:
  Desarrollar el entorno de ejecución seguro SandboxedExecutor para aislar código y scripts generados por el LLM. El aislamiento debe realizarse en un proceso worker dedicado, aplicando límites estrictos de CPU, consumo de memoria máxima, timeouts rígidos de ejecución, y restricciones de acceso al sistema de archivos mediante tecnologías como Landlock (en sistemas Linux que lo soporten) o entornos de contenedores locales ligeros.
- **Criterios de Aceptación**:
  - Clase SandboxedExecutor que ejecute comandos o scripts de Python en un entorno controlado y asilado.
  - Implementación de límites de recursos de hardware y timeouts.
  - Políticas restrictivas de lectura/escritura en el sistema de archivos (área de trabajo dedicada).
  - Pruebas unitarias de denegación de accesos prohibidos (intentar leer/escribir fuera de la carpeta designada).

---

### NOOA-12: [Runtime] ActorRuntime: orquestación del ciclo de vida de llamadas a métodos de generación (EventManager, ContextBlocks, loop LLM-sandbox, hooks `intercept()`)
- **Categoría**: Runtime
- **Prioridad**: Alta (Core)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-06, NOOA-08, NOOA-09
- **Descripción**:
  Implementar el orquestador central ActorRuntime responsable de manejar el ciclo de vida completo de un agente de NOOA. Debe coordinar el flujo de ejecución, evaluar bloques de contexto, registrar trazas en el EventManager, ejecutar las llamadas del LLM, invocar el sandbox y gestionar ganchos (hooks) de tipo intercept() para depuración y control en tiempo de ejecución.
- **Criterios de Aceptación**:
  - Clase ActorRuntime que reciba una clase de Agente e inicie su ciclo de vida.
  - Implementación del bucle principal de ejecución y llamadas a herramientas/métodos elípticos.
  - Registro de hooks intercept() ejecutables antes y después de cada llamada de LLM o herramienta.
  - Pruebas de integración simulando una ejecución interactiva completa con interceptores activos.

---

### NOOA-13: [Runtime] Estrategia Predict: generación estructurada en un solo turno
- **Categoría**: Runtime
- **Prioridad**: Alta (Core)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-12
- **Descripción**:
  Diseñar e implementar la estrategia de ejecución PredictStrategy, la cual realiza la resolución de una tarea mediante generación directa y estructurada en un único turno con el LLM. Es idónea para tareas deterministas que no requieren llamadas iterativas al sandbox o uso interactivo de herramientas.
- **Criterios de Aceptación**:
  - Clase PredictStrategy que herede de una interfaz base ExecutionStrategy.
  - Implementación del prompt de un solo turno y formateo estricto del JSON de salida que cumpla con el tipo de retorno esperado.
  - Control y formateo automático de errores si el modelo no puede responder estructuradamente.
  - Cobertura de pruebas unitarias que validen la rapidez y fiabilidad de respuestas estructuradas.

---

### NOOA-14: [Runtime] Estrategia CodeAct: REPL Python iterativo para que el LLM actúe escribiendo/ejecutando código
- **Categoría**: Runtime
- **Prioridad**: Alta (Core)
- **Componente**: `cognito-worker`
- **Dependencias**: NOOA-11, NOOA-12
- **Descripción**:
  Implementar la estrategia estrella CodeActStrategy. Esta estrategia habilita un bucle iterativo (REPL de Python) donde el LLM interactúa de forma activa escribiendo y ejecutando pequeños fragmentos de código o llamadas del sistema en el SandboxedExecutor, analizando los resultados secuencialmente en el EventManager hasta lograr el objetivo de la tarea.
- **Criterios de Aceptación**:
  - Clase CodeActStrategy interactiva y asíncrona.
  - Conexión nativa con un shell REPL persistente y aislado vía SandboxedExecutor.
  - Gestión del bucle de turnos: Generar código -> Ejecutar en Sandbox -> Leer salida/error -> Registrar en EventManager -> Iterar.
  - Pruebas unitarias que simulen la resolución interactiva de un cálculo matemático complejo que requiere iteración y uso del shell Python.

---

### NOOA-15: [Tools] Toolset incorporado: ShellTools (sesión bash persistente), TodoTools, herramientas de escritura de librerías/métodos, Web Publisher
- **Categoría**: Tools
- **Prioridad**: Media (Extensión)
- **Componente**: `cognito-worker`
- **Dependencias**: NOOA-11
- **Descripción**:
  Desarrollar el juego de herramientas (tools) básicas incorporadas en el framework. Esto incluye ShellTools para mantener sesiones de Bash persistentes, TodoTools para gestionar listas de tareas locales, herramientas avanzadas de escritura y edición de archivos de código en disco, y un WebPublisher para exportar reportes HTML simples.
- **Criterios de Aceptación**:
  - Módulo nooa.tools con la suite de herramientas estándar incorporada.
  - ShellTools con sesión de terminal persistente en segundo plano (manteniendo el estado del shell entre ejecuciones).
  - Herramientas de escritura de archivos con protecciones contra sobreescrituras accidentales de archivos protegidos.
  - Pruebas unitarias exhaustivas de cada herramienta simulando su uso interactivo.

---

### NOOA-16: [Skills] Sistema de Skills basado en `SKILL.md`: TextSkill, SkillRegistry, inyección de contexto curado sin bloatear la clase del agente
- **Categoría**: Skills
- **Prioridad**: Media (Extensión)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-09
- **Descripción**:
  Diseñar e implementar el sistema modular de 'Skills' que permita extender las habilidades del agente sin saturar la definición de la clase base con excesivos métodos. Basado en una definición de archivo descriptivo (p. ej., SKILL.md), permite empaquetar conjuntos curados de prompts, fragmentos de código y herramientas y registrarlos dinámicamente.
- **Criterios de Aceptación**:
  - Clases TextSkill, SkillRegistry y soporte de inyección dinámica.
  - Mecanismo para buscar e inyectar el contexto de la Skill seleccionada en el espacio de nombres de un agente al vuelo.
  - Soporte para cargar definiciones de Skills declaradas en un formato amigable Markdown/YAML.
  - Pruebas de registro, carga e inyección de una Skill específica.

---

### NOOA-17: [Integraciones externas] Soporte MCP (Model Context Protocol): wrapping automático de tools MCP, autenticación OAuth, ecosistema extensible
- **Categoría**: Integraciones externas
- **Prioridad**: Media (Extensión)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-12
- **Descripción**:
  Implementar soporte nativo para el protocolo estándar de la industria MCP (Model Context Protocol). El framework de NOOA debe ser capaz de conectarse a cualquier mcp-server compatible, descubrir herramientas dinámicamente y envolverlas automáticamente como herramientas nativas del agente, incluyendo soporte para flujos de autenticación OAuth si el servidor lo requiere.
- **Criterios de Aceptación**:
  - Cliente MCP asíncrono para negociar esquemas y capacidades con servidores MCP externos.
  - Wrapping automático de las herramientas expuestas por el servidor MCP en objetos de tipo AgentTool.
  - Gestión de flujos OAuth para servidores MCP que requieran autenticación de usuario.
  - Pruebas de integración conectando el framework a un mock de servidor MCP y llamando a una herramienta descubierta.

---

### NOOA-18: [Memoria largo plazo] nooa-memory: asociación espontánea de recuerdos, codificación dirigida por eventos, MemoryToolsMixin (recall/search/remember), backends SQLite + vectoriales
- **Categoría**: Memoria largo plazo
- **Prioridad**: Media (Extensión)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-08
- **Descripción**:
  Desarrollar el módulo de memoria persistente a largo plazo nooa-memory. Este componente debe admitir la codificación de recuerdos a partir de eventos clave de ejecución, indexación mediante embeddings vectoriales (usando un backend de Qdrant o bases vectoriales ligeras en SQLite) y proporcionar un mixin MemoryToolsMixin que dote a los agentes de capacidades cognitivas de tipo recall/search/remember en lenguaje natural.
- **Criterios de Aceptación**:
  - Implementación del módulo de base de datos e indexación vectorial (Soporte SQLite + SQLite-Vec o Qdrant).
  - Implementación de MemoryToolsMixin para inyectar los métodos cognitivos recall, search y remember en el agente.
  - Lógica de codificación y consolidación de memoria a partir del flujo de eventos del EventManager.
  - Pruebas unitarias que demuestren que un agente recuerda un hecho introducido en una sesión pasada.

---

### NOOA-19: [Observabilidad] Tracing basado en OpenInference/OpenTelemetry con exportadores múltiples (OTLP, Langfuse, Arize Phoenix)
- **Categoría**: Observabilidad
- **Prioridad**: Alta (Core)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-12
- **Descripción**:
  Diseñar e implementar el motor de instrumentación y trazabilidad (Tracing) nativo de NOOA. Debe basarse en el estándar OpenInference (extensión de OpenTelemetry para IA) para capturar de forma detallada llamadas a modelos, tiempos de latencia, inputs/outputs de herramientas y flujos de razonamiento, permitiendo configurar múltiples exportadores de trazas estándar.
- **Criterios de Aceptación**:
  - Auto-instrumentación de UnifiedLLM y ActorRuntime mediante especificaciones de OpenInference.
  - Configuración de exportadores para OTLP genérico, Langfuse y Arize Phoenix.
  - Garantía de rendimiento: la exportación de trazas no debe bloquear la ejecución del agente por latencias de red.
  - Pruebas que validen que se generan los spans correspondientes a una llamada del agente.

---

### NOOA-20: [Observabilidad] Scrubbing automático de secretos en las trazas
- **Categoría**: Observabilidad
- **Prioridad**: Media (Extensión)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-19
- **Descripción**:
  Implementar un componente de seguridad crítico de tipo Middleware o Filtro de Trazas que realice el scrubbing (limpieza y enmascaramiento) automático de secretos, tokens de API, contraseñas y datos sensibles presentes en las entradas, salidas y payloads de las trazas antes de ser enviadas a colectores externos.
- **Criterios de Aceptación**:
  - Filtro de exportador que escanee diccionarios y textos buscando patrones sensibles comunes.
  - Enmascaramiento de valores con la cadena estándar [REDACTED].
  - Integración transparente en la canalización de exportación de OpenTelemetry/OpenInference.
  - Pruebas que demuestren el correcto enmascaramiento de claves de API en las trazas generadas.

---

### NOOA-21: [Observabilidad] Gestión de sesiones de trazas
- **Categoría**: Observabilidad
- **Prioridad**: Media (Extensión)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-19
- **Descripción**:
  Añadir soporte para agrupar e identificar de manera lógica las trazas según sesiones de agente individuales y ejecuciones específicas de tareas. El framework debe inyectar de manera consistente el session_id y task_id en el contexto de propagación de OpenTelemetry (baggage/attributes) para permitir la correlación de trazas distribuidas.
- **Criterios de Aceptación**:
  - Propagación de contextos en el loop del agente asociando todas las trazas de una misma ejecución de tarea a un ID unificado de sesión.
  - Posibilidad de consultar y filtrar trazas locales en base al identificador de sesión.
  - Pruebas unitarias de propagación de contexto asíncrono comprobando que múltiples agentes concurrentes no mezclan sus IDs de trazas.

---

### NOOA-22: [Interoperabilidad] Exportación ATIF (Agent Trajectory Interchange Format v1.7) vía `install_atif()`/`atif_scope()`
- **Categoría**: Interoperabilidad
- **Prioridad**: Media (Extensión)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-19
- **Descripción**:
  Diseñar e implementar exportación de trayectorias de agentes compatibles con el estándar abierto ATIF v1.7. Debe permitir capturar de manera uniforme la trayectoria de razonamiento, acciones ejecutadas y observaciones recibidas del agente, facilitando exportaciones limpias para análisis, compartición de datos y depuración externa.
- **Criterios de Aceptación**:
  - Implementación de los helpers install_atif() y el gestor de contexto atif_scope().
  - Serialización completa de la trayectoria al formato JSON especificado por el estándar ATIF v1.7.
  - Pruebas unitarias que validen que las trayectorias resultantes de una tarea cumplen estrictamente con la especificación de esquema ATIF.

---

### NOOA-23: [Dev Tooling] Trace Viewer (FastAPI/React) lanzado vía `nooa start-dev`
- **Categoría**: Dev Tooling
- **Prioridad**: Baja (Soporte)
- **Componente**: `cognito-backend`
- **Dependencias**: NOOA-21
- **Descripción**:
  Implementar una interfaz web interactiva de desarrollo local denominada Trace Viewer. Consiste en una aplicación SPA en React con un servidor FastAPI de backend local que lee los logs de trazas y sesiones, proporcionando una visualización amigable de turnos de LLM, ejecuciones de código y timelines.
- **Criterios de Aceptación**:
  - Servidor API mínimo en FastAPI que sirva los endpoints de consulta de sesiones y trazas locales.
  - Interfaz web interactiva en React que renderice con claridad las llamadas, ejecuciones en sandbox y logs.
  - Comando CLI nooa start-dev para arrancar simultáneamente el backend FastAPI y levantar la interfaz de usuario.
  - Pruebas básicas del servidor FastAPI garantizando la correcta devolución de la lista de trazas en formato JSON.

---

### NOOA-24: [Análisis] TraceExplorer: agente para analizar trazas de otros agentes (debugging "agent-in-the-loop", regresiones automatizadas)
- **Categoría**: Análisis
- **Prioridad**: Baja (Soporte)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-19
- **Descripción**:
  Desarrollar TraceExplorer, un Agente especializado de NOOA diseñado para inspeccionar, analizar y depurar las trazas de ejecución generadas por otros agentes. Este enfoque "agent-in-the-loop" permite la identificación automática de bucles de error infinitos, ineficiencia en el uso de herramientas, regresiones de rendimiento y análisis post-mortem automatizado de fallas.
- **Criterios de Aceptación**:
  - Clase TraceExplorerAgent con prompts especializados para auditar trazas.
  - Herramientas nativas para cargar archivos ATIF o consultar trazas mediante la API de observabilidad.
  - Reporte final estructurado con análisis de causas raíz de fallos detectados en el agente auditado.
  - Pruebas unitarias donde TraceExplorer analice con éxito una traza sintética con fallos e identifique correctamente la causa.

---

### NOOA-25: [CLI] nooa-cli: comandos de entorno de desarrollo, ejection de configuración, shell completion
- **Categoría**: CLI
- **Prioridad**: Media (Soporte)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-01
- **Descripción**:
  Implementar la interfaz de comandos de consola del framework (nooa-cli). Debe proveer comandos interactivos para inicializar proyectos (nooa init), expulsar o exportar configuraciones avanzadas (nooa eject), levantar servidores locales de desarrollo y dar soporte completo para autocompletado en Bash, Zsh y PowerShell.
- **Criterios de Aceptación**:
  - Punto de entrada CLI nooa mediante la librería click o typer.
  - Comandos nooa init, nooa config eject y nooa dev.
  - Generación dinámica de scripts de autocompletado de comandos para las shells principales.
  - Pruebas de la CLI simulando la invocación de comandos y comprobando los códigos de salida (exit codes).

---

### NOOA-26: [Evaluación] eval_pipeline: evaluaciones batch YAML-driven, scorers (ExactMatchScorer y custom), salida `.noo-eval.jsonl`, concurrencia via subprocess workers
- **Categoría**: Evaluación
- **Prioridad**: Media (Soporte)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-12
- **Descripción**:
  Diseñar e implementar el framework de evaluación automatizada eval_pipeline. El motor debe permitir definir baterías de pruebas a agentes mediante archivos YAML, ejecutar las tareas de forma concurrente utilizando workers multiproceso independientes, evaluar los resultados con scoreres estándar (ExactMatch, heurísticas o basados en LLM), y exportar los reportes detallados en archivos append-only .noo-eval.jsonl.
- **Criterios de Aceptación**:
  - Parsing de archivos YAML que especifican sets de evaluación (input, expected outputs, scorers a usar).
  - Orquestación asíncrona concurrente con ProcessPoolExecutor o subprocess workers para aislar las ejecuciones evaluadas.
  - Implementación de ExactMatchScorer y una clase base flexible para scorers customizados de usuario.
  - Pruebas unitarias que ejecuten una suite de evaluación mínima y verifiquen el formato correcto de salida en .noo-eval.jsonl.

---

### NOOA-27: [Evaluación externa] Harbor Adapter: integración con SWE-bench Verified y Terminal-Bench 2.0 vía `harbor_adapter.py` y CLI `nemo-harbor`, ejecución en contenedores Docker/Apptainer
- **Categoría**: Evaluación externa
- **Prioridad**: Baja (Soporte)
- **Componente**: `cognito-worker`
- **Dependencias**: NOOA-26
- **Descripción**:
  Implementar el módulo Harbor Adapter para conectar los agentes desarrollados en NOOA directamente con benchmarks externos estándar y exigentes, específicamente SWE-bench Verified y Terminal-Bench 2.0. El adaptador debe envolver el entorno de estos benchmarks y lanzar contenedores Docker o Apptainer de manera transparente para aislar las pruebas de rendimiento complejas.
- **Criterios de Aceptación**:
  - Script y módulo harbor_adapter.py y pasarela para la CLI nemo-harbor.
  - Lógica para orquestar contenedores que sirvan el entorno aislado del SWE-bench / Terminal-Bench de forma automática.
  - Mapeo y traducción de los formatos de datasets externos a inputs nativos del agente de NOOA y viceversa.
  - Pruebas simuladas (mocking Docker) que comprueben la correcta generación de llamadas para arrancar un contenedor.

---

### NOOA-28: [Benchmarking] nooa-bench: BenchAgent y Runner para ejecución concurrente de tareas de benchmark
- **Categoría**: Benchmarking
- **Prioridad**: Baja (Soporte)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-26
- **Descripción**:
  Desarrollar la herramienta específica nooa-bench. Consta del agente especializado BenchAgent y un motor de ejecución concurrente Runner diseñado para estresar y medir el desempeño de modelos y estrategias de agentes en tareas concurrentes a gran escala, registrando latencia, consumo de tokens y tasa de éxito.
- **Criterios de Aceptación**:
  - Clase BenchAgent con métricas de rendimiento embebidas para medir throughput de tokens.
  - Motor Runner concurrente usando semáforos asíncronos para limitar el paralelismo de peticiones.
  - Generación automatizada de gráficos o resúmenes de rendimiento (consola / CSV) al completar un benchmark.
  - Pruebas de ejecución concurrente de múltiples agentes virtuales sin colisionar recursos.

---

### NOOA-29: [Calidad] Infraestructura de testing (unit/integration/stress) y pipeline CI/CD (test, build, frontend-build)
- **Categoría**: Calidad
- **Prioridad**: Alta (Soporte)
- **Componente**: `nooa-framework`
- **Dependencias**: Ninguna
- **Descripción**:
  Desarrollar toda la suite de infraestructura de pruebas automatizadas y aseguramiento de calidad (QA). Esto abarca la creación de configuraciones de pytest robustas (para pruebas unitarias, de integración y de estrés en paralelo) y los flujos de integración y entrega continuas (CI/CD) para compilar el framework, testearlo en múltiples versiones de Python, y construir los artefactos web del Trace Viewer.
- **Criterios de Aceptación**:
  - Configuración de pytest y organización de carpetas tests/unit, tests/integration, tests/stress.
  - Pipeline de GitHub Actions definido en YAML para automatizar las fases de testing (en Python 3.10, 3.11 y 3.12), empaquetado de librería y build de la SPA en React.
  - Pruebas de estrés que comprueben la resiliencia del framework bajo carga moderada de hilos y procesos.

---

### NOOA-30: [Ejemplos] Serie de tutoriales progresivos (quickstart) e implementación de referencia ARC-AGI-3
- **Categoría**: Ejemplos
- **Prioridad**: Baja (Soporte)
- **Componente**: `nooa-framework`
- **Dependencias**: NOOA-13, NOOA-14
- **Descripción**:
  Diseñar y programar los materiales didácticos y demostraciones prácticas de NOOA. Incluye guías rápidas de inicio paso a paso (quickstart) para cada paradigma del framework, junto a una implementación de producción de referencia para resolver tareas en el exigente benchmark ARC-AGI (versión 3) usando la combinación de agentes iterativos, REPL y herramientas complejas.
- **Criterios de Aceptación**:
  - Carpeta examples/ con código comentado y ejecutable de inicio rápido (Predict, CodeAct, memoria).
  - Implementación de Agente de referencia para resolver desafíos del set de datos ARC-AGI.
  - Documentación detallada en Markdown de la arquitectura de la solución ARC-AGI.
  - Scripts listos para correr y validar los tutoriales asegurando que no se rompen con nuevas versiones.
