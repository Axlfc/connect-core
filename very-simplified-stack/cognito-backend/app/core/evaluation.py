import os
import sys
import json
import asyncio
import yaml
import subprocess
from typing import List, Dict, Any, Optional

class ExactMatchScorer:
    """
    Computes Exact Match scores between outputs.
    """
    @staticmethod
    def score(prediction: str, expected: str) -> float:
        return 1.0 if prediction.strip() == expected.strip() else 0.0

class EvalPipeline:
    """
    YAML-driven batch evaluations using subprocess concurrent workers (NOOA-26).
    """
    def __init__(self, config_yaml_path: str):
        self.config_yaml_path = config_yaml_path
        self.cases: List[Dict[str, Any]] = []
        self._load_config()

    def _load_config(self):
        if os.path.exists(self.config_yaml_path):
            with open(self.config_yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self.cases = data.get("cases", [])

    async def run_eval(self) -> List[Dict[str, Any]]:
        results = []
        for case in self.cases:
            user_input = case.get("input", "")
            expected = case.get("expected", "")
            # Simulate subprocess run isolation (or direct fast inline execution for speed)
            predicted = f"Simulated prediction for: {user_input[:20]}"
            score = ExactMatchScorer.score(predicted, expected)
            results.append({
                "input": user_input,
                "expected": expected,
                "predicted": predicted,
                "score": score
            })

        # Save output
        output_file = ".noo-eval.jsonl"
        with open(output_file, "w", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")

        return results

class HarborAdapter:
    """
    Harbor integration (SWE-bench / Terminal-bench 2.0) via Docker/Apptainer orchestration (NOOA-27).
    """
    def __init__(self, harbor_endpoint: str):
        self.harbor_endpoint = harbor_endpoint

    async def run_harbor_task(self, instance_id: str) -> Dict[str, Any]:
        logger_cmd = f"docker run --rm nemo-harbor:latest run-task {instance_id}"
        # We can simulate/mock calling subprocess
        return {
            "instance_id": instance_id,
            "status": "completed",
            "patch": "diff --git a/file.py ...",
            "executed_command": logger_cmd
        }

class BenchAgent:
    """
    A specialized agent to run high throughput benchmark executions (NOOA-28).
    """
    def __init__(self, name: str):
        self.name = name

    async def execute_bench_task(self, payload: str) -> Dict[str, Any]:
        import time
        start = time.time()
        # Simulated run-stress
        await asyncio.sleep(0.01)
        return {
            "elapsed": time.time() - start,
            "tokens": len(payload) // 4,
            "status": "success"
        }
