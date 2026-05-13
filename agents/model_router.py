"""
Phase 1: Model Router

Routes different types of tasks to the best-suited language model.
Uses task classification to select optimal model for each problem.
"""

import requests
import json
from typing import Dict, Any, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_URL = "http://ollama:11434"
DEFAULT_MODEL = "qwen2.5-coder"

# Model profiles with strengths
MODEL_PROFILES = {
    "reasoning": {
        "models": ["deepseek-r1", "qwen2.5-coder"],
        "strengths": ["logic", "math", "analysis", "planning"],
        "description": "Best for complex reasoning and analysis",
    },
    "coding": {
        "models": ["qwen2.5-coder", "deepseek-r1"],
        "strengths": ["code", "debugging", "programming", "syntax"],
        "description": "Best for programming and technical problems",
    },
    "creative": {
        "models": ["llama3.2", "qwen2.5-coder"],
        "strengths": ["writing", "ideas", "stories", "brainstorm"],
        "description": "Best for creative and generative tasks",
    },
    "analysis": {
        "models": ["deepseek-r1", "qwen2.5-coder"],
        "strengths": ["analysis", "breakdown", "comparison", "evaluation"],
        "description": "Best for analytical and evaluative tasks",
    },
    "general": {
        "models": ["llama3.2", "qwen2.5-coder"],
        "strengths": ["general", "qa", "information", "explanation"],
        "description": "Best for general knowledge and Q&A",
    },
}


class ModelRouter:
    """
    Routes tasks to the best model based on classification.
    
    Process:
    1. Classify task into category (reasoning, coding, creative, etc.)
    2. Select best model for that category
    3. Execute task with selected model
    4. Log performance
    """

    def __init__(self):
        self.classification_history = []
        self.routing_history = []

    def call_ollama(self, prompt: str, model: str = DEFAULT_MODEL) -> str:
        """Call Ollama API."""
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.7,
                },
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "").strip()
        except requests.RequestException as e:
            logger.error(f"Ollama API error: {e}")
            return f"ERROR: {str(e)}"

    def classify_task(self, task: str) -> Dict[str, Any]:
        """
        Classify task into category using LLM.
        """
        categories = list(MODEL_PROFILES.keys())
        categories_text = ", ".join(categories)

        prompt = f"""
Classify this task into ONE category that best describes it.

Categories: {categories_text}

Task: {task}

Respond with ONLY the category name (one of the above).
Then explain why in 1-2 sentences.
"""
        response = self.call_ollama(prompt, DEFAULT_MODEL)

        # Parse category from response
        category = "general"  # default
        for cat in categories:
            if cat.lower() in response.lower():
                category = cat
                break

        classification = {
            "task": task,
            "classified_as": category,
            "confidence": self._estimate_confidence(response),
            "explanation": response,
            "available_models": MODEL_PROFILES[category]["models"],
            "strengths": MODEL_PROFILES[category]["strengths"],
        }

        self.classification_history.append(classification)
        logger.info(f"Task classified as: {category}")
        return classification

    def _estimate_confidence(self, response: str) -> float:
        """Estimate confidence based on response clarity."""
        # Simple heuristic: longer, more confident responses
        # In real system, use more sophisticated confidence scoring
        import math

        words = len(response.split())
        # Scale confidence from 0.5 to 1.0 based on response length
        confidence = min(0.5 + (words / 100) * 0.5, 1.0)
        return round(confidence, 2)

    def select_model(self, category: str) -> str:
        """
        Select best model for category.
        In simple version, returns first available model.
        """
        if category not in MODEL_PROFILES:
            logger.warning(f"Unknown category {category}, using general")
            category = "general"

        models = MODEL_PROFILES[category]["models"]
        selected = models[0] if models else DEFAULT_MODEL
        logger.info(f"Selected model: {selected} for category: {category}")
        return selected

    def route_and_execute(
        self, task: str, use_classification: bool = True
    ) -> Dict[str, Any]:
        """
        Route task to best model and execute.
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Model Router Starting")
        logger.info(f"Task: {task}")
        logger.info(f"{'='*60}\n")

        if use_classification:
            # Classify task
            classification = self.classify_task(task)
            category = classification["classified_as"]
            selected_model = self.select_model(category)
        else:
            # Use default routing
            category = "general"
            selected_model = DEFAULT_MODEL

        # Execute with selected model
        response = self.call_ollama(task, selected_model)

        routing_record = {
            "task": task,
            "category": category,
            "selected_model": selected_model,
            "response": response,
            "success": True,
        }

        self.routing_history.append(routing_record)

        logger.info(f"Task completed with {selected_model}")
        logger.info(f"{'='*60}\n")

        return {
            "task": task,
            "category": category,
            "selected_model": selected_model,
            "classification": classification if use_classification else None,
            "response": response,
            "routing_history": self.routing_history,
            "success": True,
        }

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get statistics on routing decisions."""
        if not self.routing_history:
            return {"total_tasks": 0}

        categories_used = {}
        models_used = {}

        for record in self.routing_history:
            cat = record.get("category", "unknown")
            model = record.get("selected_model", "unknown")

            categories_used[cat] = categories_used.get(cat, 0) + 1
            models_used[model] = models_used.get(model, 0) + 1

        return {
            "total_tasks": len(self.routing_history),
            "categories_used": categories_used,
            "models_used": models_used,
            "avg_classification_confidence": round(
                sum(c["confidence"] for c in self.classification_history)
                / max(len(self.classification_history), 1),
                2,
            ),
        }


# For n8n integration
def route_task(task: str, use_classification: bool = True) -> Dict[str, Any]:
    """Entry point for n8n workflow."""
    router = ModelRouter()
    return router.route_and_execute(task, use_classification)


if __name__ == "__main__":
    # Test
    test_tasks = [
        "Write a Python function to calculate fibonacci numbers",
        "What are the themes in Shakespeare's Hamlet?",
        "Prove that sqrt(2) is irrational",
    ]

    router = ModelRouter()
    for task in test_tasks:
        result = router.route_and_execute(task)
        print(f"\nTask: {task}")
        print(f"Routed to: {result['selected_model']}")
        print(f"Response: {result['response'][:100]}...")
        print("-" * 60)

    print("\nRouting Statistics:")
    print(json.dumps(router.get_routing_stats(), indent=2))
