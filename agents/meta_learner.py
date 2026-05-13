"""
Phase 3 Level 3: Meta-Learning

Extracts high-level patterns from experiences and applies them to new tasks.
Enables continuous learning and adaptation.
"""

import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class MetaLearner:
    """
    Learns meta-patterns from experiences and applies them to new tasks.
    
    Process:
    1. Extract lessons from all stored experiences
    2. Group lessons by pattern type/category
    3. Classify incoming task
    4. Apply matching patterns via prompt injection
    
    Example:
        meta = MetaLearner(memory)
        patterns = meta.extract_meta_patterns()
        # {
        #   'climate': ['explain mechanism', 'provide examples'],
        #   'coding': ['start with pseudocode', 'consider edge cases']
        # }
        
        enhanced = meta.enhance_prompt_with_patterns(
            task="What causes climate change?",
            base_prompt="Explain..."
        )
    """
    
    def __init__(self, memory=None):
        """
        Initialize Meta-Learner.
        
        Args:
            memory: MemoryManager instance for retrieving experiences
        """
        self.memory = memory
        self.extracted_patterns = {}
        self.pattern_effectiveness = defaultdict(float)
        self.category_assignments = {}
    
    def extract_meta_patterns(self) -> Dict[str, List[str]]:
        """
        Extract high-level patterns from all stored experiences.
        
        Process:
        1. Retrieve all experiences from memory
        2. Extract lessons from each
        3. Group lessons by pattern type
        4. Identify common patterns across similar tasks
        5. Create pattern library
        
        Returns:
            Dictionary mapping pattern categories to lists of patterns:
            {
                'analytical': [
                    'Break into sub-problems',
                    'Verify assumptions',
                    'Check edge cases'
                ],
                'creative': [
                    'Show multiple perspectives',
                    'Include concrete examples',
                    'Use analogies'
                ]
            }
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🧠 META-LEARNING: PATTERN EXTRACTION")
        logger.info(f"{'='*60}")
        
        if not self.memory:
            logger.warning("⚠️  No memory manager, returning empty patterns")
            return {}
        
        # Step 1: Retrieve all experiences
        logger.info("📍 Step 1: Retrieving all experiences...")
        try:
            all_experiences = self.memory.retrieve_all_experiences() or []
            logger.info(f"✅ Retrieved {len(all_experiences)} total experiences")
        except Exception as e:
            logger.warning(f"⚠️  Could not retrieve experiences: {e}")
            return {}
        
        if not all_experiences:
            logger.info("ℹ️  No experiences available yet, returning default patterns")
            return self._get_default_patterns()
        
        # Step 2: Extract lessons
        logger.info("📍 Step 2: Extracting lessons from experiences...")
        all_lessons = []
        for exp in all_experiences:
            lesson = exp.get("lesson", "")
            if lesson:
                all_lessons.append(lesson)
        logger.info(f"✅ Extracted {len(all_lessons)} lessons")
        
        # Step 3: Categorize and group
        logger.info("📍 Step 3: Categorizing patterns...")
        patterns = self._categorize_patterns(all_lessons, all_experiences)
        
        # Step 4: Deduplicate and refine
        logger.info("📍 Step 4: Refining patterns...")
        refined = self._refine_patterns(patterns)
        
        self.extracted_patterns = refined
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ PATTERN EXTRACTION COMPLETE")
        logger.info(f"Categories found: {len(refined)}")
        for category, pattern_list in refined.items():
            logger.info(f"  - {category}: {len(pattern_list)} patterns")
        logger.info(f"{'='*60}\n")
        
        return refined
    
    def _categorize_patterns(
        self,
        lessons: List[str],
        experiences: List[Dict]
    ) -> Dict[str, List[str]]:
        """
        Categorize lessons into pattern groups.
        
        Args:
            lessons: List of extracted lessons
            experiences: List of experiences (for context)
        
        Returns:
            Dictionary mapping categories to lesson lists
        """
        categories = defaultdict(list)
        
        # Keyword-based categorization
        keywords = {
            'analytical': ['analyze', 'break', 'sub-problem', 'verify', 'check', 'edge'],
            'creative': ['creative', 'perspective', 'example', 'analogy', 'imagine'],
            'coding': ['code', 'pseudocode', 'algorithm', 'syntax', 'test', 'debug'],
            'explanation': ['explain', 'mechanism', 'cause', 'reason', 'why', 'how'],
            'evidence': ['evidence', 'data', 'support', 'fact', 'example', 'concrete']
        }
        
        for lesson in lessons:
            lesson_lower = lesson.lower()
            assigned = False
            
            for category, keywords_list in keywords.items():
                if any(kw in lesson_lower for kw in keywords_list):
                    categories[category].append(lesson)
                    assigned = True
                    break
            
            if not assigned:
                categories['general'].append(lesson)
        
        return dict(categories)
    
    def _refine_patterns(self, categories: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        Refine and deduplicate patterns.
        
        Args:
            categories: Raw categorized patterns
        
        Returns:
            Refined pattern dictionary
        """
        refined = {}
        
        for category, patterns_list in categories.items():
            # Deduplicate similar patterns
            unique_patterns = []
            seen = set()
            
            for pattern in patterns_list:
                pattern_lower = pattern.lower()
                if pattern_lower not in seen and pattern not in unique_patterns:
                    unique_patterns.append(pattern)
                    seen.add(pattern_lower)
            
            # Keep top patterns
            refined[category] = unique_patterns[:5]
        
        return refined
    
    def enhance_prompt_with_patterns(
        self,
        task: str,
        base_prompt: str,
        auto_extract: bool = True
    ) -> Dict[str, Any]:
        """
        Enhance prompt with relevant meta-patterns.
        
        Process:
        1. Classify task into category
        2. Retrieve patterns for that category
        3. Inject patterns into prompt
        4. Return enhanced prompt
        
        Args:
            task: The task to solve
            base_prompt: Base prompt
            auto_extract: Auto-extract patterns if not available
        
        Returns:
            Dictionary with:
            - enhanced_prompt: Prompt with patterns injected
            - category: Task category
            - patterns_applied: List of patterns used
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🧠 META-LEARNING: PATTERN APPLICATION")
        logger.info(f"{'='*60}")
        logger.info(f"Task: {task[:80]}...")
        
        # Step 1: Extract if not available
        if not self.extracted_patterns and auto_extract:
            logger.info("📍 No patterns extracted yet, extracting now...")
            self.extract_meta_patterns()
        
        # Step 2: Classify task
        logger.info("📍 Step 1: Classifying task...")
        category = self._classify_task(task)
        logger.info(f"✅ Task classified as: {category}")
        
        # Step 3: Get patterns
        logger.info("📍 Step 2: Retrieving patterns...")
        patterns = self.extracted_patterns.get(category, [])
        if not patterns:
            patterns = self.extracted_patterns.get('general', [])
        logger.info(f"✅ Retrieved {len(patterns)} patterns")
        
        # Step 4: Inject into prompt
        logger.info("📍 Step 3: Injecting patterns into prompt...")
        enhanced = self._inject_patterns(base_prompt, category, patterns)
        logger.info(f"✅ Enhanced prompt created")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ PATTERN APPLICATION COMPLETE")
        logger.info(f"{'='*60}\n")
        
        return {
            "enhanced_prompt": enhanced,
            "category": category,
            "patterns_applied": patterns
        }
    
    def _classify_task(self, task: str) -> str:
        """
        Classify task into a category.
        
        Args:
            task: Task description
        
        Returns:
            Category name
        """
        task_lower = task.lower()
        
        keywords = {
            'analytical': ['analyze', 'compare', 'evaluate', 'explain cause'],
            'creative': ['create', 'generate', 'imagine', 'write', 'design'],
            'coding': ['code', 'algorithm', 'program', 'function', 'class'],
            'explanation': ['what', 'how', 'why', 'explain', 'describe'],
            'evidence': ['prove', 'support', 'evidence', 'data']
        }
        
        for category, keywords_list in keywords.items():
            if any(kw in task_lower for kw in keywords_list):
                return category
        
        return 'general'
    
    def _inject_patterns(
        self,
        base_prompt: str,
        category: str,
        patterns: List[str]
    ) -> str:
        """
        Inject patterns into prompt.
        
        Args:
            base_prompt: Original prompt
            category: Task category
            patterns: List of patterns to inject
        
        Returns:
            Enhanced prompt with patterns
        """
        if not patterns:
            return base_prompt
        
        patterns_text = "\n".join([f"• {p}" for p in patterns])
        
        enhanced = f"""
🧠 LEARNED PATTERNS FOR '{category.upper()}' TASKS:

Based on similar past experiences, follow these patterns:

{patterns_text}

📌 NOW APPLY THESE PATTERNS TO:

{base_prompt}
"""
        
        return enhanced
    
    def _get_default_patterns(self) -> Dict[str, List[str]]:
        """
        Get default patterns when no experiences available.
        
        Returns:
            Dictionary of default patterns by category
        """
        return {
            'analytical': [
                'Break the problem into components',
                'Identify key variables',
                'Check your assumptions',
                'Consider edge cases',
                'Verify with examples'
            ],
            'creative': [
                'Show multiple perspectives',
                'Use concrete examples',
                'Include analogies',
                'Make it vivid and specific',
                'Anticipate questions'
            ],
            'coding': [
                'Start with pseudocode',
                'Consider edge cases first',
                'Write testable code',
                'Add error handling',
                'Document assumptions'
            ],
            'explanation': [
                'Define key terms clearly',
                'Explain the mechanism',
                'Provide supporting evidence',
                'Give concrete examples',
                'Address common misconceptions'
            ],
            'general': [
                'Be clear and specific',
                'Support claims with evidence',
                'Consider multiple angles',
                'Check for accuracy',
                'Structure logically'
            ]
        }
    
    def report_pattern_effectiveness(self) -> Dict[str, Any]:
        """
        Report on pattern effectiveness.
        
        Returns:
            Dictionary with effectiveness metrics
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 PATTERN EFFECTIVENESS REPORT")
        logger.info(f"{'='*60}")
        
        logger.info(f"Patterns extracted: {len(self.extracted_patterns)}")
        for category, patterns in self.extracted_patterns.items():
            logger.info(f"  {category}: {len(patterns)} patterns")
        
        logger.info(f"{'='*60}\n")
        
        return {
            "total_categories": len(self.extracted_patterns),
            "total_patterns": sum(len(p) for p in self.extracted_patterns.values()),
            "categories": list(self.extracted_patterns.keys()),
            "effectiveness_scores": dict(self.pattern_effectiveness)
        }
    
    def update_pattern_effectiveness(self, category: str, score: float):
        """
        Update effectiveness score for a pattern category.
        
        Args:
            category: Pattern category
            score: Effectiveness score (0-1 or 1-5)
        """
        self.pattern_effectiveness[category] = score
