"""
Phase 4: Result Synthesizer - Combine sub-task results into final answer

This module synthesizes results from multiple sub-tasks into a coherent,
comprehensive final answer using the Phase 1-2 pipeline.

Key Features:
  - Intelligent result combination
  - Conflict resolution
  - Gap filling
  - Result validation
  - Quality assessment
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from parallel_task_executor import TaskResult, TaskStatus

logger = logging.getLogger(__name__)


class ResultSynthesizer:
    """
    Synthesizes sub-task results into a final comprehensive answer.
    
    Handles:
    - Extracting key findings from each result
    - Identifying connections and relationships
    - Resolving conflicting information
    - Filling gaps in coverage
    - Creating coherent final answer
    """
    
    def __init__(self, cot_agent=None, validator=None):
        """
        Initialize ResultSynthesizer.
        
        Args:
            cot_agent: ChainOfThoughtAgent for synthesis reasoning
            validator: OutputValidator for quality checking
        """
        self.cot_agent = cot_agent
        self.validator = validator
        logger.info("ResultSynthesizer initialized")
    
    def synthesize(
        self,
        main_task: str,
        subtask_results: Dict[str, TaskResult],
        subtask_descriptions: Dict[str, str]
    ) -> str:
        """
        Synthesize multiple sub-task results into final answer.
        
        Process:
        1. Extract key findings from each result
        2. Organize by theme/relevance
        3. Identify gaps
        4. Create synthesis prompt
        5. Generate final answer
        
        Args:
            main_task: Original main task description
            subtask_results: Results from all sub-tasks
            subtask_descriptions: Descriptions of sub-tasks
        
        Returns:
            Final synthesized answer
        """
        logger.info(
            f"Synthesizing {len(subtask_results)} subtask results "
            f"for main task: {main_task[:80]}..."
        )
        
        # Step 1: Filter successful results
        successful_results = {
            task_id: result
            for task_id, result in subtask_results.items()
            if result.status == TaskStatus.COMPLETED and result.result
        }
        
        if not successful_results:
            logger.warning("No successful subtask results to synthesize")
            return "Unable to synthesize results - no successful sub-tasks"
        
        logger.info(f"Using {len(successful_results)} successful results")
        
        # Step 2: Extract findings
        findings = self._extract_findings(successful_results, subtask_descriptions)
        
        # Step 3: Create synthesis prompt
        synthesis_prompt = self._create_synthesis_prompt(
            main_task,
            findings,
            successful_results
        )
        
        logger.debug(f"Synthesis prompt created ({len(synthesis_prompt)} chars)")
        
        # Step 4: Generate synthesis
        if self.cot_agent:
            # Use CoT agent for reasoning
            synthesis = self.cot_agent.solve(synthesis_prompt)
            final_answer = synthesis.get('answer', synthesis_prompt)
        else:
            # Fallback: combine results directly
            final_answer = self._combine_findings(findings)
        
        logger.info("Synthesis complete")
        return final_answer
    
    def _extract_findings(
        self,
        results: Dict[str, TaskResult],
        descriptions: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Extract key findings from each result.
        
        Args:
            results: Dictionary of task results
            descriptions: Task descriptions
        
        Returns:
            List of extracted findings
        """
        findings = []
        
        for task_id, result in results.items():
            if not result.result:
                continue
            
            finding = {
                'task_id': task_id,
                'description': descriptions.get(task_id, 'Unknown task'),
                'result': result.result,
                'quality': result.quality_score or 0.0,
                'key_points': self._extract_key_points(result.result),
                'confidence': self._assess_confidence(result)
            }
            findings.append(finding)
        
        # Sort by quality
        findings.sort(key=lambda f: f['quality'], reverse=True)
        
        logger.debug(f"Extracted findings from {len(findings)} results")
        return findings
    
    def _extract_key_points(self, text: str, num_points: int = 3) -> List[str]:
        """
        Extract key points from result text.
        
        Simple heuristic: Split by sentences and take first few.
        """
        if not text:
            return []
        
        # Split by common delimiters
        sentences = []
        for delimiter in ['. ', '! ', '? ', '\n']:
            if delimiter in text:
                sentences = text.split(delimiter)
                break
        
        if not sentences:
            sentences = [text]
        
        # Take first num_points non-empty sentences
        key_points = [
            s.strip() for s in sentences[:num_points]
            if s.strip()
        ]
        
        return key_points
    
    def _assess_confidence(self, result: TaskResult) -> float:
        """
        Assess confidence in a result.
        
        Uses quality score and number of iterations.
        """
        if result.quality_score is None:
            return 0.5
        
        # Quality is main factor
        confidence = result.quality_score / 5.0
        
        # Penalize if took many iterations
        if result.iterations_used and result.iterations_used > 3:
            confidence *= 0.8
        
        return min(1.0, confidence)
    
    def _create_synthesis_prompt(
        self,
        main_task: str,
        findings: List[Dict[str, Any]],
        results: Dict[str, TaskResult]
    ) -> str:
        """
        Create prompt for synthesis task.
        
        Args:
            main_task: Original main task
            findings: Extracted findings
            results: Original results
        
        Returns:
            Synthesis prompt
        """
        prompt = f"""
SYNTHESIS TASK:
Original Task: {main_task}

You have the following results from related sub-tasks:

"""
        
        for i, finding in enumerate(findings, 1):
            prompt += f"""
--- FINDING {i} ---
Task: {finding['description']}
Quality: {finding['quality']:.1f}/5.0
Result: {finding['result'][:300]}...

Key Points:
{chr(10).join(f"• {point}" for point in finding['key_points'])}

"""
        
        prompt += f"""
SYNTHESIS REQUIREMENTS:
1. Integrate all findings above into a comprehensive answer
2. Identify and explain connections between findings
3. Maintain logical flow and coherence
4. Fill any gaps using the findings
5. Highlight the most important conclusions
6. Acknowledge any uncertainties or conflicts

Please provide a well-structured, comprehensive synthesis that answers the original task.
"""
        
        return prompt
    
    def _combine_findings(self, findings: List[Dict[str, Any]]) -> str:
        """
        Combine findings directly (fallback when no CoT agent).
        
        Args:
            findings: Extracted findings
        
        Returns:
            Combined answer
        """
        if not findings:
            return "No findings to combine"
        
        combined = "## Synthesis of Results\n\n"
        
        for i, finding in enumerate(findings, 1):
            combined += f"### Finding {i}: {finding['description']}\n"
            combined += f"**Quality Score:** {finding['quality']:.1f}/5.0\n\n"
            combined += f"{finding['result']}\n\n"
        
        return combined
    
    def validate_synthesis(
        self,
        synthesis: str,
        findings: List[Dict[str, Any]]
    ) -> float:
        """
        Validate that synthesis covers findings.
        
        Checks:
        - Does synthesis mention key points?
        - Is it a reasonable length?
        - Does it have structure?
        
        Args:
            synthesis: Generated synthesis
            findings: Original findings
        
        Returns:
            Validation score (0-1)
        """
        logger.debug("Validating synthesis...")
        
        if not synthesis or len(synthesis) < 100:
            return 0.2
        
        # Check coverage of key findings
        coverage_score = 0.5
        covered_findings = 0
        
        for finding in findings:
            # Check if finding is mentioned (loose match)
            if any(
                point[:20] in synthesis
                for point in finding['key_points']
                if point
            ):
                covered_findings += 1
        
        if findings:
            coverage_score = covered_findings / len(findings)
        
        # Check length and structure
        length_score = min(len(synthesis) / 1000, 1.0)  # 1000+ chars is good
        structure_score = (
            1.0 if '\n' in synthesis and len(synthesis.split('\n')) > 5
            else 0.7
        )
        
        # Combine scores
        validation_score = (
            coverage_score * 0.5 +
            length_score * 0.25 +
            structure_score * 0.25
        )
        
        logger.info(f"Synthesis validation score: {validation_score:.2f}")
        return validation_score
    
    def resolve_conflicts(
        self,
        conflicting_results: List[TaskResult]
    ) -> str:
        """
        Handle contradictory results from different agents.
        
        Simple heuristic: Use highest quality result.
        
        Args:
            conflicting_results: Results with conflicting information
        
        Returns:
            Resolved answer
        """
        if not conflicting_results:
            return ""
        
        # Sort by quality and return highest
        conflicting_results.sort(
            key=lambda r: r.quality_score or 0.0,
            reverse=True
        )
        
        best_result = conflicting_results[0]
        
        if len(conflicting_results) > 1:
            logger.warning(
                f"Conflict resolution: Using result with quality "
                f"{best_result.quality_score} over others"
            )
        
        return best_result.result or ""
    
    def get_synthesis_metrics(
        self,
        findings: List[Dict[str, Any]],
        synthesis_quality: float
    ) -> Dict[str, Any]:
        """
        Get metrics about the synthesis process.
        
        Args:
            findings: Extracted findings
            synthesis_quality: Quality of synthesis
        
        Returns:
            Dictionary of metrics
        """
        avg_finding_quality = (
            sum(f['quality'] for f in findings) / len(findings)
            if findings else 0.0
        )
        
        return {
            'num_findings': len(findings),
            'average_finding_quality': avg_finding_quality,
            'synthesis_quality': synthesis_quality,
            'synthesis_confidence': (
                (avg_finding_quality / 5.0 + synthesis_quality / 2.0) / 2.0
            )
        }
