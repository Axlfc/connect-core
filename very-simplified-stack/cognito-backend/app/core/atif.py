import json
from typing import Any, Dict, List, Optional
import contextlib

class ATIFTrajectory:
    """
    Model representating Agent Trajectory Interchange Format v1.7 (NOOA-22).
    """
    def __init__(self, version: str = "1.7"):
        self.version = version
        self.trajectory_steps: List[Dict[str, Any]] = []

    def add_step(self, thought: str, action_name: str, action_args: Dict[str, Any], observation: str):
        self.trajectory_steps.append({
            "thought": thought,
            "action": {
                "name": action_name,
                "arguments": action_args
            },
            "observation": observation
        })

    def export_json(self) -> str:
        return json.dumps({
            "atif_version": self.version,
            "trajectory": self.trajectory_steps
        }, indent=2)

_CURRENT_ATIF_TRAJECTORY = None

def install_atif():
    global _CURRENT_ATIF_TRAJECTORY
    _CURRENT_ATIF_TRAJECTORY = ATIFTrajectory()

@contextlib.contextmanager
def atif_scope():
    global _CURRENT_ATIF_TRAJECTORY
    previous = _CURRENT_ATIF_TRAJECTORY
    _CURRENT_ATIF_TRAJECTORY = ATIFTrajectory()
    try:
        yield _CURRENT_ATIF_TRAJECTORY
    finally:
        _CURRENT_ATIF_TRAJECTORY = previous
