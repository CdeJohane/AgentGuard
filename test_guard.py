"""Run with: python -m unittest -v"""

import unittest

from guard import check_request, is_allowed, is_valid_request


class PermissionTests(unittest.TestCase):
    def test_allows_reading_notes(self):
        request = {"action": "read", "path": "notes.txt"}
        self.assertIs(is_allowed(request), True)

    def test_denies_writing_notes(self):
        request = {"action": "write", "path": "notes.txt"}
        self.assertIs(is_allowed(request), False)

    def test_denies_reading_another_file(self):
        request = {"action": "read", "path": "secrets.txt"}
        self.assertIs(is_allowed(request), False)

    def test_denies_unknown_actions(self):
        request = {"action": "delete", "path": "notes.txt"}
        self.assertIs(is_allowed(request), False)

    def test_denies_malformed_requests(self):
        requests = [
            {},
            {"action": "read"},
            {"path": "notes.txt"},
            {"action": 123, "path": "notes.txt"},
            {"action": "read", "path": None},
            None,
            [],
            "read notes.txt",
            42,
        ]
        for request in requests:
            with self.subTest(request=request):
                self.assertIs(is_allowed(request), False)


class DecisionReasonTests(unittest.TestCase):
    def test_explains_an_allowed_read(self):
        request = {"action": "read", "path": "notes.txt"}
        self.assertEqual(
            check_request(request), (True, "Reading notes.txt is permitted.")
        )

    def test_explains_a_forbidden_action(self):
        request = {"action": "write", "path": "notes.txt"}
        self.assertEqual(
            check_request(request), (False, "Action is not permitted.")
        )

    def test_explains_a_forbidden_file(self):
        request = {"action": "read", "path": "secrets.txt"}
        self.assertEqual(
            check_request(request), (False, "File is not permitted.")
        )

    def test_explains_malformed_requests(self):
        requests = [
            {},
            {"action": "read"},
            {"path": "notes.txt"},
            {"action": 123, "path": "notes.txt"},
            {"action": "read", "path": None},
            None,
            [],
            "read notes.txt",
            42,
        ]
        for request in requests:
            with self.subTest(request=request):
                self.assertEqual(
                    check_request(request), (False, "Malformed request.")
                )

    def test_structure_reason_takes_priority_over_action(self):
        request = {"action": "write", "path": None}
        self.assertEqual(check_request(request), (False, "Malformed request."))

    def test_action_reason_takes_priority_over_path(self):
        request = {"action": "write", "path": "secrets.txt"}
        self.assertEqual(
            check_request(request), (False, "Action is not permitted.")
        )


class ValidationTests(unittest.TestCase):
    def test_accepts_a_read_request(self):
        # A dictionary with string action and path values should be valid.
        request = {"action": "read", "path": "notes.txt"}
        self.assertTrue(is_valid_request(request))

    def test_accepts_a_forbidden_but_well_formed_request(self):
        # A write request for notes.txt is valid input, despite being forbidden.
        request = {"action": "write", "path": "notes.txt"}
        self.assertTrue(is_valid_request(request))

    def test_rejects_a_request_with_a_missing_path(self):
        request = {"action": "read"}
        self.assertFalse(is_valid_request(request))


if __name__ == "__main__":
    unittest.main()
