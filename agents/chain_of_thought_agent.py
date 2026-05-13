"""
Phase 1: Chain-of-Thought Agent

Implements step-by-step reasoning for better problem-solving.
Breaks complex problems into intermediate steps, showing reasoning at each stage.
"""

import requests
import json
from typing import List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_URL = "http://ollama:11434"
DEFAULT_MODEL = "qwen2.5-coder"


class ChainOfThoughtAgent:
    """
    Agent that reasons step-by-step through problems.
    
    Workflow:
    1. Analyze task and break into components
    2. Plan approach with intermediate steps
    3. Execute plan step by step
    4. Validate each result
    5. Synthesize final answer
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.reasoning_chain = []
        self.final_answer = None

    def call_ollama(self, prompt: str) -> str:
        """Call Ollama API with streaming disabled for simplicity."""
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.7,
                },
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "").strip()
        except requests.RequestException as e:
            logger.error(f"Ollama API error: {e}")
            return f"ERROR: {str(e)}"

    def analyze_task(self, task: str) -> Dict[str, Any]:
        """Step 1: Understand and analyze the task."""
        prompt = f"""
Analyze this task and identify:
1. What is being asked?
2. What are the main components?
3. What constraints exist?

Task: {task}

Provide a clear analysis in 3 points.
"""
        thought = "Analyzing task to understand components and constraints"
        output = self.call_ollama(prompt)

        step_result = {
            "step": 1,
            "name": "analyze_task",
            "thought": thought,
            "output": output,
        }
        self.reasoning_chain.append(step_result)
        logger.info(f"Step 1 Complete:\n{output}\n")
        return step_result

    def plan_approach(self, task: str) -> Dict[str, Any]:
        """Step 2: Create a detailed plan."""
        prompt = f"""
Create a detailed step-by-step plan to solve:
{task}

The plan should:
1. Have 3-5 specific steps
2. Build on each other logically
3. Be executable

Format as numbered steps with descriptions.
"""
        thought = "Creating structured plan with intermediate steps"
        output = self.call_ollama(prompt)

        step_result = {
            "step": 2,
            "name": "plan_approach",
            "thought": thought,
            "output": output,
        }
        self.reasoning_chain.append(step_result)
        logger.info(f"Step 2 Complete:\n{output}\n")
        return step_result

    def execute_plan(self, task: str) -> Dict[str, Any]:
        """Step 3: Execute the plan step by step."""
        prompt = f"""
Based on the task and plan, execute the approach:

Task: {task}

Show your work step-by-step. For each step:
- Explain what you're doing
- Show intermediate results
- Build toward final answer

Be thorough and show all reasoning.
"""
        thought = "Executing plan with detailed step-by-step work"
        output = self.call_ollama(prompt)

        step_result = {
            "step": 3,
            "name": "execute_plan",
            "thought": thought,
            "output": output,
        }
        self.reasoning_chain.append(step_result)
        logger.info(f"Step 3 Complete:\n{output}\n")
        return step_result

    def validate_result(self, task: str) -> Dict[str, Any]:
        """Step 4: Validate the solution."""
        prompt = f"""
Validate this solution to the task:

Original Task: {task}

Your solution shows:
{self.reasoning_chain[-1]['output'] if self.reasoning_chain else 'No solution yet'}

Check:
1. Does it answer the question? Why/why not?
2. Is the reasoning sound? 
3. Are there any errors or gaps?
4. Could it be improved?

Provide a validation assessment.
"""
        thought = "Validating solution against original task requirements"
        output = self.call_ollama(prompt)

        step_result = {
            "step": 4,
            "name": "validate_result",
            "thought": thought,
            "output": output,
        }
        self.reasoning_chain.append(step_result)
        logger.info(f"Step 4 Complete:\n{output}\n")
        return step_result

    def synthesize_answer(self, task: str) -> Dict[str, Any]:
        """Step 5: Create final synthesized answer."""
        prompt = f"""
Based on the complete reasoning chain, provide a final answer to:
{task}

Format your answer as:
1. Direct answer (1-2 sentences)
2. Key reasoning (3-4 sentences explaining why)
3. Confidence level (High/Medium/Low)

Be concise and clear.
"""
        thought = "Synthesizing final answer from reasoning chain"
        output = self.call_ollama(prompt)

        self.final_answer = output
        step_result = {
            "step": 5,
            "name": "synthesize_answer",
            "thought": thought,
            "output": output,
        }
        self.reasoning_chain.append(step_result)
        logger.info(f"Step 5 Complete:\n{output}\n")
        return step_result

    def solve(self, task: str) -> Dict[str, Any]:
        """
        Execute complete chain-of-thought reasoning.
        Returns all steps and final answer.
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Chain-of-Thought Agent Starting")
        logger.info(f"Task: {task}")
        logger.info(f"{'='*60}\n")

        # Execute all 5 steps
        self.analyze_task(task)
        self.plan_approach(task)
        self.execute_plan(task)
        self.validate_result(task)
        self.synthesize_answer(task)

        result = {
            "task": task,
            "model": self.model,
            "reasoning_chain": self.reasoning_chain,
            "final_answer": self.final_answer,
            "num_steps": len(self.reasoning_chain),
            "success": True,
        }

        logger.info(f"\n{'='*60}")
        logger.info(f"Chain-of-Thought Complete")
        logger.info(f"Final Answer:\n{self.final_answer}")
        logger.info(f"{'='*60}\n")

        return result

    def estimate_quality(self) -> Dict[str, Any]:
        """Estimate quality of reasoning chain."""
        if not self.reasoning_chain:
            return {"quality": 0, "reason": "No reasoning chain generated"}

        num_steps = len(self.reasoning_chain)
        has_analysis = any(r["name"] == "analyze_task" for r in self.reasoning_chain)
        has_plan = any(r["name"] == "plan_approach" for r in self.reasoning_chain)
        has_validation = any(r["name"] == "validate_result" for r in self.reasoning_chain)

        quality_score = 0
        if has_analysis:
            quality_score += 20
        if has_plan:
            quality_score += 20
        if has_validation:
            quality_score += 30
        if self.final_answer and len(self.final_answer) > 10:
            quality_score += 30

        return {
            "quality_score": quality_score,
            "num_steps": num_steps,
            "has_analysis": has_analysis,
            "has_plan": has_plan,
            "has_validation": has_validation,
            "has_answer": bool(self.final_answer),
        }


# For n8n integration
def run_chain_of_thought(task: str, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    """Entry point for n8n workflow."""
    agent = ChainOfThoughtAgent(model=model)
    return agent.solve(task)


if __name__ == "__main__":
    # Test
    test_task = "What is the capital of France and why is it important?"
    agent = ChainOfThoughtAgent()
    result = agent.solve(test_task)
    print(json.dumps(result, indent=2))
