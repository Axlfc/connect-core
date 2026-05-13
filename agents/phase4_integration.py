"""
Phase 4 Integration: Integration with Phases 1-3

This module integrates Phase 4 (multi-agent orchestration) with
Phase 1 (chain of thought), Phase 2 (validation), and Phase 3 (learning).

The orchestrator uses Phase 1-3 for individual task solving while
coordinating across multiple agents.
"""

import logging
from typing import Optional, Dict, Any

# Import Phase 1-3 components (would be actual imports in practice)
from phase1_integration import ChainOfThoughtIntegration
from phase2_integration import ValidationIntegration  
from phase3_integration import Phase3Integration
from multi_agent_orchestrator import MultiAgentOrchestrator

logger = logging.getLogger(__name__)


class Phase4Integration:
    """
    Complete Phase 4 integration system.
    
    Combines:
    - Phase 1: Chain of thought reasoning
    - Phase 2: Output validation
    - Phase 3: Few-shot learning
    - Phase 4: Multi-agent orchestration
    
    The orchestrator delegates individual task solving to Phase 3,
    which internally uses Phase 1 and Phase 2 as needed.
    """
    
    def __init__(
        self,
        phase1_integration: Optional[ChainOfThoughtIntegration] = None,
        phase2_integration: Optional[ValidationIntegration] = None,
        phase3_integration: Optional[Phase3Integration] = None
    ):
        """
        Initialize Phase 4 Integration.
        
        Args:
            phase1_integration: Chain of thought agent
            phase2_integration: Validation system
            phase3_integration: Few-shot learning system
        """
        self.phase1 = phase1_integration or ChainOfThoughtIntegration()
        self.phase2 = phase2_integration or ValidationIntegration()
        self.phase3 = phase3_integration or Phase3Integration(
            cot_agent=self.phase1.agent,
            validator=self.phase2.validator
        )
        
        # Initialize Phase 4 orchestrator with Phase 1-3
        self.orchestrator = MultiAgentOrchestrator(
            phase3_integration=self.phase3,
            cot_agent=self.phase1.agent,
            validator=self.phase2.validator
        )
        
        logger.info("Phase 4 Integration initialized (Phases 1-3 loaded)")
    
    def solve_complex_task(
        self,
        task: str,
        difficulty: str = "medium",
        use_learning: bool = True,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Solve a complex task using multi-agent orchestration.
        
        This is the main method that coordinates all 4 phases:
        1. Phase 1: Reason about the task
        2. Phase 2: Validate intermediate results
        3. Phase 3: Learn from examples if needed
        4. Phase 4: Orchestrate multiple agents
        
        Args:
            task: Complex task to solve
            difficulty: "easy", "medium", or "hard"
            use_learning: Whether to use Phase 3 learning
            verbose: Verbose logging
        
        Returns:
            Comprehensive solution result
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🎯 SOLVING COMPLEX TASK (Difficulty: {difficulty})")
        logger.info(f"{'='*70}")
        logger.info(f"Task: {task[:100]}...")
        
        # Determine decomposition depth based on difficulty
        max_depth = {
            'easy': 1,
            'medium': 2,
            'hard': 3
        }.get(difficulty, 2)
        
        # Use orchestrator to solve
        result = self.orchestrator.solve(
            task=task,
            use_learning=use_learning,
            max_depth=max_depth,
            verbose=verbose
        )
        
        # Enhance result with phase information
        result['phases_used'] = [1, 2, 3, 4]
        result['difficulty'] = difficulty
        
        return result
    
    def batch_solve(
        self,
        tasks: list,
        parallel: bool = False
    ) -> list:
        """
        Solve multiple tasks.
        
        Args:
            tasks: List of task descriptions
            parallel: Execute tasks in parallel (experimental)
        
        Returns:
            List of results
        """
        logger.info(f"Solving {len(tasks)} tasks...")
        
        results = []
        for i, task in enumerate(tasks, 1):
            logger.info(f"\nTask {i}/{len(tasks)}...")
            result = self.orchestrator.solve(task)
            results.append(result)
        
        return results
    
    def get_phase_statistics(self) -> Dict[str, Any]:
        """Get statistics across all phases"""
        return {
            'phase1': self.phase1.get_statistics() if hasattr(self.phase1, 'get_statistics') else {},
            'phase2': self.phase2.get_statistics() if hasattr(self.phase2, 'get_statistics') else {},
            'phase3': self.phase3.get_statistics() if hasattr(self.phase3, 'get_statistics') else {},
            'phase4': self.orchestrator.get_statistics()
        }
    
    def benchmark(self, test_tasks: list) -> Dict[str, Any]:
        """
        Run benchmark on test tasks.
        
        Args:
            test_tasks: List of test task descriptions
        
        Returns:
            Benchmark results
        """
        logger.info(f"\n🏃 BENCHMARKING ({len(test_tasks)} tasks)...")
        
        import time
        
        start_time = time.time()
        results = self.batch_solve(test_tasks)
        total_time = time.time() - start_time
        
        successful = sum(1 for r in results if r.get('success'))
        avg_quality = sum(
            r.get('final_quality', 0) for r in results
        ) / len(results) if results else 0
        
        benchmark_result = {
            'total_tasks': len(test_tasks),
            'successful': successful,
            'success_rate': successful / len(test_tasks) if test_tasks else 0,
            'average_quality': avg_quality,
            'total_time': total_time,
            'avg_time_per_task': total_time / len(test_tasks) if test_tasks else 0,
            'tasks_per_second': len(test_tasks) / total_time if total_time > 0 else 0
        }
        
        logger.info(f"\n📊 BENCHMARK RESULTS:")
        logger.info(f"  Success Rate: {benchmark_result['success_rate']*100:.1f}%")
        logger.info(f"  Avg Quality: {avg_quality:.1f}/5.0")
        logger.info(f"  Throughput: {benchmark_result['tasks_per_second']:.2f} tasks/sec")
        
        return benchmark_result
    
    def get_insights(self) -> Dict[str, Any]:
        """
        Get insights about the system's performance and behavior.
        
        Returns:
            System insights
        """
        stats = self.get_phase_statistics()
        
        insights = {
            'system_health': 'operational',
            'total_tasks_processed': self.orchestrator.execution_log.__len__(),
            'phase_contributions': {
                'phase1': 'Reasoning and chain of thought',
                'phase2': 'Quality validation',
                'phase3': 'Learning from examples',
                'phase4': 'Multi-agent orchestration'
            },
            'statistics': stats
        }
        
        return insights
