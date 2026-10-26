"""Sign-in preparation tests: python -m unittest tests.test_oauth -v"""

import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from agent_guard.oauth import callback_state_matches, create_login_attempt


class LoginPreparationTests(unittest.TestCase):
    def test_authorization_url_has_the_callback_scopes_and_pkce_challenge(self):
        # Fixed, public test values; the verifier/challenge are a known PKCE pair.
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        host_id = uuid4().urn
        with patch("agent_guard.oauth.secrets.token_urlsafe", side_effect=[
            "test-state", "test-nonce", verifier,
        ]):
            attempt = create_login_attempt(host_id, 1455)
        url = urlsplit(attempt.authorization_url)
        self.assertEqual((url.scheme, url.netloc, url.path), (
            "https", "auth.openai.com", "/api/accounts/authorize",
        ))
        parameters = parse_qs(url.query)
        self.assertEqual(parameters, {
            "client_id": ["dynamic_agent_client"],
            "agent_name_hint": ["agent-guard"],
            "ext_agent_host_id": [host_id],
            "response_type": ["code"],
            "redirect_uri": ["http://127.0.0.1:1455/auth/callback"],
            "scope": ["openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"],
            "resource": ["https://api.openai.com/v1"],
            "state": ["test-state"],
            "nonce": ["test-nonce"],
            "code_challenge_method": ["S256"],
            "code_challenge": ["E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"],
        })
        self.assertNotIn(verifier, attempt.authorization_url)

    def test_each_attempt_generates_fresh_temporary_values(self):
        host_id = uuid4().urn
        first = create_login_attempt(host_id, 1455)
        second = create_login_attempt(host_id, 1455)
        self.assertNotEqual(first.state, second.state)
        self.assertNotEqual(first.nonce, second.nonce)
        self.assertNotEqual(first.code_verifier, second.code_verifier)
        self.assertGreaterEqual(len(first.code_verifier), 43)
        self.assertLessEqual(len(first.code_verifier), 128)

    def test_object_repr_omits_temporary_values_and_authorization_url(self):
        attempt = create_login_attempt(uuid4().urn, 1455)
        for value in (attempt.state, attempt.nonce, attempt.code_verifier, attempt.authorization_url):
            self.assertNotIn(value, repr(attempt))

    def test_invalid_host_ids_and_callback_ports_are_rejected(self):
        for host_id in ("", "notes.txt", "urn:uuid:00000000-0000-0000-0000-000000000000"):
            with self.subTest(host_id=host_id):
                with self.assertRaises(ValueError):
                    create_login_attempt(host_id, 1455)
        for port in (0, -1, 65536, True, "1455"):
            with self.subTest(port=port):
                with self.assertRaises(ValueError):
                    create_login_attempt(uuid4().urn, port)


class CallbackStateTests(unittest.TestCase):
    def test_matching_state_is_accepted(self):
        self.assertIs(callback_state_matches("expected-state", "expected-state"), True)

    def test_different_state_is_rejected(self):
        self.assertIs(callback_state_matches("expected-state", "other-state"), False)

    def test_missing_empty_or_non_string_state_is_rejected(self):
        for received in (None, "", 42, []):
            self.assertIs(callback_state_matches("expected-state", received), False)

    def test_empty_expected_state_is_rejected(self):
        self.assertIs(callback_state_matches("", ""), False)

    def test_unexpected_unicode_state_is_rejected_without_crashing(self):
        self.assertIs(callback_state_matches("expected-state", "\u2603"), False)


if __name__ == "__main__":
    unittest.main()
