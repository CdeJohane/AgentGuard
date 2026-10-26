"""Prepare one ChatGPT sign-in attempt. No browser or network calls yet."""

import base64
from dataclasses import dataclass, field
import hashlib
import secrets
from urllib.parse import urlencode
from uuid import UUID


@dataclass(frozen=True)
class LoginAttempt:
    """Keep temporary sign-in values in memory and out of object repr output."""

    redirect_uri: str
    state: str = field(repr=False)
    nonce: str = field(repr=False)
    code_verifier: str = field(repr=False)
    authorization_url: str = field(repr=False)


def create_login_attempt(host_id: str, callback_port: int) -> LoginAttempt:
    """Prepare first-time registration for a caller's persistent UUIDv4 host ID.

    The future callback listener must already own callback_port before this
    URL is opened. This helper does not persist the host ID or start a listener.
    """
    try:
        host_uuid = UUID(host_id)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("A UUIDv4 host ID in urn:uuid: format is required.") from None
    if host_uuid.version != 4 or host_id != host_uuid.urn:
        raise ValueError("A UUIDv4 host ID in urn:uuid: format is required.")
    if type(callback_port) is not int or not 1 <= callback_port <= 65535:
        raise ValueError("Callback port must be an integer from 1 to 65535.")

    redirect_uri = f"http://127.0.0.1:{callback_port}/auth/callback"
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    parameters = {
        "client_id": "dynamic_agent_client",
        "agent_name_hint": "agent-guard",
        "ext_agent_host_id": host_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct",
        "resource": "https://api.openai.com/v1",
        "state": state,
        "nonce": nonce,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
    }
    authorization_url = "https://auth.openai.com/api/accounts/authorize?" + urlencode(parameters)
    return LoginAttempt(redirect_uri, state, nonce, code_verifier, authorization_url)


def callback_state_matches(expected: str, received: object) -> bool:
    """Accept only the same nonempty state returned from the browser.

    The expected value comes from our ASCII state generator. Reject empty or
    non-ASCII values and non-string received input before using compare_digest.
    """
    if not isinstance(received, str) or received == "" or expected == "" or not received.isascii() or not expected.isascii():
        return False
    else:
        return secrets.compare_digest(expected, received)
