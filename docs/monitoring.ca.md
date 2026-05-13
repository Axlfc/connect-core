# Monitorización con Prometheus + Grafana (opcional)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/monitoring.ca.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/monitoring.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/monitoring.md)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/docs/monitoring.zh-cn.md)


Este documento explica cómo habilitar una stack ligera de monitorización para supervisar uso de GPU, latencias de endpoints (p. ej. Ollama), métricas de contenedores y del sistema.

## Contenido añadido
- Serveis Docker: `prometheus`, `grafana`, `blackbox-exporter`, `node-exporter`, `cadvisor` (y `nvidia-dcgm-exporter` bajo el perfil `gpu-nvidia`).
- Configuración Prometheus: `prometheus/prometheus.yml` (scrapes para blackbox, node-exporter, cadvisor y dcgm).
- Configuración Grafana: `grafana/provisioning` + dashboards básicos en `grafana/dashboards`.

## Cómo arrancar
1. Habilita el perfil `monitoring` al arrancar:

   docker compose --profile monitoring up -d

2. Si quieres métricas de GPU NVIDIA, añade `--profile gpu-nvidia`:

   docker compose --profile gpu-nvidia --profile monitoring up -d

3. Accede a Grafana: https://monitoring.localhost (protegido por Authelia, usuario `admin` y contraseña en `.env` o `.env.example`)
4. Accede a Prometheus: http://localhost:9090

Nota: Grafana y Uptime Kuma están protegidos por Authelia cuando accedes mediante su `VIRTUAL_HOST` (p. ej. `monitoring.localhost`, `status.localhost`). Si deseas exponer Grafana sin protección, elimina `VIRTUAL_HOST` o cambia la configuración de `nginx-proxy/vhost.d/monitoring.localhost`. Esta política asegura que los dashboards y los puntos de control no queden expuestos públicamente.

## Qué se monitoriza por defecto
- Latencia HTTP de servicios LLM (p. ej. Ollama) usando `blackbox_exporter` (consulta `probe_duration_seconds{job="blackbox"}`).
- Métricas de sistema/host con `node-exporter`.
- Métricas de contenedores con `cAdvisor`.
- Métricas GPU (NVIDIA) con `nvidia-dcgm-exporter` (habilitar perfil `gpu-nvidia`).

## Dashboards incluidos
- `LLM Latency` — muestra `probe_duration_seconds` proveniente del `blackbox_exporter`.
- `GPU Usage` — panel que intenta leer métricas DCGM; dependiendo del exportador el nombre de la métrica puede variar (p. ej. `dcgm_gpu_sm_utilization` o `DCGM_FI_DEV_GPU_UTIL`).
- `Ollama - Overview` — métricas avanzadas para Ollama: latencia por modelo (p50/p95/p99), QPS por modelo, tasa de errores y tokens in/out.

## Instrumentación de Ollama (proxy)
Si Ollama no expone métricas Prometheus nativas, hemos incluido un proxy ligero `ollama-metrics-proxy` (servicio opcional bajo el perfil `monitoring`) que intercepta las peticiones a Ollama y expone métricas en `/metrics`.

- Servei: `ollama-metrics-proxy` (build desde `./ollama-metrics-proxy`)
- Qué mide: latencia (histograma), conteo de peticiones (por modelo/endpoint/status), errores, tokens in/out (si aparecen en la respuesta).

### Cómo arrancar
1. Levanta el proxy junto a la stack de monitoring:

   docker compose --profile monitoring up -d --build ollama-metrics-proxy prometheus grafana

2. Genera tráfico de prueba (herramienta incluida):

   ./scripts/test_ollama_proxy.sh http://localhost:9200

3. Verifica en Prometheus: http://localhost:9090 > Metrics > buscar `ollama_request`
4. Verifica en Grafana: Dashboard `Ollama - Overview` (https://monitoring.localhost)

> Nota: El proxy reenvía las peticiones a la URL configurada en `OLLAMA_URL` (por defecto `http://ollama:11434`); asegúrate de que Ollama esté accesible desde el proxy dentro de la red Docker (`ai`/`monitoring`).
## Añadir más endpoints a monitorizar
Edite `prometheus/prometheus.yml` y añada targets al job `blackbox` (todas las URLs HTTP que quieras comprobar). Luego recargue la configuración de Prometheus (el contenedor lo hace automáticamente cuando monta el archivo).

## Notas y recomendaciones
- Las métricas GPU dependen del driver y del soporte del host; asegúrate de que Docker tenga acceso a las GPUs (NVIDIA runtime / device requests) cuando uses `nvidia-dcgm-exporter`.
- Si prefieres métricas de contenedores más completas, puedes añadir `node-exporter` en modo `host` y/o usar `cAdvisor` (ya incluido).
- Personaliza dashboards en `grafana/dashboards/` y súbelos como JSON si deseas.

Si quieres, puedo: crear dashboards más avanzados (latencia por modelo, cola de peticiones, uso de memoria por modelo, alertas) — dime qué métricas concretas quieres y lo preparo. ✨