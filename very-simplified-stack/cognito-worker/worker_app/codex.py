import os
import asyncio
import json
import logging
import uuid
from typing import List, Dict, Any, AsyncIterator
from app.models.domain import ModelDescriptor

logger = logging.getLogger("cognito.worker.codex")

class CodexProvider:
    async def discover_models(self) -> List[ModelDescriptor]:
        raise NotImplementedError()

    async def execute_task(self, task_id: str, model: str, requirements: str, worktree_path: str, environment: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        raise NotImplementedError()

class MockCodexProvider(CodexProvider):
    async def discover_models(self) -> List[ModelDescriptor]:
        return [
            ModelDescriptor(
                model_identifier="codex.economy",
                display_name="Codex Luna (Economy)",
                executor="Codex",
                supported_reasoning_efforts=["low"],
                supported_input_modalities=["text"],
                is_available=True,
                capabilities=["coding", "generation"]
            ),
            ModelDescriptor(
                model_identifier="codex.balanced",
                display_name="Codex Terra (Balanced)",
                executor="Codex",
                supported_reasoning_efforts=["low", "medium"],
                supported_input_modalities=["text"],
                is_available=True,
                capabilities=["coding", "generation"]
            ),
            ModelDescriptor(
                model_identifier="codex.max",
                display_name="Codex Sol (Max)",
                executor="Codex",
                supported_reasoning_efforts=["low", "medium", "high"],
                supported_input_modalities=["text"],
                is_available=True,
                capabilities=["coding", "generation"]
            )
        ]

    async def execute_task(self, task_id: str, model: str, requirements: str, worktree_path: str, environment: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """
        Simulates running Codex App Server. Streams fake planning, tools, and done events.
        """
        yield {"type": "progress", "message": f"Planning task using model {model}..."}
        await asyncio.sleep(0.1)

        # Simulate read tool call
        yield {
            "type": "tool_call",
            "tool_call_id": "call_read_1",
            "tool_name": "read",
            "arguments": {"path": "README.md"}
        }
        await asyncio.sleep(0.1)

        # Yield tool result back (simulated)
        yield {
            "type": "progress",
            "message": "File read complete. Proceeding with modifications."
        }
        await asyncio.sleep(0.1)

        # Simulate write tool call
        yield {
            "type": "tool_call",
            "tool_call_id": "call_write_1",
            "tool_name": "write",
            "arguments": {"path": "src/feature.py", "content": "print('Hello World')"}
        }
        await asyncio.sleep(0.1)

        # Final delta & done
        yield {
            "type": "text_delta",
            "content": f"Task completed successfully! Modified src/feature.py using {model}."
        }
        yield {"type": "done", "stop_reason": "end_turn"}


class SubprocessCodexProvider(CodexProvider):
    """
    Launches and manages Codex App Server as a local subprocess using its supported
    stdio JSON-RPC transport.
    """
    def __init__(self, app_server_path: str = "codex-app-server"):
        self.app_server_path = app_server_path

    async def discover_models(self) -> List[ModelDescriptor]:
        # Launch subprocess, query model list via JSON-RPC, and exit
        try:
            proc = await asyncio.create_subprocess_exec(
                self.app_server_path, "--model-list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0:
                data = json.loads(stdout.decode())
                descriptors = []
                for m in data.get("models", []):
                    descriptors.append(ModelDescriptor(
                        model_identifier=m.get("id"),
                        display_name=m.get("name", m.get("id")),
                        executor="Codex",
                        supported_reasoning_efforts=m.get("reasoning_efforts", ["low"]),
                        is_available=True,
                        capabilities=["coding"]
                    ))
                return descriptors
        except Exception as e:
            logger.warning(f"Could not discover live Codex models via subprocess: {e}")
        # Return empty list if subprocess not available/fails, which tells the system Codex is not running
        return []

    async def execute_task(self, task_id: str, model: str, requirements: str, worktree_path: str, environment: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        # For execution, launch App Server in persistent JSON-RPC mode
        # Under normal conditions, we launch the process, pipe input and stream events.
        # Here we scaffold the subprocess connection protocol:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.app_server_path, "--session", task_id, "--model", model, "--workdir", worktree_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            # Stdio loop
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                event = json.loads(line.decode().strip())
                yield event
        except Exception as e:
            logger.error(f"Error executing Codex subprocess: {e}")
            yield {"type": "error", "message": str(e)}
