"""
Unit tests for the N8nMCPAgent.

This test suite covers the core functionality of the N8nMCPAgent, including
plan parsing, workflow generation, and validation.
"""

import unittest
import json
from unittest.mock import patch, MagicMock

# Ensure the parent directory is in the path to allow agent imports
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from agents.n8n_mcp_agent import N8nMCPAgent


class TestN8nMCPAgent(unittest.TestCase):
    """Test suite for the N8nMCPAgent."""

    def setUp(self):
        """Set up the test case."""
        self.agent = N8nMCPAgent(n8n_base_url="http://fake-n8n-url:5678", api_key="fake-api-key")
        self.toon_plan_str = "dummy toon plan"
        self.structured_plan = self.agent.parse_toon_plan(self.toon_plan_str)

    def test_parse_toon_plan(self):
        """Test that the TOON plan parsing (currently hardcoded) returns the expected structure."""
        plan = self.agent.parse_toon_plan(self.toon_plan_str)
        self.assertIsInstance(plan, dict)
        self.assertIn("name", plan)
        self.assertIn("trigger", plan)
        self.assertIn("steps", plan)
        self.assertEqual(plan["name"], "Dynamic Content Pipeline")

    def test_generate_n8n_workflow_basic_structure(self):
        """Test that the generated workflow has the correct basic structure and is valid JSON."""
        workflow_json = self.agent.generate_n8n_workflow(self.structured_plan)
        self.assertIsInstance(workflow_json, str)

        # Check if it's valid JSON
        try:
            workflow_data = json.loads(workflow_json)
        except json.JSONDecodeError:
            self.fail("generate_n8n_workflow did not produce valid JSON.")

        self.assertIn("name", workflow_data)
        self.assertIn("nodes", workflow_data)
        self.assertIn("connections", workflow_data)
        self.assertEqual(workflow_data["name"], self.structured_plan["name"])

    def test_generate_n8n_workflow_nodes_and_connections_structure(self):
        """Test the structure of the generated nodes and connections."""
        workflow_json = self.agent.generate_n8n_workflow(self.structured_plan)
        workflow_data = json.loads(workflow_json)

        # Test node count
        expected_node_count = 1 + len(self.structured_plan["steps"])
        self.assertEqual(len(workflow_data["nodes"]), expected_node_count)

        # Test connections structure
        connections = workflow_data["connections"]
        self.assertIsInstance(connections, dict, "Connections should be a dictionary.")

        # The number of connections should equal the number of steps
        expected_connection_count = len(self.structured_plan["steps"])
        self.assertEqual(len(connections), expected_connection_count)

        # Check that a specific connection is correctly formed
        # The trigger node 'startNode' should be a key in the connections dict
        self.assertIn("startNode", connections)
        start_node_connection = connections["startNode"]
        self.assertIn("main", start_node_connection)

        # The connection should point to the first step, 'fetch_rss'
        first_step_node_id = self.structured_plan["steps"][0]["id"]
        self.assertEqual(start_node_connection["main"][0][0]["node"], first_step_node_id)

    def test_http_request_node_generation(self):
        """Test that httpRequest nodes are generated with the correct URL and method."""
        workflow_json = self.agent.generate_n8n_workflow(self.structured_plan)
        workflow_data = json.loads(workflow_json)

        # Find the 'summarize' agent call node
        summarize_node = next((node for node in workflow_data["nodes"] if node["id"] == "summarize"), None)
        self.assertIsNotNone(summarize_node)
        self.assertEqual(summarize_node["type"], "n8n-nodes-base.httpRequest")

        params = summarize_node["parameters"]
        self.assertEqual(params["method"], "POST")
        self.assertTrue(params["url"].startswith("http://mcp-server:8000"))
        self.assertTrue(params["url"].endswith("/agent/summarizer"))
        self.assertTrue(params["sendBody"])

    def test_validate_workflow(self):
        """Test the internal workflow validation logic."""
        valid_workflow_json = self.agent.generate_n8n_workflow(self.structured_plan)
        self.assertTrue(self.agent.validate_workflow(valid_workflow_json))

        invalid_workflow_json = '{"invalid": "json"}'
        self.assertFalse(self.agent.validate_workflow(invalid_workflow_json))

        not_json = 'this is not json'
        self.assertFalse(self.agent.validate_workflow(not_json))

    @patch('requests.post')
    def test_deploy_workflow_success(self, mock_post):
        """
        Test the deploy_workflow method (currently a placeholder)
        NOTE: This test will need to be updated when real deployment logic is added.
        """
        # For now, we just test the simulation
        workflow_json = self.agent.generate_n8n_workflow(self.structured_plan)
        result = self.agent.deploy_workflow(workflow_json)
        self.assertEqual(result, "workflow_id_123")

    @patch('requests.post')
    def test_deploy_workflow_failure(self, mock_post):
        """
        Test the deploy_workflow method for a failure case.
        NOTE: This is a placeholder and will need to be updated.
        """
        # This is a placeholder for when the real deployment logic is implemented
        # For example, we might mock a non-200 response and assert an exception is raised.
        self.assertTrue(True) # Placeholder assertion

if __name__ == '__main__':
    unittest.main()
