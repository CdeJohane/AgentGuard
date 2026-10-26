"""Model response exercise: python -m unittest tests.test_model_requests -v"""

import unittest
from unittest.mock import patch

from agent_guard.audit import audit_log
from agent_guard.executor import execute_request
from agent_guard.model_requests import parse_model_request


class ModelRequestTests(unittest.TestCase):
    def setUp(self):
        audit_log.clear()

    def tearDown(self):
        audit_log.clear()

    def test_decodes_a_proposed_read(self):
        text = '{"action": "read", "path": "notes.txt"}'
        self.assertEqual(parse_model_request(text), {
            "action": "read", "path": "notes.txt",
        })

    def test_preserves_a_forbidden_proposal_for_the_guard_to_decide(self):
        text = '{"action": "write", "path": "notes.txt"}'
        self.assertEqual(parse_model_request(text), {
            "action": "write", "path": "notes.txt",
        })

    def test_invalid_json_becomes_none(self):
        texts = [
            "I would like to read your notes.",
            '{"action": "read",',
            '```json\n{"action": "read", "path": "notes.txt"}\n```',
        ]
        for text in texts:
            self.assertIsNone(parse_model_request(text), msg=f"Text: {text!r}")

    def test_other_json_values_are_decoded_without_granting_permission(self):
        cases = [('[]', []), ('"notes.txt"', 'notes.txt'), ('null', None)]
        for text, expected in cases:
            self.assertEqual(parse_model_request(text), expected)

    def test_invalid_output_is_denied_without_calling_the_reader(self):
        with patch("agent_guard.executor.simulated_read") as reader:
            request = parse_model_request("This is not JSON.")
            result = execute_request(request)
            reader.assert_not_called()
        self.assertEqual(result, (False, "Malformed request."))
        self.assertEqual(audit_log, [{
            "action": None, "path": None, "allowed": False,
            "reason": "Malformed request.",
        }])

    def test_decoded_forbidden_action_is_denied_and_audited(self):
        text = '{"action": "write", "path": "notes.txt"}'
        with patch("agent_guard.executor.simulated_read") as reader:
            result = execute_request(parse_model_request(text))
            reader.assert_not_called()
        self.assertEqual(result, (False, "Action is not permitted."))
        self.assertEqual(audit_log, [{
            "action": "write", "path": "notes.txt", "allowed": False,
            "reason": "Action is not permitted.",
        }])


if __name__ == "__main__":
    unittest.main()
