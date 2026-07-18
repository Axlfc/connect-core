import os
import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("cognito.backend.qdrant")

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
    qdrant_available = True
except ImportError:
    qdrant_available = False

class QdrantSemanticMemory:
    def __init__(self):
        self.host = os.getenv("QDRANT_HOST", "localhost")
        self.port = int(os.getenv("QDRANT_PORT", "6333"))
        self._client = None

    def _get_client(self):
        global qdrant_available
        if not qdrant_available:
            return None
        if self._client is None:
            try:
                self._client = QdrantClient(host=self.host, port=self.port, timeout=2.0)
            except Exception as e:
                logger.warning(f"Qdrant client initialization failed: {e}")
                self._client = None
        return self._client

    async def index_point(self, collection_name: str, point_id: str, vector: List[float], payload: Dict[str, Any]) -> bool:
        """
        Indices a point in a collection with metadata.
        Failure tolerant: if Qdrant is down, returns False but does not raise.
        """
        client = self._get_client()
        if not client:
            return False

        # Build payload schema
        enriched_payload = {
            "repository_id": payload.get("repository_id", "unknown"),
            "repository_url": payload.get("repository_url", "none"),
            "commit_sha": payload.get("commit_sha", "HEAD"),
            "path": payload.get("path", "none"),
            "content_type": payload.get("content_type", "text"),
            "schema_version": 1,
            "indexed_at": time.time(),
            "task_id": payload.get("task_id"),
            **payload
        }

        try:
            # Check if collection exists, if not create
            try:
                client.get_collection(collection_name)
            except Exception:
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=qmodels.VectorParams(size=len(vector), distance=qmodels.Distance.COSINE)
                )

            client.upsert(
                collection_name=collection_name,
                points=[
                    qmodels.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=enriched_payload
                    )
                ]
            )
            return True
        except Exception as e:
            logger.warning(f"Qdrant indexing failed gracefully: {e}")
            self._client = None
            return False

    async def search_points(self, collection_name: str, vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        client = self._get_client()
        if not client:
            return []
        try:
            results = client.search(
                collection_name=collection_name,
                query_vector=vector,
                limit=limit
            )
            return [r.payload for r in results]
        except Exception as e:
            logger.warning(f"Qdrant search failed gracefully: {e}")
            self._client = None
            return []

qdrant_memory = QdrantSemanticMemory()
