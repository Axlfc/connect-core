import pytest
import httpx
import json
import asyncio
from qdrant_client import QdrantClient, models

# Importar funciones y variables desde el servidor
from cognito_mcp_server import generate_with_llm, query_vector_db, OLLAMA_URL, QDRANT_URL

TEST_COLLECTION_NAME = "test_mcp_collection"

@pytest.fixture(scope="module")
async def setup_qdrant():
    """
    Prepara Qdrant para las pruebas: crea una colección e inserta un documento.
    """
    qdrant_client = QdrantClient(url=QDRANT_URL)
    httpx_client = httpx.AsyncClient()

    try:
        # 1. Generar un embedding para obtener el tamaño del vector
        embedding_response = await httpx_client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": "documento de prueba"},
            timeout=30.0
        )
        embedding_response.raise_for_status()
        embedding = embedding_response.json()["embedding"]
        vector_size = len(embedding)

        # 2. (Re)crear la colección de prueba en Qdrant
        qdrant_client.recreate_collection(
            collection_name=TEST_COLLECTION_NAME,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )

        # 3. Insertar un documento de prueba
        qdrant_client.upsert(
            collection_name=TEST_COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=1,
                    vector=embedding,
                    payload={"text": "Este es un documento de prueba sobre ciudades inteligentes."}
                )
            ],
            wait=True
        )
        print(f"Colección de Qdrant '{TEST_COLLECTION_NAME}' lista para las pruebas.")

    except httpx.ConnectError as e:
        pytest.fail(f"No se pudo conectar a los servicios para preparar Qdrant. ¿Están activos? Error: {e}")
    except Exception as e:
        pytest.fail(f"Falló la configuración de Qdrant para las pruebas: {e}")
    finally:
        await httpx_client.aclose()

    yield # Cedemos el control a los tests

    # Limpieza: eliminar la colección después de las pruebas
    try:
        qdrant_client.delete_collection(collection_name=TEST_COLLECTION_NAME)
        print(f"Colección de Qdrant '{TEST_COLLECTION_NAME}' eliminada.")
    except Exception as e:
        print(f"Error durante la limpieza de Qdrant: {e}")


@pytest.mark.asyncio
async def test_generate_with_llm():
    """
    Prueba la herramienta generate_with_llm llamando al servicio de Ollama.
    """
    try:
        response = await generate_with_llm("Di 'hola' en una sola palabra", model="llama3.2")
        assert "hola" in response.lower()
    except httpx.ConnectError:
        pytest.fail("La conexión con Ollama falló. Asegúrate de que el servicio esté en ejecución.")
    except Exception as e:
        pytest.fail(f"El test de generate_with_llm falló con un error inesperado: {e}")


@pytest.mark.asyncio
async def test_query_vector_db(setup_qdrant):
    """
    Prueba la herramienta query_vector_db consultando el documento de prueba en Qdrant.
    """
    try:
        result_json = await query_vector_db("¿De qué trata este documento?", collection=TEST_COLLECTION_NAME)
        results = json.loads(result_json)

        assert isinstance(results, list)
        assert len(results) > 0
        assert "payload" in results[0]
        assert "text" in results[0]["payload"]
        assert "ciudades inteligentes" in results[0]["payload"]["text"]
    except httpx.ConnectError as e:
        pytest.fail(f"La conexión con Ollama o Qdrant falló. Asegúrate de que los servicios estén activos. Detalles: {e}")
    except Exception as e:
        pytest.fail(f"El test de query_vector_db falló con un error inesperado: {e}")
