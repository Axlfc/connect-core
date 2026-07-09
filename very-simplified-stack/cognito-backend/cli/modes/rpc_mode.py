import sys
import json
import asyncio
import logging
from cli.config import CognitoConfig
from cli.http_client import CognitoClient

logger = logging.getLogger(__name__)

async def rpc_mode(client: CognitoClient, config: CognitoConfig):
    # Sequential JSON-RPC 2.0 loop
    loop = asyncio.get_event_loop()

    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            send_error(None, -32700, "Parse error")
            continue

        if not isinstance(request, dict) or "jsonrpc" not in request or "method" not in request:
            send_error(request.get("id") if isinstance(request, dict) else None, -32600, "Invalid Request")
            continue

        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        try:
            if method == "health":
                result = await client.health()
                send_result(request_id, result)

            elif method == "agent.sessions.list":
                result = await client.list_sessions(cwd=params.get("cwd"))
                send_result(request_id, result)

            elif method == "agent.sessions.get":
                sid = params.get("session_id")
                if not sid:
                    send_error(request_id, -32602, "Invalid params: session_id required")
                else:
                    result = await client.get_session(sid)
                    send_result(request_id, result)

            elif method == "agent.sessions.fork":
                sid = params.get("session_id")
                if not sid:
                    send_error(request_id, -32602, "Invalid params: session_id required")
                else:
                    result = await client.fork_session(sid)
                    send_result(request_id, {"session_id": result})

            elif method == "agent.loop":
                messages = params.get("messages")
                cwd = params.get("cwd")
                if not messages or not cwd:
                    send_error(request_id, -32602, "Invalid params: messages and cwd required")
                    continue

                try:
                    session_id = None
                    stop_reason = "unknown"
                    async for event in client.agent_loop(
                        messages=messages,
                        cwd=cwd,
                        session_id=params.get("session_id"),
                        model_params=params.get("model_params")
                    ):
                        if event.get("type") == "session_info":
                            session_id = event.get("session_id")
                        elif event.get("type") == "done":
                            stop_reason = event.get("stop_reason")
                            if stop_reason == "error":
                                # We'll send the result anyway but we could handle differently
                                pass

                        # Send notification for each event
                        send_notification("agent.event", {
                            "request_id": request_id,
                            **event
                        })

                    if stop_reason == "error":
                         # The actual ErrorEvent or DoneEvent with error will have been sent as notification
                         pass

                    send_result(request_id, {
                        "session_id": session_id,
                        "stop_reason": stop_reason
                    })
                except Exception as e:
                    logger.error(f"Upstream error in agent.loop: {e}", exc_info=True)
                    send_error(request_id, -32001, "Upstream error", {"detail": str(e)})

            else:
                send_error(request_id, -32601, "Method not found")

        except Exception as e:
            logger.error(f"Internal error processing {method}: {e}", exc_info=True)
            send_error(request_id, -32000, "Backend unreachable", {"detail": str(e)})

    return 0

def send_result(request_id, result):
    if request_id is None: return
    response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result
    }
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()

def send_error(request_id, code, message, data=None):
    response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message
        }
    }
    if data:
        response["error"]["data"] = data
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()

def send_notification(method, params):
    notification = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params
    }
    sys.stdout.write(json.dumps(notification) + "\n")
    sys.stdout.flush()
