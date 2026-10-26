"""OpenID Connect token exchange and identity verification; tokens stay in memory."""

from dataclasses import dataclass, field
import json
import math
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .oauth import LoginAttempt, has_plan_scope
from .oauth_callback import AuthorizationCode


ISSUER = "https://auth.openai.com"
DISCOVERY_URL = ISSUER + "/.well-known/openid-configuration"
AUTHORIZE_URL = ISSUER + "/api/accounts/authorize"
TOKEN_URL = ISSUER + "/api/accounts/oauth/token"


class AuthenticationError(Exception):
    """A safe-to-display authentication error, without token response contents."""


def require_auth_dependencies():
    try:
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError:
        raise AuthenticationError(
            "Install the optional authentication dependencies from requirements-auth.txt."
        ) from None
    return jwt


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class JsonTransport:
    """HTTPS JSON requests with bounded reads, no redirects, and redacted errors."""

    def __init__(self):
        self._opener = build_opener(_NoRedirects())

    def request(self, url: str, form: dict | None = None) -> dict:
        target = urlsplit(url)
        if target.scheme != "https" or target.netloc != "auth.openai.com" or target.fragment:
            raise AuthenticationError("The authentication endpoint is not trusted.")
        body = None if form is None else urlencode(form).encode("utf-8")
        headers = {"Accept": "application/json"}
        if form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = Request(url, data=body, headers=headers)
        try:
            with self._opener.open(request, timeout=10) as response:
                raw = response.read(1_048_577)
        except HTTPError as error:
            status = error.code
            error.close()
            raise AuthenticationError(f"The authentication service returned HTTP {status}.") from None
        except (URLError, OSError, ValueError):
            raise AuthenticationError("The authentication service could not be reached.") from None
        if len(raw) > 1_048_576:
            raise AuthenticationError("The authentication response was too large.")
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            raise AuthenticationError("The authentication response was not valid JSON.") from None
        if not isinstance(data, dict):
            raise AuthenticationError("The authentication response had an invalid structure.")
        return data


@dataclass(frozen=True)
class AuthenticatedSession:
    """Verified identity and session credentials; plan permission is a separate flag."""

    client_id: str
    subject: str = field(repr=False)
    access_token: str = field(repr=False)
    id_token: str = field(repr=False)
    refresh_token: str | None = field(repr=False)
    expires_at: float
    plan_usage_enabled: bool


class OAuthClient:
    def __init__(self, transport=None):
        self.transport = transport if transport is not None else JsonTransport()

    def prepare(self) -> dict:
        configuration = self.transport.request(DISCOVERY_URL)
        jwks_uri = configuration.get("jwks_uri")
        if not isinstance(jwks_uri, str):
            raise AuthenticationError("The identity provider configuration is invalid.")
        try:
            keys_url = urlsplit(jwks_uri)
        except ValueError:
            raise AuthenticationError("The identity provider configuration is invalid.") from None
        algorithms = configuration.get("id_token_signing_alg_values_supported")
        if (
            configuration.get("issuer") != ISSUER
            or configuration.get("authorization_endpoint") != AUTHORIZE_URL
            or configuration.get("token_endpoint") != TOKEN_URL
            or keys_url.scheme != "https" or keys_url.netloc != "auth.openai.com"
            or keys_url.query or keys_url.fragment
            or not isinstance(algorithms, list) or "RS256" not in algorithms
        ):
            raise AuthenticationError("The identity provider configuration is not supported.")
        return configuration

    def exchange_and_verify(
        self, code: AuthorizationCode, attempt: LoginAttempt,
        configuration: dict, expected_subject: str | None = None,
    ) -> AuthenticatedSession:
        jwt = require_auth_dependencies()
        tokens = self.transport.request(configuration["token_endpoint"], {
            "grant_type": "authorization_code",
            "client_id": code.client_id,
            "code": code.code,
            "code_verifier": attempt.code_verifier,
            "redirect_uri": attempt.redirect_uri,
            "resource": "https://api.openai.com/v1",
        })
        access_token = self._token_value(tokens.get("access_token"))
        id_token = self._token_value(tokens.get("id_token"))
        refresh_token = tokens.get("refresh_token")
        if refresh_token is not None:
            refresh_token = self._token_value(refresh_token)
        expires_in = tokens.get("expires_in")
        try:
            invalid_expiry = (
                type(expires_in) not in (int, float)
                or not math.isfinite(expires_in) or expires_in <= 0
            )
        except OverflowError:
            invalid_expiry = True
        if (
            not isinstance(tokens.get("token_type"), str)
            or tokens["token_type"].lower() != "bearer"
            or invalid_expiry
        ):
            raise AuthenticationError("The token response is incomplete or invalid.")
        claims = self._verify_identity(jwt, id_token, code.client_id, attempt.nonce, configuration)
        if expected_subject is not None and claims["sub"] != expected_subject:
            raise AuthenticationError("The signed-in account does not match the saved registration.")
        plan_enabled = has_plan_scope(tokens.get("scope")) is True
        return AuthenticatedSession(
            code.client_id, claims["sub"], access_token, id_token, refresh_token,
            time.time() + expires_in, plan_enabled,
        )

    @staticmethod
    def _token_value(value) -> str:
        if (
            not isinstance(value, str) or not value or not value.isascii()
            or any(character.isspace() for character in value)
        ):
            raise AuthenticationError("The token response is incomplete or invalid.")
        return value

    def _verify_identity(self, jwt, token, client_id, nonce, configuration) -> dict:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str) or not header["kid"]:
                raise AuthenticationError("The identity token uses an unsupported signing key.")
            matches = []
            # Refresh once when a key ID is unfamiliar, then fail closed.
            for _ in range(2):
                jwks = self.transport.request(configuration["jwks_uri"])
                keys = jwks.get("keys")
                if not isinstance(keys, list):
                    raise AuthenticationError("The identity provider returned invalid signing keys.")
                matches = [key for key in keys if isinstance(key, dict) and key.get("kid") == header["kid"]]
                if matches:
                    break
            if len(matches) != 1:
                raise AuthenticationError("The identity token's signing key could not be verified.")
            key = matches[0]
            if (
                key.get("kty") != "RSA" or key.get("use", "sig") != "sig"
                or key.get("alg", "RS256") != "RS256"
                or ("key_ops" in key and (
                    not isinstance(key["key_ops"], list) or "verify" not in key["key_ops"]
                ))
            ):
                raise AuthenticationError("The identity provider returned an unsupported signing key.")
            public_key = jwt.PyJWK.from_dict(key, algorithm="RS256").key
            claims = jwt.decode(
                token, public_key, algorithms=["RS256"], issuer=ISSUER,
                audience=client_id, leeway=5,
                options={"require": ["iss", "sub", "aud", "exp", "iat", "nonce"]},
            )
            actual_nonce = claims.get("nonce")
            if (
                any(type(claims[name]) not in (int, float) or not math.isfinite(claims[name]) for name in ("exp", "iat"))
                or not isinstance(actual_nonce, str) or not actual_nonce.isascii()
                or not secrets.compare_digest(nonce, actual_nonce)
                or not isinstance(claims.get("sub"), str) or not claims["sub"].strip()
                or ("azp" in claims and claims["azp"] != client_id)
                or (isinstance(claims["aud"], list) and len(claims["aud"]) > 1 and claims.get("azp") != client_id)
            ):
                raise AuthenticationError("The returned identity did not match this sign-in attempt.")
            return claims
        except (jwt.PyJWTError, ValueError, TypeError, KeyError, OverflowError):
            raise AuthenticationError("The returned identity token could not be verified.") from None
