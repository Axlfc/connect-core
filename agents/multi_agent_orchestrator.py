"""
Phase 4: Multi-Agent Orchestrator - Complete orchestration system

This is the main Phase 4 component that orchestrates task decomposition,
agent routing, parallel execution, and result synthesis.

Combines all Phase 4 components into a unified system.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
import time

from task_decomposer import TaskDecomposer, TaskDecomposition
from agent_router import AgentRouter, TaskAgentMapping
from parallel_task_executor import ParallelTaskExecutor, TaskResult, TaskStatus
from result_synthesizer import ResultSynthesizer

logger = logging.getLogger(__name__)


class MultiAgentOrchestrator:
    """
    Main orchestration engine for Phase 4.
    
    Coordinates:
    1. Task decomposition
    2. Agent assignment
    3. Parallel execution
    4. Result synthesis
    
    Integrates all Phase 4 components plus Phase 1-3.
    """
    
    def __init__(
        self,
        phase3_integration=None,
        cot_agent=None,
        validator=None,
        decomposer: Optional[TaskDecomposer] = None,
        router: Optional[AgentRouter] = None,
        executor: Optional[ParallelTaskExecutor] = None,
        synthesizer: Optional[ResultSynthesizer] = None
    ):
        """
        Initialize MultiAgentOrchestrator.
        
        Args:
            phase3_integration: Phase3Integration for sub-task solving
            cot_agent: ChainOfThoughtAgent for reasoning
            validator: OutputValidator for quality checking
            decomposer: Custom TaskDecomposer (creates default if None)
            router: Custom AgentRouter (creates default if None)
            executor: Custom ParallelTaskExecutor (creates default if None)
            synthesizer: Custom ResultSynthesizer (creates default if None)
        """
        self.phase3_integration = phase3_integration
        self.cot_agent = cot_agent
        self.validator = validator
        
        self.decomposer = decomposer or TaskDecomposer(max_depth=2)
        self.router = router or AgentRouter()
        self.executor = executor or ParallelTaskExecutor(
            phase3_integration=phase3_integration
        )
        self.synthesizer = synthesizer or ResultSynthesizer(
            cot_agent=cot_agent,
            validator=validator
        )
        
        self.execution_log: List[Dict[str, Any]] = []
        
        logger.info("MultiAgentOrchestrator initialized")
    
    def solve(
        self,
        task: str,
        use_learning: bool = True,
        max_depth: int = 2,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Main entry point: Solve a complex task end-to-end.
        
        Process:
        1. Decompose task into sub-tasks
        2. Route sub-tasks to agents
        3. Execute in parallel
        4. Synthesize results
        5. Validate final answer
        6. Return comprehensive result
        
        Args:
            task: Main task description
            use_learning: Use Phase 3 learning
            max_depth: Max decomposition depth
            verbose: Verbose logging
        
        Returns:
            Complete solution with metrics
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 MULTI-AGENT ORCHESTRATION SYSTEM")
        logger.info(f"{'='*70}")
        logger.info(f"Task: {task[:100]}...")
        
        start_time = time.time()
        result = {
            'task': task,
            'timestamp': start_time,
            'stages': {}
        }
        
        try:
            # STAGE 1: Decomposition
            logger.info(f"\n📍 STAGE 1: Task Decomposition")
            decomposition = self._stage_decompose(task, max_depth)
            result['stages']['decomposition'] = {
                'subtasks_count': len(decomposition.subtasks),
                'complexity': decomposition.complexity,
                'execution_layers': len(decomposition.execution_layers),
                'estimated_time': decomposition.estimated_total_time
            }
            
            # STAGE 2: Agent Assignment
            logger.info(f"\n📍 STAGE 2: Agent Assignment")
            agent_assignments = self._stage_assign_agents(decomposition)
            result['stages']['assignment'] = {
                'assignments_made': len(agent_assignments),
                'agents_used': list(set(
                    a.name for a in agent_assignments.values() if a
                ))
            }
            
            # STAGE 3: Parallel Execution
            logger.info(f"\n📍 STAGE 3: Parallel Execution")
            execution_results = self._stage_execute(
                decomposition,
                use_learning
            )
            result['stages']['execution'] = {
                'completed': sum(
                    1 for r in execution_results.values()
                    if r.status == TaskStatus.COMPLETED
                ),
                'failed': sum(
                    1 for r in execution_results.values()
                    if r.status == TaskStatus.FAILED
                ),
                'total': len(execution_results)
            }
            
            # STAGE 4: Synthesis
            logger.info(f"\n📍 STAGE 4: Result Synthesis")
            final_answer = self._stage_synthesize(
                task,
                decomposition,
                execution_results
            )
            result['stages']['synthesis'] = {
                'answer_length': len(final_answer),
                'uses_all_findings': len(final_answer) > 200
            }
            
            # STAGE 5: Final Validation
            logger.info(f"\n📍 STAGE 5: Final Validation")
            final_quality = self._stage_validate(final_answer)
            result['stages']['validation'] = {
                'quality_score': final_quality,
                'passed_threshold': final_quality >= 3.5
            }
            
            # Final Result
            result['final_answer'] = final_answer
            result['final_quality'] = final_quality
            result['execution_time'] = time.time() - start_time
            result['success'] = result['stages']['validation']['passed_threshold']
            
        except Exception as e:
            logger.error(f"Orchestration failed: {str(e)}")
            result['error'] = str(e)
            result['success'] = False
            result['final_answer'] = f"Error during orchestration: {str(e)}"
            result['final_quality'] = 0.0
            result['execution_time'] = time.time() - start_time
        
        # Store in log
        self.execution_log.append(result)
        
        # Log final status
        logger.info(f"\n{'='*70}")
        logger.info(f"✅ ORCHESTRATION COMPLETE")
        logger.info(f"Quality: {result['final_quality']:.1f}/5.0")
        logger.info(f"Time: {result['execution_time']:.2f}s")
        logger.info(f"Status: {'✅ SUCCESS' if result['success'] else '❌ FAILED'}")
        logger.info(f"{'='*70}\n")
        
        return result
    
    def _stage_decompose(
        self,
        task: str,
        max_depth: int
    ) -> TaskDecomposition:
        """Stage 1: Task decomposition"""
        logger.info(f"Decomposing task (max_depth={max_depth})...")
        
        self.decomposer.max_depth = max_depth
        decomposition = self.decomposer.decompose(task)
        
        logger.info(
            f"✅ Decomposed into {len(decomposition.subtasks)} subtasks "
            f"in {len(decomposition.execution_layers)} layers"
        )
        
        for i, st in enumerate(decomposition.subtasks[:3], 1):
            logger.debug(f"  {i}. {st.description[:60]}...")
        
        return decomposition
    
    def _stage_assign_agents(
        self,
        decomposition: TaskDecomposition
    ) -> Dict[int, Any]:
        """Stage 2: Assign agents to subtasks"""
        logger.info("Assigning agents to subtasks...")
        
        assignments = TaskAgentMapping()
        
        for subtask in decomposition.subtasks:
            agent = self.router.select_best_agent(
                subtask.task_type,
                subtask.complexity
            )
            
            if agent:
                assignments.add_mapping(subtask.id, agent)
                logger.debug(f"  {subtask.id} → {agent.name}")
            else:
                logger.warning(f"  ⚠️ No suitable agent for {subtask.id}")
        
        logger.info(f"✅ Assigned {len(assignments.mappings)} agents")
        return assignments.mappings
    
    def _stage_execute(
        self,
        decomposition: TaskDecomposition,
        use_learning: bool
    ) -> Dict[str, TaskResult]:
        """Stage 3: Parallel execution"""
        logger.info("Starting parallel execution...")
        
        # Run async execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            execution_results = loop.run_until_complete(
                self.executor.execute_all(
                    decomposition.subtasks,
                    decomposition.execution_layers,
                    use_learning=use_learning
                )
            )
        finally:
            loop.close()
        
        # Log results
        completed = sum(
            1 for r in execution_results.values()
            if r.status == TaskStatus.COMPLETED
        )
        
        logger.info(
            f"✅ Execution complete: {completed}/{len(execution_results)} succeeded"
        )
        
        return execution_results
    
    def _stage_synthesize(
        self,
        task: str,
        decomposition: TaskDecomposition,
        execution_results: Dict[str, TaskResult]
    ) -> str:
        """Stage 4: Synthesis"""
        logger.info("Synthesizing results...")
        
        # Create task descriptions map
        task_descriptions = {
            st.id: st.description
            for st in decomposition.subtasks
        }
        
        # Synthesize
        final_answer = self.synthesizer.synthesize(
            task,
            execution_results,
            task_descriptions
        )
        
        logger.info(f"✅ Synthesis complete ({len(final_answer)} chars)")
        return final_answer
    
    def _stage_validate(self, answer: str) -> float:
        """Stage 5: Final validation"""
        logger.info("Validating final answer...")
        
        if self.validator:
            validation_result = self.validator.evaluate(
                task="Validate orchestration result",
                answer=answer
            )
            quality = validation_result.get('overall_score', 3.5)
        else:
            # Fallback scoring
            quality = min(5.0, len(answer) / 200)  # Rough estimate
        
        logger.info(f"✅ Validation: {quality:.1f}/5.0")
        return quality
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics from execution log"""
        if not self.execution_log:
            return {'executions': 0}
        
        successful = sum(1 for r in self.execution_log if r.get('success'))
        avg_quality = sum(
            r.get('final_quality', 0) for r in self.execution_log
        ) / len(self.execution_log) if self.execution_log else 0
        
        avg_time = sum(
            r.get('execution_time', 0) for r in self.execution_log
        ) / len(self.execution_log) if self.execution_log else 0
        
        return {
            'total_executions': len(self.execution_log),
            'successful_executions': successful,
            'success_rate': successful / len(self.execution_log) if self.execution_log else 0,
            'average_quality': avg_quality,
            'average_execution_time': avg_time
        }
