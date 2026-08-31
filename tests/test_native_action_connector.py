"""Unit and integration tests for Native Action Connector."""

import unittest
import json
from native_action_connector.mcp_action_client import (
    NativeMCPActionClient,
    get_mock_native_tools_list,
)
from native_action_connector.config_generator import generate_secops_mcp_config


class TestNativeActionConnector(unittest.TestCase):
    """Test suite for SecOps OneMCP Native Action Connector."""

    def setUp(self):
        self.client = NativeMCPActionClient(
            endpoint_url="https://us-chronicle.googleapis.com/mcp",
            project_id="test-secops-project",
            customer_id="test-customer-id",
            region="us",
        )

    def test_mock_native_tools_list(self):
        """Verify mock native tool list contains valid tool definitions."""
        tools = get_mock_native_tools_list()
        self.assertTrue(len(tools) >= 3)
        for t in tools:
            self.assertIn("name", t)
            self.assertIn("description", t)
            self.assertIn("inputSchema", t)

    def test_list_available_actions(self):
        """Verify action tool discovery returns tool objects with names and schemas."""
        tools = self.client.list_available_actions()
        self.assertGreaterEqual(len(tools), 1)
        tool_names = [t.get("name") for t in tools]
        self.assertTrue(any(name in tool_names for name in ["list_cases", "list_investigations", "list_rules"]))

    def test_execute_action_payload_handling(self):
        """Verify action execution handles arguments and returns JSON-RPC response."""
        res = self.client.execute_action("get_case", {"caseId": "case_100"})
        self.assertIn("jsonrpc", res)
        self.assertEqual(res["jsonrpc"], "2.0")

    def test_generate_secops_mcp_config(self):
        """Verify mcpServers config dictionary format matches Gemini Enterprise specification."""
        config = generate_secops_mcp_config(
            tenant_name="TestSecOps",
            endpoint_url="https://us-chronicle.googleapis.com/mcp",
            project_id="my-test-project",
            timeout_ms=15000,
        )
        self.assertIn("mcpServers", config)
        self.assertIn("TestSecOps", config["mcpServers"])
        server_conf = config["mcpServers"]["TestSecOps"]
        self.assertEqual(server_conf["httpUrl"], "https://us-chronicle.googleapis.com/mcp")
        self.assertEqual(server_conf["authProviderType"], "google_credentials")
        self.assertEqual(server_conf["timeout"], 15000)
        self.assertEqual(server_conf["headers"]["X-Goog-User-Project"], "my-test-project")
        self.assertIn("https://www.googleapis.com/auth/chronicle", server_conf["oauth"]["scopes"])


if __name__ == "__main__":
    unittest.main()
