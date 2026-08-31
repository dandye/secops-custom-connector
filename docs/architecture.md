# SecOps Custom Connectors Architecture

This document provides a technical deep-dive into the architecture, component interaction, and security model of the **SecOps Custom Connectors** for **Google Cloud Discovery Engine** and **Gemini Enterprise**.

---

## 🏗️ System Overview

The solution consists of two complementary connectors:

1. **Ingestion Connector (`ingestion_connector/`)**: An asynchronous ETL pipeline that harvests rich investigation outcomes, narratives, verdicts, and telemetry steps from the **Google SecOps (Chronicle) InvestigationService** and indexes them as `discoveryengine.Document` Protobuf messages in an ACL-enabled Discovery Engine DataStore.
2. **Native Action Connector (`native_action_connector/`)**: A query-time Model Context Protocol (MCP) integration that connects Gemini Enterprise conversational agents directly to **SecOps OneMCP** (`https://us-chronicle.googleapis.com/mcp`) for live interactive tool execution (e.g. `list_cases`, `udm_search`, `get_ioc_match`, `fetch_enrichment_actions`).

```mermaid
flowchart TB
    subgraph GoogleSecOps["Google SecOps (Chronicle SIEM & SOAR)"]
        TINA["TINA Autonomous Investigation Agent"]
        InvAPI["InvestigationService API\n(/v1alpha/.../investigations)"]
        OneMCP["SecOps OneMCP Server\n(https://us-chronicle.googleapis.com/mcp)"]
        SIEM_SOAR["SIEM Rules, Cases & UDM Data Lake"]
        
        TINA --> InvAPI
        SIEM_SOAR --> OneMCP
        TINA --> OneMCP
    end

    subgraph Connectors["SecOps Custom Connectors"]
        direction TB
        subgraph Ingestion["1. Ingestion Connector (ETL Pipeline)"]
            Harvester["TINA Investigation Harvester"]
            ProtoConverter["Protobuf Mapper\n(discoveryengine.Document)"]
            IMSSync["Identity Mapping Store (IMS) Manager"]
            
            Harvester --> ProtoConverter
            ProtoConverter --> IMSSync
        end

        subgraph NativeAction["2. Native Action Connector (MCP Client)"]
            MCPClient["OneMCP Protocol Client\n(JSON-RPC 2.0)"]
            ConfigGen["mcpServers Config Generator"]
        end
    end

    subgraph GeminiPlatform["Gemini Enterprise & Discovery Engine"]
        DataStore["Discovery Engine DataStore\n(acl_enabled = true)"]
        IMS["Identity Mapping Store (IMS)"]
        SearchApp["Gemini Enterprise / Search App"]
        GeminiAgent["Gemini Enterprise Agent Platform"]
        
        IMSSync -.-> IMS
        ProtoConverter --> DataStore
        DataStore --> SearchApp
        SearchApp --> GeminiAgent
        MCPClient <--> GeminiAgent
    end

    InvAPI --> Harvester
    OneMCP <--> MCPClient
```

---

## 📥 1. Ingestion Connector Architecture

The Ingestion Connector runs as a scheduled or on-demand background worker that synchronizes investigation knowledge into Discovery Engine.

### Data Flow & Transformation

```mermaid
sequenceDiagram
    autonumber
    participant Harvester as Ingestion Harvester
    participant Chronicle as Chronicle InvestigationService
    participant Mapper as Protobuf Mapper
    participant GCS as Cloud Storage (Optional)
    participant IMS as Discovery Engine IMS
    participant DiscEng as Discovery Engine DataStore

    Harvester->>Chronicle: GET /v1alpha/projects/{project}/locations/{region}/instances/{instance}/investigations
    Chronicle-->>Harvester: ListInvestigationsResponse (TINA Agent Narratives, Verdicts, Steps)
    
    Harvester->>Mapper: Convert to discoveryengine.Document Protobufs
    Mapper->>Mapper: Generate RFC-1034 Clean ID & Rich Markdown Body
    
    alt Mode: Inline Sync
        Mapper->>DiscEng: DocumentServiceClient.import_documents(InlineSource)
    else Mode: GCS Bulk Sync (Full Reconciliation)
        Mapper->>GCS: Upload investigations.jsonl
        Harvester->>DiscEng: DocumentServiceClient.import_documents(GcsSource, FULL Reconciliation)
    end
    
    Harvester->>IMS: ImportIdentityMappings (User & Group ACLs)
    DiscEng-->>DiscEng: Build Search Index & Bind IMS ACLs
```

### Document Schema & Protobuf Representation

Each investigation is mapped to `google.cloud.discoveryengine.v1.Document`:

```protobuf
message Document {
  string id = 2;               // Normalized Investigation UUID (e.g., 405668c3-d466-4662-b603-e9344d424e5d)
  string json_data = 5;        // Serialized JSON payload containing structured metadata
}
```

The `jsonData` payload contains:
* `title`: Investigation display name / triggered detection rule.
* `verdict`: Final agent determination (`TRUE_POSITIVE`, `FALSE_POSITIVE`, `BENIGN`, `UNCERTAIN`).
* `status`: Lifecycle state (`STATUS_COMPLETED_SUCCESS`, `STATUS_IN_PROGRESS`).
* `summary`: Full multi-paragraph AI synthesis and reasoning narrative from TINA.
* `alert_ids`: List of associated Chronicle SIEM alert ticket IDs.
* `investigation_steps`: Array of sub-actions, telemetry queries, and entity lookup results.
* `start_time` / `end_time`: Investigation execution window.
* `body`: Formatted GitHub Flavored Markdown document optimized for semantic embedding, keyword ranking, and RAG snippet extraction.

---

## ⚡ 2. Native Action Connector Architecture

The Native Action Connector bridges Gemini Enterprise agents with the SecOps OneMCP server over JSON-RPC 2.0.

```mermaid
sequenceDiagram
    autonumber
    participant User as SOC Analyst
    participant Gemini as Gemini Enterprise Agent
    participant OneMCP as SecOps OneMCP Endpoint
    participant Chronicle as Chronicle SIEM / SOAR

    User->>Gemini: "What active cases are currently assigned to Tier 1 triage?"
    Gemini->>Gemini: Inspect mcpServers tool definitions
    Gemini->>OneMCP: tools/call ("list_cases", {"stage": "Triage", "pageSize": 5})
    OneMCP->>Chronicle: Query CaseService REST API
    Chronicle-->>OneMCP: Case records (name, displayName, priority, stage, alerts)
    OneMCP-->>Gemini: JSON-RPC 2.0 Response Result
    Gemini->>User: Synthesized interactive case overview with follow-up action buttons
```

### Supported Native Tool Categories

| Tool Category | Example Tools | Description |
| :--- | :--- | :--- |
| **Investigation & Triage** | `get_alert_latest_investigation`, `get_investigation_by_id`, `trigger_investigation` | Inspect autonomous agent verdicts, reasoning steps, or trigger new runs. |
| **Case & Alert Management** | `list_cases`, `get_case`, `update_case`, `list_case_alerts`, `list_case_comments` | Retrieve and modify SOC cases, assignees, priorities, and stages. |
| **Telemetry & Threat Hunting** | `udm_search`, `get_ioc_match`, `summarize_entity`, `search_entity` | Run real-time UDM queries and match indicators against threat intelligence. |
| **Detection Engineering** | `list_rules`, `get_rule`, `create_rule`, `validate_rule`, `list_rule_detections` | Inspect and validate YARA-L detection rules. |
| **Automated Response** | `fetch_enrichment_actions`, `execute_actions`, `execute_manual_action` | Run SOAR playbooks and entity enrichment actions. |

---

## 🔒 3. Security & Access Control Model

### Identity Mapping Store (IMS) and ACL Enforcement
Enterprise search requires granular access control so analysts only see investigations and telemetry permitted by their organizational role:

1. **Identity Mapping**: Third-party or SecOps identities (e.g. `secops_investigator_1`, `tier1_analyst`) are mapped to Google Workspace / Cloud Identity emails (`analyst@company.com`) or groups (`incident-response@company.com`) via `discoveryengine.IdentityMappingStoreServiceClient`.
2. **DataStore ACL Enforcement**: The Discovery Engine DataStore is created with `acl_enabled=True` and linked to the Identity Mapping Store.
3. **Query-Time Filtering**: Search requests provide `user_info=discoveryengine.UserInfo(user_id=...)` ensuring that search results and generated RAG answers respect document-level ACLs.

### Authentication & Authorization
* **OAuth 2.0 Scopes**:
  * `https://www.googleapis.com/auth/chronicle` (Access to Chronicle SIEM, SOAR, and Investigation APIs)
  * `https://www.googleapis.com/auth/cloud-platform` (Discovery Engine and Cloud Storage API calls)
* **Application Default Credentials (ADC)**: Automatically resolves credentials and attaches `X-Goog-User-Project` quota headers for enterprise GCP projects.
