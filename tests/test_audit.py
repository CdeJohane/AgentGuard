"""Audit exercise tests: python -m unittest tests.test_audit -v"""

import unittest
from unittest.mock import patch

from agent_guard.audit import audit_log, record_decision
from agent_guard.executor import execute_request


class AuditTests(unittest.TestCase):
    def setUp(self):
        audit_log.clear()

    def tearDown(self):
        audit_log.clear()

    def test_appends_one_record_with_only_the_agreed_fields(self):
        request = {"action": "read", "path": "notes.txt", "contents": "Private data"}
        record_decision(request, True, "Reading notes.txt is permitted.")
        self.assertEqual(audit_log, [{
            "action": "read",
            "path": "notes.txt",
            "allowed": True,
            "reason": "Reading notes.txt is permitted.",
        }])

    def test_handles_malformed_requests_without_losing_valid_fields(self):
        cases = [
            (None, None, None),
            ([], None, None),
            ({}, None, None),
            ({"action": "read"}, "read", None),
            ({"path": "notes.txt"}, None, "notes.txt"),
            ({"action": 123, "path": "notes.txt"}, None, "notes.txt"),
            ({"action": "read", "path": []}, "read", None),
        ]
        for request, action, path in cases:
            audit_log.clear()
            record_decision(request, False, "Malformed request.")
            self.assertEqual(audit_log, [{
                "action": action,
                "path": path,
                "allowed": False,
                "reason": "Malformed request.",
            }], msg=f"Request: {request!r}")

    def test_record_is_a_snapshot_of_the_request(self):
        request = {"action": "read", "path": "notes.txt"}
        record_decision(request, True, "Reading notes.txt is permitted.")
        request["action"] = "write"
        request["path"] = "changed.txt"
        self.assertEqual(audit_log, [{
            "action": "read",
            "path": "notes.txt",
            "allowed": True,
            "reason": "Reading notes.txt is permitted.",
        }])

    def test_allowed_request_is_logged_before_reader_runs(self):
        expected_record = {
            "action": "read",
            "path": "notes.txt",
            "allowed": True,
            "reason": "Reading notes.txt is permitted.",
        }

        def reader_after_logging(path):
            self.assertEqual(audit_log, [expected_record])
            return "Private file contents"

        with patch("agent_guard.executor.simulated_read", side_effect=reader_after_logging) as reader:
            result = execute_request({"action": "read", "path": "notes.txt"})
            reader.assert_called_once_with("notes.txt")
        self.assertEqual(result, (True, "Private file contents"))
        self.assertEqual(audit_log, [expected_record])

    def test_denied_requests_are_logged_without_calling_reader(self):
        cases = [
            ({"action": "write", "path": "notes.txt"}, "Action is not permitted.", "write", "notes.txt"),
            ({"action": "read", "path": "secrets.txt"}, "File is not permitted.", "read", "secrets.txt"),
            (None, "Malformed request.", None, None),
        ]
        for request, reason, action, path in cases:
            audit_log.clear()
            with patch("agent_guard.executor.simulated_read") as reader:
                result = execute_request(request)
                reader.assert_not_called()
            self.assertEqual(result, (False, reason))
            self.assertEqual(audit_log, [{
                "action": action,
                "path": path,
                "allowed": False,
                "reason": reason,
            }], msg=f"Request: {request!r}")

    def test_multiple_attempts_append_once_each_in_order(self):
        execute_request({"action": "read", "path": "notes.txt"})
        execute_request({"action": "write", "path": "notes.txt"})
        execute_request(None)
        self.assertEqual(audit_log, [
            {
                "action": "read", "path": "notes.txt", "allowed": True,
                "reason": "Reading notes.txt is permitted.",
            },
            {
                "action": "write", "path": "notes.txt", "allowed": False,
                "reason": "Action is not permitted.",
            },
            {
                "action": None, "path": None, "allowed": False,
                "reason": "Malformed request.",
            },
        ])


if __name__ == "__main__":
    unittest.main()
