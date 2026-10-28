"""CLI orchestration with fake authentication and inference; no live usage."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import unittest
from unittest.mock import patch

from agent_guard.audit import audit_log
from agent_guard.executor import OperationError
from agent_guard.live_demo import main
from agent_guard.model_client import ModelChoice, ModelRequestError


class LiveDemoTests(unittest.TestCase):
    def setUp(self):
        audit_log.clear()

    def tearDown(self):
        audit_log.clear()

    def test_unavailable_model_lists_choices_without_inference(self):
        with patch("agent_guard.live_demo.sign_in"), patch("agent_guard.live_demo.ModelClient") as factory:
            client = factory.return_value
            client.list_models.return_value = [ModelChoice("first", "First model")]
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["Read notes.txt", "--model", "unavailable"]), 2)
        client.propose.assert_not_called()
        self.assertIn("First model", output.getvalue())
        self.assertEqual(audit_log, [])

    def test_completed_text_reaches_pipeline_once_and_result_is_displayed(self):
        with patch("agent_guard.live_demo.sign_in"):
            with patch("agent_guard.live_demo.ModelClient") as factory, patch("agent_guard.live_demo.execute_model_response") as pipeline:
                client = factory.return_value
                client.list_models.return_value = [ModelChoice("first", "First model")]
                client.propose.return_value = '{"action":"write","path":"notes.txt"}'
                pipeline.return_value = (False, "Action is not permitted.")
                output = StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(["Write notes.txt"]), 0)
        client.propose.assert_called_once_with("Write notes.txt", "first")
        pipeline.assert_called_once_with('{"action":"write","path":"notes.txt"}')
        self.assertIn("DENIED", output.getvalue())
        self.assertIn("Audit trail:", output.getvalue())

    def test_model_failure_does_not_reach_pipeline_reader_or_audit(self):
        with patch("agent_guard.live_demo.sign_in"):
            with patch("agent_guard.live_demo.ModelClient") as factory, patch("agent_guard.live_demo.execute_model_response") as pipeline:
                factory.return_value.list_models.return_value = [ModelChoice("first", "First model")]
                factory.return_value.propose.side_effect = ModelRequestError("Inference incomplete.")
                with patch("agent_guard.executor.simulated_read") as reader:
                    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                        self.assertEqual(main(["Read notes.txt"]), 1)
        pipeline.assert_not_called()
        reader.assert_not_called()
        self.assertEqual(audit_log, [])

    def test_unexpected_error_details_are_not_printed(self):
        with patch("agent_guard.live_demo.sign_in", side_effect=RuntimeError("private token")):
            errors = StringIO()
            with redirect_stdout(StringIO()), redirect_stderr(errors):
                self.assertEqual(main(["Read notes.txt"]), 1)
        self.assertNotIn("private token", errors.getvalue())

    def test_operation_failure_is_displayed_with_allowed_audit_and_failure_exit_status(self):
        with patch("agent_guard.live_demo.sign_in"), patch("agent_guard.live_demo.ModelClient") as factory:
            client = factory.return_value
            client.list_models.return_value = [ModelChoice("first", "First model")]
            client.propose.return_value = '{"action":"read","path":"notes.txt"}'
            output = StringIO()
            with patch("agent_guard.executor.simulated_read", side_effect=OperationError()) as reader:
                with redirect_stdout(output):
                    self.assertEqual(main(["Read notes.txt"]), 1)
        client.propose.assert_called_once_with("Read notes.txt", "first")
        reader.assert_called_once_with("notes.txt")
        text = output.getvalue()
        self.assertIn("\nFAILED\n  The permitted read failed.\n", text)
        self.assertNotIn("\nEXECUTED\n", text)
        self.assertNotIn("\nDENIED\n", text)
        self.assertIn("Audit trail:", text)
        self.assertEqual(audit_log, [{
            "action": "read", "path": "notes.txt", "allowed": True,
            "reason": "Reading notes.txt is permitted.",
        }])
