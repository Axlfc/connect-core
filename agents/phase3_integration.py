"""
Phase 3 Integration: Complete Learning System

Combines Phases 1, 2, and 3 into a unified learning architecture.

Architecture:
  Input Task
    ↓
  [Memory]: Retrieve similar experiences (Level 1)
    ↓
  [Few-Shot]: Format examples (Level 2)
    ↓
  [Meta]: Extract patterns (Level 3)
    ↓
  [Phase 1]: CoT reasoning (with examples + patterns)
    ↓
  [Phase 2]: Validation & iteration
    ↓
  [Memory]: Store successful experience
    ↓
  Output
"""

import logging
from typing import Dict, Any, List, Optional
import time

logger = logging.getLogger(__name__)


class Phase3Integration:
    """
    Unified system integrating all phases with learning.
    
    Combines:
    - Phase 1: Chain-of-Thought reasoning
    - Phase 2: Self-validation and iteration
    - Phase 3: Memory and meta-learning
    
    Example:
        system = Phase3Integration(
            cot_agent=cot_agent,
            validator=validator,
            iteration_manager=iteration_mgr,
            memory=memory,
            few_shot=few_shot_prompter,
            meta_learner=meta_learner
        )
        
        result = system.solve_with_learning(task="What is photosynthesis?")
        # Returns: answer with learning applied and stored
    """
    
    def __init__(
        self,
        cot_agent=None,
        validator=None,
        iteration_manager=None,
        memory=None,
        few_shot_prompter=None,
        meta_learner=None
    ):
        """
        Initialize Phase 3 Integration.
        
        Args:
            cot_agent: ChainOfThoughtAgent (Phase 1)
            validator: OutputValidator (Phase 1)
            iteration_manager: IterationManager (Phase 2)
            memory: MemoryManager (for storing experiences)
            few_shot_prompter: FewShotPrompt (Phase 3 Level 2)
            meta_learner: MetaLearner (Phase 3 Level 3)
        """
        self.cot_agent = cot_agent
        self.validator = validator
        self.iteration_manager = iteration_manager
        self.memory = memory
        self.few_shot_prompter = few_shot_prompter
        self.meta_learner = meta_learner
        
        self.execution_log = []
    
    def solve_with_learning(
        self,
        task: str,
        use_memory: bool = True,
        use_few_shot: bool = True,
        use_meta: bool = True,
        store_result: bool = True
    ) -> Dict[str, Any]:
        """
        Solve task using complete learning system.
        
        Process:
        1. If enabled: Retrieve experiences from memory (Level 1)
        2. If enabled: Create few-shot prompt with examples (Level 2)
        3. If enabled: Add meta-patterns to prompt (Level 3)
        4. Use Phase 1: CoT reasoning with enhanced prompt
        5. Use Phase 2: Validation and iteration
        6. If enabled: Store result for future learning
        
        Args:
            task: Task to solve
            use_memory: Enable memory retrieval
            use_few_shot: Enable few-shot learning
            use_meta: Enable meta-learning
            store_result: Store result in memory
        
        Returns:
            Dictionary with complete results and learning info
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 PHASE 3 INTEGRATED LEARNING SYSTEM")
        logger.info(f"{'='*70}")
        logger.info(f"📝 Task: {task[:80]}...")
        logger.info(f"   Memory: {'✅' if use_memory else '❌'} | "
                   f"Few-Shot: {'✅' if use_few_shot else '❌'} | "
                   f"Meta: {'✅' if use_meta else '❌'}")
        logger.info(f"{'='*70}\n")
        
        start_time = time.time()
        enhanced_task = task
        learning_info = {
            "used_memory": False,
            "memory_experiences_retrieved": 0,
            "used_few_shot": False,
            "few_shot_examples": 0,
            "used_meta": False,
            "meta_patterns": []
        }
        
        # LEVEL 1: Memory Retrieval
        if use_memory and self.memory:
            logger.info("📍 LEVEL 1: Memory Retrieval")
            memory_result = self._retrieve_from_memory(task)
            learning_info["used_memory"] = memory_result["found"]
            learning_info["memory_experiences_retrieved"] = memory_result["count"]
            logger.info(f"   ✅ Retrieved {memory_result['count']} experiences\n")
        
        # LEVEL 2: Few-Shot Learning
        if use_few_shot and self.few_shot_prompter:
            logger.info("📍 LEVEL 2: Few-Shot Prompt Enhancement")
            few_shot_result = self._enhance_with_few_shot(task, enhanced_task)
            enhanced_task = few_shot_result["enhanced_prompt"]
            learning_info["used_few_shot"] = few_shot_result["used"]
            learning_info["few_shot_examples"] = few_shot_result["examples_count"]
            logger.info(f"   ✅ Added {few_shot_result['examples_count']} examples\n")
        
        # LEVEL 3: Meta-Learning
        if use_meta and self.meta_learner:
            logger.info("📍 LEVEL 3: Meta-Learning Pattern Injection")
            meta_result = self._enhance_with_meta_patterns(enhanced_task)
            enhanced_task = meta_result["enhanced_prompt"]
            learning_info["used_meta"] = meta_result["used"]
            learning_info["meta_patterns"] = meta_result["patterns"]
            logger.info(f"   ✅ Applied {len(meta_result['patterns'])} patterns\n")
        
        # PHASE 1 & 2: CoT + Validation (with enhanced prompt)
        logger.info("📍 PHASE 1+2: CoT Reasoning + Validation")
        if self.iteration_manager:
            solve_result = self.iteration_manager.solve_with_iteration(enhanced_task)
        else:
            logger.warning("⚠️  No iteration manager, using basic CoT")
            solve_result = {
                "answer": "No solver available",
                "final_quality": 0,
                "iterations_used": 0
            }
        logger.info(f"   ✅ Quality: {solve_result.get('final_quality', 0):.1f}/5.0")
        logger.info(f"   ✅ Iterations: {solve_result.get('iterations_used', 0)}\n")
        
        # Store in memory if successful
        if store_result and self.memory:
            logger.info("📍 Storing experience in memory")
            store_success = self._store_in_memory(task, solve_result)
            logger.info(f"   ✅ Experience stored: {store_success}\n")
        
        total_time = time.time() - start_time
        
        logger.info(f"{'='*70}")
        logger.info(f"✅ PHASE 3 COMPLETE")
        logger.info(f"{'='*70}\n")
        
        # Compile final result
        final_result = {
            "task": task,
            "answer": solve_result.get("answer", ""),
            "final_quality": solve_result.get("final_quality", 0),
            "iterations_used": solve_result.get("iterations_used", 0),
            "learning_applied": learning_info,
            "total_time": total_time,
            "phase1_result": solve_result.get("reasoning_chain", []),
            "phase2_improvements": solve_result.get("improvement", 0)
        }
        
        self.execution_log.append(final_result)
        
        return final_result
    
    def _retrieve_from_memory(self, task: str) -> Dict[str, Any]:
        """
        Retrieve similar experiences from memory.
        
        Args:
            task: Task to find similar experiences for
        
        Returns:
            Dictionary with retrieval results
        """
        try:
            similar = self.memory.retrieve_similar_experiences(task, top_k=3)
            return {
                "found": len(similar) > 0,
                "count": len(similar),
                "experiences": similar
            }
        except Exception as e:
            logger.warning(f"⚠️  Memory retrieval failed: {e}")
            return {
                "found": False,
                "count": 0,
                "experiences": []
            }
    
    def _enhance_with_few_shot(self, task: str, base_prompt: str) -> Dict[str, Any]:
        """
        Enhance prompt with few-shot examples.
        
        Args:
            task: Original task
            base_prompt: Base prompt
        
        Returns:
            Dictionary with enhancement results
        """
        try:
            result = self.few_shot_prompter.create_few_shot_prompt(
                task=task,
                base_prompt=base_prompt
            )
            return {
                "used": result["examples_found"] > 0,
                "examples_count": result["examples_found"],
                "enhanced_prompt": result["enhanced_prompt"]
            }
        except Exception as e:
            logger.warning(f"⚠️  Few-shot enhancement failed: {e}")
            return {
                "used": False,
                "examples_count": 0,
                "enhanced_prompt": base_prompt
            }
    
    def _enhance_with_meta_patterns(self, base_prompt: str) -> Dict[str, Any]:
        """
        Enhance prompt with meta-patterns.
        
        Args:
            base_prompt: Base prompt
        
        Returns:
            Dictionary with enhancement results
        """
        try:
            # Extract patterns if not done yet
            if not self.meta_learner.extracted_patterns:
                self.meta_learner.extract_meta_patterns()
            
            # Apply patterns
            result = self.meta_learner.enhance_prompt_with_patterns(
                task=base_prompt[:100],
                base_prompt=base_prompt
            )
            return {
                "used": len(result["patterns_applied"]) > 0,
                "patterns": result["patterns_applied"],
                "enhanced_prompt": result["enhanced_prompt"]
            }
        except Exception as e:
            logger.warning(f"⚠️  Meta-learning enhancement failed: {e}")
            return {
                "used": False,
                "patterns": [],
                "enhanced_prompt": base_prompt
            }
    
    def _store_in_memory(self, task: str, result: Dict) -> bool:
        """
        Store successful result in memory for future learning.
        
        Args:
            task: Original task
            result: Result dictionary from Phase 2
        
        Returns:
            Whether storage was successful
        """
        try:
            self.memory.store_experience(
                task=task,
                solution=result.get("answer", ""),
                outcome="success" if result.get("final_quality", 0) >= 3.5 else "partial",
                lesson=self._extract_lesson(task, result),
                quality=result.get("final_quality", 0)
            )
            return True
        except Exception as e:
            logger.warning(f"⚠️  Storage failed: {e}")
            return False
    
    def _extract_lesson(self, task: str, result: Dict) -> str:
        """
        Extract learning lesson from successful result.
        
        Args:
            task: Original task
            result: Result dictionary
        
        Returns:
            Extracted lesson string
        """
        quality = result.get("final_quality", 0)
        iterations = result.get("iterations_used", 0)
        
        lessons = []
        
        if quality >= 4.5:
            lessons.append("Complex analysis benefits from structured approach")
        
        if iterations == 1:
            lessons.append("Clear prompt understanding leads to first-try success")
        
        if "why" in task.lower() or "explain" in task.lower():
            lessons.append("Explanation tasks need mechanism details and examples")
        
        return "; ".join(lessons) if lessons else "Task solved successfully"
    
    def get_learning_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the learning system.
        
        Returns:
            Dictionary with learning statistics
        """
        total_tasks = len(self.execution_log)
        
        if total_tasks == 0:
            return {
                "total_tasks_solved": 0,
                "average_quality": 0,
                "learning_usage": {}
            }
        
        avg_quality = sum(
            t.get("final_quality", 0) for t in self.execution_log
        ) / total_tasks
        
        used_memory = sum(
            1 for t in self.execution_log
            if t.get("learning_applied", {}).get("used_memory", False)
        )
        
        used_few_shot = sum(
            1 for t in self.execution_log
            if t.get("learning_applied", {}).get("used_few_shot", False)
        )
        
        used_meta = sum(
            1 for t in self.execution_log
            if t.get("learning_applied", {}).get("used_meta", False)
        )
        
        return {
            "total_tasks_solved": total_tasks,
            "average_quality": avg_quality,
            "learning_usage": {
                "memory_retrieved": used_memory,
                "few_shot_used": used_few_shot,
                "meta_patterns_used": used_meta
            },
            "learning_effectiveness": {
                "memory_rate": used_memory / total_tasks if total_tasks > 0 else 0,
                "few_shot_rate": used_few_shot / total_tasks if total_tasks > 0 else 0,
                "meta_rate": used_meta / total_tasks if total_tasks > 0 else 0
            }
        }
