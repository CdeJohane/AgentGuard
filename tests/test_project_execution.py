"""Verify explicit project-mode execution, blocked review, and safe failures.

Run with: python -m unittest tests.test_project_execution -v
No model calls or real file access take place.
"""

import traceback
import unittest
from unittest.mock import patch

from agent_guard.audit import audit_log
from agent_guard.executor import OperationError, _allows_execution, execute_request


class ExecutionGateTests(unittest.TestCase):
    def test_only_exact_allow_returns_boolean_true(self):
        self.assertIs(_allows_execution("allow"), True)
        for decision in ("deny", "review", "ALLOW", " allow ", "unknown", "", None, True, 1, [], {}):
            with self.subTest(decision=decision):
                self.assertIs(_allows_execution(decision), False)


class ProjectExecutionTests(unittest.TestCase):
    def setUp(self):
        audit_log.clear()

    def tearDown(self):
        audit_log.clear()

    def test_allow_reads_once_after_one_permission_record(self):
        expected_audit = {"action": "read", "path": "notes.txt", "allowed": True,
                          "reason": "project: Reading notes.txt is permitted."}

        def read_after_audit(path):
            self.assertEqual(audit_log, [expected_audit])
            return "Private simulated contents"

        with patch("agent_guard.executor.simulated_read", side_effect=read_after_audit) as reader:
            result = execute_request({"action": "read", "path": "notes.txt"}, use_project_policy=True)
        reader.assert_called_once_with("notes.txt")
        self.assertEqual(result, {"decision": "allow", "executed": True,
                                  "message": "Private simulated contents"})
        self.assertEqual(audit_log, [expected_audit])

    def test_review_is_distinct_from_denial_and_never_reads(self):
        with patch("agent_guard.executor.simulated_read") as reader:
            result = execute_request({"action": "read", "path": "draft.txt"}, use_project_policy=True)
        reader.assert_not_called()
        self.assertEqual(result, {"decision": "review", "executed": False,
                                  "message": "project: File requires review."})
        self.assertEqual(audit_log, [{"action": "read", "path": "draft.txt", "allowed": False,
                                     "reason": "project: File requires review."}])

    def test_denial_never_reads_and_is_audited_once(self):
        with patch("agent_guard.executor.simulated_read") as reader:
            result = execute_request({"action": "write", "path": "notes.txt"}, use_project_policy=True)
        reader.assert_not_called()
        self.assertEqual(result, {"decision": "deny", "executed": False,
                                  "message": "project: Action is not permitted."})
        self.assertEqual(audit_log, [{"action": "write", "path": "notes.txt", "allowed": False,
                                     "reason": "project: Action is not permitted."}])

    def test_malformed_requests_never_read_and_are_audited_once(self):
        for request in (None, {}, {"action": "read", "path": ""}):
            audit_log.clear()
            with patch("agent_guard.executor.simulated_read") as reader:
                result = execute_request(request, use_project_policy=True)
            reader.assert_not_called()
            self.assertEqual(result, {"decision": "deny", "executed": False,
                                      "message": "project: Malformed request."})
            self.assertEqual(len(audit_log), 1)
            self.assertIs(audit_log[0]["allowed"], False)
            self.assertEqual(audit_log[0]["reason"], "project: Malformed request.")

    def test_permitted_reader_failure_retains_safe_error_and_allowed_audit(self):
        with patch("agent_guard.executor.simulated_read", side_effect=OSError("private detail")) as reader:
            with self.assertRaises(OperationError) as caught:
                execute_request({"action": "read", "path": "notes.txt"}, use_project_policy=True)
        reader.assert_called_once_with("notes.txt")
        self.assertEqual(str(caught.exception), "The permitted read failed.")
        self.assertNotIn("private detail", "".join(traceback.format_exception(caught.exception)))
        self.assertEqual(audit_log, [{"action": "read", "path": "notes.txt", "allowed": True,
                                     "reason": "project: Reading notes.txt is permitted."}])

    def test_audit_failure_stops_before_reader(self):
        error = OSError("example audit failure")
        with patch("agent_guard.executor.record_decision", side_effect=error):
            with patch("agent_guard.executor.simulated_read") as reader:
                with self.assertRaises(OSError) as caught:
                    execute_request({"action": "read", "path": "notes.txt"}, use_project_policy=True)
        self.assertIs(caught.exception, error)
        reader.assert_not_called()

    def test_malformed_policy_record_is_denied_without_echoing_its_reason(self):
        bad_record = {"layer": "project", "decision": "unknown", "reason": "private policy detail"}
        with patch("agent_guard.executor.evaluate_project_request", return_value=bad_record):
            with patch("agent_guard.executor.simulated_read") as reader:
                result = execute_request({"action": "read", "path": "notes.txt"}, use_project_policy=True)
        reader.assert_not_called()
        self.assertEqual(result, {"decision": "deny", "executed": False,
                                  "message": "Malformed policy decisions."})
        self.assertEqual(audit_log, [{"action": "read", "path": "notes.txt", "allowed": False,
                                     "reason": "Malformed policy decisions."}])

    def test_request_fields_cannot_enable_project_mode(self):
        request = {"action": "read", "path": "draft.txt", "use_project_policy": True}
        with patch("agent_guard.executor.simulated_read") as reader:
            result = execute_request(request)
        reader.assert_not_called()
        self.assertEqual(result, {"decision": "deny", "executed": False,
                                  "message": "File is not permitted."})
        self.assertEqual(len(audit_log), 1)


if __name__ == "__main__":
    unittest.main()
