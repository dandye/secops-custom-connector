# SecOps Custom Connectors Usage Guide

This guide describes how security operations teams, SOC analysts, and AI agents utilize the **SecOps Custom Connectors** for semantic search, historical investigation retrieval, and real-time interactive threat hunting.

---

## 👥 Personas & Key Use Cases

| Persona | Primary Goal | Connector Utilized | How It Is Used |
| :--- | :--- | :--- | :--- |
| **SOC Analyst / Triage Engineer** | Rapidly investigate incoming alerts by finding similar past investigations and false-positive precedents. | **Ingestion Connector** (via Discovery Engine RAG) | Natural language queries in Gemini Enterprise search ("Have we seen `mimikatz.exe` on domain controllers before?"). |
| **Autonomous / Semi-Autonomous Agent** | Execute live telemetry searches, IoC lookups, and case modifications during a triage conversation. | **Native Action Connector** (OneMCP) | Gemini agent automatically calls `udm_search`, `get_ioc_match`, or `update_case` via JSON-RPC. |
| **Detection Engineer** | Analyze past false positive rationales to tune YARA-L rules and reduce alert fatigue. | **Ingestion Connector** | Searches for rule names and filters by `verdict: "FALSE_POSITIVE"` to inspect model rationale. |
| **SOC Lead / Security Admin** | Automate continuous knowledge synchronization between Google SecOps and Discovery Engine. | **Ingestion Connector** (CLI / Scheduler) | Schedules recurring incremental inline syncs or nightly GCS full reconciliations. |

---

## 🔍 Use Case 1: SOC Analyst Investigation Retrieval (RAG via Gemini Enterprise)

When an analyst encounters a suspicious alert or indicator in the SOC, they query Gemini Enterprise. Discovery Engine searches the ingested TINA investigations and returns synthesized findings with citations.

### Example User Prompts

#### Prompt 1: Investigating a Suspicious Binary
> **Analyst**: *"Has TINA investigated any alerts involving `Avl.exe` or file hash `14f9fbbf7e82888bdc9c314872bf0509835a464d1f03cd8e1a629d0c4d268b0c`? What was the verdict and why?"*

**Gemini Enterprise Answer** *(grounded on ingested DataStore)*:
> Yes. On **August 31, 2026**, the Autonomous Investigation Agent (TINA) completed an investigation for alert `de_d0ebb131-...` involving `Avl.exe` on host `wrk-pacman.lunarstiiiness.com` (*Investigation ID: `405668c3-d466-4662-b603-e9344d424e5d`*).
> 
> **Autonomous Verdict**: `FALSE_POSITIVE`
> 
> **Key Findings & Evidence**:
> 1. **Initial Trigger**: Google Applied Threat Intelligence (ATI) flagged the file `Avl.exe` executed from `AppData\Local\Temp` by user `michelle.wright`.
> 2. **Telemetry Sub-Queries**: TINA executed multiple secondary searches across Sysmon, Network, and Authentication logs.
> 3. **Reasoning**: No outbound network connections, persistence mechanisms, or unauthorized privilege escalations were detected following execution.
> 4. **Recommendation**: No remediation action required.
> 
> *Sources: [Investigation 405668c3-d466...](https://chronicle.security/investigations/405668c3-d466-4662-b603-e9344d424e5d)*

---

#### Prompt 2: Lateral Movement & Credential Dumping Precedents
> **Analyst**: *"Summarize all recent true positive credential dumping investigations on our production workstations."*

**Gemini Enterprise Answer**:
> In the last 30 days, **2 investigations** were determined to be `TRUE_POSITIVE` for credential dumping:
> 
> 1. **Host `WKS-PROD-88` (Investigation `8a1290bb-...`)**:
>    * **Technique**: LSASS process memory handle access via `mimikatz.exe`.
>    * **Activity**: 14 subsequent NTLM authentication attempts against Domain Controller `DC-01` using compromised account `svc_backup`.
>    * **Action Taken**: Host isolated, credentials revoked.
> 2. **Host `SRV-DB-02` (Investigation `inv_987652`)**:
>    * **Technique**: High volume encrypted DNS exfiltration to `exfil-tunnel.badtld`.

---

## ⚡ Use Case 2: Query-Time Agent Tool Calling (Native Action Connector)

When Gemini Enterprise is configured with the SecOps OneMCP server, the model can execute real-time actions on Google SecOps during a conversation.

### Interaction Flow

```
[User] "Show me the top 3 open cases in triage right now, and check if any involved hostnames match 'WKS-PROD-88'."
   │
   ▼
[Gemini Enterprise]
   ├── Executes OneMCP Tool: `list_cases` (filter: "Status='OPENED' AND Stage='Triage'", pageSize: 3)
   ├── Inspects returned cases:
   │     1. Case 17343: suspicious_dns_query_threat_intel (Priority: MEDIUM)
   │     2. Case 17342: SCC BigQuery Exfiltration to Google Drive (Priority: HIGH)
   │     3. Case 17341: win_repeatedAuthFailure_thenSuccess (Priority: MEDIUM)
   └── Executes OneMCP Tool: `udm_search` (query: 'principal.hostname = "WKS-PROD-88"', maxEvents: 10)
   │
   ▼
[Gemini Enterprise Output]
"Here are the top 3 open triage cases:
 1. **Case 17342** (High) - SCC BigQuery Exfiltration to Google Drive
 2. **Case 17343** (Medium) - Suspicious DNS Threat Intel Match
 3. **Case 17341** (Medium) - Repeated Auth Failure followed by Success

I ran a UDM telemetry search for `WKS-PROD-88` across these cases. Host `WKS-PROD-88` was active in Case 17341 during the authentication burst at 14:15 UTC. Would you like me to assign Case 17341 to you or trigger a deep TINA investigation?"
```

---

## 🛠️ Use Case 3: Automated Ingestion Scheduling (Operations)

For production environments, the Ingestion Connector is run on a scheduled interval to keep the Discovery Engine DataStore synchronized with live Chronicle investigations.

### Deployment Patterns

#### Pattern A: Scheduled Cloud Run Job (Recommended)
Deploy the connector as a containerized Cloud Run Job triggered by Cloud Scheduler:

```bash
# 1. Build and push container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/secops-ingestion-connector:latest .

# 2. Create Cloud Run Job
gcloud run jobs create secops-investigations-sync \
  --image gcr.io/YOUR_PROJECT_ID/secops-ingestion-connector:latest \
  --command "python" \
  --args "ingestion_connector/main.py,--project-id,YOUR_PROJECT_ID,--secops-project-id,YOUR_PROJECT_ID,--secops-customer-id,YOUR_CUSTOMER_ID,--data-store-id,secops-inv-ds1,--ims-id,secops-inv-ims1,--mode,inline" \
  --service-account "secops-connector-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --region "us-central1"

# 3. Schedule execution every hour
gcloud scheduler jobs create http secops-sync-hourly \
  --schedule "0 * * * *" \
  --uri "https://us-central1-run.googleapis.com/v2/projects/YOUR_PROJECT_ID/locations/us-central1/jobs/secops-investigations-sync:run" \
  --http-method POST \
  --oauth-service-account-email "secops-connector-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com"
```

#### Pattern B: Nightly Full Reconciliation via Cloud Storage
For large SOC environments with thousands of historical investigations, use the GCS bulk mode with `FULL` reconciliation:

```bash
# Ingest full history with stale record pruning
just run-ingestion-gcs \
  bucket="YOUR_GCS_BUCKET" \
  project_id="YOUR_PROJECT_ID" \
  data_store_id="secops-inv-ds1"
```
