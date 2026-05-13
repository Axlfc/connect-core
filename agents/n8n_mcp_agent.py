"""
n8n MCP Agent - A specialized agent for building and deploying n8n workflows.

This agent can translate a high-level plan (initially represented as a Python dictionary,
eventually as a TOON plan) into a valid n8n workflow JSON format. It will also
be responsible for deploying and managing these workflows via the n8n API.
"""
import logging
import json
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class N8nMCPAgent:
    """
    Agent responsible for generating, deploying, and managing n8n workflows.
    """
    def __init__(self, n8n_base_url: str = "http://localhost:5678", api_key: Optional[str] = None):
        """
        Initialize the N8nMCPAgent.

        Args:
            n8n_base_url: The base URL of the n8n instance.
            api_key: The API key for authenticating with the n8n API.
        """
        self.n8n_base_url = n8n_base_url
        self.api_key = api_key
        logger.info(f"N8nMCPAgent initialized for n8n instance at {n8n_base_url}")

    def parse_toon_plan(self, toon: str) -> Dict[str, Any]:
        """
        Parses a TOON plan string into a structured dictionary.

        NOTE: This is a placeholder. For now, it returns a hardcoded
              dictionary representing the "Dynamic Content Pipeline" plan.

        Args:
            toon: The TOON plan string.

        Returns:
            A dictionary representing the structured plan.
        """
        logger.debug("Parsing TOON plan (using hardcoded plan for now).")
        # This hardcoded plan simulates the output of a TOON parser for the content pipeline
        return {
            "name": "Dynamic Content Pipeline",
            "trigger": {
                "type": "schedule",
                "params": {"interval": "every 6 hours"}
            },
            "steps": [
                {"id": "fetch_rss", "tool": "fetch.rss", "params": {"url": "https://arxiv.org/rss/cs.AI"}},
                {"id": "summarize", "tool": "call.agent.summarizer", "params": {"content": "{{$json.items[0].content}}"}},
                {"id": "create_prompt", "tool": "call.agent.creative", "params": {"concept": "{{$json.summary}}"}},
                {"id": "generate_image", "tool": "ai.image.comfyui", "params": {"prompt": "{{$json.image_prompt}}"}},
                {"id": "write_post", "tool": "call.agent.writer", "params": {"topic": "{{$json.summary}}"}},
                {"id": "post_blog", "tool": "post.wordpress", "params": {"title": "{{$json.title}}", "content": "{{$json.post}}", "image": "{{$json.image_url}}"}},
                {"id": "post_social", "tool": "post.twitter", "params": {"text": "{{$json.tweet}}", "media": "{{$json.image_url}}"}}
            ]
        }

    def generate_n8n_workflow(self, plan: Dict[str, Any]) -> str:
        """
        Generates an n8n workflow JSON from a structured plan.

        Args:
            plan: A dictionary representing the structured plan.

        Returns:
            A JSON string representing the n8n workflow.
        """
        logger.info(f"Generating n8n workflow for plan: {plan.get('name', 'Untitled')}")

        nodes = []
        connections = {}

        # Mapping from our plan tool names to n8n node types and configurations
        TOOL_TO_N8N_MAP = {
            "schedule": {"type": "n8n-nodes-base.cron", "version": 1},
            "fetch.rss": {"type": "n8n-nodes-base.rssFeedRead", "version": 1},
            "call.agent.summarizer": {"type": "n8n-nodes-base.httpRequest", "version": 1, "endpoint": "/agent/summarizer"},
            "call.agent.creative": {"type": "n8n-nodes-base.httpRequest", "version": 1, "endpoint": "/agent/creative"},
            "ai.image.comfyui": {"type": "n8n-nodes-base.httpRequest", "version": 1, "endpoint": "http://comfyui:8188/prompt"},
            "call.agent.writer": {"type": "n8n-nodes-base.httpRequest", "version": 1, "endpoint": "/agent/writer"},
            "post.wordpress": {"type": "n8n-nodes-base.wordpress", "version": 1},
            "post.twitter": {"type": "n8n-nodes-base.twitter", "version": 1},
        }

        # Create Trigger Node
        trigger_node_id = "startNode"
        trigger_plan = plan["trigger"]
        trigger_tool_info = TOOL_TO_N8N_MAP.get(trigger_plan["type"])

        # Translate plan params to n8n params. E.g. "every 6 hours" -> "every6Hours"
        trigger_params = {}
        if "interval" in trigger_plan.get("params", {}):
            interval_str = trigger_plan["params"]["interval"]
            # A more robust solution would be a proper parser
            n8n_rule = interval_str.replace(" ", "")
            trigger_params["rule"] = n8n_rule

        nodes.append({
            "parameters": trigger_params,
            "name": trigger_plan["type"].replace("_", " ").title(),
            "type": trigger_tool_info["type"],
            "typeVersion": trigger_tool_info["version"],
            "position": [250, 300],
            "id": trigger_node_id,
        })

        last_node_id = trigger_node_id

        # Create Step Nodes and Connections
        for i, step in enumerate(plan["steps"]):
            node_id = step["id"]
            tool_info = TOOL_TO_N8N_MAP.get(step["tool"])
            if not tool_info:
                logger.warning(f"No n8n node mapping found for tool: {step['tool']}. Skipping.")
                continue

            params = step.get("params", {})
            # Special handling for httpRequest nodes to structure the parameters correctly
            if tool_info["type"] == "n8n-nodes-base.httpRequest":
                # Assume agent calls are POST requests to the MCP server
                is_agent_call = step["tool"].startswith("call.agent")
                url = f"http://mcp-server:8000{tool_info['endpoint']}" if is_agent_call else tool_info["endpoint"]

                final_params = {
                    "url": url,
                    "method": "POST",
                    "sendBody": True,
                    "body": json.dumps(params),
                    "json": True, # Automatically parse the response as JSON
                    "options": {}
                }
            else:
                final_params = params

            node = {
                "parameters": final_params,
                "name": step["id"].replace("_", " ").title(),
                "type": tool_info["type"],
                "typeVersion": tool_info["version"],
                "position": [250 + (i + 1) * 200, 300],
                "id": node_id,
            }
            nodes.append(node)

            # Create a connection from the previous node.
            # The key of the connections dictionary is the source node ID.
            connections[last_node_id] = {
                "main": [[{
                    "node": node_id,
                    "type": "main",
                    "index": 0
                }]]
            }
            last_node_id = node_id

        workflow = {
            "name": plan["name"],
            "nodes": nodes,
            "connections": connections,
            "active": False,
            "settings": {},
            "id": "1" # Placeholder ID
        }

        return json.dumps(workflow, indent=2)

    def deploy_workflow(self, workflow_json: str) -> str:
        """
        Deploys a workflow to the n8n instance.

        (Placeholder for now - would involve an HTTP POST request)

        Args:
            workflow_json: The JSON string of the workflow to deploy.

        Returns:
            The ID of the deployed workflow.
        """
        logger.info("Deploying workflow to n8n (simulation)...")
        workflow_data = json.loads(workflow_json)
        logger.info(f"Successfully deployed workflow: {workflow_data['name']}")
        return "workflow_id_123" # Dummy ID

    def validate_workflow(self, workflow_json: str) -> bool:
        """
        Validates the structure of the n8n workflow JSON.

        (Placeholder for now - would involve schema validation)

        Args:
            workflow_json: The JSON string of the workflow.

        Returns:
            True if the workflow is valid, False otherwise.
        """
        try:
            data = json.loads(workflow_json)
            is_valid = "nodes" in data and "connections" in data and "name" in data
            if is_valid:
                logger.info("Workflow JSON structure is valid.")
            else:
                logger.warning("Workflow JSON structure is invalid.")
            return is_valid
        except json.JSONDecodeError:
            logger.error("Failed to decode workflow JSON.")
            return False
