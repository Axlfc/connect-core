import sys
import asyncio
import argparse
import os
import logging
from cli.config import load_config
from cli.http_client import CognitoClient
from cli.modes.print_mode import print_mode
from cli.modes.json_mode import json_mode
from cli.modes.rpc_mode import rpc_mode

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("cognito-cli")

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

            # For print and json mode, we need a prompt
            prompt = args.prompt
            if not prompt:
                if not sys.stdin.isatty():
                    prompt = sys.stdin.read()

            if not prompt:
                sys.stderr.write("Error: No prompt provided.\n")
                return 1

            messages = [{"role": "user", "content": prompt}]
            event_iterator = client.agent_loop(
                messages=messages,
                cwd=cwd,
                session_id=args.session_id
            )

            if args.mode == "json":
                return await json_mode(event_iterator, config)
            else: # print
                return await print_mode(event_iterator, config)

    except Exception as e:
        if args.mode == "rpc":
            # For RPC, we already handle errors inside rpc_mode mostly,
            # but if it fails before starting the loop:
            print(json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": "Internal error", "data": {"detail": str(e)}},
                "id": None
            }))
        else:
            # Check for network errors specifically
            import httpx
            if isinstance(e, (httpx.ConnectError, httpx.TimeoutException)):
                sys.stderr.write(f"Error: no se pudo conectar con {config.endpoint}: {str(e)}\n")
                return 2
            else:
                sys.stderr.write(f"Error: {str(e)}\n")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
