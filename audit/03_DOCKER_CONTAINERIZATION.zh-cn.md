# AUDIT 03: ANÁLISIS DE DOCKER Y CONTAINERIZACIÓN
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/03_DOCKER_CONTAINERIZATION.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/03_DOCKER_CONTAINERIZATION.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/03_DOCKER_CONTAINERIZATION.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/03_DOCKER_CONTAINERIZATION.ca.md)


**Fecha:** 2024-07-25
**Analista:** Jules

## 1. Resumen de Hallazgos

| Estado | Área | Resumen de Hallazgos |
| :--- | :--- | :--- |
| ✓ | **Orquestación** | El archivo `docker-compose.yml` está **bien estructurado**, utilizando anclas de YAML, perfiles y redes segmentadas de manera efectiva. Demuestra un diseño de arquitectura sólido. |
| ✓ | **Healthchecks** | La mayoría de los servicios críticos implementan `healthchecks`, una práctica excelente que asegura un orden de inicio correcto y mejora la resiliencia del stack. |
| ⚠️ | **Optimización de Imágenes** | Los Dockerfiles personalizados son funcionales pero **carecen de optimizaciones clave**. No utilizan builds multi-etapa, lo que resulta en imágenes más grandes de lo necesario que contienen herramientas de compilación no requeridas en tiempo de ejecución. |
| ✗ | **Dependencias No Fijadas** | El uso generalizado de la etiqueta `:latest` en `docker-compose.yml` y en los Dockerfiles es un **riesgo crítico para la estabilidad y la seguridad**. Esto conduce a builds no reproducibles y a la introducción inesperada de cambios disruptivos. |
| ✗ | **Falta de Límites de Recursos** | La gran mayoría de los servicios no tienen límites de CPU o memoria definidos en la sección `deploy.resources`. Esto crea un riesgo de que un solo servicio consuma todos los recursos del host, provocando una denegación de servicio para todo el stack. |
| ✗ | **Inconsistencias y Malas Prácticas** | Se observan varias malas prácticas, como la instalación de dependencias con `apt-get` sin limpiar la caché, y la clonación de repositorios `git` desde ramas `master` en lugar de etiquetas o commits específicos. |

---

## 2. Hallazgos Detallados

### ✓ Lo que está bien

1.  **Estructura de `docker-compose.yml`:**
    *   El uso de anclas de YAML (ej. `x-ollama: &service-ollama`) para definir servicios base es excelente para la mantenibilidad y reduce la duplicación de código.
    *   La segmentación de la red en `frontend`, `backend`, `ai` y `monitoring` (con las últimas tres marcadas como `internal: true`) es una implementación de seguridad de red de libro de texto, aislando efectivamente los servicios.
    *   El uso de perfiles (`cpu`, `gpu-nvidia`, `monitoring`, etc.) permite un control granular sobre qué servicios se inician, adaptando el stack a diferentes entornos de hardware.

2.  **Definición de Healthchecks:**
    *   服务s como `postgres`, `redis`, `n8n`, y `authelia` tienen `healthchecks` bien definidos. Esto es crucial para la directiva `depends_on.condition: service_healthy`, que previene que los servicios dependientes se inicien antes de que sus dependencias estén listas.

3.  **Manejo de Volúmenes:**
    *   La estrategia de volúmenes es clara, utilizando volúmenes nombrados de Docker para la persistencia de datos (ej. `postgres_storage`) y montajes de tipo `bind` para la configuración (ej. `./authelia:/config`), lo cual es una práctica estándar y robusta.

### ✗ Problemas Encontrados

| ID | Severidad | Problema | Impacto |
| :- | :--- | :--- | :--- |
| **D-01** | **CRÍTICO** | **使用 de la etiqueta `:latest`** | Múltiples servicios (`qdrant`, `ollama`, `authelia`, `libretranslate`, `languagetool`, etc.) y Dockerfiles (`Dockerfile.comfyui`) usan `:latest`. Esto rompe la reproducibilidad de los builds. Una actualización en la imagen remota puede romper la aplicación sin previo aviso o introducir una vulnerabilidad. |
| **D-02** | **ALTO** | **Ausencia de Límites de Recursos** | La mayoría de los servicios no tienen una sección `deploy.resources` con `limits`. Un proceso con fugas de memoria o un pico de CPU en un servicio (ej. `ollama` procesando una solicitud compleja) podría derribar todo el servidor host. |
| **D-03** | **ALTO** | **Builds No Reproducibles en Dockerfiles** | `Dockerfile.comfyui` instala dependencias de PyTorch desde una URL `nightly` y clona repositorios de git desde la rama `master`. Esto significa que construir la misma imagen en dos momentos diferentes puede resultar en dos imágenes completamente diferentes, con distintas versiones y funcionalidades. |
| **D-04** | **MEDIO** | **Imágenes Infladas (Bloated Images)** | Dockerfiles como `Dockerfile.runners` instalan paquetes de compilación (`gcc`, `g++`, `build-base`) pero no los eliminan. Esto aumenta innecesariamente el tamaño de la imagen final y, por lo tanto, la superficie de ataque. |
| **D-05** | **MEDIO** | **Falta de Limpieza de Caché de APT** | En varios Dockerfiles, se ejecutan comandos `apt-get install` sin `&& rm -rf /var/lib/apt/lists/*` en la misma capa `RUN`. Esto deja datos de caché innecesarios en una capa de la imagen, aumentando su tamaño. |

### ⚠️ Warnings/Recomendaciones

1.  **Versionado de la Configuración de Compose:**
    *   El `docker-compose.yml` es de versión "3.8". Aunque es funcional, considerar actualizar a la especificación más reciente de `compose` para aprovechar nuevas características en el futuro.

2.  **Claridad en los 端口s Expuestos:**
    *   Algunos servicios exponen puertos solo a `127.0.0.1` (ej. `postgres`), lo cual es una buena práctica de seguridad. Sin embargo, otros los exponen a `0.0.0.0` (ej. `whisper-stt`). Se recomienda añadir comentarios que justifiquen por qué un puerto necesita estar abierto a todas las interfaces para evitar confusiones.

### 🔧 Soluciones Sugeridas

1.  **Para D-01 (Fijar Versiones - CRÍTICO):**
    *   **解决方案:** Realizar una auditoría de cada servicio que usa `:latest` y reemplazarlo con una etiqueta de versión específica y estable.
        ```diff
        --- a/docker-compose.yml
        +++ b/docker-compose.yml
        @@ -201,7 +201,7 @@
         # QDRANT - Vector Database
         # ========================================
         qdrant:
        -  image: qdrant/qdrant:latest
        +  image: qdrant/qdrant:v1.9.0  # O la versión estable más reciente
           hostname: qdrant
           container_name: qdrant
           networks:
        ```

2.  **Para D-02 (Añadir Límites de Recursos):**
    *   **解决方案:** Añadir una sección `deploy.resources` a cada servicio, definiendo `limits` y `reservations` razonables. Estos valores deben ajustarse en función de pruebas de carga, pero un punto de partida es esencial.
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

3.  **Para D-03 (Builds Reproducibles):**
    *   **解决方案 para `Dockerfile.comfyui`:**
        *   Fijar la versión de la imagen base (`ghcr.io/ai-dock/comfyui:v1.2.3`).
        *   Descargar las dependencias de PyTorch, verificar sus checksums (SHA256), y luego instalarlas.
        *   Al clonar repositorios de `git`, usar `git clone --branch v1.0.0` o `git checkout <commit-hash>` en lugar de clonar desde `master`.

4.  **Para D-04 y D-05 (Optimizar Imágenes):**
    *   **解决方案:** Utilizar builds multi-etapa y combinar comandos `RUN` para reducir el número de capas y limpiar artefactos de compilación.
        ```dockerfile
        # Ejemplo para Dockerfile.runners

        # Etapa 1: Build
        FROM n8nio/runners:1.121.0 as builder
        USER root
        RUN apk add --no-cache gcc g++ musl-dev python3-dev build-base
        RUN python3 -m venv /home/runner/custom-venv
        # ... instalar todas las dependencias con pip ...

        # Etapa 2: Final
        FROM n8nio/runners:1.121.0
        USER root
        # Copiar solo el venv de la etapa de build
        COPY --from=builder /home/runner/custom-venv /home/runner/custom-venv
        COPY n8n-task-runners.json /etc/n8n-task-runners.json
        # Asegurar permisos y cambiar de usuario
        RUN chown -R runner:runner /home/runner/custom-venv
        USER runner
        ENV PATH="/home/runner/custom-venv/bin:$PATH"
        ```
