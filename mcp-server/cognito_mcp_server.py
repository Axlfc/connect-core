import os
import json
import httpx
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Obtener URLs de los servicios desde variables de entorno
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
N8N_URL = os.getenv("N8N_URL", "http://localhost:5678")
N8N_API_KEY = os.getenv("N8N_API_KEY", "n8n_api_xxxxxxxxxxxxxxxxxxxxxxxx")
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://localhost:8188")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:3000")
JWT_TOKEN = os.getenv("JWT_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJ0ZXN0LXVzZXIifQ.xxxxx")


mcp = FastMCP("cognito-tools")

@mcp.tool()
async def generate_with_llm(
    prompt: str,
    model: str = "llama3.2",
    system_prompt: str = ""
) -> str:
    """
    Genera texto usando Ollama.

    Args:
        prompt: Prompt del usuario
        model: Modelo a usar (llama3.2, qwen2.5-coder, deepseek-r1)
        system_prompt: Instrucciones del sistema
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False
            },
            timeout=60.0
        )
        response.raise_for_status()
        return response.json()["response"]

@mcp.tool()
async def query_vector_db(query: str, collection: str = "documents") -> str:
    """
    Busca en Qdrant usando embeddings generados con Ollama.

    Args:
        query: Texto de búsqueda
        collection: Colección de Qdrant a consultar

    Returns:
        JSON con documentos relevantes y scores
    """
    async with httpx.AsyncClient() as client:
        # 1. Generar embedding del query con Ollama
        embedding_response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": query},
            timeout=30.0
        )
        embedding_response.raise_for_status()
        embedding = embedding_response.json()["embedding"]

        # 2. Buscar en Qdrant
        qdrant_response = await client.post(
            f"{QDRANT_URL}/collections/{collection}/points/search",
            json={
                "vector": embedding,
                "limit": 5,
                "with_payload": True
            }
        )
        qdrant_response.raise_for_status()

        results = qdrant_response.json()["result"]
        return json.dumps(results, indent=2)

@mcp.tool()
async def create_n8n_workflow(workflow_name: str, description: str) -> str:
    """
    Crea un workflow vacío en n8n.

    Args:
        workflow_name: Nombre del workflow
        description: Descripción de lo que hace (no usado por la API actualmente)
    """
    async with httpx.AsyncClient() as client:
        headers = {
            "Accept": "application/json",
            "X-N8N-API-KEY": N8N_API_KEY,
        }
        # Estructura básica de un workflow vacío con un trigger manual
        workflow_data = {
            "name": workflow_name,
            "nodes": [
                {
                    "parameters": {},
                    "name": "Start",
                    "type": "n8n-nodes-base.start",
                    "typeVersion": 1,
                    "position": [240, 300]
                }
            ],
            "connections": {},
            "active": False,
            "settings": {},
            "tags": []
        }
        try:
            response = await client.post(
                f"{N8N_URL}/api/v1/workflows",
                json=workflow_data,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            return f"✅ Workflow '{workflow_name}' creado con ID: {result.get('id')}"
        except httpx.HTTPStatusError as e:
            return f"Error al crear workflow: {e.response.status_code} {e.response.text}"
        except Exception as e:
            return f"Error inesperado al crear workflow: {str(e)}"

import uuid
import aiohttp

@mcp.tool()
async def generate_image(prompt: str, width: int = 1024, height: int = 1024) -> str:
    """
    Genera una imagen usando un workflow de ComfyUI (texto a imagen).

    Args:
        prompt: Descripción de la imagen a generar.
        width: Ancho de la imagen.
        height: Alto de la imagen.
    """
    client_id = str(uuid.uuid4())

    # Definición del workflow de ComfyUI en formato API
    # Este workflow es un text-to-image básico
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 15668,
                "steps": 25,
                "cfg": 7,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0]
            }
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "sd_xl_base_1.0.safetensors"
            }
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["4", 1]
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "ugly, bad anatomy, worst quality, low quality",
                "clip": ["4", 1]
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2]
            }
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "mcp_generated_image",
                "images": ["8", 0]
            }
        }
    }

    try:
        # 1. Enviar el prompt a la cola de ComfyUI
        async with httpx.AsyncClient() as client:
            prompt_payload = {"prompt": workflow, "client_id": client_id}
            headers = {"Content-Type": "application/json"}

            resp = await client.post(f"{COMFYUI_URL}/prompt", json=prompt_payload, headers=headers)
            resp.raise_for_status()
            prompt_id = resp.json().get('prompt_id')
            if not prompt_id:
                return "Error: No se recibió prompt_id de ComfyUI."

        # 2. Escuchar en el WebSocket para obtener el resultado
        ws_url = f"ws://{COMFYUI_URL.split('//')[1]}/ws?clientId={client_id}"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_url) as ws:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data.get('type') == 'executed' and data['data']['node'] == '9': # '9' es el ID de SaveImage
                            output = data['data']['output']
                            image_info = output['images'][0]
                            filename = image_info['filename']

                            # 3. Construir la URL final de la imagen
                            image_url = f"{COMFYUI_URL}/view?filename={filename}&subfolder={image_info.get('subfolder', '')}&type={image_info.get('type', 'output')}"
                            return f"✅ Imagen generada: {image_url}"
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break
        return "Error: La conexión WebSocket se cerró antes de recibir la imagen."

    except httpx.HTTPStatusError as e:
        return f"Error HTTP al contactar ComfyUI: {e.response.status_code} {e.response.text}"
    except Exception as e:
        return f"Error inesperado al generar la imagen: {str(e)}"

@mcp.tool()
async def run_python_code(code: str, context: dict = None) -> str:
    """
    Ejecuta código Python de forma aislada a través de un workflow de n8n.
    El workflow debe tener un webhook trigger y estar diseñado para recibir
    un JSON con 'code' y 'context'.

    Args:
        code: El código Python a ejecutar.
        context: Un diccionario de variables que estarán disponibles en el scope del código.
    """
    PYTHON_EXECUTION_WORKFLOW_ID = os.getenv("PYTHON_EXECUTION_WORKFLOW_ID", "3")

    webhook_url = f"{N8N_URL}/webhook/{PYTHON_EXECUTION_WORKFLOW_ID}"

    payload = {
        "code": code,
        "context": context or {}
    }

    async with httpx.AsyncClient() as client:
        try:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            response = await client.post(webhook_url, json=payload, headers=headers, timeout=120.0)
            response.raise_for_status()

            # Asumimos que el workflow de n8n devuelve un JSON con la salida.
            # La estructura exacta dependerá de cómo esté configurado el workflow.
            try:
                result = response.json()
                # Extraer la salida de la ejecución del código
                execution_output = result.get("body", {}).get("result", "No output captured.")
                return f"✅ Código Python ejecutado.\nSalida:\n---\n{execution_output}\n---"
            except json.JSONDecodeError:
                return f"✅ Código Python ejecutado. Respuesta no es JSON válido:\n{response.text}"

        except httpx.HTTPStatusError as e:
            return f"Error al ejecutar el workflow de Python: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return f"Error inesperado al ejecutar código Python: {str(e)}"

@mcp.tool()
async def run_javascript_code(code: str, context: dict = None) -> str:
    """
    Ejecuta código Javascript de forma aislada a través de un workflow de n8n.
    El workflow debe tener un webhook trigger y estar diseñado para recibir
    un JSON con 'code' y 'context'.

    Args:
        code: El código Javascript a ejecutar.
        context: Un diccionario de variables que estarán disponibles en el scope del código.
    """
    JS_EXECUTION_WORKFLOW_ID = os.getenv("JS_EXECUTION_WORKFLOW_ID", "4")
    webhook_url = f"{N8N_URL}/webhook/{JS_EXECUTION_WORKFLOW_ID}"

    payload = {
        "code": code,
        "context": context or {}
    }
    async with httpx.AsyncClient() as client:
        try:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            response = await client.post(webhook_url, json=payload, headers=headers, timeout=120.0)
            response.raise_for_status()
            try:
                result = response.json()
                execution_output = result.get("body", {}).get("result", "No output captured.")
                return f"✅ Código Javascript ejecutado.\nSalida:\n---\n{execution_output}\n---"
            except json.JSONDecodeError:
                return f"✅ Código Javascript ejecutado. Respuesta no es JSON válido:\n{response.text}"

        except httpx.HTTPStatusError as e:
            return f"Error al ejecutar el workflow de Javascript: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return f"Error inesperado al ejecutar código Javascript: {str(e)}"

@mcp.tool()
async def query_project_data(project_id: str) -> str:
    """
    Consulta datos de un proyecto específico en la API de Tarragona Connect.

    Args:
        project_id: El ID del proyecto a consultar.
    """
    api_url = f"{API_BASE_URL}/projects/{project_id}"
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Accept": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(api_url, headers=headers, timeout=30.0)

            if response.status_code == 404:
                return f"ℹ️ No se encontró ningún proyecto con el ID '{project_id}'."

            response.raise_for_status()

            try:
                project_data = response.json()
                return json.dumps(project_data, indent=2)
            except json.JSONDecodeError:
                return f"Error: La respuesta de la API no es un JSON válido: {response.text}"

        except httpx.HTTPStatusError as e:
            return f"Error al consultar la API: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return f"Error inesperado al consultar datos del proyecto: {str(e)}"

@mcp.tool()
async def execute_rag_pipeline(
    query: str,
    project_id: str = None,
    use_web_search: bool = False
) -> str:
    """
    Pipeline RAG completo: recuperación + generación contextualizada.

    Args:
        query: Pregunta del usuario
        project_id: ID del proyecto para filtrar contexto
        use_web_search: Si buscar también en web externa (no implementado)

    Returns:
        Respuesta generada con fuentes citadas
    """
    # 1. Recuperar contexto de Qdrant
    docs_json = await query_vector_db(query, collection="projects")
    docs = json.loads(docs_json)

    context_str = "\n".join([doc.get("payload", {}).get("text", "") for doc in docs])

    # 2. Si hay project_id, obtener datos adicionales (mockeado por ahora)
    if project_id:
        project_data = await query_project_data(project_id)
        context_str += f"\n\nDatos del proyecto:\n{project_data}"

    # 3. Generar respuesta con LLM
    system_prompt = """Eres un asistente experto en Tarragona Connect OS.
    Usa el contexto proporcionado para responder con precisión.
    Cita las fuentes usadas."""

    full_prompt = f"""Contexto relevante:
{context_str}

Pregunta del usuario: {query}

Responde citando las fuentes."""

    response = await generate_with_llm(
        prompt=full_prompt,
        model="llama3.2",
        system_prompt=system_prompt
    )

    return response

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
