import sys
import os
import json
import argparse
from typing import List, Dict, Any

# Ensure both backend and evals root are in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from evals.router.schemas import LabeledTestCase
from evals.router.metrics import calculate_evaluation_metrics
from app.services.policy_engine import policy_engine
from app.services.ollama_classifier import ClassificationResponse
from app.models.domain import TaskContext, RepositoryContext, EditorContext

DATASET_PATH = os.path.join(os.path.dirname(__file__), "dataset", "core.jsonl")

def load_dataset() -> List[LabeledTestCase]:
    cases = []
    if not os.path.exists(DATASET_PATH):
        return []
    with open(DATASET_PATH, "r") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                cases.append(LabeledTestCase.model_validate(data))
    return cases

def run_evals(shadow: bool = False):
    cases = load_dataset()
    results = []

    print(f"Running evaluation suite on {len(cases)} cases... (Shadow Mode: {shadow})")

    for case in cases:
        # Mock TaskContext
        repo = RepositoryContext(
            repository_id="eval-repo",
            root_path="/tmp",
            current_branch="main",
            base_commit="abc1234",
            is_dirty=False,
            changed_files_count=0
        )
        editor = EditorContext(workspace_folder="/tmp")
        context = TaskContext(
            repository=repo,
            editor=editor,
            user_task=case.user_task,
            sensitive_path_indicators=case.sensitive_path_indicators
        )

        # In offline/mocked mode we simulate classification recommendations, or run policy engine directly
        # To make it deterministic and fast, we map case expectations to mocked classification response
        mock_classif = ClassificationResponse(
            task_type=case.category,
            complexity="medium",
            risk=case.risk,
            scope="multi_file",
            ambiguity="clear",
            expected_write_requirement=case.expected_executor == "Codex",
            expected_network_requirement=False,
            probable_file_count=2,
            recommended_logical_tier=case.expected_logical_tier,
            confidence=0.9
        )

        # Run policy engine
        decision = policy_engine.evaluate(context, mock_classif)
        results.append({
            "case": case,
            "decision": decision
        })

        if shadow:
            # Shadow mode does not run actual worker tasks, just outputs recommended decision
            print(f"Shadow recommendation for '{case.user_task[:30]}...': Executor={decision.executor}, Tier={decision.logical_tier}")

    # Compute metrics
    metrics = calculate_evaluation_metrics(results)

    # Save a baseline run file
    report_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
    with open(report_path, "w") as f:
        # Pydantic serialization
        serializable_results = []
        for r in results:
            serializable_results.append({
                "case": r["case"].model_dump(),
                "decision": r["decision"].model_dump()
            })
        json.dump({"metrics": metrics, "results": serializable_results}, f, indent=2)

    print_report(metrics)

def print_report(metrics: Dict[str, Any]):
    print("\n" + "="*50)
    print("🧠 COGNITO ROUTER EVALUATION REPORT")
    print("="*50)
    print(f"Total Cases: {metrics.get('total_cases')}")
    print(f"Exact Tier Agreement: {metrics.get('exact_tier_agreement_rate')*100:.1f}%")
    print(f"Executor Agreement: {metrics.get('executor_agreement_rate')*100:.1f}%")
    print(f"Safe-Route Agreement: {metrics.get('safe_route_agreement_rate')*100:.1f}%")
    print(f"Under-routing Rate: {metrics.get('under_routing_rate')*100:.1f}%")
    print(f"Under-routing Weighted Cost: {metrics.get('under_routing_weighted_cost')}")
    print(f"Over-routing Rate: {metrics.get('over_routing_rate')*100:.1f}%")
    print(f"High-risk Recall Rate: {metrics.get('high_risk_recall')*100:.1f}%")
    print("="*50 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Cognito Intelligent Router Evaluation Suite")
    parser.add_argument("command", choices=["validate", "run", "report"])
    parser.add_argument("--shadow", action="store_true", help="Run in shadow mode")

    args = parser.parse_args()

    if args.command == "validate":
        ok = policy_engine.validate_policy()
        print(f"Policy validation: {'PASSED' if ok else 'FAILED'}")
        sys.exit(0 if ok else 1)
    elif args.command == "run":
        run_evals(shadow=args.shadow)
    elif args.command == "report":
        report_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
        if os.path.exists(report_path):
            with open(report_path, "r") as f:
                data = json.load(f)
                print_report(data["metrics"])
        else:
            print("No evaluation results found. Run evals first: python -m evals.router run")

if __name__ == "__main__":
    main()
