"""Verify policy-flow output and the absence of execution or audit changes.

Run with: python -m unittest tests.test_policy_demo -v
"""

from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import unittest
from unittest.mock import patch

from agent_guard.audit import audit_log
from agent_guard.policy_demo import main


class PolicyDemoTests(unittest.TestCase):
    def test_demo_displays_real_evaluation_and_explanations_for_all_cases(self):
        output = StringIO()
        with redirect_stdout(output):
            main()
        self.assertEqual(
            output.getvalue(),
            "Policy decisions only; no actions will be executed.\n\n"
            "Read notes.txt: ALLOW\n"
            "  project: Reading notes.txt is permitted.\n"
            "Read draft.txt: REVIEW\n"
            "  project: File requires review.\n"
            "Write notes.txt: DENY\n"
            "  project: Action is not permitted.\n"
            "Malformed request: DENY\n"
            "  project: Malformed request.\n",
        )

    def test_repeated_demo_does_not_execute_actions_or_change_existing_audit(self):
        original = deepcopy(audit_log)
        existing = [{"action": "read", "path": "notes.txt", "allowed": True,
                     "reason": "Existing permission record"}]
        try:
            audit_log[:] = deepcopy(existing)
            with (
                patch("agent_guard.executor.execute_request") as execute,
                patch("agent_guard.executor.simulated_read") as reader,
                patch("agent_guard.audit.record_decision") as record,
                redirect_stdout(StringIO()),
            ):
                main()
                main()
            execute.assert_not_called()
            reader.assert_not_called()
            record.assert_not_called()
            self.assertEqual(audit_log, existing)
        finally:
            audit_log[:] = original


if __name__ == "__main__":
    unittest.main()
