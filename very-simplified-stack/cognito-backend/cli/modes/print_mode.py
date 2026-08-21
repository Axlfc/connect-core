import sys
from cli.config import CognitoConfig
from typing import Dict, Any, Tuple, Optional

RESET = "\x1b[0m"

def get_uncertainty_color(score: float) -> str:
    if score < 0.5:
        # blue (100, 200, 255) -> amber (255, 200, 60)
        t = score / 0.5
        r = int(100 + t * (255 - 100))
        g = 200
        b = int(255 + t * (60 - 255))
    else:
        # amber (255, 200, 60) -> red (255, 60, 40)
        t = (score - 0.5) / 0.5
        r = 255
        g = int(200 + t * (60 - 200))
        b = int(60 + t * (40 - 60))
    return f"\x1b[38;2;{r};{g};{b}m"

async def print_mode(event_iterator, config: CognitoConfig) -> Tuple[int, Optional[str]]:
    session_id = None
    async for event in event_iterator:
        event_type = event.get("type")

        if event_type == "session_info":
            session_id = event.get("session_id")
            sys.stderr.write(f"[session: {session_id}]\n")
            sys.stderr.flush()

        elif event_type == "text_delta":
            content = event.get("content", "")
            uncertainty = event.get("uncertainty")

            if not config.no_color and config.enable_uncertainty and uncertainty is not None:
                if config.color_mode == "threshold":
                    if uncertainty >= config.uncertainty_threshold:
                        sys.stdout.write(f"\x1b[31m{content}{RESET}")
                    else:
                        sys.stdout.write(content)
                else: # full
                    color = get_uncertainty_color(uncertainty)
                    sys.stdout.write(f"{color}{content}{RESET}")
            else:
                sys.stdout.write(content)
            sys.stdout.flush()

        elif event_type == "tool_call":
            sys.stderr.write(f"→ ejecutando {event.get('tool_name')}({event.get('arguments')})\n")
            sys.stderr.flush()

        elif event_type == "tool_result":
            output = event.get("output", "")
            size = len(output)
            sys.stderr.write(f"← {event.get('tool_name')}: {size} bytes\n")
            sys.stderr.flush()

        elif event_type == "done":
            stop_reason = event.get("stop_reason")
            if stop_reason != "end_turn":
                sys.stderr.write(f"[done: {stop_reason}]\n")
                if event.get("error_message"):
                    sys.stderr.write(f"Error: {event.get('error_message')}\n")
                sys.stderr.flush()
            sys.stdout.write("\n")
            sys.stdout.flush()
            return (0 if stop_reason == "end_turn" else 1), session_id

        elif event_type == "error":
            sys.stderr.write(f"Error: {event.get('message')}\n")
            sys.stderr.flush()
            return 1, session_id

    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0, session_id
