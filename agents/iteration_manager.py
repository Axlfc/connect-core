"""
Phase 2: Iteration Manager

Orchestrates the evaluation-feedback-regeneration loop.
Automatically improves answers through iterative refinement.
"""

import logging
from typing import Dict, Any, List
import time

from chain_of_thought_agent import ChainOfThoughtAgent
from output_validator import OutputValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IterationManager:
    """
    Manages iterative improvement of answers through validation and feedback.
    
    Workflow:
    1. Generate answer using Chain-of-Thought
    2. Validate answer quality (1-5 scale)
    3. Check if quality >= threshold
    4. If not, generate feedback and regenerate
    5. Track iterations until threshold met or max iterations reached
    
    Example:
        manager = IterationManager(quality_threshold=3.5)
        result = manager.solve_with_iteration("What is 2+2?")
        print(result['final_quality'])  # 4.2/5.0
    """
    
    def __init__(
        self,
        quality_threshold: float = 3.5,
        max_iterations: int = 3,
        model: str = "qwen2.5-coder"
    ):
        """
        Initialize Iteration Manager.
        
        Args:
            quality_threshold: Minimum quality score (1-5) to accept answer (default: 3.5)
            max_iterations: Maximum number of iteration attempts (default: 3)
            model: LLM model to use (default: "qwen2.5-coder")
        """
        self.quality_threshold = quality_threshold
        self.max_iterations = max_iterations
        self.model = model
        self.agent = ChainOfThoughtAgent(model=model)
        self.validator = OutputValidator(model=model)
        self.iterations_log = []
    
    def solve_with_iteration(self, task: str) -> Dict[str, Any]:
        """
        Solve task with automatic iteration until quality threshold met.
        
        Process:
        1. Call Chain-of-Thought agent to generate answer
        2. Validate answer quality
        3. If quality >= threshold, return (success)
        4. If quality < threshold AND iterations < max, generate feedback
        5. Regenerate answer with feedback and loop
        6. After max iterations, return best answer found
        
        Args:
            task: The task/question to solve
        
        Returns:
            Dictionary containing:
            - task: Original task
            - answer: Best answer found
            - iterations_used: How many iterations it took
            - final_quality: Quality score of best answer (1-5)
            - met_threshold: Whether quality >= threshold
            - reasoning_chain: Step-by-step reasoning
            - iterations_log: Log of all iterations
            - improvement: Quality change from first to last iteration
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🔄 ITERATION MANAGER STARTING")
        logger.info(f"{'='*60}")
        logger.info(f"📝 Task: {task}")
        logger.info(f"🎯 Quality Threshold: {self.quality_threshold}/5.0")
        logger.info(f"⚙️  Max Iterations: {self.max_iterations}")
        logger.info(f"{'='*60}\n")
        
        current_task = task
        iteration = 0
        best_result = None
        best_quality = 0
        start_time = time.time()
        
        while iteration < self.max_iterations:
            iteration += 1
            iter_start = time.time()
            
            logger.info(f"\n--- Iteration {iteration}/{self.max_iterations} ---\n")
            
            # Step 1: Generate answer with Chain-of-Thought
            logger.info("📍 Step 1: Generating answer with Chain-of-Thought...")
            cot_result = self.agent.solve(current_task)
            answer = cot_result["final_answer"]
            reasoning_chain = cot_result.get("reasoning_chain", [])
            
            logger.info(f"✅ Generated answer ({len(answer)} chars)")
            
            # Step 2: Evaluate quality
            logger.info("📍 Step 2: Validating answer quality...")
            eval_result = self.validator.evaluate(task, answer)
            quality = eval_result["overall_score"]
            
            iter_time = time.time() - iter_start
            
            logger.info(f"✅ Quality Score: {quality:.1f}/5.0 (took {iter_time:.1f}s)")
            logger.info(f"   Criteria scores:")
            for criterion in eval_result.get("criteria", []):
                logger.info(f"   - {criterion['criterion']}: {criterion['rating']:.1f}/5.0")
            
            # Track best result
            if quality > best_quality:
                best_quality = quality
                best_result = {
                    "iteration": iteration,
                    "task": task,
                    "answer": answer,
                    "quality": quality,
                    "evaluation": eval_result,
                    "reasoning_chain": reasoning_chain,
                    "time_taken": iter_time
                }
                logger.info(f"🌟 New best quality: {quality:.1f}/5.0")
            
            # Log iteration
            self.iterations_log.append({
                "iteration": iteration,
                "quality": quality,
                "answer": answer,
                "time_taken": iter_time
            })
            
            # Step 3: Check if good enough
            if quality >= self.quality_threshold:
                logger.info(f"\n✅ QUALITY THRESHOLD REACHED!")
                logger.info(f"✅ Iterations used: {iteration}/{self.max_iterations}")
                logger.info(f"✅ Final quality: {quality:.1f}/{self.quality_threshold}\n")
                break
            
            # Step 4: If not good enough and iterations remain, generate feedback
            if iteration < self.max_iterations:
                logger.info("📍 Step 3: Quality below threshold, generating feedback...")
                feedback = self._generate_feedback(eval_result, answer)
                
                logger.info(f"✅ Feedback generated for iteration {iteration + 1}")
                logger.info(f"📋 Feedback preview: {feedback[:150]}...\n")
                
                # Step 5: Update task with feedback for next iteration
                current_task = f"""
Original task: {task}

Previous attempt quality: {quality:.1f}/5.0

FEEDBACK FOR IMPROVEMENT:
{feedback}

Please try again, addressing the feedback above.
"""
            else:
                logger.info(f"\n⚠️  Max iterations ({self.max_iterations}) reached")
                logger.info(f"Using best answer found: quality {best_quality:.1f}/5.0\n")
        
        total_time = time.time() - start_time
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🏁 ITERATION COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"📊 Final Quality: {best_quality:.1f}/5.0")
        logger.info(f"⏱️  Total Time: {total_time:.1f}s")
        logger.info(f"🔢 Iterations Used: {iteration}/{self.max_iterations}")
        logger.info(f"{'='*60}\n")
        
        return {
            "task": task,
            "iterations_used": iteration,
            "max_iterations": self.max_iterations,
            "final_quality": best_quality,
            "quality_score": best_quality,  # Alias for compatibility
            "met_threshold": best_quality >= self.quality_threshold,
            "answer": best_result["answer"] if best_result else "No valid answer found",
            "reasoning_chain": best_result["reasoning_chain"] if best_result else [],
            "iterations_log": self.iterations_log,
            "improvement": best_quality - (self.iterations_log[0]["quality"] if self.iterations_log else 0),
            "total_time": total_time,
            "average_time_per_iteration": total_time / iteration if iteration > 0 else 0
        }
    
    def _generate_feedback(self, evaluation: Dict[str, Any], answer: str) -> str:
        """
        Generate specific, actionable feedback based on evaluation results.
        
        Identifies the worst-performing criterion and provides targeted improvement
        suggestions to address it in the next iteration.
        
        Args:
            evaluation: Dictionary from OutputValidator.evaluate() containing criteria scores
            answer: The answer being evaluated
        
        Returns:
            Feedback string with specific improvement suggestions
        """
        # Find worst criterion
        criteria = evaluation.get("criteria", [])
        if not criteria:
            return "No specific feedback available. Please review and improve overall."
        
        worst_criterion = min(criteria, key=lambda x: x.get("rating", 5))
        worst_name = worst_criterion.get("criterion", "unknown").upper()
        worst_rating = worst_criterion.get("rating", 0)
        worst_eval = worst_criterion.get("evaluation", "Low quality")
        
        feedback = f"""
🎯 QUALITY ISSUES IDENTIFIED

❌ Worst Area: {worst_name}
   Current Rating: {worst_rating:.1f}/5.0
   Issue: {worst_eval}

💡 IMPROVEMENT FOCUS:
   - PRIORITY: Specifically improve the {worst_name.lower()}
   - Keep what's working well from previous attempt
   - Be more thorough and complete
   - Add examples, details, or explanations where needed
   - Check for accuracy and factual correctness

📝 ACTION STEPS:
   1. Re-examine the original question carefully
   2. Identify what's missing in the {worst_name.lower()}
   3. Add specific content to address the weakness
   4. Verify accuracy of all facts and claims
   5. Ensure completeness and clarity
"""
        return feedback
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about all iterations performed.
        
        Returns:
            Dictionary with:
            - total_iterations: Number of iterations run
            - avg_quality: Average quality score across all iterations
            - max_quality: Best quality score achieved
            - min_quality: Worst quality score
            - quality_improvement: Change from first to last iteration
            - converged: Whether quality threshold was met
        """
        if not self.iterations_log:
            return {
                "total_iterations": 0,
                "avg_quality": 0,
                "max_quality": 0,
                "min_quality": 0,
                "quality_improvement": 0,
                "converged": False
            }
        
        qualities = [it["quality"] for it in self.iterations_log]
        times = [it.get("time_taken", 0) for it in self.iterations_log]
        
        return {
            "total_iterations": len(self.iterations_log),
            "avg_quality": sum(qualities) / len(qualities),
            "max_quality": max(qualities),
            "min_quality": min(qualities),
            "quality_improvement": qualities[-1] - qualities[0] if qualities else 0,
            "converged": qualities[-1] >= self.quality_threshold if qualities else False,
            "avg_time_per_iteration": sum(times) / len(times) if times else 0,
            "total_time": sum(times)
        }
    
    def reset(self):
        """Clear iteration log for next solve."""
        self.iterations_log = []
