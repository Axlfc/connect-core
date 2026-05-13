# mcp-server/tests/test_mcp_server.py
import pytest
import pytest_asyncio
import json
import os
import sys
from qdrant_client import QdrantClient, models
import httpx

# Añadir el directorio del servidor MCP al path para poder importar sus módulos
mcp_server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if mcp_server_path not in sys.path:
    sys.path.append(mcp_server_path)

from cognito_mcp_server import (
    generate_with_llm,
    query_vector_db,
    execute_rag_pipeline,
    OLLAMA_URL,
    QDRANT_URL
)

TEST_COLLECTION_NAME = "mcp_pytest_collection"

@pytest_asyncio.fixture(scope="module")
async def setup_qdrant():
    """
    Prepara una colección en Qdrant con un documento de ejemplo para las pruebas.
    Esta fixture se ejecuta una vez por módulo.
    """
    print("--- Preparando Qdrant para las pruebas ---")
    try:
        qdrant_client = QdrantClient(url=QDRANT_URL, timeout=20)
        async with httpx.AsyncClient(timeout=30.0) as client:
            test_doc = "Tarragona está explorando el uso de IA en servicios urbanos."
            embedding_response = await client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": test_doc}
            )
            embedding_response.raise_for_status()
            embedding = embedding_response.json()["embedding"]
            vector_size = len(embedding)

            qdrant_client.recreate_collection(
                collection_name=TEST_COLLECTION_NAME,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE)
            )

            qdrant_client.upsert(
                collection_name=TEST_COLLECTION_NAME,
                points=[models.PointStruct(id=1, vector=embedding, payload={"text": test_doc})],
                wait=True
            )
        print(f"✓ Qdrant listo. Colección '{TEST_COLLECTION_NAME}' preparada.")
        yield
        print("\n--- Limpiando Qdrant después de las pruebas ---")
        qdrant_client.delete_collection(collection_name=TEST_COLLECTION_NAME)
        print(f"✓ Colección '{TEST_COLLECTION_NAME}' eliminada.")
    except Exception as e:
        pytest.fail(f"No se pudo preparar Qdrant para las pruebas: {e}")

@pytest.mark.asyncio
async def test_generate_with_llm():
    """
    Valida la herramienta 'generate_with_llm' conectándose a Ollama.
    """
    response = await generate_with_llm(
        prompt="Explica qué es un LLM en una frase corta.",
        model="llama3.2"
    )
    assert isinstance(response, str)
    assert len(response) > 10, "La respuesta del LLM debería tener una longitud razonable."

@pytest.mark.asyncio
async def test_query_vector_db(setup_qdrant):
    """
    Valida la herramienta 'query_vector_db' buscando en la colección de prueba.
    Depende de la fixture 'setup_qdrant'.
    """
    result_json = await query_vector_db(
        query="servicios para la ciudad",
        collection=TEST_COLLECTION_NAME
    )
    results = json.loads(result_json)
    assert isinstance(results, list)
    assert len(results) > 0, "Debería encontrar al menos un documento relevante."
    assert "IA" in results[0]['payload']['text'], "El documento recuperado no es el esperado."

@pytest.mark.asyncio
async def test_execute_rag_pipeline(setup_qdrant, monkeypatch):
    """
    Valida el pipeline RAG completo, usando un mock para la colección.
    Depende de 'setup_qdrant' y usa 'monkeypatch' de pytest.
    """
    query = "¿Cómo usa Tarragona la inteligencia artificial?"

    # Usamos monkeypatch para asegurarnos de que la función RAG
    # use nuestra colección de prueba en lugar de la predeterminada.
    async def mocked_query_vector_db(query, collection):
        # Ignoramos la 'collection' por defecto y usamos la de prueba
        return await query_vector_db(query, collection=TEST_COLLECTION_NAME)

    monkeypatch.setattr("cognito_mcp_server.query_vector_db", mocked_query_vector_db)

    response = await execute_rag_pipeline(query=query)

    assert isinstance(response, str)
    assert len(response) > 20, "La respuesta del RAG es demasiado corta."
    assert "servicios urbanos" in response.lower() or "ia" in response.lower(), \
        "La respuesta del RAG no contiene el contexto esperado."
