"""
Tests for Phase 3: Memory & Learning System

Unit tests for FewShotPrompt, MetaLearner, and Phase3Integration classes.
Tests cover:
- Few-shot prompt generation
- Meta-pattern extraction
- Pattern application
- Full integration workflow
"""

import pytest
from few_shot_prompter import FewShotPrompt
from meta_learner import MetaLearner
from phase3_integration import Phase3Integration


class TestFewShotPrompt:
    """Test few-shot prompt generation"""
    
    def test_few_shot_init(self):
        """Test FewShotPrompt initialization"""
        prompter = FewShotPrompt(num_examples=3)
        
        assert prompter.num_examples == 3
        assert prompter.memory is None
        assert prompter.default_model == "qwen2.5-coder"
    
    def test_few_shot_init_with_memory(self):
        """Test FewShotPrompt init with memory"""
        mock_memory = object()
        prompter = FewShotPrompt(memory=mock_memory, num_examples=5)
        
        assert prompter.memory is mock_memory
        assert prompter.num_examples == 5
    
    def test_create_few_shot_prompt_no_memory(self):
        """Test prompt creation without memory"""
        prompter = FewShotPrompt(num_examples=3)
        
        result = prompter.create_few_shot_prompt(
            task="Test task",
            base_prompt="Test prompt"
        )
        
        assert result["examples_found"] == 0
        assert result["enhanced_prompt"] == "Test prompt"
        assert len(result["example_sources"]) == 0
    
    def test_format_examples(self):
        """Test example formatting"""
        prompter = FewShotPrompt()
        
        experiences = [
            {
                "task": "What is 2+2?",
                "solution": "The answer is 4",
                "quality": 4.5,
                "lesson": "Basic math"
            }
        ]
        
        formatted = prompter._format_examples(experiences)
        
        assert len(formatted) == 1
        assert "What is 2+2?" in formatted[0]
        assert "4.5" in formatted[0]
        assert "Basic math" in formatted[0]
    
    def test_inject_examples(self):
        """Test example injection into prompt"""
        prompter = FewShotPrompt()
        
        examples = ["Example 1", "Example 2"]
        base = "Solve this problem"
        
        result = prompter._inject_examples(base, examples)
        
        assert "Example 1" in result
        assert "Example 2" in result
        assert "Solve this problem" in result
    
    def test_evaluate_improvement(self):
        """Test improvement evaluation"""
        prompter = FewShotPrompt()
        
        result = prompter.evaluate_improvement(
            task="Test",
            without_examples_quality=3.5,
            with_examples_quality=4.2
        )
        
        assert result["absolute_improvement"] == pytest.approx(0.7)
        assert result["was_helpful"] is True
    
    def test_get_statistics(self):
        """Test statistics retrieval"""
        prompter = FewShotPrompt(num_examples=3)
        stats = prompter.get_statistics()
        
        assert stats["num_examples"] == 3
        assert stats["memory_available"] is False
        assert stats["default_model"] == "qwen2.5-coder"


class TestMetaLearner:
    """Test meta-learning functionality"""
    
    def test_meta_learner_init(self):
        """Test MetaLearner initialization"""
        learner = MetaLearner()
        
        assert learner.memory is None
        assert len(learner.extracted_patterns) == 0
    
    def test_meta_learner_init_with_memory(self):
        """Test MetaLearner init with memory"""
        mock_memory = object()
        learner = MetaLearner(memory=mock_memory)
        
        assert learner.memory is mock_memory
    
    def test_classify_task_analytical(self):
        """Test task classification - analytical"""
        learner = MetaLearner()
        
        category = learner._classify_task("Analyze the data")
        assert category == "analytical"
        
        category = learner._classify_task("Compare two approaches")
        assert category == "analytical"
    
    def test_classify_task_creative(self):
        """Test task classification - creative"""
        learner = MetaLearner()
        
        category = learner._classify_task("Create a story")
        assert category == "creative"
    
    def test_classify_task_coding(self):
        """Test task classification - coding"""
        learner = MetaLearner()
        
        category = learner._classify_task("Write Python code")
        assert category == "coding"
    
    def test_classify_task_default(self):
        """Test task classification - default"""
        learner = MetaLearner()
        
        category = learner._classify_task("Random unknown task")
        assert category == "general"
    
    def test_get_default_patterns(self):
        """Test default pattern retrieval"""
        learner = MetaLearner()
        
        patterns = learner._get_default_patterns()
        
        assert "analytical" in patterns
        assert "creative" in patterns
        assert "coding" in patterns
        assert len(patterns["analytical"]) > 0
    
    def test_categorize_patterns(self):
        """Test pattern categorization"""
        learner = MetaLearner()
        
        lessons = [
            "Break into sub-problems",
            "Consider creative angles",
            "Write pseudocode first"
        ]
        
        categories = learner._categorize_patterns(lessons, [])
        
        # Should have some categorization
        assert isinstance(categories, dict)
    
    def test_refine_patterns(self):
        """Test pattern refinement"""
        learner = MetaLearner()
        
        categories = {
            "test": [
                "Pattern 1",
                "Pattern 1",  # Duplicate
                "Pattern 2"
            ]
        }
        
        refined = learner._refine_patterns(categories)
        
        # Should remove duplicates
        assert len(refined["test"]) == 2
    
    def test_inject_patterns(self):
        """Test pattern injection"""
        learner = MetaLearner()
        
        base = "Solve this problem"
        patterns = ["Pattern 1", "Pattern 2"]
        
        result = learner._inject_patterns(base, "test", patterns)
        
        assert "Pattern 1" in result
        assert "Pattern 2" in result
        assert "Solve this problem" in result
    
    def test_extract_meta_patterns_no_memory(self):
        """Test pattern extraction without memory"""
        learner = MetaLearner()
        
        patterns = learner.extract_meta_patterns()
        
        # Should return empty
        assert isinstance(patterns, dict)
    
    def test_enhance_prompt_with_patterns(self):
        """Test prompt enhancement with patterns"""
        learner = MetaLearner()
        
        result = learner.enhance_prompt_with_patterns(
            task="Analyze this data",
            base_prompt="Analyze thoroughly"
        )
        
        assert "enhanced_prompt" in result
        assert "category" in result
        assert "patterns_applied" in result
        assert result["category"] == "analytical"
    
    def test_report_pattern_effectiveness(self):
        """Test effectiveness reporting"""
        learner = MetaLearner()
        learner.extracted_patterns = {
            "analytical": ["Pattern 1", "Pattern 2"],
            "creative": ["Pattern 3"]
        }
        
        report = learner.report_pattern_effectiveness()
        
        assert report["total_categories"] == 2
        assert report["total_patterns"] == 3
    
    def test_update_pattern_effectiveness(self):
        """Test effectiveness update"""
        learner = MetaLearner()
        
        learner.update_pattern_effectiveness("analytical", 0.85)
        
        assert learner.pattern_effectiveness["analytical"] == 0.85


class TestPhase3Integration:
    """Test Phase 3 integration"""
    
    def test_phase3_init(self):
        """Test Phase3Integration initialization"""
        integration = Phase3Integration()
        
        assert integration.cot_agent is None
        assert integration.validator is None
        assert integration.memory is None
        assert integration.few_shot_prompter is None
        assert integration.meta_learner is None
    
    def test_phase3_init_with_components(self):
        """Test init with all components"""
        mock_cot = object()
        mock_memory = object()
        
        integration = Phase3Integration(
            cot_agent=mock_cot,
            memory=mock_memory
        )
        
        assert integration.cot_agent is mock_cot
        assert integration.memory is mock_memory
    
    def test_retrieve_from_memory_no_memory(self):
        """Test memory retrieval without memory"""
        integration = Phase3Integration()
        
        result = integration._retrieve_from_memory("Test task")
        
        assert result["found"] is False
        assert result["count"] == 0
    
    def test_enhance_with_few_shot_no_prompter(self):
        """Test few-shot enhancement without prompter"""
        integration = Phase3Integration()
        
        result = integration._enhance_with_few_shot("Task", "Prompt")
        
        assert result["used"] is False
        assert result["examples_count"] == 0
        assert result["enhanced_prompt"] == "Prompt"
    
    def test_enhance_with_meta_no_learner(self):
        """Test meta enhancement without learner"""
        integration = Phase3Integration()
        
        result = integration._enhance_with_meta_patterns("Prompt")
        
        assert result["used"] is False
        assert len(result["patterns"]) == 0
    
    def test_extract_lesson(self):
        """Test lesson extraction"""
        integration = Phase3Integration()
        
        result = {
            "final_quality": 4.8,
            "iterations_used": 1
        }
        
        lesson = integration._extract_lesson("Explain photosynthesis", result)
        
        assert len(lesson) > 0
        assert isinstance(lesson, str)
    
    def test_store_in_memory_no_memory(self):
        """Test storage without memory"""
        integration = Phase3Integration()
        
        result = integration._store_in_memory("Task", {"answer": "Test"})
        
        assert result is False
    
    def test_get_learning_statistics_empty(self):
        """Test statistics with no execution"""
        integration = Phase3Integration()
        
        stats = integration.get_learning_statistics()
        
        assert stats["total_tasks_solved"] == 0
        assert stats["average_quality"] == 0
    
    def test_get_learning_statistics_with_executions(self):
        """Test statistics with execution log"""
        integration = Phase3Integration()
        
        integration.execution_log = [
            {
                "final_quality": 4.5,
                "learning_applied": {
                    "used_memory": True,
                    "used_few_shot": False,
                    "used_meta": True
                }
            },
            {
                "final_quality": 4.0,
                "learning_applied": {
                    "used_memory": False,
                    "used_few_shot": True,
                    "used_meta": False
                }
            }
        ]
        
        stats = integration.get_learning_statistics()
        
        assert stats["total_tasks_solved"] == 2
        assert stats["average_quality"] == pytest.approx(4.25)
        assert stats["learning_usage"]["memory_retrieved"] == 1
        assert stats["learning_usage"]["few_shot_used"] == 1


class TestPhase3Integration:
    """Additional integration tests"""
    
    def test_solve_with_learning_minimal(self):
        """Test solve with minimal setup"""
        integration = Phase3Integration()
        
        result = integration.solve_with_learning(
            task="Test task",
            use_memory=False,
            use_few_shot=False,
            use_meta=False,
            store_result=False
        )
        
        assert result["task"] == "Test task"
        assert "learning_applied" in result
        assert result["learning_applied"]["used_memory"] is False
    
    def test_solve_with_learning_all_disabled(self):
        """Test solve with all learning disabled"""
        integration = Phase3Integration()
        
        result = integration.solve_with_learning(
            task="Solve this",
            use_memory=False,
            use_few_shot=False,
            use_meta=False
        )
        
        assert result["answer"] == "No solver available"  # No iteration manager
    
    def test_execution_log_tracking(self):
        """Test execution log tracking"""
        integration = Phase3Integration()
        
        integration.solve_with_learning(
            task="Task 1",
            use_memory=False,
            use_few_shot=False,
            use_meta=False,
            store_result=False
        )
        
        integration.solve_with_learning(
            task="Task 2",
            use_memory=False,
            use_few_shot=False,
            use_meta=False,
            store_result=False
        )
        
        assert len(integration.execution_log) == 2
        assert integration.execution_log[0]["task"] == "Task 1"
        assert integration.execution_log[1]["task"] == "Task 2"
