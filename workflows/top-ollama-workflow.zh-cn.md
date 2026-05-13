Workflow: Generación LLM + embeddings (plantilla para `n8n`)

Objetivo
- Recibir prompt por webhook, generar texto con `Ollama`, calcular embeddings y almacenar en `Qdrant`.

Nodos (pasos)
1. Webhook (trigger)
   - Método: POST
   - Payload esperado: { "prompt": "...", "metadata": {...} }

2. Set / Transform
   - Normalizar prompt, añadir contexto (system prompt).

3. HTTP Request → Ollama
   - URL: http://ollama:11434/api/generate (ajustar según API expuesta)
   - Method: POST
   - Body (JSON): { "model": "<modelo>", "prompt": "{{$json["prompt"]}}", "max_tokens": 512 }
   - Headers: Content-Type: application/json

4. Execute Command / n8n-runner (opcional)
   - Usar un runner Python si quieres calcular embeddings con `sentence-transformers` localmente.
   - Script ejemplo (en runner venv):
     ```python
     from sentence_transformers import SentenceTransformer
     m = SentenceTransformer('all-MiniLM-L6-v2')
     emb = m.encode(text)
     print(emb.tolist())
     ```
   - En n8n: usar nodo `Execute Command` apuntando al runner Python (según `n8n-task-runners.json`).

5. HTTP Request → Qdrant
   - URL: http://qdrant:6333/collections/<collection>/points
   - Method: POST
   - Body: { "points": [{"id": "<uuid>", "vector": <embedding_array>, "payload": {"text": "...", "meta": {...}}}] }
   - Headers: Content-Type: application/json

6. Respond
   - Return: generado + id de vector en Qdrant

Variables / Secrets necesarias
- `OLLAMA_API_URL` (por defecto: http://ollama:11434)
- `QDRANT_URL` (por defecto: http://qdrant:6333)
- `N8N_RUNNERS_AUTH_TOKEN` (si usas runners externos)

Rebuild / prueba
```bash
# Si modificaste dependencias del runner
[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-ollama-workflow.zh-cn.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-ollama-workflow.en.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-ollama-workflow.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-ollama-workflow.ca.md)

[![zh-cn](https://img.shields.io/badge/lang-zh--cn-red.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-ollama-workflow.zh-cn.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-ollama-workflow.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-ollama-workflow.en.md)
[![ca](https://img.shields.io/badge/lang-ca-blue.svg)](https://github.com/Axlfc/connect-core/blob/master/workflows/top-ollama-workflow.ca.md)

docker compose build n8n-runner
docker compose up -d n8n-runner
# Probar webhook (ejemplo):
curl -X POST http://localhost:5678/webhook/top-ollama -H 'Content-Type: application/json' -d '{"prompt":"Hola mundo"}'
```

Notas
- Si prefieres calcular embeddings en Ollama (si el modelo lo permite), omite el runner.
- Asegúrate de tener creada la colección en Qdrant antes de enviar puntos.