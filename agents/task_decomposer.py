"""
Phase 4: Task Decomposer - Break down complex tasks into manageable sub-tasks

This module handles automatic decomposition of complex tasks into structured
sub-tasks with dependencies, complexity estimates, and type classification.

Key Features:
  - Recursive task decomposition (1-3 levels)
  - Automatic dependency identification
  - Complexity estimation
  - Task type classification
  - Priority assignment
"""

import logging
import json
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import re

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of tasks for routing to appropriate agents"""
    ANALYSIS = "analysis"
    RESEARCH = "research"
    CODE = "code"
    CREATIVE = "creative"
    SYNTHESIS = "synthesis"
    EVALUATION = "evaluation"
    PLANNING = "planning"
    IMPLEMENTATION = "implementation"


@dataclass
class SubTask:
    """Represents a single sub-task"""
    id: str
    description: str
    task_type: TaskType
    complexity: int  # 1-10
    priority: int  # 1-5
    dependencies: List[str] = field(default_factory=list)
    estimated_time: float = 1.0  # minutes
    parent_task_id: Optional[str] = None
    depth: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['task_type'] = self.task_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SubTask':
        """Create from dictionary"""
        data = data.copy()
        data['task_type'] = TaskType(data.get('task_type', 'analysis'))
        return cls(**data)


@dataclass
class TaskDecomposition:
    """Result of task decomposition"""
    main_task: str
    main_task_type: TaskType
    complexity: int
    subtasks: List[SubTask]
    execution_layers: List[List[str]]  # Groups of tasks that can run in parallel
    estimated_total_time: float  # minutes
    decomposition_depth: int


class TaskDecomposer:
    """
    Decomposes complex tasks into manageable sub-tasks.
    
    Uses keyword analysis and heuristics to identify task structure,
    determine dependencies, and estimate complexity.
    """
    
    # Keywords for task type classification
    TASK_TYPE_KEYWORDS = {
        TaskType.ANALYSIS: [
            'analyze', 'examine', 'compare', 'evaluate', 'assess',
            'review', 'check', 'verify', 'validate', 'inspect'
        ],
        TaskType.RESEARCH: [
            'research', 'investigate', 'explore', 'find', 'discover',
            'search', 'gather', 'collect', 'survey', 'study'
        ],
        TaskType.CODE: [
            'code', 'program', 'implement', 'build', 'develop',
            'algorithm', 'function', 'script', 'refactor', 'optimize'
        ],
        TaskType.CREATIVE: [
            'create', 'generate', 'write', 'design', 'invent',
            'imagine', 'brainstorm', 'ideate', 'compose', 'author'
        ],
        TaskType.SYNTHESIS: [
            'combine', 'synthesize', 'integrate', 'merge', 'unite',
            'consolidate', 'summarize', 'compile', 'aggregate'
        ],
        TaskType.EVALUATION: [
            'evaluate', 'judge', 'rate', 'score', 'rank',
            'assess', 'determine', 'decide', 'conclude'
        ],
        TaskType.PLANNING: [
            'plan', 'schedule', 'organize', 'arrange', 'coordinate',
            'prepare', 'strategize', 'outline', 'design'
        ],
        TaskType.IMPLEMENTATION: [
            'implement', 'execute', 'perform', 'apply', 'use',
            'deploy', 'launch', 'run', 'conduct'
        ]
    }
    
    # Complexity estimation patterns
    COMPLEXITY_INDICATORS = {
        'multi-part': 3,
        'complex': 2,
        'difficult': 2,
        'advanced': 2,
        'and': 1,
        'then': 1,
        'first': 1,
        'next': 1,
        'integration': 3,
        'optimization': 2,
        'analysis': 2
    }
    
    def __init__(self, max_depth: int = 3):
        """
        Initialize TaskDecomposer.
        
        Args:
            max_depth: Maximum decomposition depth (1-3)
        """
        self.max_depth = min(max_depth, 3)
        logger.info(f"TaskDecomposer initialized with max_depth={self.max_depth}")
    
    def decompose(
        self,
        task: str,
        depth: int = 1,
        parent_task_id: Optional[str] = None
    ) -> TaskDecomposition:
        """
        Decompose a complex task into sub-tasks.
        
        Args:
            task: The main task description
            depth: Current decomposition depth
            parent_task_id: ID of parent task (for recursive calls)
        
        Returns:
            TaskDecomposition with sub-tasks and execution plan
        """
        logger.info(f"Decomposing task (depth={depth}): {task[:100]}...")
        
        # Classify main task
        main_task_type = self._classify_task(task)
        main_complexity = self._estimate_complexity(task)
        
        # Generate initial sub-tasks
        subtasks = self._generate_subtasks(
            task,
            main_task_type,
            parent_task_id=parent_task_id
        )
        
        # Recursively decompose if needed
        if depth < self.max_depth and len(subtasks) > 0:
            expanded_subtasks = []
            for subtask in subtasks:
                # Only decompose complex tasks
                if subtask.complexity >= 5:
                    logger.debug(f"Further decomposing subtask: {subtask.id}")
                    sub_decomposition = self.decompose(
                        subtask.description,
                        depth=depth + 1,
                        parent_task_id=subtask.id
                    )
                    # Keep the original subtask but mark as has children
                    subtask.depth = depth
                    expanded_subtasks.append(subtask)
                    # Add all sub-subtasks
                    expanded_subtasks.extend(sub_decomposition.subtasks)
                else:
                    subtask.depth = depth
                    expanded_subtasks.append(subtask)
            subtasks = expanded_subtasks
        
        # Identify dependencies
        dependencies = self._identify_dependencies(subtasks, task)
        for subtask in subtasks:
            if subtask.id in dependencies:
                subtask.dependencies = dependencies[subtask.id]
        
        # Create execution layers (dependency-aware)
        execution_layers = self._create_execution_layers(subtasks)
        
        # Estimate total time
        total_time = sum(st.estimated_time for st in subtasks)
        
        result = TaskDecomposition(
            main_task=task,
            main_task_type=main_task_type,
            complexity=main_complexity,
            subtasks=subtasks,
            execution_layers=execution_layers,
            estimated_total_time=total_time,
            decomposition_depth=depth
        )
        
        logger.info(
            f"Decomposition complete: {len(subtasks)} subtasks, "
            f"{len(execution_layers)} execution layers"
        )
        
        return result
    
    def _classify_task(self, task: str) -> TaskType:
        """Classify task type by keyword matching"""
        task_lower = task.lower()
        
        # Check each task type's keywords
        for task_type, keywords in self.TASK_TYPE_KEYWORDS.items():
            if any(keyword in task_lower for keyword in keywords):
                logger.debug(f"Classified task as: {task_type.value}")
                return task_type
        
        # Default to analysis
        return TaskType.ANALYSIS
    
    def _estimate_complexity(self, task: str) -> int:
        """
        Estimate task complexity (1-10).
        
        Uses keyword matching, length, and task type indicators.
        """
        complexity = 1
        task_lower = task.lower()
        
        # Base complexity from indicators
        for indicator, weight in self.COMPLEXITY_INDICATORS.items():
            if indicator in task_lower:
                complexity += weight
        
        # Length-based adjustment
        words = len(task.split())
        if words > 50:
            complexity += 3
        elif words > 30:
            complexity += 2
        elif words > 20:
            complexity += 1
        
        # Clamp to 1-10
        complexity = max(1, min(10, complexity))
        logger.debug(f"Estimated complexity: {complexity}")
        return complexity
    
    def _generate_subtasks(
        self,
        task: str,
        task_type: TaskType,
        parent_task_id: Optional[str] = None,
        num_subtasks: int = 3
    ) -> List[SubTask]:
        """Generate initial set of sub-tasks"""
        subtasks = []
        
        # Use task type to guide decomposition
        if task_type == TaskType.ANALYSIS:
            subtask_descriptions = [
                f"Identify key aspects of: {task}",
                f"Analyze each aspect in detail",
                f"Synthesize findings into comprehensive analysis"
            ]
        elif task_type == TaskType.RESEARCH:
            subtask_descriptions = [
                f"Search for relevant information about: {task}",
                f"Gather and compile findings",
                f"Summarize research results"
            ]
        elif task_type == TaskType.CODE:
            subtask_descriptions = [
                f"Design solution for: {task}",
                f"Implement the code",
                f"Test and optimize"
            ]
        elif task_type == TaskType.CREATIVE:
            subtask_descriptions = [
                f"Brainstorm ideas for: {task}",
                f"Develop selected ideas",
                f"Polish and finalize creative output"
            ]
        else:
            # Default decomposition
            subtask_descriptions = [
                f"Prepare for: {task}",
                f"Execute main work",
                f"Review and finalize"
            ]
        
        # Create sub-tasks
        for i, description in enumerate(subtask_descriptions[:num_subtasks]):
            subtask_id = f"{parent_task_id}_st{i+1}" if parent_task_id else f"st_{i+1}"
            subtask_type = self._classify_task(description)
            complexity = self._estimate_complexity(description)
            
            subtask = SubTask(
                id=subtask_id,
                description=description,
                task_type=subtask_type,
                complexity=complexity,
                priority=5 - i,  # First task has higher priority
                parent_task_id=parent_task_id,
                estimated_time=2.0 + complexity * 0.5
            )
            subtasks.append(subtask)
            logger.debug(f"Generated subtask: {subtask_id} - {description[:50]}...")
        
        return subtasks
    
    def _identify_dependencies(
        self,
        subtasks: List[SubTask],
        main_task: str
    ) -> Dict[str, List[str]]:
        """
        Identify dependencies between subtasks.
        
        Uses heuristics like "first", "then", "after", "before".
        """
        dependencies: Dict[str, List[str]] = {}
        task_lower = main_task.lower()
        
        # Find ordering keywords
        ordering_keywords = {
            'first': 0,
            'then': 1,
            'next': 1,
            'after': 1,
            'before': -1,
            'finally': 2
        }
        
        # By default, each subtask depends on the previous one
        # except the first one
        for i, subtask in enumerate(subtasks):
            if i > 0:
                # Check if there are explicit dependencies
                dependencies[subtask.id] = [subtasks[i-1].id]
            else:
                dependencies[subtask.id] = []
        
        logger.debug(f"Identified {len(dependencies)} task dependencies")
        return dependencies
    
    def _create_execution_layers(
        self,
        subtasks: List[SubTask]
    ) -> List[List[str]]:
        """
        Create execution layers based on dependencies.
        
        Tasks with no dependencies run in layer 0.
        Tasks depending only on layer 0 tasks run in layer 1, etc.
        """
        layers: List[List[str]] = []
        assigned: Set[str] = set()
        
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
                # Break circular dependencies (shouldn't happen)
                break
        
        logger.debug(f"Created {len(layers)} execution layers")
        return layers
    
    def to_dict(self, decomposition: TaskDecomposition) -> Dict[str, Any]:
        """Convert decomposition to dictionary"""
        return {
            'main_task': decomposition.main_task,
            'main_task_type': decomposition.main_task_type.value,
            'complexity': decomposition.complexity,
            'subtasks': [st.to_dict() for st in decomposition.subtasks],
            'execution_layers': decomposition.execution_layers,
            'estimated_total_time': decomposition.estimated_total_time,
            'decomposition_depth': decomposition.decomposition_depth
        }
    
    def from_dict(self, data: Dict[str, Any]) -> TaskDecomposition:
        """Create decomposition from dictionary"""
        return TaskDecomposition(
            main_task=data['main_task'],
            main_task_type=TaskType(data.get('main_task_type', 'analysis')),
            complexity=data['complexity'],
            subtasks=[
                SubTask.from_dict(st) for st in data['subtasks']
            ],
            execution_layers=data['execution_layers'],
            estimated_total_time=data['estimated_total_time'],
            decomposition_depth=data['decomposition_depth']
        )
