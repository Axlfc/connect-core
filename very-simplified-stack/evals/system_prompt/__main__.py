import sys
import os
import argparse
from typing import Optional

# Ensure both backend and evals root are in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from evals.system_prompt.evaluator import evaluate_prompt_version
from evals.system_prompt.schemas import SystemPromptEvalReport

def print_report(report: SystemPromptEvalReport):
    print("\n" + "="*50)
    print(f"📋 COGNITO SYSTEM PROMPT EVALUATION REPORT [{report.version}]")
    print("="*50)
    print(f"Total Cases:  {report.total_cases}")
    print(f"Passed Cases: {report.passed_cases}")
    print(f"Pass Rate:    {report.pass_rate*100:.1f}%")
    print("\nCategory Breakdown:")
    for cat, score in report.category_scores.items():
        print(f"  - {cat:<20}: {score*100:.1f}%")
    print("="*50)

    if report.passed_cases < report.total_cases:
        print("\nFailures:")
        for r in report.results:
            if not r.passed:
                print(f"  [{r.case_id}] ({r.category}): {', '.join(r.failed_rules)}")
        print("="*50 + "\n")
    else:
        print("\nAll evaluation cases PASSED!\n" + "="*50 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Cognito System Prompt Evaluation Suite")
    parser.add_argument("command", choices=["run", "report"])
    parser.add_argument("--version", default="v1", help="Prompt version to evaluate (e.g., v1, v1.1)")

    args = parser.parse_args()

    if args.command == "run":
        try:
            report = evaluate_prompt_version(args.version)
            print_report(report)
            sys.exit(0 if report.passed_cases == report.total_cases else 1)
        except Exception as e:
            print(f"Error running evaluation: {e}")
            sys.exit(1)
    elif args.command == "report":
        report_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                report = SystemPromptEvalReport.model_validate_json(f.read())
                print_report(report)
        else:
            print("No evaluation results found. Run evals first: python3 -m evals.system_prompt run")

if __name__ == "__main__":
    main()
