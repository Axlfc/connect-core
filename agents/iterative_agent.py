"""
Phase 2/3: Iterative Agent

Combines Chain-of-Thought with Output Validation to create
an agent that iterates until quality threshold is met.
"""

import json
from typing import Dict, Any, Optional
import logging

from .chain_of_thought_agent import ChainOfThoughtAgent
from .output_validator import OutputValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen2.5-coder"


class IterativeAgent:
    """
    Agent that combines reasoning with evaluation.
    
    Process:
    1. Use ChainOfThoughtAgent to generate answer
    2. Use OutputValidator to evaluate quality
    3. If quality < threshold, iterate (regenerate with feedback)
    4. Stop when threshold reached or max iterations hit
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        quality_threshold: float = 3.5,
        max_iterations: int = 3,
    ):
        self.model = model
        self.quality_threshold = quality_threshold
        self.max_iterations = max_iterations
        self.iterations = []
        self.final_result = None

    def solve_iteratively(self, task: str) -> Dict[str, Any]:
        """
        Solve task with iteration until quality threshold.
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Iterative Agent Starting")
        logger.info(f"Task: {task}")
        logger.info(f"Quality Threshold: {self.quality_threshold}/5.0")
        logger.info(f"Max Iterations: {self.max_iterations}")
        logger.info(f"{'='*60}\n")

        current_task = task
        iteration_num = 0

        while iteration_num < self.max_iterations:
            iteration_num += 1
            logger.info(f"\n--- Iteration {iteration_num}/{self.max_iterations} ---\n")

            # Step 1: Generate answer with Chain-of-Thought
            agent = ChainOfThoughtAgent(model=self.model)
            reasoning_result = agent.solve(current_task)

            # Step 2: Evaluate quality
            validator = OutputValidator(model=self.model)
            output_to_evaluate = reasoning_result["final_answer"]

            evaluation_result = validator.evaluate(task, output_to_evaluate)
            quality_score = evaluation_result["overall_score"]

            logger.info(f"Iteration {iteration_num} Quality Score: {quality_score}/5.0\n")

            # Store iteration data
            iteration_data = {
                "iteration": iteration_num,
                "task_used": current_task,
                "reasoning_chain": reasoning_result["reasoning_chain"],
                "final_answer": output_to_evaluate,
                "evaluation": evaluation_result,
                "quality_score": quality_score,
                "met_threshold": quality_score >= self.quality_threshold,
            }
            self.iterations.append(iteration_data)

            # Step 3: Check if we should stop
            if quality_score >= self.quality_threshold:
                logger.info(
                    f"\n✅ Quality threshold reached after {iteration_num} iterations!"
                )
                self.final_result = iteration_data
                break

            # Step 4: If not good enough, create new prompt with feedback
            if iteration_num < self.max_iterations:
                # Get improvement suggestions
                suggestions = validator.get_improvement_suggestions()
                logger.info(f"Improvement needed: {suggestions}\n")

                # Create new task with feedback
                current_task = f"""
Original task: {task}

Previous attempt quality score: {quality_score}/5.0

Feedback: {suggestions}

Please try again, addressing this feedback.
"""

        # If we hit max iterations without reaching threshold
        if not self.final_result:
            logger.warning(f"Max iterations reached without meeting threshold")
            # Use the best iteration (highest quality score)
            best = max(self.iterations, key=lambda x: x["quality_score"])
            self.final_result = best

        return {
            "task": task,
            "model": self.model,
            "quality_threshold": self.quality_threshold,
            "iterations_used": iteration_num,
            "max_iterations": self.max_iterations,
            "final_quality_score": self.final_result["quality_score"],
            "met_threshold": self.final_result["met_threshold"],
            "final_answer": self.final_result["final_answer"],
            "all_iterations": self.iterations,
            "success": True,
        }

    def compare_iterations(self) -> Dict[str, Any]:
        """Compare quality across all iterations."""
        if not self.iterations:
            return {"comparison": "No iterations to compare"}

        comparison = {
            "total_iterations": len(self.iterations),
            "quality_scores": [i["quality_score"] for i in self.iterations],
            "improvement": (
                self.iterations[-1]["quality_score"] - self.iterations[0]["quality_score"]
            ),
            "best_iteration": max(
                enumerate(self.iterations), key=lambda x: x[1]["quality_score"]
            )[0]
            + 1,
        }
        return comparison


# For n8n integration
def solve_with_iteration(
    task: str,
    model: str = DEFAULT_MODEL,
    quality_threshold: float = 3.5,
    max_iterations: int = 3,
) -> Dict[str, Any]:
    """Entry point for n8n workflow."""
    agent = IterativeAgent(
        model=model,
        quality_threshold=quality_threshold,
        max_iterations=max_iterations,
    )
    return agent.solve_iteratively(task)


if __name__ == "__main__":
    # Test
    test_task = "Explain quantum mechanics in simple terms"
    agent = IterativeAgent(quality_threshold=3.5, max_iterations=3)
    result = agent.solve_iteratively(test_task)
    print(json.dumps(result, indent=2))
