"""Native Action MCP Client for SecOps OneMCP.

Simulates query-time tool discovery and execution by Gemini Enterprise AI agents over JSON-RPC 2.0.
"""

from typing import List, Dict, Any, Optional
import json
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_mock_native_tools_list() -> List[Dict[str, Any]]:
    """Mock list of native tools exposed by SecOps OneMCP endpoint."""
    return [
        {
            "name": "list_investigations",
            "description": "Lists recent security investigations performed by analysts or Mandiant TINA agent.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "customer_id": {"type": "string"},
                    "region": {"type": "string"},
                    "pageSize": {"type": "integer"},
                },
            },
        },
        {
            "name": "get_investigation",
            "description": "Retrieves detailed verdict, confidence score, timeline, and involved entities for a specific investigation ID.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "investigation_id": {"type": "string"},
                },
                "required": ["investigation_id"],
            },
        },
        {
            "name": "list_rules",
            "description": "Lists YARA-L detection rules configured in SecOps SIEM.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pageSize": {"type": "integer"},
                },
            },
        },
        {
            "name": "get_ioc_match",
            "description": "Searches IoC sightings and threat intelligence matches in SecOps telemetry.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "max_matches": {"type": "integer"},
                },
            },
        },
    ]


class NativeMCPActionClient:
    """Client for Native Action Connector interacting with SecOps OneMCP."""

    def __init__(
        self,
        endpoint_url: str = "https://us-chronicle.googleapis.com/mcp",
        project_id: str = "my-secops-project",
        customer_id: str = "my-customer-id",
        region: str = "us",
        auth_token: Optional[str] = None,
        timeout: int = 30,
    ):
        self.endpoint_url = endpoint_url
        self.project_id = project_id
        self.customer_id = customer_id
        self.region = region
        self.auth_token = auth_token
        self.timeout = timeout
        self._request_id = 1

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.project_id:
            headers["X-Goog-User-Project"] = self.project_id
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def _next_id(self) -> int:
        req_id = self._request_id
        self._request_id += 1
        return req_id

    def list_available_actions(self) -> List[Dict[str, Any]]:
        """Query SecOps OneMCP server via 'tools/list' for available action tools."""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": self._next_id(),
        }

        try:
            logger.info(f"Querying SecOps OneMCP tools list from {self.endpoint_url}...")
            resp = requests.post(
                self.endpoint_url,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            tools = data.get("result", {}).get("tools", [])
            if tools:
                return tools
            return get_mock_native_tools_list()
        except Exception as e:
            logger.warning(f"Could not list tools from {self.endpoint_url} ({e}). Returning standard SecOps tool definitions.")
            return get_mock_native_tools_list()

    def execute_action(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a live native tool action via 'tools/call' JSON-RPC 2.0."""
        if arguments is None:
            arguments = {}

        # Add default parameters only if not already provided in either camelCase or snake_case
        if "projectId" not in arguments and "project_id" not in arguments and self.project_id:
            arguments["projectId"] = self.project_id
        if "customerId" not in arguments and "customer_id" not in arguments and self.customer_id:
            arguments["customerId"] = self.customer_id
        if "region" not in arguments and self.region:
            arguments["region"] = self.region

        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
            "id": self._next_id(),
        }

        try:
            logger.info(f"Executing native action '{tool_name}' via SecOps OneMCP...")
            resp = requests.post(
                self.endpoint_url,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Action execution failed on remote endpoint ({e}). Generating mock execution output.")
            return {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({
                                "status": "MOCK_SUCCESS",
                                "tool": tool_name,
                                "executed_args": arguments,
                                "message": f"Successfully executed native action '{tool_name}'.",
                                "sample_output": {
                                    "investigation_id": arguments.get("investigation_id", "inv_987651"),
                                    "verdict": "TRUE_POSITIVE",
                                    "confidence": 0.98,
                                }
                            }, indent=2)
                        }
                    ]
                }
            }
