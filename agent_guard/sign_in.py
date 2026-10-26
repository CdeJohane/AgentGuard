"""Browser sign-in check. Tokens remain in memory; no model requests are made."""

from pathlib import Path
import sys
import webbrowser

from .auth_tokens import AuthenticationError, OAuthClient, require_auth_dependencies
from .local_state import Registration, load_or_create_host_id, load_registration, save_registration
from .oauth_callback import CallbackError, CallbackListener


def sign_in(state_directory: Path = Path(".agent_guard")):
    """Connect in the browser and return a verified in-memory session.

    This function does not call a model, run agent tools, or persist tokens.
    A valid account without the required scope returns plan_usage_enabled=False.
    """
    require_auth_dependencies()
    try:
        host_id = load_or_create_host_id(state_directory / "host.json")
        registration = load_registration(state_directory / "registration.json")
    except (ValueError, OSError):
        raise AuthenticationError("Local sign-in metadata could not be loaded.") from None
    client = OAuthClient()
    configuration = client.prepare()
    saved_client = registration.client_id if registration is not None else None
    saved_subject = registration.subject if registration is not None else None
    with CallbackListener(host_id, client_id=saved_client) as listener:
        attempt = listener.attempt
        if not webbrowser.open(attempt.authorization_url):
            raise AuthenticationError("The browser could not be opened for sign-in.")
        code = listener.wait()
    if registration is None:
        # Retain the issued ID before exchange, so an expired code can be retried
        # with this registration. A pending ID is not an authenticated account.
        try:
            save_registration(state_directory / "registration.json", Registration(code.client_id))
        except OSError:
            raise AuthenticationError("Issued registration metadata could not be saved.") from None
    session = client.exchange_and_verify(code, attempt, configuration, saved_subject)
    try:
        save_registration(
            state_directory / "registration.json", Registration(session.client_id, session.subject),
        )
    except OSError:
        raise AuthenticationError("Verified registration metadata could not be saved.") from None
    return session


def main() -> int:
    print("Continue with ChatGPT in the browser to verify this connection.")
    try:
        session = sign_in()
    except KeyboardInterrupt:
        print("Sign-in cancelled.", file=sys.stderr)
        return 130
    except (AuthenticationError, CallbackError, TimeoutError) as error:
        print(f"Sign-in failed: {error}", file=sys.stderr)
        return 1
    except Exception:
        # Unexpected exception messages can contain private response data.
        print("Sign-in failed unexpectedly; no account connection was confirmed.", file=sys.stderr)
        return 1
    if not session.plan_usage_enabled:
        print("Account verified, but ChatGPT plan usage permission was not granted.", file=sys.stderr)
        return 2
    print("Account verified. ChatGPT plan usage permission granted.")
    print("No model request was made. This check does not save login tokens.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
