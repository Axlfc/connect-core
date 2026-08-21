import os
import sys
import json
import logging
from pathlib import Path

logger = logging.getLogger("mcp-server")

# Deprecation Notice
print("[DEPRECATION NOTICE] 'mcp-server/cognito_mcp_server.py' is consolidated into the canonical MCP server at 'very-simplified-stack/cognito-backend/app/services/mcp_server.py'.")

# Try importing tools from canonical location if accessible in PYTHONPATH
try:
    backend_path = Path(__file__).resolve().parent.parent / "very-simplified-stack" / "cognito-backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))

    from app.services.mcp_server import (
        mcp,
        execute_agent_task,
        get_session_status,
        cognito_repository_search,
        cognito_architecture_context,
        cognito_known_failures,
        cognito_task_status,
        cognito_model_catalog,
        cognito_worker_health,
        cognito_verification_results,
        generate_with_llm,
        query_vector_db,
        execute_rag_pipeline,
        load_mcp_config,
        verify_mcp_auth
    )
except Exception as err:
    logger.warning(f"Could not directly import canonical app.services.mcp_server: {err}")
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("cognito-tools")

    @mcp.tool()
    async def generate_with_llm(prompt: str, model: str = "llama3.2", system_prompt: str = "") -> str:
        """[Deprecated Fallback] Genera texto usando Ollama."""
        import httpx
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ollama_url}/api/generate",
                json={"model": model, "prompt": prompt, "system": system_prompt, "stream": False},
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()["response"]

    @mcp.tool()
    async def query_vector_db(query: str, collection: str = "documents") -> str:
        """[Deprecated Fallback] Busca en Qdrant usando embeddings de Ollama."""
        import httpx
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        async with httpx.AsyncClient() as client:
            embedding_response = await client.post(
                f"{ollama_url}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": query},
                timeout=30.0
            )
            embedding_response.raise_for_status()
            embedding = embedding_response.json()["embedding"]

            qdrant_response = await client.post(
                f"{qdrant_url}/collections/{collection}/points/search",
                json={"vector": embedding, "limit": 5, "with_payload": True}
            )
            qdrant_response.raise_for_status()
            results = qdrant_response.json()["result"]
            return json.dumps(results, indent=2)

    @mcp.tool()
    async def execute_rag_pipeline(query: str, project_id: str = None) -> str:
        """[Deprecated Fallback] Pipeline RAG completo."""
        docs_json = await query_vector_db(query, collection="documents")
        docs = json.loads(docs_json)
        context_str = "\n".join([doc.get("payload", {}).get("text", "") for doc in docs if isinstance(doc, dict)])
        full_prompt = f"Contexto relevante:\n{context_str}\n\nPregunta: {query}"
        return await generate_with_llm(prompt=full_prompt, model="llama3.2")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
