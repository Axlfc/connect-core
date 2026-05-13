Workflow: Generación de imágenes con ComfyUI + post-procesado (plantilla para `n8n`)

Objetivo
- Recibir petición de generación, enviar job a ComfyUI/ComfyAPI, esperar resultado, mover output a `./shared/` y notificar vía webhook o Matrix.

Nodos (pasos)
1. Webhook (trigger)
   - Payload esperado: { "prompt": "...", "width":512, "height":512, "params": {...} }

2. Set
   - Construir payload para ComfyUI (prompt, configuración de sampler, seed).

3. HTTP Request → ComfyUI
   - URL: http://comfyui:8188/api/generate (ajustar a la API real del servicio)
   - Method: POST
   - Body: JSON con prompt y parámetros
   - Esperar jobId en respuesta.

4. Wait / Poll
   - Nodo `Wait` o ciclo que revise el estado del job (HTTP GET a /api/status/<jobId>) hasta `done`.

5. Move / Copy
   - Cuando esté listo, copiar resultado desde volumen compartido (`./shared/`) a la ruta de export.
   - Opcional: ejecutar script en `n8n-runner` para post-procesado (resize, watermark) usando `Pillow`.

6. Notificar
   - Enviar URL del asset final por webhook / Matrix / email.

Variables / Secrets necesarias
- `COMFYUI_URL` (por defecto: http://comfyui:8188)
- `SHARED_DIR` (ruta host: `./shared/` montada en ComfyUI y otros servicios)

Rebuild / prueba
```bash
# Si añadiste paquetes al runner (pillow, etc.)
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-comfyui-workflow.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-comfyui-workflow.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-comfyui-workflow.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-comfyui-workflow.ca.md)

[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-comfyui-workflow.zh-cn.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-comfyui-workflow.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-comfyui-workflow.en.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-comfyui-workflow.ca.md)

docker compose build n8n-runner
docker compose up -d n8n-runner
# Probar webhook:
curl -X POST http://localhost:5678/webhook/top-comfyui -H 'Content-Type: application/json' -d '{"prompt":"A serene landscape"}'
```

Notas
- `ComfyUI` a veces expone endpoints distintos según la imagen; ajusta la URL/endpoint según `Dockerfile.comfyui` y `docker-compose.yml`.
- Usa `./shared/` para intercambio de archivos entre servicios.