"""CLI Runner for Native Action Connector (SecOps OneMCP).

Usage:
  # List available native actions:
  python native_action_connector/main.py --list-tools

  # Call a native action tool:
  python native_action_connector/main.py --call-tool list_investigations

  # Generate mcpServers configuration:
  python native_action_connector/main.py --generate-config
"""

import argparse
import sys
import json
import logging
from native_action_connector.mcp_action_client import NativeMCPActionClient
from native_action_connector.config_generator import generate_secops_mcp_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Native SecOps OneMCP Action Connector CLI")
    parser.add_argument("--secops-mcp-url", default="https://us-chronicle.googleapis.com/mcp", help="SecOps OneMCP endpoint")
    parser.add_argument("--secops-project-id", default="my-secops-project", help="SecOps GCP Project ID")
    parser.add_argument("--secops-customer-id", default="my-customer-id", help="SecOps Customer ID")
    parser.add_argument("--secops-region", default="us", help="SecOps Region")

    parser.add_argument("--list-tools", action="store_true", help="List available native actions from SecOps OneMCP")
    parser.add_argument("--call-tool", help="Name of native tool to execute")
    parser.add_argument("--tool-args", default="{}", help="JSON string of arguments for tool call")
    parser.add_argument("--generate-config", action="store_true", help="Generate Gemini Enterprise mcpServers configuration")

    args = parser.parse_args()

    auth_token = None
    try:
        import google.auth
        from google.auth.transport.requests import Request
        creds, auto_project = google.auth.default(scopes=[
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/chronicle"
        ])
        creds.refresh(Request())
        auth_token = creds.token
        if args.secops_project_id == "my-secops-project" and auto_project:
            args.secops_project_id = auto_project
    except Exception as e:
        logger.debug(f"ADC auto-auth note: {e}")

    client = NativeMCPActionClient(
        endpoint_url=args.secops_mcp_url,
        project_id=args.secops_project_id,
        customer_id=args.secops_customer_id,
        region=args.secops_region,
        auth_token=auth_token,
    )

    if args.generate_config:
        config = generate_secops_mcp_config(
            endpoint_url=args.secops_mcp_url,
            project_id=args.secops_project_id,
        )
        print("\n--- Generated Native Action mcpServers Config ---")
        print(json.dumps(config, indent=2))
        return

    if args.list_tools:
        tools = client.list_available_actions()
        print(f"\n--- Discovered {len(tools)} Native SecOps Actions ---")
        for tool in tools:
            print(f"• Name: {tool.get('name')}")
            print(f"  Description: {tool.get('description')}")
            print(f"  Schema: {json.dumps(tool.get('inputSchema', {}))}\n")
        return

    if args.call_tool:
        try:
            parsed_args = json.loads(args.tool_args)
        except Exception as e:
            logger.error(f"Invalid JSON string for --tool-args ({e})")
            sys.exit(1)

        result = client.execute_action(args.call_tool, parsed_args)
        print(f"\n--- Native Action Execution Result ('{args.call_tool}') ---")
        print(json.dumps(result, indent=2))
        return

    # Default action if no flags provided
    tools = client.list_available_actions()
    print(f"Discovered {len(tools)} native actions. Use --list-tools, --call-tool, or --generate-config.")


if __name__ == "__main__":
    main()
