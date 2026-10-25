"""End-to-end demo tests: python -m unittest tests.test_simulate -v"""

from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import patch

from agent_guard.audit import audit_log
from agent_guard.simulate import main


class DemoTests(unittest.TestCase):
    def setUp(self):
        audit_log.clear()

    def tearDown(self):
        audit_log.clear()

    def test_demo_executes_only_the_allowed_read_and_displays_its_audit_trail(self):
        output = StringIO()
        with redirect_stdout(output):
            with patch("agent_guard.executor.simulated_read", return_value="Demo file contents") as reader:
                main()
                reader.assert_called_once_with("notes.txt")

        result_text, separator, audit_text = output.getvalue().partition("Audit trail:\n")
        self.assertTrue(separator, "The demo must display the audit trail after its results.")
        self.assertEqual(result_text.count("EXECUTED:"), 1)
        self.assertEqual(result_text.count("DENIED:"), 3)
        self.assertIn("Demo file contents", result_text)
        self.assertIn("Action is not permitted.", result_text)
        self.assertIn("File is not permitted.", result_text)
        self.assertIn("Malformed request.", result_text)
        expected_records = [
            {
                "action": "read", "path": "notes.txt", "allowed": True,
                "reason": "Reading notes.txt is permitted.",
            },
            {
                "action": "write", "path": "notes.txt", "allowed": False,
                "reason": "Action is not permitted.",
            },
            {
                "action": "read", "path": "secrets.txt", "allowed": False,
                "reason": "File is not permitted.",
            },
            {
                "action": None, "path": None, "allowed": False,
                "reason": "Malformed request.",
            },
        ]
        self.assertEqual(audit_log, expected_records)
        self.assertEqual(len(audit_text.strip().splitlines()), 4)
        for record in expected_records:
            self.assertIn(repr(record), audit_text)
        self.assertNotIn("Demo file contents", audit_text)

    def test_running_demo_twice_starts_with_a_fresh_audit_log(self):
        with redirect_stdout(StringIO()):
            main()
            first_run = audit_log.copy()
            main()
        self.assertEqual(len(audit_log), 4)
        self.assertEqual(audit_log, first_run)


if __name__ == "__main__":
    unittest.main()
