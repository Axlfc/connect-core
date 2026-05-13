# AUDIT 13: DEPENDENCIAS Y LIBRERIAS
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/13_DEPENDENCIES_AND_LIBRARIES.zh-cn.md)


**Fecha:** 2024-07-25
**Analista:** Jules

## 1. Resumen de Hallazgos

| Estado | Área | Resumen de Hallazgos |
| :--- | :--- | :--- |
| ✓ | **Usage de Herramientas Estándar** | El proyecto utiliza manejadores de paquetes estándar de la industria (`pip` para Python, `npm`/`pnpm` para Node.js), lo que facilita la gestión y auditoría de las dependencias. |
| ✗ | **Dependencias No Fijadas (Unpinned)** | **CRÍTICO:** Múltiples archivos `requirements.txt` y Dockerfiles **no fijan las versiones** de las dependencias que instalan. Esto conduce a builds no reproducibles y crea un riesgo significativo de que una nueva versión de una librería introduzca una vulnerabilidad o un cambio disruptivo. |
| ✗ | **Falta de Escaneo de Vulnerabilidades** | No hay evidencia de que se utilice ninguna herramienta para escanear las dependencias (ej. `pip-audit`, `npm audit`, `snyk`, `trivy`) en busca de vulnerabilidades conocidas (CVEs). |
| ⚠️ | **Usage de Dependencias "Nightly"** | El `Dockerfile.comfyui` instala versiones "nightly" de PyTorch. Estas versiones son inestables por definición, no están pensadas para producción, y pueden contener bugs o vulnerabilidades no descubiertas. |
| ⚠️ | **Falta de `package-lock.json`** | El servicio `ollama-proxy` (Node.js) no incluye un archivo `package-lock.json` en el repositorio. Esto significa que las versiones exactas de las dependencias transitivas no están garantizadas, socavando la reproducibilidad. |

---

## 2. Hallazgos Detallados

### ✓ Lo que está bien

1.  **Gestión Centralizada:**
    *   Cada componente (ej. `voice-gateway`, `ollama-proxy`) tiene su propio archivo de dependencias (`requirements.txt`, `package.json`), lo cual es una buena práctica que aísla los entornos.

### ✗ Problemas Encontrados

| ID | Severidad | Problema | Impacto |
| :- | :--- | :--- | :--- |
| **DEP-01** | **CRÍTICO** | **Versiones No Fijadas en `requirements.txt`** | El archivo `voice-gateway/requirements.txt` lista dependencias como `fastapi` o `redis` sin especificar una versión. `pip install -r requirements.txt` instalará la última versión disponible en ese momento, lo que puede variar día a día, haciendo imposible garantizar un build estable y seguro. |
| **DEP-02** | **ALTO** | **Usage de Versionado Flexible (`^`) en `package.json`** | El `ollama-proxy/package.json` utiliza `^` para sus dependencias (ej. `"express": "^4.18.2"`). Aunque esto previene cambios mayores (versión 5.x), sigue permitiendo actualizaciones menores (ej. 4.19.0) que podrían introducir regresiones o vulnerabilidades. La ausencia de un `package-lock.json` agrava este problema. |
| **DEP-03** | **ALTO** | **Dependencias "Nightly" en `Dockerfile.comfyui`** | El Dockerfile instala PyTorch directamente desde un índice de `nightly`. Esto es inaceptable para un entorno de producción, ya que estas builds no tienen ninguna garantía de estabilidad o seguridad. |

### ⚠️ Warnings/Recomendaciones

1.  **Auditoría de Licenses:**
    *   No hay un proceso para auditar las licencias de las dependencias. Esto podría suponer un riesgo legal si una librería con una licencia restrictiva (como AGPL) se utilizara sin cumplir con sus términos.

2.  **Dependencias del Sistema Operativo:**
    *   Los Dockerfiles instalan dependencias del SO a través de `apt-get` o `apk`. Estas dependencias también deberían ser auditadas y, si es posible, fijadas a una versión específica si el manejador de paquetes lo permite.

### 🔧 Soluciones Sugeridas

1.  **Para DEP-01 (Fijar Versiones en `requirements.txt` - CRÍTICO):**
    *   **Solution:** Utilizar una herramienta como `pip-tools` para gestionar las dependencias de Python de forma robusta.
        1.  **Crear un archivo `requirements.in`:**
            ```
            # voice-gateway/requirements.in
            fastapi
            uvicorn
            httpx
            redis
            python-multipart
            ```
        2.  **Generar `requirements.txt`:**
            ```bash
            # Instalar pip-tools
            pip install pip-tools
            # Compilar el archivo de requerimientos
            pip-compile voice-gateway/requirements.in > voice-gateway/requirements.txt
            ```
        3.  **Resultado:** El `requirements.txt` generado contendrá las versiones exactas de todas las dependencias y sus dependencias transitivas, con hashes para verificar la integridad.
            ```
            # via -r requirements.in
            fastapi==0.109.2
            # ... (todas las demás dependencias con versiones exactas y hashes)
            ```

2.  **Para DEP-02 (Fijar Versiones en `package.json`):**
    *   **Solution:**
        1.  **Eliminar los `^`:** Reemplazar `^x.y.z` con `x.y.z` para todas las dependencias en `package.json`.
        2.  **Generar y Commitear el Lock File:** Ejecutar `npm install` localmente y añadir el archivo `package-lock.json` resultante al repositorio. Esto garantizará que siempre se instalen las mismas versiones exactas de todas las dependencias.

3.  **Para DEP-03 (Eliminar Dependencias "Nightly"):**
    *   **Solution:** Modificar `Dockerfile.comfyui` para que utilice la última **versión estable** de PyTorch que sea compatible con el hardware de destino.
        ```diff
        # En Dockerfile.comfyui
        -      --index-url https://download.pytorch.org/whl/nightly/cu128
        +      --index-url https://download.pytorch.org/whl/cu128
        ```
    *   Fijar la versión de PyTorch a un número específico es aún mejor.

4.  **Implementar Escaneo de Vulnerabilidades:**
    *   **Solution:** Integrar herramientas de escaneo en el proceso de CI/CD.
        *   **Para Python:** Añadir un paso que ejecute `pip-audit`.
        *   **Para Node.js:** Añadir un paso que ejecute `npm audit --audit-level=high`.
        *   **Para Imágenes Docker:** Utilizar una herramienta como `Trivy` o `Grype` para escanear las imágenes construidas en busca de vulnerabilidades tanto en las dependencias del SO como en las de la aplicación.
