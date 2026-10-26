"""Offline token validation tests with locally generated signing keys."""

from io import BytesIO
import json
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs
from uuid import uuid4

from agent_guard.auth_tokens import (
    AUTHORIZE_URL, DISCOVERY_URL, ISSUER, TOKEN_URL,
    AuthenticationError, JsonTransport, OAuthClient,
)
from agent_guard.oauth import create_login_attempt
from agent_guard.oauth_callback import AuthorizationCode

try:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    HAVE_AUTH_DEPENDENCIES = True
except ImportError:
    HAVE_AUTH_DEPENDENCIES = False


JWKS_URL = ISSUER + "/.well-known/jwks.json"
CONFIGURATION = {
    "issuer": ISSUER, "authorization_endpoint": AUTHORIZE_URL,
    "token_endpoint": TOKEN_URL, "jwks_uri": JWKS_URL,
    "id_token_signing_alg_values_supported": ["RS256"],
}


class FakeTransport:
    def __init__(self, tokens, keys):
        self.tokens = tokens
        self.keys = keys
        self.calls = []

    def request(self, url, form=None):
        self.calls.append((url, form))
        if url == DISCOVERY_URL:
            return CONFIGURATION.copy()
        if url == TOKEN_URL:
            return self.tokens.copy()
        if url == JWKS_URL:
            return {"keys": self.keys}
        raise AssertionError("Unexpected endpoint in offline test.")


@unittest.skipUnless(HAVE_AUTH_DEPENDENCIES, "Install requirements-auth.txt to run signed-token tests")
class IdentityVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.jwk = jwt.algorithms.RSAAlgorithm.to_jwk(cls.private_key.public_key(), as_dict=True)
        cls.jwk.update({"kid": "offline-test-key", "use": "sig", "alg": "RS256"})

    def setUp(self):
        self.attempt = create_login_attempt(uuid4().urn, 1455)
        self.code = AuthorizationCode("fake-authorization-code", "oaiapp_test")
        now = int(time.time())
        self.claims = {
            "iss": ISSUER, "sub": "offline-test-subject", "aud": "oaiapp_test",
            "iat": now, "exp": now + 3600, "nonce": self.attempt.nonce,
        }

    def tokens(self, claims=None, key=None, algorithm="RS256"):
        encoded = jwt.encode(
            self.claims if claims is None else claims,
            self.private_key if key is None else key,
            algorithm=algorithm, headers={"kid": "offline-test-key"},
        )
        return {
            "access_token": "fake-access-token", "id_token": encoded,
            "refresh_token": "fake-refresh-token", "token_type": "Bearer",
            "expires_in": 3600, "scope": "openid chatgpt.tokens.use.direct",
        }

    def complete(self, tokens, *, expected_subject=None, plan_granted=True, keys=None):
        transport = FakeTransport(tokens, [self.jwk] if keys is None else keys)
        client = OAuthClient(transport)
        configuration = client.prepare()
        with patch("agent_guard.auth_tokens.has_plan_scope", return_value=plan_granted):
            session = client.exchange_and_verify(self.code, self.attempt, configuration, expected_subject)
        return session, transport

    def test_verified_identity_and_token_request_are_bound_to_the_attempt(self):
        session, transport = self.complete(self.tokens())
        self.assertEqual(session.subject, "offline-test-subject")
        self.assertTrue(session.plan_usage_enabled)
        self.assertEqual(transport.calls[1], (TOKEN_URL, {
            "grant_type": "authorization_code", "client_id": "oaiapp_test",
            "code": self.code.code, "code_verifier": self.attempt.code_verifier,
            "redirect_uri": self.attempt.redirect_uri, "resource": "https://api.openai.com/v1",
        }))
        for secret in (session.subject, session.access_token, session.id_token, session.refresh_token):
            self.assertNotIn(secret, repr(session))

    def test_forged_signature_is_rejected_without_exposing_tokens(self):
        with self.assertRaises(AuthenticationError) as captured:
            self.complete(self.tokens(key=self.other_key))
        self.assertNotIn("fake-access-token", str(captured.exception))

    def test_invalid_identity_claims_are_rejected(self):
        now = int(time.time())
        replacements = [
            {"iss": "https://other.invalid"}, {"aud": "oaiapp_other"},
            {"exp": now - 100}, {"iat": now + 100}, {"nonce": "wrong"},
            {"nonce": "\u2603"}, {"sub": ""}, {"azp": "oaiapp_other"},
            {"aud": ["oaiapp_test", "other"]}, {"exp": str(now + 3600)},
        ]
        for replacement in replacements:
            with self.subTest(replacement=replacement):
                with self.assertRaises(AuthenticationError):
                    self.complete(self.tokens({**self.claims, **replacement}))
        missing_nonce = self.claims.copy()
        del missing_nonce["nonce"]
        with self.assertRaises(AuthenticationError):
            self.complete(self.tokens(missing_nonce))

    def test_symmetric_algorithm_is_not_accepted_as_an_identity_signature(self):
        with self.assertRaises(AuthenticationError):
            self.complete(self.tokens(key="offline-test-symmetric-key-at-least-32-bytes", algorithm="HS256"))

    def test_unknown_or_ambiguous_signing_keys_are_rejected(self):
        for keys in ([], [self.jwk, self.jwk]):
            with self.subTest(key_count=len(keys)):
                with self.assertRaises(AuthenticationError):
                    self.complete(self.tokens(), keys=keys)

    def test_invalid_token_response_fields_are_rejected(self):
        for replacement in (
            {"access_token": "contains whitespace"}, {"id_token": None},
            {"token_type": "Other"}, {"expires_in": 0}, {"expires_in": True},
            {"expires_in": float("inf")}, {"expires_in": 10 ** 1000},
        ):
            with self.subTest(replacement=replacement):
                with self.assertRaises(AuthenticationError):
                    self.complete({**self.tokens(), **replacement})

    def test_a_returning_registration_cannot_change_accounts(self):
        with self.assertRaises(AuthenticationError):
            self.complete(self.tokens(), expected_subject="a-different-account")

    def test_valid_identity_without_scope_keeps_plan_usage_disabled(self):
        session, _ = self.complete(self.tokens(), plan_granted=False)
        self.assertEqual(session.subject, "offline-test-subject")
        self.assertFalse(session.plan_usage_enabled)


class ProviderAndTransportTests(unittest.TestCase):
    def test_untrusted_discovery_endpoints_are_rejected(self):
        changes = [
            {"issuer": "https://other.invalid"},
            {"token_endpoint": "https://other.invalid/tokens"},
            {"jwks_uri": "http://auth.openai.com/keys"},
            {"jwks_uri": "https://other.invalid/keys"},
            {"id_token_signing_alg_values_supported": None},
        ]
        for replacement in changes:
            with self.subTest(replacement=replacement):
                transport = unittest.mock.Mock()
                transport.request.return_value = {**CONFIGURATION, **replacement}
                with self.assertRaises(AuthenticationError):
                    OAuthClient(transport).prepare()

    def test_token_transport_encodes_form_and_does_not_use_redirects(self):
        transport = JsonTransport()
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"ok": true}'
        with patch.object(transport._opener, "open", return_value=response) as opened:
            self.assertEqual(transport.request(TOKEN_URL, {"code": "fake-code+value"}), {"ok": True})
        request = opened.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(parse_qs(request.data.decode()), {"code": ["fake-code+value"]})

    def test_http_error_body_is_not_exposed(self):
        transport = JsonTransport()
        error = HTTPError(TOKEN_URL, 400, "private details", {}, BytesIO(b'fake-private-token'))
        with patch.object(transport._opener, "open", side_effect=error):
            with self.assertRaises(AuthenticationError) as captured:
                transport.request(TOKEN_URL, {"code": "fake-code"})
        self.assertIn("400", str(captured.exception))
        self.assertNotIn("private", str(captured.exception))

    def test_non_authentication_hosts_are_rejected_before_request(self):
        transport = JsonTransport()
        with patch.object(transport._opener, "open") as opened:
            with self.assertRaises(AuthenticationError):
                transport.request("https://other.invalid/tokens", {"code": "fake-code"})
            opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
