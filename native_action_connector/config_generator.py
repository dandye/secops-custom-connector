"""Configuration Generator for Native SecOps OneMCP Action Connector.

Generates mcpServers JSON configuration for Gemini Enterprise / Gemini CLI.
"""

from typing import Dict, Any
import json
import argparse
import sys


def generate_secops_mcp_config(
    tenant_name: str = "GoogleSecOps",
    endpoint_url: str = "https://us-chronicle.googleapis.com/mcp",
    project_id: str = "my-secops-project",
    timeout_ms: int = 30000,
) -> Dict[str, Any]:
    """Generates mcpServers configuration dictionary."""
    return {
        "mcpServers": {
            tenant_name: {
                "httpUrl": endpoint_url,
                "authProviderType": "google_credentials",
                "oauth": {
                    "scopes": [
                        "https://www.googleapis.com/auth/chronicle",
                        "https://www.googleapis.com/auth/cloud-platform",
                    ]
                },
                "timeout": timeout_ms,
                "headers": {
                    "X-Goog-User-Project": project_id,
                },
            }
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Generate SecOps OneMCP Action Connector Configuration")
    parser.add_argument("--tenant-name", default="GoogleSecOps", help="Custom MCP Server tenant name")
    parser.add_argument("--endpoint-url", default="https://us-chronicle.googleapis.com/mcp", help="SecOps OneMCP endpoint")
    parser.add_argument("--project-id", default="my-secops-project", help="Google Cloud Project ID")
    parser.add_argument("--output-file", help="Optional output JSON file path")

    args = parser.parse_args()

    config = generate_secops_mcp_config(
        tenant_name=args.tenant_name,
        endpoint_url=args.endpoint_url,
        project_id=args.project_id,
    )

    formatted_json = json.dumps(config, indent=2)

    if args.output_file:
        with open(args.output_file, "w") as f:
            f.write(formatted_json + "\n")
        print(f"Written SecOps OneMCP action configuration to: {args.output_file}")
    else:
        print("\n--- Gemini Enterprise / Gemini CLI Native Action MCP Config ---")
        print(formatted_json)


if __name__ == "__main__":
    main()
