# SecOps Connectors Suite for Gemini Enterprise
### Complete Setup, Configuration, and Deployment Guide

This repository contains a production-ready solution for integrating **Google SecOps (Chronicle SIEM & SOAR)** with **Gemini Enterprise & Discovery Engine**.

It supports two distinct integration architectures:
1. **[Data Ingestion Connector](ingestion_connector/)**: Periodically harvests **SecOps Investigations** (verdicts, confidence scores, timelines, involved entities), converts them into `discoveryengine.Document` protobuf messages, and indexes them into Discovery Engine Data Stores for grounded enterprise search & RAG.
2. **[Native Action Connector](native_action_connector/)**: Integrates **SecOps OneMCP** directly as an Agent Tool / Action Connector for live, query-time tool discovery (`tools/list`) and execution (`tools/call`) by Gemini Enterprise AI agents.

---

## 📚 Documentation Index

* **[Architecture & Security Guide](docs/architecture.md)**: Component diagrams, data flow models, Protobuf schemas, and Identity Mapping Store (IMS) ACL enforcement.
* **[Usage & Operations Guide](docs/usage_guide.md)**: Personas, sample Gemini Enterprise RAG queries, prompt walkthroughs, and Cloud Run / Cloud Scheduler automation patterns.
* **[Gemini Enterprise & Agent Integration Guide](docs/gemini_enterprise_integration.md)**: Step-by-step setup for attaching Discovery Engine DataStores to Gemini Search Apps, configuring `mcpServers`, and Gemini CLI integration.

---

## 🏗️ Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                                 GOOGLE SECOPS                                     |
|                      (Chronicle SIEM & SOAR OneMCP API)                           |
+------------------------------------------+----------------------------------------+
                                           |
                   +-----------------------+-----------------------+
                   |                                               |
                   v                                               v
     [ 1. INGESTION CONNECTOR ]                        [ 2. NATIVE ACTION CONNECTOR ]
  Harvests SecOps Investigations                    Direct Query-Time Tool Execution
                   |                                               |
                   v                                               v
    Discovery Engine Data Store                         Gemini Enterprise Agent Space
(Incremental or Full Reconciliation)                  (Live Action Execution via OneMCP)
```

---

## 📋 Prerequisites & GCP API Setup

### 1. Enable Required Google Cloud APIs
Ensure the following Google Cloud APIs are enabled in your GCP project:
```bash
gcloud services enable \
  discoveryengine.googleapis.com \
  storage.googleapis.com \
  chronicle.googleapis.com \
  mcp.googleapis.com
```

### 2. Required IAM Roles & Permissions
Ensure your user principal or Service Account has the following IAM roles assigned:

| Resource / Product | Required IAM Role | Role ID |
| :--- | :--- | :--- |
| **Discovery Engine** | Discovery Engine Admin | `roles/discoveryengine.admin` |
| **Cloud Storage** | Storage Object Admin (or Viewer for GCS import) | `roles/storage.objectAdmin` |
| **Google SecOps** | Chronicle Viewer / Editor & MCP Tool User | `roles/chronicle.viewer`, `roles/mcp.toolUser` |

---

## ⚙️ Local Environment Setup

### 1. Clone & Set Up Virtual Environment
```bash
# Using 'just' (Recommended):
just setup

# Or manually via bash:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Authenticate Google Cloud Application Default Credentials (ADC)
```bash
gcloud auth login
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform","https://www.googleapis.com/auth/chronicle"
gcloud config set project YOUR_GCP_PROJECT_ID
```

---

## 🚀 1. Deploying the Ingestion Connector

The **Ingestion Connector** harvests SecOps Investigations via OneMCP, binds an **Identity Mapping Store (IMS)** for access control (ACLs), and indexes data into Discovery Engine.

### Step 1: Verify Ingestion via Dry-Run (Offline Test)
Test data harvesting and document transformation without connecting to live GCP resources:
```bash
just dry-run-ingestion
# Or: PYTHONPATH=. .venv/bin/python ingestion_connector/main.py --dry-run
```

### Step 2: Deploy Live Inline Ingestion (Incremental Reconciliation)
Ideal for continuous or frequent syncs (e.g., cron jobs or sidecars):
```bash
just run-ingestion-inline project_id="YOUR_PROJECT_ID" data_store_id="secops-inv-ds1"
# Or:
PYTHONPATH=. .venv/bin/python ingestion_connector/main.py \
  --project-id YOUR_PROJECT_ID \
  --location global \
  --data-store-id secops-inv-ds1 \
  --ims-id secops-inv-ims1 \
  --mode inline
```

### Step 3: Deploy Live Bulk Ingestion via Cloud Storage (Full Reconciliation)
Ideal for large-scale periodic synchronization with automated deletion of stale records:
```bash
just run-ingestion-gcs bucket="YOUR_GCS_BUCKET_NAME" project_id="YOUR_PROJECT_ID"
# Or:
PYTHONPATH=. .venv/bin/python ingestion_connector/main.py \
  --project-id YOUR_PROJECT_ID \
  --location global \
  --data-store-id secops-inv-ds1 \
  --mode gcs \
  --gcs-bucket YOUR_GCS_BUCKET_NAME \
  --gcs-blob-path secops/investigations.jsonl
```

---

## ⚡ 2. Deploying the Native Action Connector

The **Native Action Connector** registers SecOps OneMCP as a query-time tool endpoint, allowing Gemini Enterprise agents to query SecOps tools on demand.

### Step 1: Discover Available Native Actions
List available SecOps OneMCP action tools (`list_investigations`, `get_investigation`, `list_rules`, `get_ioc_match`):
```bash
just test-action-list
# Or: PYTHONPATH=. .venv/bin/python native_action_connector/main.py --list-tools
```

### Step 2: Test Action Tool Execution
Test executing a specific SecOps action tool:
```bash
just test-action-exec tool="list_investigations"
# Or: PYTHONPATH=. .venv/bin/python native_action_connector/main.py --call-tool list_investigations
```

### Step 3: Generate & Deploy Gemini Enterprise `mcpServers` Configuration
Generate the JSON configuration to register SecOps OneMCP with Gemini Enterprise or Gemini CLI:
```bash
just generate-mcp-config project_id="YOUR_SECOPS_PROJECT_ID"
# Or: PYTHONPATH=. .venv/bin/python native_action_connector/config_generator.py --project-id YOUR_PROJECT_ID --output-file secops_mcp_config.json
```

**Deploying to Gemini CLI / Extension Directory**:
Copy the generated config to your extension folder (e.g. `~/.gemini/extensions/secopsmcp/gemini-extension.json`):
```json
{
  "name": "secops",
  "version": "1.0.0",
  "mcpServers": {
    "GoogleSecOps": {
      "httpUrl": "https://us-chronicle.googleapis.com/mcp",
      "authProviderType": "google_credentials",
      "oauth": {
        "scopes": [
          "https://www.googleapis.com/auth/chronicle",
          "https://www.googleapis.com/auth/cloud-platform"
        ]
      },
      "timeout": 30000,
      "headers": {
        "X-Goog-User-Project": "YOUR_SECOPS_PROJECT_ID"
      }
    }
  }
}
```

---

## 🛠️ Complete `just` Command Reference

| `just` Command | Parameters | Description |
| :--- | :--- | :--- |
| `just setup` | None | Creates `.venv` and installs dependencies. |
| `just test` | None | Runs the full automated test suite (unit and e2e CLI tests). |
| `just dry-run-ingestion` | None | Runs offline test for SecOps Investigations conversion. |
| `just run-ingestion-inline` | `project_id`, `data_store_id` | Deploys inline incremental ingestion. |
| `just run-ingestion-gcs` | `bucket`, `project_id`, `data_store_id` | Deploys GCS bulk full reconciliation ingestion. |
| `just test-action-list` | None | Lists available native SecOps OneMCP action tools. |
| `just test-action-exec` | `tool` | Executes a specific native SecOps OneMCP tool action. |
| `just generate-mcp-config` | `project_id` | Outputs `mcpServers` configuration JSON. |

---

## 🔒 Security & Best Practices

1. **OAuth Scopes**: Ensure requests include `https://www.googleapis.com/auth/chronicle` and `https://www.googleapis.com/auth/cloud-platform`.
2. **Access Control (ACLs)**: The Ingestion Connector creates and binds an **Identity Mapping Store (IMS)** (`acl_enabled=True`) to ensure user and group permissions are respected in Gemini Enterprise search results.
3. **Automated Scheduling**: For production deployments, run `run-ingestion-inline` or `run-ingestion-gcs` on a recurring schedule using **Cloud Scheduler**, **Kubernetes CronJob**, or a background sidecar service.
