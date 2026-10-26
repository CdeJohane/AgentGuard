"""One-use local OAuth callback receiver. No token exchange or browser launch."""

from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
import math
import socket
from threading import Timer
import time
from urllib.parse import parse_qs, urlsplit

from .oauth import LoginAttempt, callback_state_matches, create_login_attempt


class CallbackError(Exception):
    """Sign-in was declined or a callback for this attempt was malformed."""


@dataclass(frozen=True)
class AuthorizationCode:
    """Pending code and issued client ID; not a validated account or login."""

    code: str = field(repr=False)
    client_id: str


class _CallbackServer(HTTPServer):
    def get_request(self):
        connection, address = super().get_request()
        # Bound reads from clients that connect but do not finish a request.
        remaining = self.owner._deadline - time.monotonic()
        connection.settimeout(max(0.001, min(1.0, remaining)))
        # Socket read timeouts restart on each read. Enforce the whole attempt's
        # deadline too, including clients that keep trickling incomplete headers.
        def close_at_deadline():
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        self._connection_timer = Timer(max(0.001, remaining), close_at_deadline)
        self._connection_timer.daemon = True
        self._connection_timer.start()
        return connection, address

    def shutdown_request(self, request):
        self._connection_timer.cancel()
        super().shutdown_request(request)

    def handle_error(self, request, client_address):
        # Do not print a traceback containing callback request data.
        if not self.owner._finished:
            if time.monotonic() >= self.owner._deadline:
                self.owner._expire()
            else:
                self.owner._error = CallbackError("The callback listener failed.")
                self.owner._finished = True


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        status, message = self.server.owner._receive(self.path)
        body = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        # Default HTTP logging includes the URL and its authorization code.
        pass


class CallbackListener:
    """Bind loopback first, then prepare and receive one registration attempt.

    Use as a context manager. After entering, attempt.authorization_url can be
    opened in a browser by a future sign-in controller. wait() may be called once.
    """

    def __init__(self, host_id: str, timeout_seconds: float = 180.0, *, client_id: str | None = None):
        if (
            type(timeout_seconds) not in (int, float)
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("The callback timeout must be a positive finite number.")
        self._host_id = host_id
        self._client_id = client_id
        self._timeout_seconds = timeout_seconds
        self._server = None
        self._attempt = None
        self._deadline = 0.0
        self._entered = False
        self._finished = False
        self._wait_called = False
        self._result = None
        self._error = None

    def __enter__(self) -> "CallbackListener":
        if self._entered:
            raise RuntimeError("A callback listener can only be entered once.")
        self._entered = True
        server = _CallbackServer(("127.0.0.1", 0), _CallbackHandler)
        try:
            self._attempt = create_login_attempt(self._host_id, server.server_port, self._client_id)
        except BaseException:
            server.server_close()
            raise
        self._deadline = time.monotonic() + self._timeout_seconds
        server.owner = self
        self._server = server
        return self

    def __exit__(self, exc_type, exc, traceback):
        self._server.server_close()
        self._server = None
        self._attempt = None
        self._result = None

    @property
    def attempt(self) -> LoginAttempt:
        if self._attempt is None:
            raise RuntimeError("The callback listener is not active.")
        return self._attempt

    def wait(self) -> AuthorizationCode:
        """Wait for a matching callback, denial, or timeout; never exchange tokens."""
        if self._server is None:
            raise RuntimeError("The callback listener is not active.")
        if self._wait_called:
            raise RuntimeError("The callback can only be awaited once.")
        self._wait_called = True
        while not self._finished:
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                self._expire()
                break
            self._server.timeout = min(remaining, 0.25)
            self._server.handle_request()
        if self._error is not None:
            raise self._error
        result = self._result
        self._result = None
        return result

    def _expire(self):
        self._finished = True
        self._error = TimeoutError("Sign-in timed out. Start a new attempt.")

    def _receive(self, request_target: str) -> tuple[int, str]:
        if self._finished:
            return 410, "This sign-in attempt is no longer active."
        if time.monotonic() >= self._deadline:
            self._expire()
            return 410, "This sign-in attempt has expired."
        try:
            target = urlsplit(request_target)
            if target.scheme or target.netloc or target.fragment:
                return 400, "Invalid callback request."
            if target.path != "/auth/callback":
                return 404, "Not found."
            fields = parse_qs(target.query, keep_blank_values=True, max_num_fields=20)
        except ValueError:
            return 400, "Invalid callback request."
        states = fields.get("state", [])
        if len(states) != 1 or not callback_state_matches(self.attempt.state, states[0]):
            return 400, "Sign-in could not be verified."

        # A matching callback consumes the attempt even if it reports an error.
        self._finished = True
        if "error" in fields:
            errors = fields["error"]
            message = (
                "Sign-in was declined."
                if errors == ["access_denied"] else "Sign-in did not complete."
            )
            self._error = CallbackError(message)
            return 400, "Sign-in did not complete. You may close this tab."
        codes = fields.get("code", [])
        clients = fields.get("client_id", [])
        if self._client_id is not None and "client_id" not in fields:
            clients = [self._client_id]
        if (
            len(codes) != 1 or not codes[0].strip()
            or len(clients) != 1 or not clients[0].strip()
            or clients[0] == "dynamic_agent_client"
            or (self._client_id is not None and clients[0] != self._client_id)
        ):
            self._error = CallbackError("The sign-in callback was incomplete or ambiguous.")
            return 400, "Invalid sign-in callback. Start a new attempt."
        self._result = AuthorizationCode(codes[0], clients[0])
        return 200, "Authorization received. You may close this tab."
