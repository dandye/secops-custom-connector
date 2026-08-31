"""Unit and integration tests for Ingestion Connector."""

import unittest
import json
from google.cloud import discoveryengine_v1 as discoveryengine
from ingestion_connector.secops_investigations_mcp import (
    SecOpsInvestigationsMCPClient,
    get_mock_secops_investigations,
)
from ingestion_connector.connector import (
    convert_investigations_to_documents,
    convert_documents_to_jsonl,
    harvest_and_convert_investigations,
)


class TestIngestionConnector(unittest.TestCase):
    """Test suite for SecOps Investigations Ingestion Connector."""

    def setUp(self):
        self.sample_investigations = get_mock_secops_investigations()
        self.client = SecOpsInvestigationsMCPClient(
            endpoint_url="https://us-chronicle.googleapis.com/mcp",
            project_id="test-project",
            customer_id="test-customer-id",
            region="us",
        )

    def test_mock_investigations_structure(self):
        """Verify sample mock investigations contain required fields."""
        self.assertTrue(len(self.sample_investigations) >= 2)
        for inv in self.sample_investigations:
            self.assertIn("id", inv)
            self.assertIn("displayName", inv)
            self.assertIn("description", inv)
            self.assertIn("verdict", inv)
            self.assertIn("confidenceScore", inv)
            self.assertIn("entities", inv)

    def test_convert_investigations_to_documents(self):
        """Verify conversion from investigation dicts to discoveryengine.Document protobufs."""
        docs = convert_investigations_to_documents(self.sample_investigations)
        self.assertEqual(len(docs), len(self.sample_investigations))

        for idx, doc in enumerate(docs):
            self.assertIsInstance(doc, discoveryengine.Document)
            self.assertEqual(doc.id, self.sample_investigations[idx]["id"])
            self.assertTrue(doc.json_data)

            # Validate json_data content
            payload = json.loads(doc.json_data)
            self.assertEqual(payload["verdict"], self.sample_investigations[idx]["verdict"])
            self.assertEqual(payload["type"], "secops_investigation")
            self.assertIn("title", payload)
            self.assertIn("body", payload)
            self.assertIn("entities", payload)

    def test_convert_documents_to_jsonl(self):
        """Verify serialization of Document protobufs to JSONL format."""
        docs = convert_investigations_to_documents(self.sample_investigations)
        jsonl_str = convert_documents_to_jsonl(docs)

        self.assertTrue(jsonl_str.endswith("\n"))
        lines = [line for line in jsonl_str.strip().split("\n") if line]
        self.assertEqual(len(lines), len(docs))

        # Check each line can be deserialized
        for line in lines:
            record = json.loads(line)
            self.assertIn("id", record)
            self.assertIn("jsonData", record)
            inner_payload = json.loads(record["jsonData"])
            self.assertEqual(inner_payload["type"], "secops_investigation")

    def test_harvest_and_convert_investigations(self):
        """Test full harvesting and conversion flow."""
        docs = harvest_and_convert_investigations(self.client)
        self.assertGreaterEqual(len(docs), 1)
        self.assertIsInstance(docs[0], discoveryengine.Document)


if __name__ == "__main__":
    unittest.main()
