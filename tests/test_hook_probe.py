"""Offline protocol and receipt checks; no live hooks or Codex calls."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from agent_guard.hook_probe import BLOCK_REASON, MAX_EVENT_CHARACTERS, main, make_block_decision
from tests.helpers import local_test_directory


def denial():
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": BLOCK_REASON,
    }}


class HookProbeTests(unittest.TestCase):
    def event(self, **changes):
        return {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                "cwd": str(Path("probe-workspace").resolve()),
                "tool_input": {"command": "private example command"}, **changes}

    def run_probe(self, raw, *, workspace=None, receipt=None):
        output, errors = StringIO(), StringIO()
        arguments = ["--workspace", str(Path("probe-workspace").resolve() if workspace is None else workspace)]
        if receipt is not None:
            arguments.extend(["--receipt", str(receipt)])
        with patch("sys.stdin", StringIO(raw)), redirect_stdout(output), redirect_stderr(errors):
            status = main(arguments)
        return status, output.getvalue(), errors.getvalue()

    def test_learner_response_matches_the_documented_denial_schema(self):
        self.assertEqual(make_block_decision(), denial())

    def test_scoped_shell_call_emits_json_denial_without_echoing_input(self):
        with patch("agent_guard.hook_probe.make_block_decision", return_value=denial()):
            status, output, errors = self.run_probe(json.dumps(self.event()))
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output), denial())
        self.assertEqual(errors, "")
        self.assertNotIn("private example command", output)

    def test_other_workspace_tool_or_event_receives_no_probe_decision(self):
        cases = [self.event(cwd=str(Path("other-workspace").resolve())),
                 self.event(tool_name="apply_patch"), self.event(hook_event_name="PostToolUse")]
        with patch("agent_guard.hook_probe.make_block_decision") as builder:
            for event in cases:
                with self.subTest(event=event):
                    status, output, errors = self.run_probe(json.dumps(event))
                    self.assertEqual((status, json.loads(output), errors), (0, {}, ""))
        builder.assert_not_called()

    def test_malformed_input_blocks_with_exit_two_and_redacted_message(self):
        cases = ["private invalid JSON", "[]", "{}", json.dumps(self.event(tool_input=None))]
        for raw in cases:
            with self.subTest(raw=raw):
                status, output, errors = self.run_probe(raw)
                self.assertEqual((status, output), (2, ""))
                self.assertIn("execution is blocked", errors)
                self.assertNotIn("private", errors)

    def test_oversized_event_is_rejected(self):
        status, output, errors = self.run_probe("x" * (MAX_EVENT_CHARACTERS + 1))
        self.assertEqual((status, output), (2, ""))
        self.assertIn("execution is blocked", errors)

    def test_builder_error_blocks_without_leaking_exception_details(self):
        with patch("agent_guard.hook_probe.make_block_decision", side_effect=RuntimeError("private token")):
            status, output, errors = self.run_probe(json.dumps(self.event()))
        self.assertEqual((status, output), (2, ""))
        self.assertNotIn("private token", errors)

    def test_unsupported_ask_or_extra_output_fields_block_locally(self):
        ask = denial()
        ask["hookSpecificOutput"]["permissionDecision"] = "ask"
        extra = {**denial(), "continue": False}
        for value in (ask, extra):
            with self.subTest(value=value):
                with patch("agent_guard.hook_probe.make_block_decision", return_value=value):
                    status, output, errors = self.run_probe(json.dumps(self.event()))
                self.assertEqual((status, output), (2, ""))
                self.assertIn("execution is blocked", errors)

    def test_receipt_records_denial_and_command_digest_without_raw_command(self):
        with local_test_directory() as workspace:
            receipt = workspace / "hook-receipts.jsonl"
            command = "private example command referencing blocked-marker.txt"
            event = self.event(cwd=str(workspace), tool_input={"command": command})
            status, output, errors = self.run_probe(json.dumps(event), workspace=workspace, receipt=receipt)
            self.assertEqual((status, json.loads(output), errors), (0, denial(), ""))
            raw = receipt.read_text(encoding="utf-8")
            self.assertNotIn(command, raw)
            self.assertEqual(json.loads(raw), {
                "event": "PreToolUse", "tool": "Bash", "decision": "deny",
                "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
                "target_marker_mentioned": True,
            })

    def test_receipt_cannot_be_written_outside_expected_probe_path(self):
        with local_test_directory() as workspace:
            wrong = workspace / "unrelated.txt"
            event = self.event(cwd=str(workspace))
            status, output, errors = self.run_probe(json.dumps(event), workspace=workspace, receipt=wrong)
            self.assertEqual((status, output), (2, ""))
            self.assertIn("execution is blocked", errors)
            self.assertFalse(wrong.exists())

    def test_receipt_write_failure_requests_block_without_private_exception_text(self):
        with local_test_directory() as workspace:
            with patch("agent_guard.hook_probe._record_probe_call", side_effect=OSError("private path")):
                status, output, errors = self.run_probe(
                    json.dumps(self.event(cwd=str(workspace))), workspace=workspace,
                    receipt=workspace / "hook-receipts.jsonl",
                )
            self.assertEqual((status, output), (2, ""))
            self.assertNotIn("private path", errors)
