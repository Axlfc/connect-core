"""
Phase 4: Parallel Task Executor - Execute tasks in parallel respecting dependencies

This module handles asyncio-based parallel execution of sub-tasks with
dependency management, timeout handling, and error recovery.

Key Features:
  - Asyncio-based parallel execution
  - Dependency-aware task scheduling
  - Timeout management
  - Error handling and recovery
  - Progress tracking
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
import uuid

from phase3_integration import Phase3Integration
from agent_router import Agent, TaskType
from task_decomposer import SubTask

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a task during execution"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    TIMEOUT = "timeout"


@dataclass
class TaskResult:
    """Result of executing a task"""
    task_id: str
    status: TaskStatus
    result: Optional[str] = None
    quality_score: Optional[float] = None
    execution_time: float = 0.0
    error: Optional[str] = None
    retry_count: int = 0
    agent_used: Optional[str] = None
    iterations_used: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'task_id': self.task_id,
            'status': self.status.value,
            'result': self.result,
            'quality_score': self.quality_score,
            'execution_time': self.execution_time,
            'error': self.error,
            'retry_count': self.retry_count,
            'agent_used': self.agent_used,
            'iterations_used': self.iterations_used
        }


@dataclass
class ExecutionState:
    """State of parallel execution"""
    total_tasks: int
    completed_tasks: int = 0
    failed_tasks: int = 0
    in_progress_tasks: int = 0
    results: Dict[str, TaskResult] = field(default_factory=dict)
    execution_start_time: float = 0.0
    execution_end_time: Optional[float] = None
    
    @property
    def progress(self) -> float:
        """Get progress percentage"""
        if self.total_tasks == 0:
            return 100.0
        return (self.completed_tasks + self.failed_tasks) / self.total_tasks * 100
    
    @property
    def execution_time(self) -> float:
        """Get total execution time"""
        if self.execution_end_time is None:
            return time.time() - self.execution_start_time
        return self.execution_end_time - self.execution_start_time


class ParallelTaskExecutor:
    """
    Executes sub-tasks in parallel with dependency management.
    
    Uses asyncio to parallelize execution while respecting task dependencies.
    Automatically manages retries and timeouts.
    """
    
    def __init__(
        self,
        phase3_integration: Optional[Phase3Integration] = None,
        timeout_seconds: float = 300.0,
        max_retries: int = 2
    ):
        """
        Initialize ParallelTaskExecutor.
        
        Args:
            phase3_integration: Phase3Integration instance for solving subtasks
            timeout_seconds: Timeout for each task
            max_retries: Maximum retries per task
        """
        self.phase3_integration = phase3_integration
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.execution_state: Optional[ExecutionState] = None
        
        logger.info(
            f"ParallelTaskExecutor initialized "
            f"(timeout={timeout_seconds}s, max_retries={max_retries})"
        )
    
    async def execute_all(
        self,
        subtasks: List[SubTask],
        execution_layers: List[List[str]],
        use_learning: bool = True
    ) -> Dict[str, TaskResult]:
        """
        Execute all sub-tasks respecting dependencies.
        
        Args:
            subtasks: List of SubTask objects
            execution_layers: Execution order (list of task ID groups)
            use_learning: Whether to use Phase 3 learning
        
        Returns:
            Dictionary mapping task_id to TaskResult
        """
        logger.info(
            f"Starting parallel execution of {len(subtasks)} tasks "
            f"in {len(execution_layers)} layers"
        )
        
        # Initialize execution state
        self.execution_state = ExecutionState(
            total_tasks=len(subtasks),
            execution_start_time=time.time()
        )
        
        # Create task map for quick lookup
        task_map = {st.id: st for st in subtasks}
        results: Dict[str, TaskResult] = {}
        
        # Execute layer by layer
        for layer_idx, layer_task_ids in enumerate(execution_layers):
            logger.info(
                f"Executing layer {layer_idx + 1}/{len(execution_layers)} "
                f"({len(layer_task_ids)} tasks)"
            )
            
            # Create tasks for this layer
            layer_tasks = [
                self._execute_single_task(
                    task_map[task_id],
                    use_learning
                )
                for task_id in layer_task_ids
            ]
            
            # Execute layer tasks in parallel
            layer_results = await asyncio.gather(
                *layer_tasks,
                return_exceptions=True
            )
            
            # Process results
            for task_id, result_or_error in zip(layer_task_ids, layer_results):
                if isinstance(result_or_error, Exception):
                    results[task_id] = TaskResult(
                        task_id=task_id,
                        status=TaskStatus.FAILED,
                        error=str(result_or_error)
                    )
                else:
                    results[task_id] = result_or_error
                
                # Update execution state
                if results[task_id].status == TaskStatus.COMPLETED:
                    self.execution_state.completed_tasks += 1
                elif results[task_id].status == TaskStatus.FAILED:
                    self.execution_state.failed_tasks += 1
        
        # Finalize execution state
        self.execution_state.results = results
        self.execution_state.execution_end_time = time.time()
        
        logger.info(
            f"Execution complete: {self.execution_state.completed_tasks} "
            f"succeeded, {self.execution_state.failed_tasks} failed "
            f"({self.execution_state.execution_time:.2f}s total)"
        )
        
        return results
    
    async def _execute_single_task(
        self,
        subtask: SubTask,
        use_learning: bool = True,
        retry_count: int = 0
    ) -> TaskResult:
        """
        Execute a single sub-task with timeout and retry.
        
        Args:
            subtask: SubTask to execute
            use_learning: Whether to use learning
            retry_count: Current retry count
        
        Returns:
            TaskResult
        """
        logger.debug(f"Executing task: {subtask.id} - {subtask.description[:50]}...")
        
        result = TaskResult(task_id=subtask.id)
        start_time = time.time()
        
        try:
            # Execute with timeout
            if self.phase3_integration is not None:
                result_dict = await asyncio.wait_for(
                    self._execute_with_phase3(subtask, use_learning),
                    timeout=self.timeout_seconds
                )
                result.result = result_dict.get('answer')
                result.quality_score = result_dict.get('final_quality', 0.0)
                result.iterations_used = result_dict.get('iterations_used', 1)
            else:
                # Fallback: return dummy result
                result.result = f"Mock result for {subtask.description}"
                result.quality_score = 3.5
            
            result.status = TaskStatus.COMPLETED
            
        except asyncio.TimeoutError:
            logger.warning(f"Task {subtask.id} timed out")
            result.status = TaskStatus.TIMEOUT
            result.error = f"Timeout after {self.timeout_seconds}s"
            
            # Retry if possible
            if retry_count < self.max_retries:
                logger.info(f"Retrying task {subtask.id} (attempt {retry_count + 1})")
                result.status = TaskStatus.RETRYING
                return await self._execute_single_task(
                    subtask,
                    use_learning,
                    retry_count + 1
                )
        
        except Exception as e:
            logger.error(f"Task {subtask.id} failed: {str(e)}")
            result.status = TaskStatus.FAILED
            result.error = str(e)
            
            # Retry on other errors
            if retry_count < self.max_retries:
                logger.info(f"Retrying task {subtask.id} (attempt {retry_count + 1})")
                result.status = TaskStatus.RETRYING
                await asyncio.sleep(1.0)  # Wait before retry
                return await self._execute_single_task(
                    subtask,
                    use_learning,
                    retry_count + 1
                )
        
        finally:
            result.execution_time = time.time() - start_time
            result.retry_count = retry_count
        
        return result
    
    async def _execute_with_phase3(
        self,
        subtask: SubTask,
        use_learning: bool
    ) -> Dict[str, Any]:
        """
        Execute task using Phase 3 integration.
        
        Args:
            subtask: SubTask to execute
            use_learning: Whether to use learning
        
        Returns:
            Result dictionary from Phase3Integration
        """
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.phase3_integration.solve_with_learning(
                subtask.description,
                use_memory=use_learning,
                use_few_shot=use_learning,
                use_meta=use_learning,
                store_result=use_learning
            )
        )
    
    def resolve_dependencies(
        self,
        subtasks: List[SubTask]
    ) -> List[List[str]]:
        """
        Resolve dependencies into execution layers.
        
        Args:
            subtasks: List of SubTask objects
        
        Returns:
            List of task ID lists representing execution layers
        """
        logger.debug("Resolving task dependencies")
        
        layers: List[List[str]] = []
        assigned: set = set()
        
        while len(assigned) < len(subtasks):
            current_layer: List[str] = []
            
            for subtask in subtasks:
                if subtask.id in assigned:
                    continue
                
                # Check if all dependencies are assigned
                all_deps_assigned = all(
                    dep_id in assigned
                    for dep_id in subtask.dependencies
                )
                
                if all_deps_assigned:
                    current_layer.append(subtask.id)
                    assigned.add(subtask.id)
            
            if current_layer:
                layers.append(current_layer)
            else:
                # Circular dependency detected
                logger.warning("Circular dependencies detected")
                break
        
        logger.info(f"Resolved to {len(layers)} execution layers")
        return layers
    
    def get_execution_progress(self) -> Dict[str, Any]:
        """Get current execution progress"""
        if self.execution_state is None:
            return {
                'progress': 0.0,
                'completed': 0,
                'failed': 0,
                'total': 0
            }
        
        return {
            'progress': self.execution_state.progress,
            'completed': self.execution_state.completed_tasks,
            'failed': self.execution_state.failed_tasks,
            'total': self.execution_state.total_tasks,
            'execution_time': self.execution_state.execution_time
        }
    
    def get_results_summary(self) -> Dict[str, Any]:
        """Get summary of execution results"""
        if self.execution_state is None:
            return {}
        
        results = self.execution_state.results
        successful = [r for r in results.values() if r.status == TaskStatus.COMPLETED]
        failed = [r for r in results.values() if r.status == TaskStatus.FAILED]
        
        avg_quality = (
            sum(r.quality_score for r in successful if r.quality_score)
            / len(successful)
            if successful else 0.0
        )
        
        return {
            'total_tasks': self.execution_state.total_tasks,
            'successful': len(successful),
            'failed': len(failed),
            'average_quality': avg_quality,
            'total_execution_time': self.execution_state.execution_time,
            'average_time_per_task': (
                self.execution_state.execution_time / self.execution_state.total_tasks
                if self.execution_state.total_tasks > 0 else 0.0
            )
        }
