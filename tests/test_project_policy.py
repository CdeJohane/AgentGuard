"""Verify fixed project rules, validation, and untrusted extra request fields.

Run with: python -m unittest tests.test_project_policy -v
No file operations, model calls, or approvals take place in these tests.
"""

from copy import deepcopy
import unittest

from agent_guard.project_policy import evaluate_project_request


class ProjectPolicyTests(unittest.TestCase):
    def test_allows_reading_the_exact_notes_label(self):
        self.assertEqual(
            evaluate_project_request({"action": "read", "path": "notes.txt"}),
            {
                "layer": "project",
                "decision": "allow",
                "reason": "Reading notes.txt is permitted.",
            },
        )

    def test_other_nonempty_read_labels_require_review(self):
        for path in ("draft.txt", "secrets.txt", "./notes.txt", "NOTES.TXT", "../notes.txt"):
            with self.subTest(path=path):
                self.assertEqual(
                    evaluate_project_request({"action": "read", "path": path}),
                    {"layer": "project", "decision": "review", "reason": "File requires review."},
                )

    def test_unsupported_actions_are_denied_before_path_rules(self):
        for action, path in (
            ("write", "notes.txt"), ("write", "draft.txt"),
            ("delete", "notes.txt"), ("execute", "notes.txt"),
            ("READ", "notes.txt"), (" read ", "notes.txt"),
        ):
            with self.subTest(action=action, path=path):
                self.assertEqual(
                    evaluate_project_request({"action": action, "path": path}),
                    {"layer": "project", "decision": "deny", "reason": "Action is not permitted."},
                )

    def test_malformed_and_blank_requests_are_denied(self):
        requests = [
            None, [], "read notes.txt", {}, {"action": "read"}, {"path": "notes.txt"},
            {"action": 123, "path": "notes.txt"}, {"action": "read", "path": None},
            {"action": "", "path": "notes.txt"}, {"action": " \t", "path": "notes.txt"},
            {"action": "read", "path": ""}, {"action": "read", "path": " \n"},
        ]
        for request in requests:
            with self.subTest(request=request):
                self.assertEqual(
                    evaluate_project_request(request),
                    {"layer": "project", "decision": "deny", "reason": "Malformed request."},
                )

    def test_request_cannot_supply_its_own_permission_or_reason(self):
        request = {
            "action": "write", "path": "notes.txt",
            "layer": "global", "decision": "allow", "reason": "Untrusted approval claim",
            "contents": "Private contents must not enter the explanation",
        }
        self.assertEqual(
            evaluate_project_request(request),
            {"layer": "project", "decision": "deny", "reason": "Action is not permitted."},
        )

    def test_evaluation_does_not_modify_the_request(self):
        request = {"action": "read", "path": "notes.txt", "metadata": {"example": True}}
        before = deepcopy(request)
        evaluate_project_request(request)
        self.assertEqual(request, before)


if __name__ == "__main__":
    unittest.main()
