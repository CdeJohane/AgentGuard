"""Execution tests: python -m unittest tests.test_executor -v"""

import traceback
import unittest
from unittest.mock import patch

from agent_guard.audit import audit_log
from agent_guard.executor import OperationError, execute_request


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        audit_log.clear()

    def tearDown(self):
        audit_log.clear()

    def test_allowed_request_calls_reader_once_and_returns_its_contents(self):
        request = {"action": "read", "path": "notes.txt"}
        with patch("agent_guard.executor.simulated_read", return_value="Contents from reader") as reader:
            result = execute_request(request)
            reader.assert_called_once_with("notes.txt")
            self.assertEqual(result, (True, "Contents from reader"))

    def test_forbidden_action_never_calls_reader(self):
        request = {"action": "write", "path": "notes.txt"}
        with patch("agent_guard.executor.simulated_read") as reader:
            result = execute_request(request)
            reader.assert_not_called()
            self.assertEqual(result, (False, "Action is not permitted."))

    def test_forbidden_path_never_calls_reader(self):
        request = {"action": "read", "path": "secrets.txt"}
        with patch("agent_guard.executor.simulated_read") as reader:
            result = execute_request(request)
            reader.assert_not_called()
            self.assertEqual(result, (False, "File is not permitted."))

    def test_malformed_requests_never_call_reader(self):
        requests = [
            None,
            {},
            {"action": "read"},
            {"action": 123, "path": "notes.txt"},
            {"action": "read", "path": None},
            [],
        ]
        for request in requests:
            with patch("agent_guard.executor.simulated_read") as reader:
                result = execute_request(request)
                reader.assert_not_called()
                self.assertEqual(result, (False, "Malformed request."))

    def test_reader_oserror_becomes_safe_failure_with_one_allowed_audit_record(self):
        request = {"action": "read", "path": "notes.txt"}
        with patch("agent_guard.executor.simulated_read", side_effect=OSError("private reader detail")) as reader:
            with self.assertRaises(OperationError) as caught:
                execute_request(request)
        reader.assert_called_once_with("notes.txt")
        self.assertEqual(str(caught.exception), "The permitted read failed.")
        self.assertTrue(caught.exception.__suppress_context__, "Use 'from None' to hide the original error.")
        formatted = "".join(traceback.format_exception(caught.exception))
        self.assertNotIn("private reader detail", formatted)
        self.assertEqual(audit_log, [{
            "action": "read", "path": "notes.txt", "allowed": True,
            "reason": "Reading notes.txt is permitted.",
        }])

    def test_unexpected_reader_errors_are_not_disguised_as_expected_failures(self):
        bug = ValueError("example programming error")
        with patch("agent_guard.executor.simulated_read", side_effect=bug):
            with self.assertRaises(ValueError) as caught:
                execute_request({"action": "read", "path": "notes.txt"})
        self.assertIs(caught.exception, bug)

    def test_audit_failure_stops_before_reader_and_is_not_wrapped_as_reader_failure(self):
        audit_error = OSError("example audit failure")
        with patch("agent_guard.executor.record_decision", side_effect=audit_error):
            with patch("agent_guard.executor.simulated_read") as reader:
                with self.assertRaises(OSError) as caught:
                    execute_request({"action": "read", "path": "notes.txt"})
        self.assertIs(caught.exception, audit_error)
        reader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
