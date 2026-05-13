"""
Phase 3 Level 2: Few-Shot Learning

Creates prompts with examples from similar past experiences.
Improves model performance by showing working solutions.
"""

import logging
from typing import Dict, Any, List, Optional
import json

logger = logging.getLogger(__name__)


class FewShotPrompt:
    """
    Creates enhanced prompts with few-shot examples from memory.
    
    Process:
    1. Retrieve similar past experiences from memory
    2. Format them as examples
    3. Insert into prompt
    4. Model learns from examples
    
    Example:
        prompter = FewShotPrompt(memory)
        enhanced = prompter.create_few_shot_prompt(
            task="What causes climate change?",
            base_prompt="Explain in detail...",
            num_examples=3
        )
        # Returns prompt with 3 similar examples inserted
    """
    
    def __init__(self, memory=None, num_examples: int = 3):
        """
        Initialize Few-Shot Prompter.
        
        Args:
            memory: MemoryManager instance for retrieving experiences
            num_examples: Number of examples to include (default: 3)
        """
        self.memory = memory
        self.num_examples = num_examples
        self.default_model = "qwen2.5-coder"
    
    def create_few_shot_prompt(
        self,
        task: str,
        base_prompt: str = None,
        quality_threshold: float = 3.5
    ) -> Dict[str, Any]:
        """
        Create prompt enhanced with few-shot examples.
        
        Process:
        1. Retrieve similar experiences from memory
        2. Filter by quality threshold
        3. Format as examples
        4. Inject into base prompt
        5. Return enhanced prompt
        
        Args:
            task: The new task to solve
            base_prompt: Base prompt template (optional)
            quality_threshold: Minimum quality of examples (1-5)
        
        Returns:
            Dictionary with:
            - enhanced_prompt: Prompt with examples injected
            - examples_found: Number of examples used
            - example_sources: Which experiences were used
            - retrieval_scores: Similarity scores
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"📚 FEW-SHOT PROMPT GENERATION")
        logger.info(f"{'='*60}")
        logger.info(f"Task: {task[:80]}...")
        logger.info(f"Examples to include: {self.num_examples}")
        
        # If no memory, return base prompt
        if not self.memory:
            logger.warning("⚠️  No memory manager provided, returning base prompt only")
            return {
                "enhanced_prompt": base_prompt or task,
                "examples_found": 0,
                "example_sources": [],
                "retrieval_scores": []
            }
        
        # Step 1: Retrieve similar experiences
        logger.info("📍 Step 1: Retrieving similar experiences...")
        try:
            similar_experiences = self.memory.retrieve_similar_experiences(
                task=task,
                top_k=self.num_examples
            )
            logger.info(f"✅ Retrieved {len(similar_experiences)} experiences")
        except Exception as e:
            logger.warning(f"⚠️  Could not retrieve experiences: {e}")
            similar_experiences = []
        
        # Step 2: Filter by quality
        logger.info("📍 Step 2: Filtering by quality...")
        high_quality = [
            exp for exp in similar_experiences
            if exp.get("quality", 0) >= quality_threshold
        ]
        logger.info(f"✅ {len(high_quality)} high-quality experiences ({quality_threshold}+)")
        
        if not high_quality:
            logger.info("ℹ️  No high-quality examples found, using best available")
            high_quality = similar_experiences[:self.num_examples]
        
        # Step 3: Format examples
        logger.info("📍 Step 3: Formatting examples...")
        formatted_examples = self._format_examples(high_quality)
        logger.info(f"✅ Formatted {len(formatted_examples)} examples")
        
        # Step 4: Create enhanced prompt
        logger.info("📍 Step 4: Injecting examples into prompt...")
        enhanced_prompt = self._inject_examples(
            base_prompt or task,
            formatted_examples
        )
        logger.info(f"✅ Enhanced prompt created ({len(enhanced_prompt)} chars)")
        
        # Step 5: Compile results
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ FEW-SHOT PROMPT READY")
        logger.info(f"{'='*60}\n")
        
        return {
            "enhanced_prompt": enhanced_prompt,
            "examples_found": len(high_quality),
            "example_sources": [
                exp.get("task", "Unknown")[:50] for exp in high_quality
            ],
            "retrieval_scores": [
                exp.get("similarity_score", 0) for exp in high_quality
            ]
        }
    
    def _format_examples(self, experiences: List[Dict]) -> List[str]:
        """
        Format experiences as readable examples.
        
        Args:
            experiences: List of experience dictionaries
        
        Returns:
            List of formatted example strings
        """
        examples = []
        
        for i, exp in enumerate(experiences[:self.num_examples], 1):
            task = exp.get("task", "Unknown task")
            solution = exp.get("solution", "No solution")
            quality = exp.get("quality", 0)
            lesson = exp.get("lesson", "")
            
            # Truncate if too long
            task = (task[:100] + "...") if len(task) > 100 else task
            solution = (solution[:200] + "...") if len(solution) > 200 else solution
            
            example_text = f"""
EXAMPLE {i}:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Question: {task}

Solution: {solution}

Quality Score: {quality:.1f}/5.0
{f"Lesson: {lesson}" if lesson else ""}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            examples.append(example_text)
        
        return examples
    
    def _inject_examples(self, base_prompt: str, examples: List[str]) -> str:
        """
        Inject examples into the base prompt.
        
        Args:
            base_prompt: Original prompt
            examples: Formatted example strings
        
        Returns:
            Enhanced prompt with examples
        """
        if not examples:
            return base_prompt
        
        examples_section = "\n".join(examples)
        
        enhanced = f"""
📚 LEARNING FROM SIMILAR TASKS:

You have access to solutions from similar problems. Use these as guidance:

{examples_section}

📌 NOW SOLVE THIS NEW TASK:

{base_prompt}

Use the patterns and approaches from the examples above when applicable.
"""
        
        return enhanced
    
    def evaluate_improvement(
        self,
        task: str,
        without_examples_quality: float,
        with_examples_quality: float
    ) -> Dict[str, Any]:
        """
        Evaluate how much examples improved the result.
        
        Args:
            task: The task being evaluated
            without_examples_quality: Quality score without few-shot
            with_examples_quality: Quality score with few-shot
        
        Returns:
            Dictionary with improvement metrics
        """
        improvement = with_examples_quality - without_examples_quality
        improvement_pct = (improvement / without_examples_quality) * 100 if without_examples_quality > 0 else 0
        
        return {
            "task": task[:80],
            "without_examples": without_examples_quality,
            "with_examples": with_examples_quality,
            "absolute_improvement": improvement,
            "percentage_improvement": improvement_pct,
            "was_helpful": improvement > 0
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about few-shot usage.
        
        Returns:
            Dictionary with usage statistics
        """
        return {
            "num_examples": self.num_examples,
            "memory_available": self.memory is not None,
            "default_model": self.default_model
        }
