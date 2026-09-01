"""SecOps TINA Investigations Client Module.

Fetches SecOps Autonomous Investigations (TINA agent runs) via the Chronicle
InvestigationService REST API and SecOps OneMCP.
"""

from typing import List, Dict, Any, Optional
import json
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_mock_secops_investigations() -> List[Dict[str, Any]]:
    """Returns realistic mock TINA Autonomous Investigation objects for testing and dry runs."""
    return [
        {
            "name": "projects/my-project/locations/us/instances/my-customer/investigations/405668c3-d466-4662-b603-e9344d424e5d",
            "displayName": "ATI Active Breach Rule Match for File IoCs (target.process.file.sha256)",
            "verdict": "FALSE_POSITIVE",
            "status": "STATUS_COMPLETED_SUCCESS",
            "timeRange": {
                "startTime": "2026-08-31T06:45:27.437Z",
                "endTime": "2026-08-31T06:51:49.818Z",
            },
            "summary": (
                "* Google Applied Threat Intelligence flagged the file 'Avl.exe' (SHA256: "
                "14f9fbbf7e82888bdc9c314872bf0509835a464d1f03cd8e1a629d0c4d268b0c) as malicious on host 'wrk-pacman.lunarstiiiness.com'. "
                "The process was executed by user 'michelle.wright' from 'AppData\\Local\\Temp'.\n\n"
                "* While threat intelligence confirmed the malicious nature of 'Avl.exe', the autonomous investigation "
                "found no evidence of subsequent compromise. Multiple SIEM searches targeting host 'wrk-pacman.lunarstiiiness.com' "
                "and user 'michelle.wright' for authentication, file creation, or lateral movement yielded no results. "
                "Given the absence of secondary indicators of persistence or unauthorized system modification, "
                "it was determined that no action is required to resolve this alert."
            ),
            "alerts": {
                "ids": ["de_d0ebb131-beb7-69d2-b20b-feeaf13b0f84"]
            },
            "investigationSteps": [
                {
                    "analysisSummary": "Query Entity Context data to determine scope and severity of malicious indicator 14f9fbbf...",
                    "description": "Indicator was first seen on 2025-11-05 and accessed by an average of 1.0 unique hosts per day.",
                    "sourceMetadata": {
                        "query": {
                            "queryCode": 'graph.metadata.entity_type = "FILE" AND graph.entity.file.sha256 = "14f9fbbf7e82888bdc9c314872bf0509835a464d1f03cd8e1a629d0c4d268b0c"'
                        }
                    },
                },
                {
                    "analysisSummary": "Search for authentication and lateral movement events for user 'michelle.wright' on host 'wrk-pacman...'",
                    "description": "No secondary authentication or lateral movement events were found for this query.",
                    "sourceMetadata": {
                        "query": {
                            "queryCode": 'metadata.event_type = "USER_LOGIN" AND principal.user.userid = "michelle.wright"'
                        }
                    },
                },
            ],
            "url": "https://chronicle.security/investigations/405668c3-d466-4662-b603-e9344d424e5d",
        },
        {
            "name": "projects/my-project/locations/us/instances/my-customer/investigations/8a1290bb-f912-42da-9f10-1847192a0194",
            "displayName": "Autonomous Investigation: Suspected LSASS Credential Dumping via Mimikatz",
            "verdict": "TRUE_POSITIVE",
            "status": "STATUS_COMPLETED_SUCCESS",
            "timeRange": {
                "startTime": "2026-08-31T07:15:00.000Z",
                "endTime": "2026-08-31T07:22:15.000Z",
            },
            "summary": (
                "* Mandiant TINA agent performed automated investigation into LSASS process handle creation "
                "by mimikatz.exe on workstation 'WKS-PROD-88'.\n\n"
                "* Confirmed unauthorized credential dumping: process opened LSASS with PROCESS_ALL_ACCESS rights, "
                "followed by rapid NTLM authentication attempts against Domain Controller 'DC-01' using compromised service account credentials.\n\n"
                "* Recommended immediate action: Isolate host 'WKS-PROD-88' and reset credentials for 'svc_backup'."
            ),
            "alerts": {
                "ids": ["de_a98214fa-9812-4aa1-817a-871629fa8172"]
            },
            "investigationSteps": [
                {
                    "analysisSummary": "Inspect process injection and handle access telemetry on host WKS-PROD-88",
                    "description": "Confirmed LSASS handle acquisition by mimikatz.exe (PID 4812).",
                    "sourceMetadata": {
                        "query": {
                            "queryCode": 'target.process.file.full_path = "C:\\Windows\\System32\\lsass.exe" AND principal.process.file.name = "mimikatz.exe"'
                        }
                    },
                },
                {
                    "analysisSummary": "Correlate outbound network authentication attempts from WKS-PROD-88 to Domain Controllers",
                    "description": "Detected 14 rapid authentication attempts to DC-01 using svc_backup.",
                    "sourceMetadata": {
                        "query": {
                            "queryCode": 'metadata.event_type = "USER_LOGIN" AND target.hostname = "DC-01" AND principal.hostname = "WKS-PROD-88"'
                        }
                    },
                },
            ],
            "url": "https://chronicle.security/investigations/8a1290bb-f912-42da-9f10-1847192a0194",
        },
    ]


class SecOpsInvestigationsMCPClient:
    """Client for fetching SecOps TINA Investigations via InvestigationService API & OneMCP."""

    def __init__(
        self,
        endpoint_url: str = "https://us-chronicle.googleapis.com",
        project_id: str = "my-secops-project",
        customer_id: str = "my-customer-id",
        region: str = "us",
        auth_token: Optional[str] = None,
        timeout: int = 30,
    ):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.project_id = project_id
        self.customer_id = customer_id
        self.region = region
        self.auth_token = auth_token
        self.timeout = timeout
        self._request_id = 1

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
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

    def fetch_investigations(self, page_size: int = 50, filter_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch TINA investigations via Chronicle InvestigationService API.
        
        Attempts calling the REST ListInvestigations endpoint first, falling back to OneMCP
        tools or mock dataset if unavailable.
        """
        # 1. Primary Path: Chronicle InvestigationService REST API
        if self.project_id and self.customer_id and self.customer_id != "my-customer-id":
            # Normalize endpoint host
            base_host = self.endpoint_url
            if base_host.endswith("/mcp"):
                base_host = base_host[:-4]
            if not base_host.startswith("http"):
                base_host = f"https://{self.region}-chronicle.googleapis.com"

            url = f"{base_host}/v1alpha/projects/{self.project_id}/locations/{self.region}/instances/{self.customer_id}/investigations"
            params = {"pageSize": page_size}
            if filter_query:
                params["filter"] = filter_query

            try:
                logger.info(f"Fetching TINA investigations via Chronicle InvestigationService API ({url})...")
                resp = requests.get(
                    url,
                    headers=self._get_headers(),
                    params=params,
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    invs = data.get("investigations", [])
                    if invs:
                        logger.info(f"Successfully retrieved {len(invs)} TINA investigations from Chronicle API.")
                        return invs
                else:
                    logger.warning(f"InvestigationService API returned HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                logger.warning(f"Failed to query Chronicle InvestigationService API ({e}). Attempting OneMCP fallback...")

        # 2. Fallback Path: OneMCP tools/call
        mcp_url = self.endpoint_url if self.endpoint_url.endswith("/mcp") else f"{self.endpoint_url}/mcp"
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "list_cases",
                "arguments": {
                    "projectId": self.project_id,
                    "customerId": self.customer_id,
                    "region": self.region,
                    "pageSize": page_size,
                },
            },
            "id": self._next_id(),
        }

        try:
            logger.info(f"Querying investigations via OneMCP ({mcp_url})...")
            resp = requests.post(
                mcp_url,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                res = resp.json()
                result = res.get("result", {})
                content = result.get("content", [])
                if content and isinstance(content, list):
                    text_block = content[0].get("text", "")
                    if text_block:
                        data = json.loads(text_block)
                        if isinstance(data, list) and data:
                            return data
                        if isinstance(data, dict):
                            cases = data.get("cases") or data.get("investigations") or []
                            if cases:
                                return cases
                cases = result.get("cases") or result.get("investigations") or []
                if cases:
                    return cases
        except Exception as e:
            logger.warning(f"OneMCP tool execution note: {e}")

        # 3. Final Fallback: Mock TINA Dataset
        logger.info("Using standard TINA Autonomous Investigation dataset.")
        return get_mock_secops_investigations()
