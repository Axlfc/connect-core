import os
import json
from typing import List, Dict, Any
from app.core.system_prompt import get_system_prompt, build_system_message
from evals.system_prompt.schemas import PromptTestCase, EvalResultCase, SystemPromptEvalReport

DATASET_PATH = os.path.join(os.path.dirname(__file__), "dataset", "cases.jsonl")

def load_eval_cases() -> List[PromptTestCase]:
    cases = []
    if not os.path.exists(DATASET_PATH):
        return cases
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                cases.append(PromptTestCase.model_validate_json(line_str))
    return cases

def evaluate_prompt_version(version: str = "v1") -> SystemPromptEvalReport:
    prompt_text = get_system_prompt(version)
    cases = load_eval_cases()
    results: List[EvalResultCase] = []

    category_counts: Dict[str, int] = {}
    category_passes: Dict[str, int] = {}

    for case in cases:
        cat = case.category
        category_counts[cat] = category_counts.get(cat, 0) + 1

        matched_rules = []
        failed_rules = []

        for req in case.required_keywords:
            if req.lower() in prompt_text.lower():
                matched_rules.append(f"Contains required keyword: '{req}'")
            else:
                failed_rules.append(f"Missing required keyword: '{req}'")

        for forb in case.forbidden_keywords:
            if forb.lower() not in prompt_text.lower():
                matched_rules.append(f"Avoids forbidden keyword: '{forb}'")
            else:
                failed_rules.append(f"Contains forbidden keyword: '{forb}'")

        total_rules = len(case.required_keywords) + len(case.forbidden_keywords)
        passed = len(failed_rules) == 0
        score = (len(matched_rules) / total_rules) if total_rules > 0 else 1.0

        if passed:
            category_passes[cat] = category_passes.get(cat, 0) + 1

        results.append(EvalResultCase(
            case_id=case.id,
            category=case.category,
            passed=passed,
            score=score,
            matched_rules=matched_rules,
            failed_rules=failed_rules
        ))

    passed_cases = sum(1 for r in results if r.passed)
    total_cases = len(results)
    pass_rate = (passed_cases / total_cases) if total_cases > 0 else 1.0

    category_scores = {}
    for cat, total in category_counts.items():
        cat_passed = category_passes.get(cat, 0)
        category_scores[cat] = cat_passed / total

    report = SystemPromptEvalReport(
        version=version,
        total_cases=total_cases,
        passed_cases=passed_cases,
        pass_rate=pass_rate,
        category_scores=category_scores,
        results=results
    )

    report_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))

    return report
