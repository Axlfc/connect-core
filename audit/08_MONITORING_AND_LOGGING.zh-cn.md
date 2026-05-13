# AUDIT 08: MONITOREO, LOGGING Y OBSERVABILIDAD
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/audit/08_MONITORING_AND_LOGGING.ca.md)


**Fecha:** 2024-07-25
**Analista:** Jules

## 1. Resumen de Hallazgos

| Estado | Área | Resumen de Hallazgos |
| :--- | :--- | :--- |
| ✓ | **Recolección de Métricas** | El stack de Prometheus está **bien configurado** para recolectar métricas clave de la infraestructura, incluyendo métricas del host (`node-exporter`), de los contenedores (`cadvisor`), y métricas especializadas de GPU (`nvidia-dcgm-exporter`). |
| ✓ | **Provisioning de Grafana** | El enfoque de GitOps para la configuración de Grafana es **excelente**. Tanto la fuente de datos de Prometheus como los dashboards se provisionan automáticamente, lo que asegura consistencia y reproducibilidad. |
| ⚠️ | **Visibilidad Limitada** | Los dashboards existentes se centran casi exclusivamente en métricas de los servicios de IA (Ollama, GPU). **Faltan dashboards cruciales** para la salud general del sistema y de los contenedores, lo que crea puntos ciegos importantes. |
| ✗ | **Sin Sistema de Alertas** | La configuración de Prometheus **carece por completo de una sección de `alerting` y de `rule_files`**. Esto significa que el sistema no puede notificar proactivamente a los operadores sobre fallos de servicio, agotamiento de recursos o comportamiento anómalo. El monitoreo es puramente pasivo. |
| ✗ | **Logging No Centralizado** | No existe un sistema de agregación de logs (como el stack ELK/Loki). Los logs se escriben en archivos dentro de volúmenes de Docker o en la salida estándar (`stdout`). Esto hace que la correlación de eventos entre diferentes servicios sea **extremadamente difícil y lenta**, especialmente durante la investigación de un incidente. |
| ✗ | **Acceso Inseguro a Logs** | No hay un mecanismo centralizado y securizado para acceder a los logs. Para revisar los logs, un operador necesitaría acceso directo al sistema de archivos del host de Docker, lo cual es una mala práctica de seguridad que viola el principio de mínimo privilegio. |

---

## 2. Hallazgos Detallados

### ✓ Lo que está bien

1.  **Base de Métricas Sólida:**
    *   La configuración de `prometheus.yml` es robusta. Incluye `scrape_configs` para `node-exporter` (métricas del host), `cadvisor` (métricas de contenedores), `nvidia-dcgm-exporter` (métricas de GPU), y el `blackbox-exporter` para health checks de endpoints de aplicación. Esta es una base excelente para la observabilidad.

2.  **Infraestructura como Código (IaC) para Monitoreo:**
    *   Grafana se provisiona a través de archivos YAML (`grafana/provisioning`), lo que significa que la configuración de la fuente de datos y los dashboards está versionada en Git. Esto es una práctica moderna y muy recomendada que evita la configuración manual y la deriva de configuración.

### ✗ Problemas Encontrados

| ID | Severidad | Problema | Impacto |
| :- | :--- | :--- | :--- |
| **M-01** | **CRÍTICO** | **Ausencia Total de Alertas** | Si un servicio crítico como `postgres` o `authelia` cae, o si el disco del servidor se llena, **nadie será notificado**. El fallo solo se descubrirá cuando los usuarios reporten problemas, lo que aumenta drásticamente el Tiempo Medio de Detección (MTTD) y el Tiempo Medio de Resolución (MTTR). |
| **M-02** | **ALTO** | **Falta de Agregación de Logs** | Durante un incidente de seguridad o un fallo en cascada, es crucial poder ver una secuencia de eventos correlacionada en el tiempo a través de múltiples servicios. Sin un sistema de logging centralizado, esta tarea es manual, lenta y propensa a errores, lo que dificulta enormemente el análisis de la causa raíz. |
| **M-03** | **MEDIO** | **Puntos Ciegos en los Dashboards** | Aunque existen dashboards para Ollama, no hay ninguno para visualizar métricas vitales del host (CPU, memoria, I/O de disco, uso de red del `node-exporter`) ni para la salud general de los contenedores (uso de recursos, reinicios, estado del `cadvisor`). Esto impide la detección proactiva de problemas de rendimiento o de capacidad. |

### ⚠️ Warnings/Recomendaciones

1.  **Retención de Métricas:**
    *   Prometheus está configurado con una retención de 15 días (`--storage.tsdb.retention.time=15d`). Esto es bajo para análisis de tendencias a largo plazo. Se debería considerar el uso de una solución de almacenamiento a largo plazo como Thanos o VictoriaMetrics si se necesita un historial más extenso.

2.  **Seguridad de Grafana:**
    *   Las credenciales de administrador de Grafana se establecen a través de variables de entorno, lo cual es mejor que tenerlas hardcodeadas. Sin embargo, la contraseña por defecto es `admin`. El `docker-compose.yml` debe incluir un comentario claro que indique que esta contraseña debe ser cambiada inmediatamente después del primer inicio de sesión.

### 🔧 Soluciones Sugeridas

1.  **Para M-01 (Implementar Alertas):**
    *   **解决方案:** Integrar `Alertmanager` en el stack de monitoreo.
        1.  **Añadir `Alertmanager` a `docker-compose.yml`:**
            ```yaml
            alertmanager:
              image: prom/alertmanager:v0.27.0
              container_name: alertmanager
              networks: [monitoring]
              restart: unless-stopped
              volumes:
                - ./prometheus/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
              ports:
                - "9093:9093"
            ```
        2.  **Crear `prometheus/alertmanager.yml`:** Configurar los receptores de notificaciones (ej. Email, Slack, Telegram).
        3.  **Actualizar `prometheus.yml`:** Añadir la configuración para que Prometheus envíe las alertas a Alertmanager y cargar los archivos de reglas.
            ```yaml
            # En prometheus.yml
            alerting:
              alertmanagers:
                - static_configs:
                    - targets: ['alertmanager:9093']

            rule_files:
              - "/etc/prometheus/alert-rules.yml"
            ```
        4.  **Crear `prometheus/alert-rules.yml`:** Definir reglas de alerta críticas (ej. `HostHighCpuLoad`, `ContainerDown`, `DiskSpaceLow`).

2.  **Para M-02 (Centralizar Logs):**
    *   **解决方案:** Añadir `Loki` y `Promtail` al stack para la agregación de logs.
        1.  **Añadir `Loki` y `Promtail` a `docker-compose.yml`:**
            ```yaml
            loki:
              image: grafana/loki:2.9.0
              # ... configuración de Loki ...
            promtail:
              image: grafana/promtail:2.9.0
              # ... configuración de Promtail para recolectar logs de contenedores ...
            ```
        2.  **Configurar Grafana:** Añadir Loki como una nueva fuente de datos para poder explorar y visualizar los logs junto a las métricas.

3.  **Para M-03 (Mejorar la Visibilidad):**
    *   **解决方案:** Añadir dashboards estándar de la comunidad para `node-exporter` y `cadvisor`.
        *   Descargar los JSON de dashboards populares desde el [Marketplace de Grafana](https://grafana.com/grafana/dashboards/), como el "Node Exporter Full" (ID 1860) y el de "Docker and System Monitoring" (ID 893).
        *   Añadirlos al directorio `grafana/dashboards/` para que sean provisionados automáticamente.
