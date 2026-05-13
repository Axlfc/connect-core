"""
Phase 3: Memory Manager

Stores and retrieves experiences using Qdrant vector database.
Enables agents to learn from past tasks and apply lessons to new ones.
"""

import requests
import json
from typing import Dict, Any, List, Optional
import logging
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QDRANT_URL = "http://qdrant:6333"
OLLAMA_URL = "http://ollama:11434"
DEFAULT_MODEL = "qwen2.5-coder"


class MemoryManager:
    """
    Manages agent experience memory using Qdrant.
    
    Features:
    - Store experiences (task, solution, outcome, lesson)
    - Retrieve similar experiences
    - Generate embeddings
    - Extract meta-lessons
    - Track improvement over time
    """

    def __init__(self, collection_name: str = "agent_experiences"):
        self.collection_name = collection_name
        self.experiences = []
        self._ensure_collection_exists()

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using Ollama.
        Uses embedding model or generates via LLM output.
        """
        # Simple approach: use Ollama to generate a hash-based embedding
        # In production, use proper embedding model
        import hashlib

        text_hash = hashlib.md5(text.encode()).hexdigest()
        # Convert hash to embedding-like vector (384 dimensions for Qdrant compatibility)
        embedding = [
            float(int(text_hash[i : i + 2], 16)) / 255.0
            for i in range(0, min(len(text_hash), 384 * 2), 2)
        ]
        # Pad to 384 dimensions
        while len(embedding) < 384:
            embedding.append(0.5)
        return embedding[:384]

    def _ensure_collection_exists(self):
        """Ensure Qdrant collection exists."""
        try:
            # Check if collection exists
            response = requests.get(f"{QDRANT_URL}/collections/{self.collection_name}")
            if response.status_code != 200:
                # Create collection
                self._create_collection()
        except Exception as e:
            logger.warning(f"Could not verify Qdrant collection: {e}")

    def _create_collection(self):
        """Create new collection in Qdrant."""
        try:
            requests.put(
                f"{QDRANT_URL}/collections/{self.collection_name}",
                json={
                    "vectors": {
                        "size": 384,
                        "distance": "Cosine",
                    }
                },
            )
            logger.info(f"Created Qdrant collection: {self.collection_name}")
        except Exception as e:
            logger.warning(f"Could not create Qdrant collection: {e}")

    def store_experience(
        self, task: str, solution: str, outcome: str, lesson: str = ""
    ) -> Dict[str, Any]:
        """
        Store an experience in memory.
        
        Args:
            task: The task/problem
            solution: How it was solved
            outcome: Result/success metric
            lesson: What was learned
        """
        if not lesson:
            # Extract lesson automatically
            lesson = self._extract_lesson(task, solution, outcome)

        # Create embedding
        combined_text = f"{task} {solution} {lesson}"
        embedding = self.generate_embedding(combined_text)

        # Create experience record
        experience = {
            "task": task,
            "solution": solution,
            "outcome": outcome,
            "lesson": lesson,
            "embedding": embedding,
        }

        self.experiences.append(experience)

        # Store in Qdrant if available
        try:
            point_id = len(self.experiences)
            requests.put(
                f"{QDRANT_URL}/collections/{self.collection_name}/points",
                json={
                    "points": [
                        {
                            "id": point_id,
                            "vector": embedding,
                            "payload": {
                                "task": task,
                                "solution": solution,
                                "outcome": outcome,
                                "lesson": lesson,
                            },
                        }
                    ]
                },
            )
            logger.info(f"Experience stored in Qdrant (ID: {point_id})")
        except Exception as e:
            logger.warning(f"Could not store in Qdrant: {e}")

        return {
            "stored": True,
            "experience_id": len(self.experiences),
            "lesson": lesson,
        }

    def _extract_lesson(self, task: str, solution: str, outcome: str) -> str:
        """Extract key lesson from task/solution/outcome."""
        prompt = f"""
Extract the KEY LESSON from this task completion.

Task: {task}

Solution approach: {solution}

Outcome: {outcome}

Lesson (1-2 sentences): What should be remembered for similar tasks in the future?
"""
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": DEFAULT_MODEL,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=60,
            )
            result = response.json()
            return result.get("response", "").strip()[:200]
        except Exception as e:
            logger.warning(f"Could not extract lesson: {e}")
            return f"Completed: {outcome}"

    def retrieve_similar_experiences(
        self, task: str, top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar past experiences.
        """
        embedding = self.generate_embedding(task)

        # Search locally first
        similar_local = self._find_similar_local(embedding, top_k)

        # Try Qdrant search
        similar_qdrant = []
        try:
            response = requests.post(
                f"{QDRANT_URL}/collections/{self.collection_name}/points/search",
                json={
                    "vector": embedding,
                    "limit": top_k,
                },
            )
            if response.status_code == 200:
                results = response.json()
                similar_qdrant = results.get("result", [])
                logger.info(f"Found {len(similar_qdrant)} similar experiences in Qdrant")
        except Exception as e:
            logger.warning(f"Qdrant search failed: {e}")

        return similar_local

    def _find_similar_local(
        self, embedding: List[float], top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """Find similar experiences from local memory."""
        if not self.experiences:
            return []

        # Simple cosine similarity
        scores = []
        for exp in self.experiences:
            similarity = self._cosine_similarity(
                embedding, exp.get("embedding", [])
            )
            scores.append((similarity, exp))

        # Sort by similarity and return top k
        scores.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scores[:top_k]]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math

        if not a or not b or len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def extract_meta_lessons(self) -> Dict[str, Any]:
        """
        Extract meta-level lessons from all experiences.
        """
        if not self.experiences:
            return {"meta_lessons": [], "total_experiences": 0}

        # Group lessons by topic
        lessons_text = "\n".join(exp["lesson"] for exp in self.experiences)

        prompt = f"""
Analyze these lessons from completed tasks and extract 3-5 META-LESSONS
(higher-level principles that apply across multiple tasks):

Lessons:
{lessons_text}

Meta-lessons:
1. [Pattern or principle]
2. [Pattern or principle]
...

Be concise.
"""

        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": DEFAULT_MODEL,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=60,
            )
            result = response.json()
            meta_lessons = result.get("response", "").strip()
        except Exception as e:
            logger.warning(f"Could not extract meta-lessons: {e}")
            meta_lessons = "Meta-lesson extraction not available"

        return {
            "total_experiences": len(self.experiences),
            "meta_lessons": meta_lessons,
        }

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about stored memory."""
        return {
            "total_experiences": len(self.experiences),
            "memory_size_mb": len(json.dumps(self.experiences)) / (1024 * 1024),
            "average_lesson_length": (
                sum(len(exp["lesson"]) for exp in self.experiences)
                / max(len(self.experiences), 1)
            ),
        }


# For n8n integration
def store_learning_experience(
    task: str, solution: str, outcome: str, lesson: str = ""
) -> Dict[str, Any]:
    """Entry point for n8n workflow."""
    manager = MemoryManager()
    return manager.store_experience(task, solution, outcome, lesson)


def retrieve_similar_past_tasks(task: str, top_k: int = 3) -> Dict[str, Any]:
    """Entry point for n8n workflow."""
    manager = MemoryManager()
    similar = manager.retrieve_similar_experiences(task, top_k)
    return {
        "task": task,
        "similar_experiences": similar,
        "count": len(similar),
    }


if __name__ == "__main__":
    # Test
    manager = MemoryManager()

    # Store some experiences
    manager.store_experience(
        task="Calculate sum of numbers 1 to 10",
        solution="Used formula n*(n+1)/2 = 10*11/2 = 55",
        outcome="success",
        lesson="For arithmetic sequences, use closed formulas instead of iteration",
    )

    manager.store_experience(
        task="Find maximum value in list",
        solution="Iterated through list keeping track of max",
        outcome="success",
        lesson="Iteration works but built-in max() is faster",
    )

    # Retrieve similar
    similar = manager.retrieve_similar_experiences("Sum numbers 1 to 20")
    print("Similar experiences found:", len(similar))

    # Get meta-lessons
    meta = manager.extract_meta_lessons()
    print("Meta-lessons:", meta)

    # Stats
    stats = manager.get_memory_stats()
    print(json.dumps(stats, indent=2))
