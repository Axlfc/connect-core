import sys
import asyncio
import argparse
import os
import json
import logging
from typing import Optional
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

from cli.config import load_config
from cli.http_client import CognitoClient
from cli.modes.print_mode import print_mode
from cli.modes.json_mode import json_mode
from cli.modes.rpc_mode import rpc_mode
from cli.slash_commands import handle_slash_command

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("cognito-cli")

async def interactive_loop(client: CognitoClient, config, cwd: str, session_id: Optional[str] = None) -> int:
    prompt_session = PromptSession(history=InMemoryHistory())
    current_session_id = session_id

    sys.stdout.write("Cognito CLI - Modo Interactivo\n")
    sys.stdout.write("Escribe tus consultas o comandos slash (/status, /trust, /compact, /clear). Usa Ctrl+C o Ctrl+D para salir.\n\n")
    sys.stdout.flush()

    while True:
        try:
            user_input = await prompt_session.prompt_async("cognito> ")
        except (KeyboardInterrupt, EOFError):
            sys.stdout.write("\n[Saliendo de Cognito CLI...]\n")
            sys.stdout.flush()
            break

        line = user_input.strip()
        if not line:
            continue

        if line in ("/exit", "/quit"):
            sys.stdout.write("[Saliendo de Cognito CLI...]\n")
            sys.stdout.flush()
            break

        # 1. Intercept slash commands
        handled, current_session_id = await handle_slash_command(line, cwd, current_session_id)
        if handled:
            continue

        # 2. Non-slash input -> send to LLM agent_loop via API
        messages = [{"role": "user", "content": line}]
        event_iterator = client.agent_loop(
            messages=messages,
            cwd=cwd,
            session_id=current_session_id
        )

        code, new_session_id = await print_mode(event_iterator, config)
        if new_session_id:
            current_session_id = new_session_id

    return 0

async def main():
    parser = argparse.ArgumentParser(description="Cognito CLI Client")
    parser.add_argument("prompt", nargs="?", help="The prompt to send. If missing, reads from stdin.")
    parser.add_argument("--mode", choices=["print", "json", "rpc"], default="print", help="Output mode (default: print)")
    parser.add_argument("--endpoint", help="Server endpoint URL")
    parser.add_argument("--threshold", type=float, help="Uncertainty threshold")
    parser.add_argument("--no-color", action="store_true", help="Disable colors")
    parser.add_argument("--timeout", type=float, help="Network timeout in seconds")
    parser.add_argument("--cwd", help="Workspace directory (default: current directory)")
    parser.add_argument("--session-id", help="Session ID to continue (or 'latest')")
    parser.add_argument("--color-mode", choices=["full", "threshold", "none"], help="Color mode")

    args = parser.parse_args()

    config = load_config(
        cli_endpoint=args.endpoint,
        cli_threshold=args.threshold,
        cli_no_color=args.no_color,
        cli_timeout=args.timeout,
        cli_color_mode=args.color_mode
    )

    cwd = os.path.realpath(args.cwd or os.getcwd())

    try:
        async with CognitoClient(config.endpoint, config.timeout) as client:
            if args.mode == "rpc":
                return await rpc_mode(client, config)

            # Determine prompt if provided via arg or stdin pipe
            prompt = args.prompt
            is_piped = not sys.stdin.isatty()

            if not prompt and is_piped:
                prompt = sys.stdin.read().strip()

            # If mode is json, we must have a prompt
            if args.mode == "json":
                if not prompt:
                    sys.stderr.write("Error: No prompt provided.\n")
                    return 1
                messages = [{"role": "user", "content": prompt}]
                event_iterator = client.agent_loop(
                    messages=messages,
                    cwd=cwd,
                    session_id=args.session_id
                )
                return await json_mode(event_iterator, config)

            # If print mode and a prompt was provided
            if prompt:
                handled, new_session_id = await handle_slash_command(prompt, cwd, args.session_id)
                if handled:
                    return 0

                messages = [{"role": "user", "content": prompt}]
                event_iterator = client.agent_loop(
                    messages=messages,
                    cwd=cwd,
                    session_id=args.session_id
                )
                code, _ = await print_mode(event_iterator, config)
                return code

            # Interactive print mode
            return await interactive_loop(client, config, cwd, args.session_id)

    except Exception as e:
        if args.mode == "rpc":
            print(json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": "Internal error", "data": {"detail": str(e)}},
                "id": None
            }))
        else:
            import httpx
            if isinstance(e, (httpx.ConnectError, httpx.TimeoutException)):
                sys.stderr.write(f"Error: no se pudo conectar con {config.endpoint}: {str(e)}\n")
                return 2
            else:
                sys.stderr.write(f"Error: {str(e)}\n")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
