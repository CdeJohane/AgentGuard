"""Execution tests: python -m unittest tests.test_executor -v"""

import unittest
from unittest.mock import patch

from agent_guard.executor import execute_request


class ExecutionTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
