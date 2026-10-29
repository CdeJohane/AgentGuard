"""Verify decision priority, empty input, and malformed policy decisions.

Run with: python -m unittest tests.test_policy -v
These tests combine decisions only; they never execute an agent action.
"""

from itertools import permutations
import unittest

from agent_guard.policy import combine_decisions


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


if __name__ == "__main__":
    unittest.main()
