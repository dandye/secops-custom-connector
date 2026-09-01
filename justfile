# Top-level Justfile for SecOps Connectors

default: help

# Display available commands
help:
	@echo "================================================================"
	@echo " SecOps Connectors (Ingestion & Native Action Connectors)"
	@echo "================================================================"
	@echo "  just setup                     - Setup python virtual environment and install requirements"
	@echo ""
	@echo "  --- Ingestion Connector (SecOps Investigations) ---"
	@echo "  just dry-run-ingestion         - Run offline dry-run test for Investigations ingestion"
	@echo "  just run-ingestion-inline      - Run live inline ingestion for SecOps Investigations"
	@echo "  just run-ingestion-gcs BUCKET  - Run live GCS bulk ingestion for SecOps Investigations"
	@echo ""
	@echo "  --- Native Action Connector (SecOps OneMCP Tools) ---"
	@echo "  just test-action-list          - List native SecOps OneMCP tools"
	@echo "  just test-action-exec TOOL     - Call a native SecOps OneMCP action tool"
	@echo "  just generate-mcp-config       - Generate Gemini Enterprise mcpServers configuration"

# Setup python virtualenv and dependencies
setup:
	python3 -m venv .venv
	.venv/bin/pip install --index-url https://pypi.org/simple -r requirements.txt

# Run complete test suite (unit and e2e)
test:
	PYTHONPATH=. .venv/bin/python -m unittest discover -s tests -p "test_*.py" -v

# Run offline dry-run test for SecOps Investigations Ingestion Connector
dry-run-ingestion:
	PYTHONPATH=. .venv/bin/python ingestion_connector/main.py --dry-run

# Run live inline ingestion for SecOps Investigations
run-ingestion-inline project_id="ucs-3p-connectors-testing" data_store_id="secops-inv-ds1":
	PYTHONPATH=. .venv/bin/python ingestion_connector/main.py --project-id {{project_id}} --data-store-id {{data_store_id}} --mode inline

# Run live GCS bulk ingestion for SecOps Investigations
run-ingestion-gcs bucket project_id="ucs-3p-connectors-testing" data_store_id="secops-inv-ds1":
	PYTHONPATH=. .venv/bin/python ingestion_connector/main.py --project-id {{project_id}} --data-store-id {{data_store_id}} --mode gcs --gcs-bucket {{bucket}}

# List native SecOps OneMCP action tools
test-action-list:
	PYTHONPATH=. .venv/bin/python native_action_connector/main.py --list-tools

# Call a native SecOps OneMCP action tool
test-action-exec tool="list_investigations":
	PYTHONPATH=. .venv/bin/python native_action_connector/main.py --call-tool {{tool}}

# Generate mcpServers configuration for Gemini Enterprise / Gemini CLI
generate-mcp-config project_id="my-secops-project":
	PYTHONPATH=. .venv/bin/python native_action_connector/config_generator.py --project-id {{project_id}}
