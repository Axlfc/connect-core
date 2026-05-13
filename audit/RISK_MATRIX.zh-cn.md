# MATRIZ DE RIESGOS - Auditoría Cognito-Stack
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/RISK_MATRIX.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/RISK_MATRIX.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/RISK_MATRIX.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/cognito-stack/blob/master/audit/RISK_MATRIX.ca.md)


**Fecha:** 2024-07-25
**Analista:** Jules

## 1. Introducción

Esta matriz consolida los hallazgos de la auditoría técnica completa del proyecto `cognito-stack`. Cada entrada representa un riesgo identificado, evaluado en términos de su **Severidad** (el nivel de peligrosidad intrínseco del problema) y su **Impacto** (el efecto adverso que podría tener en el proyecto en un entorno de producción). Se proponen mitigaciones para cada riesgo.

**Niveles de Severidad:**
*   **CRÍTICO:** Vulnerabilidad grave que puede llevar a un compromiso del sistema, exposición de datos o denegación de servicio. Debe ser solucionado antes de cualquier despliegue.
*   **ALTO:** Defecto de seguridad o de diseño significativo que crea un riesgo sustancial para la estabilidad, seguridad o mantenibilidad del sistema.
*   **MEDIO:** Mala práctica o debilidad que no es directamente explotable pero que aumenta la superficie de ataque, degrada el rendimiento o dificulta el mantenimiento.
*   **BAJO:** Problema menor o recomendación de mejora que no representa un riesgo inmediato.

---

## 2. Matriz de Riesgos

| ID | Área Auditada | Severidad | Riesgo Identificado | Impacto Potencial | Mitigación Sugerida |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DS-01** | **Seguridad Docker** | **CRÍTICO** | `fail2ban` se ejecuta con `network_mode: host`. | Compromiso de la red del host; bypass del aislamiento de contenedores. | Ejecutar `fail2ban` directamente en el host o rediseñar su despliegue en contenedor sin `network_mode: host`. |
| **S-n8n-01**| **Seguridad de 服务s** | **CRÍTICO** | Sandboxing deshabilitado en los runners de n8n (`allow: "*"`). | **Ejecución Remota de Código (RCE)** por cualquier usuario de n8n; compromiso total del contenedor del runner y acceso a la red interna. | Implementar una "deny-list" estricta para módulos peligrosos (`fs`, `child_process`, `os`) en `n8n-task-runners.json`. |
| **A-01** | **Authelia** | **CRÍTICO** | Hashing de contraseñas débil (`iterations: 1`). | Cracking offline de contraseñas a alta velocidad si la base de datos de usuarios es comprometida. | Incrementar las iteraciones de `argon2id` a un valor seguro (ej. `3`) y forzar el reseteo de todas las contraseñas. |
| **A-02** | **Authelia** | **CRÍTICO** | Cookie de sesión insegura (`secure: false`). | Secuestro de sesión (Session Hijacking) si la conexión es degradada a HTTP. | Establecer `secure: true` para la cookie de sesión en `authelia/configuration.yml`. |
| **DS-02** | **Seguridad Docker** | **CRÍTICO** | El entrypoint del contenedor de `matrix-synapse` expone secretos en los logs. | Exposición de secretos de servidor (macaroon key, etc.) a cualquiera con acceso a los logs de Docker. | Modificar el entrypoint para que escriba los secretos en un archivo con permisos restringidos en lugar de en `stdout`. |
| **DEP-01** | **Dependencias** | **CRÍTICO** | Dependencias de Python no fijadas en `requirements.txt`. | Builds no reproducibles; riesgo de introducir vulnerabilidades o cambios disruptivos automáticamente. | Utilizar `pip-tools` para generar un `requirements.txt` con versiones y hashes fijados. |
| **C-01** | **Configuración** | **ALTO** | 使用 de variables de entorno para secretos críticos (Postgres, Redis). | Exposición de credenciales a través de `docker inspect`, logs o herramientas de monitoreo. | Migrar todos los secretos para que se gestionen exclusivamente a través de Docker Secrets (usando `_FILE` convention). |
| **RP-01** | **Reverse Proxy** | **ALTO** | Ausencia de headers de seguridad (HSTS, CSP, X-Frame-Options). | Vulnerabilidad a ataques de Clickjacking, XSS, y `sslstrip`. | Añadir una configuración global en Nginx para inyectar estos headers en todas las respuestas. |
| **D-01** | **Docker** | **ALTO** | 使用 generalizado de la etiqueta `:latest` para las imágenes. | Inestabilidad y builds no reproducibles; introduce riesgos de seguridad sin control de versiones. | Reemplazar todas las instancias de `:latest` con etiquetas de versión específicas y estables. |
| **DS-03** | **Seguridad Docker** | **ALTO** | Ejecución como `root` en contenedores clave (Ollama, Whisper). | Una vulnerabilidad de RCE en la aplicación escala inmediatamente a `root` dentro del contenedor. | Refactorizar los Dockerfiles para crear y usar un usuario no privilegiado (`USER appuser`). |
| **DS-04** | **Seguridad Docker** | **ALTO** | 使用 de la capacidad `DAC_OVERRIDE` en servicios de base de datos. | Permite eludir los permisos del sistema de archivos, aumentando el riesgo en caso de compromiso del contenedor. | Solucionar los problemas de permisos de volúmenes en el host (`setup-permissions.sh`) y eliminar esta capacidad. |
| **M-01** | **Monitoreo** | **ALTO** | Ausencia total de un sistema de alertas. | Incapacidad de detectar proactivamente fallos de servicio o problemas de recursos, dependiendo de reportes de usuarios. | Integrar `Alertmanager` en el stack y definir reglas de alerta para condiciones críticas. |
| **V-01** | **Volúmenes** | **ALTO** | Proceso de backup completamente manual y no implementado. | Alto riesgo de pérdida de datos. Sin una estrategia de backup automatizada, es probable que no se realicen backups de forma consistente. | Automatizar la configuración del trabajo de Duplicati a través de un script de inicialización. |
| **V-02** | **Volúmenes** | **ALTO** | Ausencia de un plan de recuperación de desastres. | Tiempo de recuperación (RTO) muy alto y riesgo de errores en la restauración en caso de un fallo catastrófico del host. | Crear un documento `DISASTER_RECOVERY.md` con un procedimiento paso a paso y probarlo. |
| **T-01** | **Testing** | **ALTO** | Ausencia total de tests automatizados. | Riesgo extremadamente alto de regresiones; imposibilidad de verificar la corrección del sistema sin una validación manual completa. | Implementar una estrategia de testing con `pytest`, cubriendo pruebas unitarias, de integración y E2E. |
| **T-02** | **Testing** | **ALTO** | El pipeline de CI/CD no es bloqueante (`continue-on-error: true`). | El CI da una falsa sensación de éxito, permitiendo que código de baja calidad o con errores de linting se fusione en el repositorio. | Eliminar `continue-on-error: true` de los pasos de validación en los workflows de GitHub Actions. |
| **S-ollama-01**| **Seguridad de 服务s** | **ALTO** | El `ollama-proxy` no tiene ninguna capa de seguridad. | Si Authelia es bypassado, no hay una segunda línea de defensa contra el abuso de recursos de la IA. | Añadir rate limiting y logging de peticiones al proxy. |
| **M-02** | **Monitoreo** | **ALTO** | Falta de agregación centralizada de logs. | Dificultad extrema para investigar incidentes y correlacionar eventos entre múltiples servicios. | Integrar `Loki` y `Promtail` en el stack para la centralización de logs. |
| **VG-01**| **Voice Gateway**| **CRÍTICO**| Subida de archivos de audio sin límite de tamaño.| Denegación de 服务 (DoS) por agotamiento de memoria al subir un archivo maliciosamente grande.| Implementar una validación del tamaño del archivo antes de leerlo en memoria. |
| **DEP-03**| **Dependencias**| **ALTO**| 使用 de dependencias "nightly" en `Dockerfile.comfyui`.| Riesgo de inestabilidad y vulnerabilidades no parcheadas en un componente clave.| Usar la última versión estable de PyTorch y fijar su versión. |
| **CPL-01**| **Compliance**| **CRÍTICO**| Incumplimiento del `DESIGN_TRUTH_CONTRACT`.| El proyecto no cumple con sus propios estándares de calidad y testing, haciéndolo no apto para producción según sus propias reglas.| Implementar las pruebas críticas definidas en el roadmap. |
