"""
Phase 4: Agent Router - Routes tasks to appropriate specialized agents

This module handles task classification and agent selection based on
task type, complexity, and agent capabilities.

Key Features:
  - Automatic task type classification
  - Intelligent agent selection
  - Load balancing across agents
  - Capability matching
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field

from task_decomposer import TaskType

logger = logging.getLogger(__name__)


class AgentCapability(Enum):
    """Capabilities that agents can have"""
    ANALYSIS = "analysis"
    RESEARCH = "research"
    CODE_GENERATION = "code_generation"
    CREATIVE = "creative"
    SYNTHESIS = "synthesis"
    EVALUATION = "evaluation"


@dataclass
class Agent:
    """Represents an AI agent with specific capabilities"""
    name: str
    agent_type: str
    capabilities: List[AgentCapability]
    max_complexity: int  # Maximum complexity it can handle (1-10)
    current_load: int = 0
    success_rate: float = 0.95  # Historical success rate
    
    def can_handle(self, task_type: TaskType, complexity: int) -> bool:
        """Check if agent can handle the task"""
        # Check complexity
        if complexity > self.max_complexity:
            return False
        
        # Check capability match
        capability_map = {
            TaskType.ANALYSIS: AgentCapability.ANALYSIS,
            TaskType.RESEARCH: AgentCapability.RESEARCH,
            TaskType.CODE: AgentCapability.CODE_GENERATION,
            TaskType.CREATIVE: AgentCapability.CREATIVE,
            TaskType.SYNTHESIS: AgentCapability.SYNTHESIS,
            TaskType.EVALUATION: AgentCapability.EVALUATION,
        }
        
        required_capability = capability_map.get(task_type, AgentCapability.ANALYSIS)
        return required_capability in self.capabilities
    
    def get_load_score(self) -> float:
        """Get current load score (0-1, higher = busier)"""
        return self.current_load / 100.0  # Assume max 100 tasks per agent
    
    def add_load(self, amount: int = 1):
        """Add load to agent"""
        self.current_load += amount
    
    def remove_load(self, amount: int = 1):
        """Remove load from agent"""
        self.current_load = max(0, self.current_load - amount)


class AgentRegistry:
    """Registry of available agents"""
    
    def __init__(self):
        """Initialize with default agents"""
        self.agents: Dict[str, Agent] = {}
        self._setup_default_agents()
    
    def _setup_default_agents(self):
        """Setup default agent pool"""
        # Analytic Agent - for analysis tasks
        self.agents['analytic'] = Agent(
            name='AnalyticAgent',
            agent_type='analytic',
            capabilities=[
                AgentCapability.ANALYSIS,
                AgentCapability.EVALUATION
            ],
            max_complexity=8,
            success_rate=0.96
        )
        
        # Research Agent - for research tasks
        self.agents['research'] = Agent(
            name='ResearchAgent',
            agent_type='research',
            capabilities=[
                AgentCapability.RESEARCH,
                AgentCapability.ANALYSIS
            ],
            max_complexity=7,
            success_rate=0.94
        )
        
        # Code Agent - for coding tasks
        self.agents['code'] = Agent(
            name='CodeAgent',
            agent_type='code',
            capabilities=[
                AgentCapability.CODE_GENERATION,
                AgentCapability.ANALYSIS
            ],
            max_complexity=9,
            success_rate=0.93
        )
        
        # Creative Agent - for creative tasks
        self.agents['creative'] = Agent(
            name='CreativeAgent',
            agent_type='creative',
            capabilities=[
                AgentCapability.CREATIVE,
                AgentCapability.ANALYSIS
            ],
            max_complexity=6,
            success_rate=0.95
        )
        
        # Synthesis Agent - for combining results
        self.agents['synthesis'] = Agent(
            name='SynthesisAgent',
            agent_type='synthesis',
            capabilities=[
                AgentCapability.SYNTHESIS,
                AgentCapability.EVALUATION,
                AgentCapability.ANALYSIS
            ],
            max_complexity=7,
            success_rate=0.97
        )
        
        logger.info(f"Initialized {len(self.agents)} default agents")
    
    def get_agent(self, agent_type: str) -> Optional[Agent]:
        """Get agent by type"""
        return self.agents.get(agent_type)
    
    def list_agents(self) -> List[Agent]:
        """List all agents"""
        return list(self.agents.values())
    
    def add_agent(self, agent: Agent):
        """Add custom agent"""
        self.agents[agent.agent_type] = agent
        logger.info(f"Added agent: {agent.name}")


class AgentRouter:
    """
    Routes tasks to appropriate agents based on task characteristics.
    
    Uses intelligent matching of task requirements to agent capabilities,
    with load balancing to distribute work evenly.
    """
    
    def __init__(self, registry: Optional[AgentRegistry] = None):
        """
        Initialize AgentRouter.
        
        Args:
            registry: Optional AgentRegistry. Creates default if not provided.
        """
        self.registry = registry or AgentRegistry()
        logger.info("AgentRouter initialized")
    
    def select_best_agent(
        self,
        task_type: TaskType,
        complexity: int,
        preferences: Optional[List[str]] = None
    ) -> Optional[Agent]:
        """
        Select the best agent for a task.
        
        Selection criteria (in order):
        1. Can handle the task (capability + complexity)
        2. Lowest current load
        3. Highest historical success rate
        
        Args:
            task_type: Type of task
            complexity: Complexity level (1-10)
            preferences: Preferred agent types (in order)
        
        Returns:
            Selected Agent, or None if no suitable agent found
        """
        logger.debug(
            f"Selecting agent for {task_type.value} task "
            f"(complexity={complexity})"
        )
        
        # Get candidates
        candidates: List[Tuple[Agent, float]] = []
        
        # First, check preferences
        if preferences:
            for pref in preferences:
                agent = self.registry.get_agent(pref)
                if agent and agent.can_handle(task_type, complexity):
                    logger.debug(f"Found preferred agent: {agent.name}")
                    return agent
        
        # Then, find all capable agents
        for agent in self.registry.list_agents():
            if agent.can_handle(task_type, complexity):
                # Calculate score: lower is better
                # Lower load is better, higher success rate is better
                score = (
                    agent.get_load_score() * 0.7 +  # 70% weight on load
                    (1 - agent.success_rate) * 0.3   # 30% weight on success rate
                )
                candidates.append((agent, score))
        
        if not candidates:
            logger.warning(
                f"No suitable agent found for {task_type.value} "
                f"(complexity={complexity})"
            )
            return None
        
        # Select agent with lowest score
        best_agent = min(candidates, key=lambda x: x[1])[0]
        logger.info(f"Selected agent: {best_agent.name}")
        return best_agent
    
    def select_agents_for_tasks(
        self,
        tasks: List[Tuple[TaskType, int]]  # (task_type, complexity)
    ) -> Dict[int, Optional[Agent]]:
        """
        Select agents for multiple tasks.
        
        Args:
            tasks: List of (task_type, complexity) tuples
        
        Returns:
            Mapping of task index to selected agent
        """
        logger.info(f"Selecting agents for {len(tasks)} tasks")
        
        assignments: Dict[int, Optional[Agent]] = {}
        for i, (task_type, complexity) in enumerate(tasks):
            agent = self.select_best_agent(task_type, complexity)
            assignments[i] = agent
            if agent:
                agent.add_load(1)
        
        return assignments
    
    def classify_and_select(
        self,
        task_description: str,
        complexity: int
    ) -> Optional[Agent]:
        """
        Classify task type and select appropriate agent.
        
        Args:
            task_description: Description of the task
            complexity: Complexity level
        
        Returns:
            Selected Agent, or None
        """
        # Classify task
        task_type = self._classify_task(task_description)
        logger.debug(f"Classified task as: {task_type.value}")
        
        # Select agent
        return self.select_best_agent(task_type, complexity)
    
    @staticmethod
    def _classify_task(task_description: str) -> TaskType:
        """
        Classify task type based on description.
        
        Uses same keywords as TaskDecomposer.
        """
        keywords = {
            TaskType.ANALYSIS: ['analyze', 'compare', 'evaluate', 'assess', 'examine'],
            TaskType.RESEARCH: ['research', 'investigate', 'explore', 'find', 'search'],
            TaskType.CODE: ['code', 'program', 'implement', 'algorithm', 'function'],
            TaskType.CREATIVE: ['create', 'generate', 'write', 'design', 'invent'],
            TaskType.SYNTHESIS: ['combine', 'synthesize', 'integrate', 'merge'],
            TaskType.EVALUATION: ['evaluate', 'judge', 'rate', 'score'],
        }
        
        task_lower = task_description.lower()
        
        for task_type, words in keywords.items():
            if any(word in task_lower for word in words):
                return task_type
        
        # Default
        return TaskType.ANALYSIS
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        status = {}
        for agent in self.registry.list_agents():
            status[agent.name] = {
                'type': agent.agent_type,
                'current_load': agent.current_load,
                'load_score': agent.get_load_score(),
                'success_rate': agent.success_rate,
                'capabilities': [cap.value for cap in agent.capabilities]
            }
        return status
    
    def reset_loads(self):
        """Reset all agent loads to 0"""
        for agent in self.registry.list_agents():
            agent.current_load = 0
        logger.info("Reset all agent loads")


class TaskAgentMapping:
    """Mapping of tasks to selected agents"""
    
    def __init__(self):
        self.mappings: Dict[str, Agent] = {}
    
    def add_mapping(self, task_id: str, agent: Agent):
        """Add task-to-agent mapping"""
        self.mappings[task_id] = agent
    
    def get_agent(self, task_id: str) -> Optional[Agent]:
        """Get agent for task"""
        return self.mappings.get(task_id)
    
    def get_tasks_for_agent(self, agent: Agent) -> List[str]:
        """Get all tasks assigned to an agent"""
        return [
            task_id for task_id, a in self.mappings.items()
            if a == agent
        ]
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary (task_id -> agent_name)"""
        return {
            task_id: agent.name
            for task_id, agent in self.mappings.items()
        }
