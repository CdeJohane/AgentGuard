"""Completed model proposals must pass through the parser and guarded executor."""

import unittest
from unittest.mock import patch

from agent_guard.agent import execute_model_response
from agent_guard.audit import audit_log


class AgentPipelineTests(unittest.TestCase):
    def setUp(self):
        audit_log.clear()

    def tearDown(self):
        audit_log.clear()

    def test_allowed_proposal_reaches_the_reader_and_is_audited_once(self):
        with patch("agent_guard.executor.simulated_read", return_value="Pretend notes") as reader:
            result = execute_model_response('{"action":"read","path":"notes.txt"}')
        self.assertEqual(result, (True, "Pretend notes"))
        reader.assert_called_once_with("notes.txt")
        self.assertEqual(audit_log, [{
            "action": "read", "path": "notes.txt", "allowed": True,
            "reason": "Reading notes.txt is permitted.",
        }])

    def test_forbidden_proposal_is_not_rewritten_or_executed(self):
        with patch("agent_guard.executor.simulated_read") as reader:
            result = execute_model_response('{"action":"write","path":"notes.txt"}')
        self.assertEqual(result, (False, "Action is not permitted."))
        reader.assert_not_called()
        self.assertEqual(len(audit_log), 1)
        self.assertEqual(audit_log[0]["action"], "write")
        self.assertFalse(audit_log[0]["allowed"])

    def test_invalid_json_is_denied_and_audited(self):
        with patch("agent_guard.executor.simulated_read") as reader:
            result = execute_model_response("not JSON")
        reader.assert_not_called()
        self.assertEqual(result, (False, "Malformed request."))
        self.assertEqual(len(audit_log), 1)
        self.assertIsNone(audit_log[0]["action"])

    def test_valid_json_with_the_wrong_structure_is_still_denied(self):
        with patch("agent_guard.executor.simulated_read") as reader:
            result = execute_model_response('["read", "notes.txt"]')
        reader.assert_not_called()
        self.assertEqual(result, (False, "Malformed request."))
        self.assertEqual(len(audit_log), 1)
