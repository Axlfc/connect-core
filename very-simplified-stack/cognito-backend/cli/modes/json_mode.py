import sys
import json
from cli.config import CognitoConfig

async def json_mode(event_iterator, config: CognitoConfig):
    exit_code = 0
    async for event in event_iterator:
        sys.stdout.write(json.dumps(event) + "\n")
        sys.stdout.flush()

        if event.get("type") == "done":
            if event.get("stop_reason") != "end_turn":
                exit_code = 1
        elif event.get("type") == "error":
            exit_code = 1

    return exit_code
