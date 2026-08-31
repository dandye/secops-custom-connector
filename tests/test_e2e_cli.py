"""End-to-end CLI tests for Ingestion and Native Action Connectors."""

import unittest
import subprocess
import os
import json


class TestE2ECLI(unittest.TestCase):
    """End-to-end CLI verification suite."""

    def setUp(self):
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = "."
        self.python_bin = ".venv/bin/python" if os.path.exists(".venv/bin/python") else "python3"

    def test_ingestion_cli_dry_run(self):
        """Test 'ingestion_connector/main.py --dry-run' command."""
        cmd = [self.python_bin, "ingestion_connector/main.py", "--dry-run"]
        res = subprocess.run(cmd, env=self.env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertIn("Harvested and converted", res.stdout)
        self.assertIn("Ingestion Connector dry-run completed successfully!", res.stdout)

    def test_native_action_cli_list_tools(self):
        """Test 'native_action_connector/main.py --list-tools' command."""
        cmd = [self.python_bin, "native_action_connector/main.py", "--list-tools"]
        res = subprocess.run(cmd, env=self.env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertIn("Discovered", res.stdout)
        self.assertIn("Native SecOps Actions", res.stdout)

    def test_native_action_cli_call_tool(self):
        """Test 'native_action_connector/main.py --call-tool list_cases' command."""
        cmd = [self.python_bin, "native_action_connector/main.py", "--call-tool", "list_cases"]
        res = subprocess.run(cmd, env=self.env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertIn("Native Action Execution Result", res.stdout)

    def test_native_action_cli_generate_config(self):
        """Test 'native_action_connector/main.py --generate-config' command."""
        cmd = [self.python_bin, "native_action_connector/main.py", "--generate-config"]
        res = subprocess.run(cmd, env=self.env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        self.assertIn("mcpServers", res.stdout)
        self.assertIn("GoogleSecOps", res.stdout)


if __name__ == "__main__":
    unittest.main()
