"""Verify decision priority, empty input, and malformed policy decisions.

Run with: python -m unittest tests.test_policy -v
These tests combine decisions only; they never execute an agent action.
"""

from copy import deepcopy
from itertools import permutations
import unittest

from agent_guard.policy import combine_decisions, explain_decisions


class PolicyCombinationTests(unittest.TestCase):
    def test_all_layers_must_allow(self):
        for decisions in (["allow"], ["allow", "allow", "allow"]):
            with self.subTest(decisions=decisions):
                self.assertEqual(combine_decisions(decisions), "allow")

    def test_deny_wins_regardless_of_layer_order(self):
        for decisions in permutations(["allow", "review", "deny"]):
            with self.subTest(decisions=decisions):
                self.assertEqual(combine_decisions(list(decisions)), "deny")
        self.assertEqual(combine_decisions(["deny"]), "deny")

    def test_review_wins_over_allow(self):
        for decisions in (["review"], ["allow", "review"], ["review", "allow"]):
            with self.subTest(decisions=decisions):
                self.assertEqual(combine_decisions(decisions), "review")

    def test_no_decisions_requires_review(self):
        self.assertEqual(combine_decisions([]), "review")

    def test_malformed_decisions_are_denied(self):
        malformed = [
            None, "allow", {}, ("allow",),
            [None], [True], [1], [[]], [{}],
            ["ALLOW"], [""], ["unknown"],
            ["allow", "unknown"], ["review", None],
        ]
        for decisions in malformed:
            with self.subTest(decisions=decisions):
                self.assertEqual(combine_decisions(decisions), "deny")


class PolicyExplanationTests(unittest.TestCase):
    """Check contributing reasons, safe validation errors, and unchanged input."""

    def test_allow_explains_all_allowing_layers(self):
        records = [
            {"layer": "global", "decision": "allow", "reason": "Within global limits"},
            {"layer": "project", "decision": "allow", "reason": "Approved destination"},
        ]
        self.assertEqual(
            explain_decisions(records),
            ("allow", "global: Within global limits; project: Approved destination"),
        )

    def test_deny_includes_both_denials_and_omits_review(self):
        records = [
            {"layer": "global", "decision": "deny", "reason": "Secret files are protected"},
            {"layer": "language", "decision": "review", "reason": "Package approval required"},
            {"layer": "project", "decision": "deny", "reason": "Destination is forbidden"},
        ]
        self.assertEqual(
            explain_decisions(records),
            ("deny", "global: Secret files are protected; project: Destination is forbidden"),
        )

    def test_review_explains_only_layers_requiring_review(self):
        records = [
            {"layer": "global", "decision": "allow", "reason": "Within global limits"},
            {"layer": "language", "decision": "review", "reason": "Package approval required"},
            {"layer": "project", "decision": "review", "reason": "Dependency changes need review"},
        ]
        self.assertEqual(
            explain_decisions(records),
            ("review", "language: Package approval required; project: Dependency changes need review"),
        )

    def test_empty_input_has_a_fixed_review_explanation(self):
        self.assertEqual(
            explain_decisions([]), ("review", "No policy decisions were provided.")
        )

    def test_malformed_input_has_a_fixed_denial_without_echoing_values(self):
        valid = {"layer": "global", "decision": "allow", "reason": "Within global limits"}
        malformed = [
            None, {}, "allow", [None], [[]], [{}],
            [{"layer": "global", "decision": "allow"}],
            [{**valid, "layer": ""}], [{**valid, "layer": "   "}],
            [{**valid, "layer": 12}], [{**valid, "reason": None}],
            [{**valid, "reason": "\t"}], [{**valid, "decision": "ALLOW"}],
            [{**valid, "decision": "untrusted input must not be echoed"}],
            [valid, {**valid, "decision": None}],
        ]
        for records in malformed:
            with self.subTest(records=records):
                self.assertEqual(
                    explain_decisions(records), ("deny", "Malformed policy decisions.")
                )

    def test_caller_records_are_not_modified(self):
        records = [{"layer": "project", "decision": "allow", "reason": "Approved destination"}]
        before = deepcopy(records)
        explain_decisions(records)
        self.assertEqual(records, before)


if __name__ == "__main__":
    unittest.main()
