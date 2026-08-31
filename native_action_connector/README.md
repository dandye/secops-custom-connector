# Native Action Connector for SecOps OneMCP

Connects Gemini Enterprise & AI Agents directly to **SecOps OneMCP** endpoints for query-time tool discovery (`tools/list`) and live action execution (`tools/call`).

## Files
- `mcp_action_client.py`: Native MCP client simulating query-time tool execution.
- `config_generator.py`: Generates `mcpServers` JSON config for Gemini Enterprise / Gemini CLI.
- `main.py`: CLI runner.

## Usage
```bash
# List native actions:
python main.py --list-tools

# Call a native action tool:
python main.py --call-tool list_investigations

# Generate mcpServers configuration:
python main.py --generate-config
```
