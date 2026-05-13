# PLAN DE ACCIÓN PRIORIZADO - Auditoría Cognito-Stack
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/ACTION_PLAN.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/ACTION_PLAN.en.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/ACTION_PLAN.ca.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/ACTION_PLAN.zh-cn.md)


**Fecha:** 2024-07-25
**Analista:** Jules

## 1. Introducción

Este documento presenta un plan de acción priorizado para remediar los hallazgos de la auditoría técnica. El plan está estructurado en fases, abordando primero las vulnerabilidades más críticas para asegurar el proyecto y luego pasando a mejoras de robustez, mantenibilidad y observabilidad.

**Prioridades:**
*   **Fase 1: Remediación Crítica (Bloqueadores de Producción)** - Tareas que **deben** completarse antes de que el proyecto pueda ser considerado para cualquier despliegue en un entorno de producción.
*   **Fase 2: Hardening y Robustez** - Tareas que fortalecen la seguridad y la estabilidad del sistema.
*   **Fase 3: Calidad y Observabilidad** - Tareas que mejoran la mantenibilidad, el testing y la capacidad de monitorear el sistema.
*   **Fase 4: Mejoras Continuas** - Recomendaciones a largo plazo.

---

## 2. Plan de Acción Detallado

### FASE 1: Remediación Crítica (Bloqueadores de Producción)

*   **Objetivo:** Eliminar las vulnerabilidades más graves que exponen el sistema a riesgos inaceptables.
*   **Estimación de Esfuerzo:** 2-3 días de desarrollo.

| ID | Prioridad | Tarea | Estimación | Dependencias |
| :--- | :--- | :--- | :--- | :--- |
| **1.1** | **CRÍTICA** | **(S-n8n-01) Asegurar los Runners de n8n:** Modificar `n8n-task-runners.json` para deshabilitar el acceso a módulos de sistema peligrosos. | **2 horas** | - |
| **1.2** | **CRÍTICA** | **(A-01, A-02) Fortalecer la Configuración de Authelia:** Incrementar las iteraciones de `argon2id` a `3` y establecer la cookie de sesión como `secure: true`. | **1 horas** | Requiere reseteo de contraseñas de todos los usuarios. |
| **1.3** | **CRÍTICA** | **(DS-01) Eliminar `network_mode: host` de `fail2ban`:** Rediseñar la implementación de `fail2ban` para que se ejecute directamente en el host o de una manera que no rompa el aislamiento del contenedor. | **4 horas** | Requiere acceso al host. |
| **1.4** | **CRÍTICA** | **(DS-02) Ocultar Secretos en Logs de Matrix:** Modificar el entrypoint de `Dockerfile.matrix` para que los secretos se guarden en un archivo en lugar de imprimirse. | **2 horas** | - |
| **1.5** | **CRÍTICA** | **(VG-01) Añadir Validación de Tamaño de Archivo en Voice Gateway:** Implementar un límite de tamaño para la subida de archivos de audio para prevenir DoS. | **3 horas** | - |
| **1.6** | **CRÍTICA** | **(CPL-01, DOC-01) Actualizar la Documentación Pública:** Eliminar las afirmaciones de "listo para producción" del `README.md` y añadir una advertencia de seguridad. | **1 horas** | - |

---

### FASE 2: Hardening y Robustez

*   **Objetivo:** Mejorar la defensa en profundidad, la estabilidad y la reproducibilidad del sistema.
*   **Estimación de Esfuerzo:** 3-5 días de desarrollo.

| ID | Prioridad | Tarea | Estimación | Dependencias |
| :--- | :--- | :--- | :--- | :--- |
| **2.1** | **ALTA** | **(C-01) Unificar la Gestión de Secretos:** Migrar todos los secretos (Postgres, Redis, etc.) para que se gestionen exclusivamente a través de Docker Secrets. | **1 día** | - |
| **2.2** | **ALTA** | **(D-01, DEP-01, DEP-03) Fijar Todas las Dependencias:** Reemplazar `:latest` en `docker-compose.yml`, fijar versiones en todos los `requirements.txt` y eliminar el uso de dependencias "nightly". | **1 día** | - |
| **2.3** | **ALTA** | **(DS-03) Ejecutar Contenedores como No-Root:** Refactorizar los Dockerfiles de `ollama`, `whisper-stt` y otros para que se ejecuten con un usuario no privilegiado. | **1 día** | - |
| **2.4** | **ALTA** | **(RP-01) Implementar Headers de Seguridad en Nginx:** Añadir HSTS, CSP, X-Frame-Options y otros headers para fortalecer el reverse proxy. | **4 horas** | - |
| **2.5** | **ALTA** | **(D-02) Establecer Límites de Recursos:** Definir `limits` de CPU y memoria para todos los servicios críticos en `docker-compose.yml`. | **4 horas** | Requiere pruebas de carga para un ajuste fino. |
| **2.6** | **ALTA** | **(V-01, V-02) Implementar y Documentar Backups/Restauración:** Automatizar la configuración de Duplicati y crear el documento `DISASTER_RECOVERY.md`. | **1 día** | - |

---

### FASE 3: Calidad y Observabilidad

*   **Objetivo:** Implementar una estrategia de testing real y mejorar la visibilidad del estado del sistema.
*   **Estimación de Esfuerzo:** 5-7 días de desarrollo.

| ID | Prioridad | Tarea | Estimación | Dependencias |
| :--- | :--- | :--- | :--- | :--- |
| **3.1** | **ALTA** | **(T-02) Hacer que el CI/CD sea Bloqueante:** Eliminar `continue-on-error: true` del workflow de validación para hacer cumplir los estándares de calidad. | **2 horas** | - |
| **3.2** | **ALTA** | **(T-01) Implementar una Suite de Pruebas Automatizadas (`pytest`):** Traducir los notebooks de prueba existentes a un formato `pytest` y añadir pruebas unitarias básicas para los componentes clave. | **3-4 días** | Fase 2 completada. |
| **3.3** | **ALTA** | **(M-01) Implementar un Sistema de Alertas:** Integrar `Alertmanager` y definir reglas de alerta para los fallos más críticos (servicios caídos, disco lleno). | **1 día** | - |
| **3.4** | **MEDIA** | **(M-02) Implementar Logging Centralizado:** Añadir `Loki` y `Promtail` al stack para agregar los logs de todos los contenedores. | **1 día** | - |
| **3.5** | **MEDIA** | **(M-03) Añadir Dashboards de Monitoreo del Sistema:** Añadir dashboards de Grafana para `node-exporter` y `cadvisor`. | **4 horas** | - |

---

### FASE 4: Mejoras Continuas

*   **Objetivo:** Refinar y mejorar continuamente la seguridad, el rendimiento y la mantenibilidad.
*   **Estimación de Esfuerzo:** Continuo.

| ID | Prioridad | Tarea | Estimación | Dependencias |
| :--- | :--- | :--- | :--- | :--- |
| **4.1** | **MEDIA** | **(S-ollama-01) Fortalecer el `ollama-proxy`:** Añadir rate limiting y logging. | **4 horas** | - |
| **4.2** | **MEDIA** | **(D-04) Optimizar Imágenes Docker:** Implementar builds multi-etapa en los Dockerfiles personalizados para reducir su tamaño y superficie de ataque. | **1 día** | - |
| **4.3** | **MEDIA** | **(RP-03) Implementar Rate Limiting en Nginx:** Añadir `limit_req_zone` para proteger contra ataques de fuerza bruta y DoS a nivel de proxy. | **3 horas** | - |
| **4.4** | **BAJA** | **(DOC-02) Centralizar la Documentación:** Refactorizar la documentación en un directorio `/docs` unificado. | **1 día** | - |
| **4.5** | **BAJA** | **(CPL-01) Expandir la Cobertura de Pruebas:** Continuar implementando el plan de testing definido en el `DESIGN_TRUTH_CONTRACT.md`. | **Continuo** | - |
