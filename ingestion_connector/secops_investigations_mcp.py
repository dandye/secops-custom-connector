"""SecOps Investigations OneMCP Client Module.

Fetches SecOps Security Investigations via SecOps OneMCP server endpoints.
Interacts with SecOps OneMCP tools (e.g., list_cases, get_alert_latest_investigation,
get_investigation_by_id, list_security_alerts).
"""

from typing import List, Dict, Any, Optional
import json
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_mock_secops_investigations() -> List[Dict[str, Any]]:
    """Returns sample SecOps Investigations for testing and dry-run mode."""
    return [
        {
            "id": "inv_987651",
            "displayName": "Autonomous Investigation: Suspected Credential Dumping via LSASS Access",
            "description": (
                "Mandiant TINA agent performed automated investigation into LSASS process handle creation "
                "by mimikatz.exe. Confirmed unauthorized credential dumping on Host WKS-PROD-88."
            ),
            "verdict": "TRUE_POSITIVE",
            "confidenceScore": 0.98,
            "status": "OPEN",
            "assignee": "tina_autonomous_agent@company.com",
            "entities": ["WKS-PROD-88", "10.0.4.15", "admin_user"],
            "createdTime": "2026-08-04T14:15:00Z",
            "updatedTime": "2026-08-04T14:16:30Z",
            "url": "https://chronicle.security/investigations/inv_987651",
        },
        {
            "id": "inv_987652",
            "displayName": "Autonomous Investigation: Potential Data Exfiltration over Encrypted DNS",
            "description": (
                "High volume DNS TXT query traffic to domain exfil-tunnel.badtld. Verdict: Suspected C2 data exfiltration. "
                "Recommended immediate host isolation for SRV-DB-02."
            ),
            "verdict": "TRUE_POSITIVE",
            "confidenceScore": 0.94,
            "status": "UNDER_REVIEW",
            "assignee": "soc_lead@company.com",
            "entities": ["SRV-DB-02", "192.168.10.20", "exfil-tunnel.badtld"],
            "createdTime": "2026-08-04T15:00:00Z",
            "updatedTime": "2026-08-04T15:10:00Z",
            "url": "https://chronicle.security/investigations/inv_987652",
        },
        {
            "id": "inv_987653",
            "displayName": "Autonomous Investigation: Legitimate IT Admin PowerShell Script Execution",
            "description": (
                "Automated investigation evaluated encoded PowerShell execution on Domain Controller DC-01. "
                "Activity matched scheduled maintenance playbook by IT Admin user."
            ),
            "verdict": "FALSE_POSITIVE",
            "confidenceScore": 0.99,
            "status": "CLOSED",
            "assignee": "auto_closed@company.com",
            "entities": ["DC-01", "10.0.1.5", "svc_maintenance"],
            "createdTime": "2026-08-04T16:00:00Z",
            "updatedTime": "2026-08-04T16:01:15Z",
            "url": "https://chronicle.security/investigations/inv_987653",
        },
    ]


class SecOpsInvestigationsMCPClient:
    """Client for fetching SecOps Investigations from SecOps OneMCP server."""

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

    def fetch_investigations(self, page_size: int = 50) -> List[Dict[str, Any]]:
        """Fetch SecOps Investigations via SecOps OneMCP tools.
        
        Attempts calling list_cases or get_alert_latest_investigation, falling back to mock dataset
        if offline or unauthenticated.
        """
        arguments = {"pageSize": page_size}
        if self.project_id:
            arguments["projectId"] = self.project_id
            arguments["project_id"] = self.project_id
        if self.customer_id:
            arguments["customerId"] = self.customer_id
            arguments["customer_id"] = self.customer_id
        if self.region:
            arguments["region"] = self.region

        # Try list_cases or list_security_alerts
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "list_cases",
                "arguments": arguments,
            },
            "id": self._next_id(),
        }

        try:
            logger.info(f"Fetching SecOps Investigations via OneMCP ({self.endpoint_url})...")
            resp = requests.post(
                self.endpoint_url,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            res = resp.json()
            result = res.get("result", {})
            content = result.get("content", [])
            if content and isinstance(content, list):
                text_block = content[0].get("text", "")
                if text_block:
                    cases = json.loads(text_block)
                    if isinstance(cases, list):
                        return cases
            cases = result.get("cases", [])
            if cases:
                return cases
            return get_mock_secops_investigations()
        except Exception as e:
            logger.warning(f"Could not fetch investigations via SecOps OneMCP ({e}). Falling back to mock dataset.")
            return get_mock_secops_investigations()
