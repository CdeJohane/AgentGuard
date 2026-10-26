"""Browser-controller tests with no browser, network calls, or real credentials."""

import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from agent_guard.auth_tokens import AuthenticationError
from agent_guard.local_state import Registration, load_registration, save_registration
from agent_guard.oauth import create_login_attempt
from agent_guard.oauth_callback import AuthorizationCode, CallbackError
from agent_guard.sign_in import main, sign_in
from tests.helpers import local_test_directory


class SignInControllerTests(unittest.TestCase):
    def setUp(self):
        self.dependencies = patch("agent_guard.sign_in.require_auth_dependencies")
        self.dependencies.start()
        self.addCleanup(self.dependencies.stop)

    def fake_listener(self):
        context = MagicMock()
        listener = context.__enter__.return_value
        listener.attempt = create_login_attempt(uuid4().urn, 1455)
        listener.wait.return_value = AuthorizationCode("fake-code", "oaiapp_test")
        return context, listener

    def test_success_saves_registration_metadata_without_tokens(self):
        with local_test_directory() as directory:
            context, listener = self.fake_listener()
            session = SimpleNamespace(client_id="oaiapp_test", subject="verified-subject", access_token="fake-private-token")
            with patch("agent_guard.sign_in.CallbackListener", return_value=context) as factory:
                with patch("agent_guard.sign_in.webbrowser.open", return_value=True) as browser:
                    with patch("agent_guard.sign_in.OAuthClient") as client:
                        client.return_value.exchange_and_verify.return_value = session
                        self.assertIs(sign_in(directory), session)
            factory.assert_called_once()
            self.assertIsNone(factory.call_args.kwargs["client_id"])
            browser.assert_called_once_with(listener.attempt.authorization_url)
            data = json.loads((directory / "registration.json").read_text(encoding="utf-8"))
            self.assertEqual(data, {"client_id": "oaiapp_test", "subject": "verified-subject"})
            self.assertNotIn("fake-private-token", json.dumps(data))

    def test_returning_registration_is_used_and_subject_is_bound(self):
        with local_test_directory() as directory:
            save_registration(directory / "registration.json", Registration("oaiapp_saved", "saved-subject"))
            context, listener = self.fake_listener()
            with patch("agent_guard.sign_in.CallbackListener", return_value=context) as factory:
                with patch("agent_guard.sign_in.webbrowser.open", return_value=True):
                    with patch("agent_guard.sign_in.OAuthClient") as client:
                        client.return_value.exchange_and_verify.return_value = SimpleNamespace(
                            client_id="oaiapp_saved", subject="saved-subject",
                        )
                        sign_in(directory)
                        self.assertEqual(client.return_value.exchange_and_verify.call_args.args[-1], "saved-subject")
            self.assertEqual(factory.call_args.kwargs["client_id"], "oaiapp_saved")

    def test_browser_failure_closes_listener_without_exchanging_tokens(self):
        with local_test_directory() as directory:
            context, _ = self.fake_listener()
            with patch("agent_guard.sign_in.CallbackListener", return_value=context):
                with patch("agent_guard.sign_in.webbrowser.open", return_value=False):
                    with patch("agent_guard.sign_in.OAuthClient") as client:
                        with self.assertRaises(AuthenticationError):
                            sign_in(directory)
                        client.return_value.exchange_and_verify.assert_not_called()
            context.__exit__.assert_called_once()
            self.assertFalse((directory / "registration.json").exists())

    def test_declined_callback_does_not_exchange_or_save_registration(self):
        with local_test_directory() as directory:
            context, listener = self.fake_listener()
            listener.wait.side_effect = CallbackError("Sign-in was declined.")
            with patch("agent_guard.sign_in.CallbackListener", return_value=context):
                with patch("agent_guard.sign_in.webbrowser.open", return_value=True):
                    with patch("agent_guard.sign_in.OAuthClient") as client:
                        with self.assertRaises(CallbackError):
                            sign_in(directory)
                        client.return_value.exchange_and_verify.assert_not_called()
            self.assertFalse((directory / "registration.json").exists())

    def test_failed_identity_validation_preserves_previous_registration(self):
        with local_test_directory() as directory:
            path = directory / "registration.json"
            save_registration(path, Registration("oaiapp_saved", "saved-subject"))
            before = path.read_bytes()
            context, _ = self.fake_listener()
            with patch("agent_guard.sign_in.CallbackListener", return_value=context):
                with patch("agent_guard.sign_in.webbrowser.open", return_value=True):
                    with patch("agent_guard.sign_in.OAuthClient") as client:
                        client.return_value.exchange_and_verify.side_effect = AuthenticationError("Invalid identity.")
                        with self.assertRaises(AuthenticationError):
                            sign_in(directory)
            self.assertEqual(path.read_bytes(), before)

    def test_first_exchange_failure_retains_only_the_pending_client_id(self):
        with local_test_directory() as directory:
            context, _ = self.fake_listener()
            with patch("agent_guard.sign_in.CallbackListener", return_value=context):
                with patch("agent_guard.sign_in.webbrowser.open", return_value=True):
                    with patch("agent_guard.sign_in.OAuthClient") as client:
                        client.return_value.exchange_and_verify.side_effect = AuthenticationError("Code expired.")
                        with self.assertRaises(AuthenticationError):
                            sign_in(directory)
            self.assertEqual(load_registration(directory / "registration.json"), Registration("oaiapp_test"))
            self.assertEqual(json.loads((directory / "registration.json").read_text()), {
                "client_id": "oaiapp_test", "subject": None,
            })


class RegistrationMetadataTests(unittest.TestCase):
    def test_saved_registration_round_trips_without_temporary_files(self):
        with local_test_directory() as directory:
            path = directory / "registration.json"
            registration = Registration("oaiapp_test", "subject")
            save_registration(path, registration)
            self.assertEqual(load_registration(path), registration)
            self.assertEqual(list(directory.iterdir()), [path])

    def test_invalid_registration_is_rejected_without_changing_file(self):
        with local_test_directory() as directory:
            path = directory / "registration.json"
            for data in ({}, {"client_id": "dynamic_agent_client", "subject": "subject"},
                         {"client_id": "oaiapp_test", "subject": "subject", "access_token": "fake-private-token"}):
                path.write_text(json.dumps(data), encoding="utf-8")
                before = path.read_bytes()
                with self.assertRaises(ValueError):
                    load_registration(path)
                self.assertEqual(path.read_bytes(), before)


class SignInCommandTests(unittest.TestCase):
    def run_command(self, *, session=None, error=None):
        output, errors = StringIO(), StringIO()
        with patch("agent_guard.sign_in.sign_in", return_value=session, side_effect=error):
            with redirect_stdout(output), redirect_stderr(errors):
                status = main()
        return status, output.getvalue(), errors.getvalue()

    def test_success_reports_permission_without_printing_tokens(self):
        session = SimpleNamespace(plan_usage_enabled=True, access_token="fake-private-token")
        status, output, errors = self.run_command(session=session)
        self.assertEqual(status, 0)
        self.assertIn("permission granted", output)
        self.assertEqual(errors, "")
        self.assertNotIn("fake-private-token", output)

    def test_missing_plan_permission_has_a_separate_status(self):
        status, _, errors = self.run_command(session=SimpleNamespace(plan_usage_enabled=False))
        self.assertEqual(status, 2)
        self.assertIn("not granted", errors)

    def test_expected_failure_has_a_clear_message(self):
        status, _, errors = self.run_command(error=AuthenticationError("Service unavailable."))
        self.assertEqual(status, 1)
        self.assertIn("Service unavailable", errors)

    def test_unexpected_exception_contents_are_not_printed(self):
        status, _, errors = self.run_command(error=RuntimeError("fake-private-response"))
        self.assertEqual(status, 1)
        self.assertIn("unexpectedly", errors)
        self.assertNotIn("fake-private-response", errors)

    def test_keyboard_interrupt_is_cancelled_without_traceback(self):
        status, _, errors = self.run_command(error=KeyboardInterrupt())
        self.assertEqual(status, 130)
        self.assertIn("cancelled", errors)
        self.assertNotIn("Traceback", errors)


if __name__ == "__main__":
    unittest.main()
