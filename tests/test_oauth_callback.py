"""Local fake-callback tests; no browser or OpenAI requests."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from http.client import HTTPConnection
from io import StringIO
import socket
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

from agent_guard.oauth_callback import CallbackError, CallbackListener


def send_callback(listener, parameters, path="/auth/callback"):
    uri = urlsplit(listener.attempt.redirect_uri)
    connection = HTTPConnection(uri.hostname, uri.port, timeout=2)
    try:
        connection.request("GET", path + "?" + urlencode(parameters))
        response = connection.getresponse()
        return response.status, response.read().decode("utf-8"), dict(response.getheaders())
    finally:
        connection.close()


class CallbackListenerTests(unittest.TestCase):
    def valid_parameters(self, listener):
        return {"state": listener.attempt.state, "code": "fake-code-for-test", "client_id": "oaiapp_test"}

    def test_receives_code_on_loopback_without_logging_or_echoing_it(self):
        captured = StringIO()
        with redirect_stderr(captured), redirect_stdout(captured):
            with CallbackListener(uuid4().urn) as listener, ThreadPoolExecutor(max_workers=1) as pool:
                uri = urlsplit(listener.attempt.redirect_uri)
                self.assertEqual(uri.hostname, "127.0.0.1")
                self.assertGreater(uri.port, 0)
                pending = pool.submit(listener.wait)
                status, body, headers = send_callback(listener, self.valid_parameters(listener))
                result = pending.result(timeout=2)
                self.assertEqual(status, 200)
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertNotIn("fake-code-for-test", body)
                self.assertEqual((result.code, result.client_id), ("fake-code-for-test", "oaiapp_test"))
                self.assertNotIn(result.code, repr(result))
        self.assertEqual(captured.getvalue(), "")

    def test_invalid_state_and_paths_do_not_consume_the_attempt(self):
        with CallbackListener(uuid4().urn) as listener, ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(listener.wait)
            invalid = [
                ({"code": "fake-code-for-test", "client_id": "oaiapp_test"}, "/auth/callback", 400),
                ({"state": "wrong"}, "/auth/callback", 400),
                ([("state", listener.attempt.state), ("state", listener.attempt.state)], "/auth/callback", 400),
                (self.valid_parameters(listener), "/wrong-path", 404),
            ]
            for parameters, path, expected_status in invalid:
                status, _, _ = send_callback(listener, parameters, path)
                self.assertEqual(status, expected_status)
            self.assertEqual(send_callback(listener, self.valid_parameters(listener))[0], 200)
            self.assertEqual(pending.result(timeout=2).code, "fake-code-for-test")

    def test_matching_but_incomplete_or_ambiguous_callbacks_fail(self):
        cases = [
            {"client_id": "oaiapp_test"},
            {"code": "fake-code-for-test"},
            {"code": "fake-code-for-test", "client_id": "dynamic_agent_client"},
            [("code", "one"), ("code", "two"), ("client_id", "oaiapp_test")],
        ]
        for values in cases:
            with self.subTest(values=values):
                with CallbackListener(uuid4().urn) as listener, ThreadPoolExecutor(max_workers=1) as pool:
                    fields = list(values.items()) if isinstance(values, dict) else list(values)
                    fields.append(("state", listener.attempt.state))
                    pending = pool.submit(listener.wait)
                    self.assertEqual(send_callback(listener, fields)[0], 400)
                    with self.assertRaises(CallbackError):
                        pending.result(timeout=2)

    def test_declined_consent_stops_the_attempt_even_if_a_code_is_present(self):
        with CallbackListener(uuid4().urn) as listener, ThreadPoolExecutor(max_workers=1) as pool:
            fields = self.valid_parameters(listener)
            fields["error"] = "access_denied"
            pending = pool.submit(listener.wait)
            self.assertEqual(send_callback(listener, fields)[0], 400)
            with self.assertRaisesRegex(CallbackError, "declined"):
                pending.result(timeout=2)

    def test_result_can_only_be_awaited_once(self):
        with CallbackListener(uuid4().urn) as listener, ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(listener.wait)
            send_callback(listener, self.valid_parameters(listener))
            pending.result(timeout=2)
            with self.assertRaisesRegex(RuntimeError, "once"):
                listener.wait()

    def test_attempt_expired_before_wait_is_rejected(self):
        with patch("agent_guard.oauth_callback.time.monotonic", return_value=100.0):
            with CallbackListener(uuid4().urn, timeout_seconds=5) as listener:
                with patch("agent_guard.oauth_callback.time.monotonic", return_value=105.0):
                    with self.assertRaises(TimeoutError):
                        listener.wait()

    def test_no_callback_times_out(self):
        with CallbackListener(uuid4().urn, timeout_seconds=0.03) as listener:
            started = time.monotonic()
            with self.assertRaises(TimeoutError):
                listener.wait()
            self.assertLess(time.monotonic() - started, 1.0)

    def test_slow_incomplete_http_headers_cannot_extend_login_deadline(self):
        with CallbackListener(uuid4().urn, timeout_seconds=0.1) as listener:
            uri = urlsplit(listener.attempt.redirect_uri)
            with socket.create_connection((uri.hostname, uri.port), timeout=1) as client:
                started = time.monotonic()

                def drip_headers():
                    try:
                        client.sendall(b"GET /auth/callback HTTP/1.1\r\nX-Slow: ")
                        while time.monotonic() - started < 2:
                            client.sendall(b"x")
                            time.sleep(0.01)
                    except OSError:
                        pass

                with ThreadPoolExecutor(max_workers=1) as pool:
                    dripping = pool.submit(drip_headers)
                    with self.assertRaises(TimeoutError):
                        listener.wait()
                    elapsed = time.monotonic() - started
                    dripping.result(timeout=3)
                self.assertLess(elapsed, 0.75)

    def test_closed_listener_cannot_be_used(self):
        with CallbackListener(uuid4().urn) as listener:
            pass
        with self.assertRaises(RuntimeError):
            listener.wait()
        with self.assertRaises(RuntimeError):
            _ = listener.attempt

    def test_invalid_timeouts_are_rejected(self):
        for timeout in (0, -1, True, "180", float("inf"), float("nan")):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    CallbackListener(uuid4().urn, timeout_seconds=timeout)


if __name__ == "__main__":
    unittest.main()
