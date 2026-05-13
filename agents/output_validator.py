"""
Phase 2: Output Validator

Implements self-evaluation to check if outputs meet quality criteria.
Used by iterative agents to determine if more work is needed.
"""

import requests
import json
from typing import Dict, Any, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_URL = "http://ollama:11434"
DEFAULT_MODEL = "qwen2.5-coder"


class OutputValidator:
    """
    Validates AI outputs against multiple criteria.
    
    Checks:
    - Completeness: Does it address all parts of the task?
    - Correctness: Is the information accurate?
    - Clarity: Is it understandable?
    - Relevance: Is it on-topic?
    - Safety: Does it follow constraints?
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.criteria_results = {}
        self.overall_score = 0

    def validate(self, output: Any) -> bool:
        """
        Validate the output of an agent.
        Checks for required keys: 'status' and 'result'.
        """
        if not isinstance(output, dict):
            return False

        required_keys = ["status", "result"]
        return all(key in output for key in required_keys)

    def call_ollama(self, prompt: str) -> str:
        """Call Ollama API."""
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.3,  # Lower temp for evaluation
                },
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "").strip()
        except requests.RequestException as e:
            logger.error(f"Ollama API error: {e}")
            return f"ERROR: {str(e)}"

    def check_completeness(self, task: str, output: str) -> Dict[str, Any]:
        """Check if output addresses all aspects of the task."""
        prompt = f"""
Evaluate completeness: Does this answer fully address the task?

Task: {task}

Output: {output}

Rate on scale 1-5:
1 = Incomplete, misses major parts
2 = Partially complete, misses some important points
3 = Mostly complete, minor gaps
4 = Complete, covers all main points
5 = Comprehensive, covers all aspects thoroughly

Provide: RATING and REASON (1-2 sentences)
"""
        evaluation = self.call_ollama(prompt)

        # Parse rating from response
        rating = self._extract_rating(evaluation)
        return {
            "criterion": "completeness",
            "rating": rating,
            "evaluation": evaluation,
            "weight": 0.25,
        }

    def check_correctness(self, task: str, output: str) -> Dict[str, Any]:
        """Check if output is factually correct."""
        prompt = f"""
Evaluate correctness: Is the information in this output accurate?

Task: {task}

Output: {output}

Rate on scale 1-5:
1 = Incorrect, contains major errors
2 = Mostly incorrect, significant mistakes
3 = Partially correct, some errors
4 = Mostly correct, minor issues
5 = Correct, accurate information

Provide: RATING and REASON (1-2 sentences)
"""
        evaluation = self.call_ollama(prompt)
        rating = self._extract_rating(evaluation)
        return {
            "criterion": "correctness",
            "rating": rating,
            "evaluation": evaluation,
            "weight": 0.35,  # Highest weight
        }

    def check_clarity(self, task: str, output: str) -> Dict[str, Any]:
        """Check if output is clear and understandable."""
        prompt = f"""
Evaluate clarity: Is this output clear and well-organized?

Output: {output}

Rate on scale 1-5:
1 = Very unclear, hard to understand
2 = Somewhat unclear, confusing
3 = Adequately clear, mostly understandable
4 = Clear, well-organized
5 = Very clear, excellent structure

Provide: RATING and REASON (1-2 sentences)
"""
        evaluation = self.call_ollama(prompt)
        rating = self._extract_rating(evaluation)
        return {
            "criterion": "clarity",
            "rating": rating,
            "evaluation": evaluation,
            "weight": 0.20,
        }

    def check_relevance(self, task: str, output: str) -> Dict[str, Any]:
        """Check if output is relevant to the task."""
        prompt = f"""
Evaluate relevance: Is this output on-topic and relevant to the task?

Task: {task}

Output: {output}

Rate on scale 1-5:
1 = Completely irrelevant
2 = Mostly off-topic
3 = Somewhat relevant
4 = Relevant, stays on topic
5 = Highly relevant, perfectly on-topic

Provide: RATING and REASON (1-2 sentences)
"""
        evaluation = self.call_ollama(prompt)
        rating = self._extract_rating(evaluation)
        return {
            "criterion": "relevance",
            "rating": rating,
            "evaluation": evaluation,
            "weight": 0.20,
        }

    def check_safety(
        self, output: str, safety_constraints: List[str] = None
    ) -> Dict[str, Any]:
        """Check if output violates safety constraints."""
        if not safety_constraints:
            safety_constraints = [
                "No harmful content",
                "No misinformation",
                "No illegal advice",
                "No bias or discrimination",
            ]

        constraints_text = "\n".join(f"- {c}" for c in safety_constraints)

        prompt = f"""
Evaluate safety: Does this output violate any safety constraints?

Safety Constraints:
{constraints_text}

Output: {output}

Rate on scale 1-5:
1 = Violates multiple constraints
2 = Violates some constraints
3 = Neutral, unclear if safe
4 = Safe, passes most constraints
5 = Fully safe, passes all constraints

Provide: RATING and REASON (1-2 sentences)
"""
        evaluation = self.call_ollama(prompt)
        rating = self._extract_rating(evaluation)
        return {
            "criterion": "safety",
            "rating": rating,
            "evaluation": evaluation,
            "weight": 0.25,  # Equal weight with correctness
        }

    def _extract_rating(self, text: str) -> int:
        """Extract numeric rating from evaluation text."""
        import re

        # Look for number 1-5 at start of text
        match = re.search(r"[1-5]", text)
        if match:
            return int(match.group())
        return 3  # Default to neutral

    def evaluate(
        self, task: str, output: str, safety_constraints: List[str] = None
    ) -> Dict[str, Any]:
        """
        Run full evaluation against all criteria.
        Returns overall score and per-criterion results.
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Output Validator Starting")
        logger.info(f"{'='*60}\n")

        # Check all criteria
        results = [
            self.check_completeness(task, output),
            self.check_correctness(task, output),
            self.check_clarity(task, output),
            self.check_relevance(task, output),
            self.check_safety(output, safety_constraints),
        ]

        self.criteria_results = results

        # Calculate weighted overall score
        total_weighted = sum(r["rating"] * r["weight"] for r in results)
        total_weight = sum(r["weight"] for r in results)
        self.overall_score = round(total_weighted / total_weight, 2)

        logger.info(f"Evaluation Complete: {self.overall_score}/5.0")
        logger.info(f"{'='*60}\n")

        return {
            "task": task,
            "output": output,
            "overall_score": self.overall_score,
            "num_criteria": len(results),
            "criteria": results,
            "success": True,
        }

    def needs_iteration(self, threshold: float = 3.5) -> bool:
        """Determine if output needs improvement."""
        return self.overall_score < threshold

    def get_improvement_suggestions(self) -> str:
        """Get suggestions for improvement based on lowest-scored criteria."""
        if not self.criteria_results:
            return "No evaluation results available"

        # Find lowest-scored criteria
        sorted_criteria = sorted(
            self.criteria_results, key=lambda x: x["rating"]
        )
        lowest = sorted_criteria[0]

        return f"Focus on improving {lowest['criterion']}: {lowest['evaluation']}"


# For n8n integration
def validate_output(
    task: str, output: str, safety_constraints: List[str] = None
) -> Dict[str, Any]:
    """Entry point for n8n workflow."""
    validator = OutputValidator()
    return validator.evaluate(task, output, safety_constraints)


if __name__ == "__main__":
    # Test
    test_task = "What is the capital of France?"
    test_output = "Paris is the capital of France. It's a major city."

    validator = OutputValidator()
    result = validator.evaluate(test_task, test_output)
    print(json.dumps(result, indent=2))
