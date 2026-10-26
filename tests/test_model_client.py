"""Fake catalog and SSE responses; no browser, credentials, or model allowance."""

from dataclasses import replace
from email.message import Message
from io import BytesIO
import json
import time
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError

from agent_guard.auth_tokens import AuthenticatedSession
from agent_guard.model_client import (
    MAX_RESPONSE_BYTES, MODELS_URL, RESPONSES_URL,
    ModelClient, ModelRequestError, ModelTransport, read_completed_text,
)


def session():
    return AuthenticatedSession(
        "test-client", "test-subject", "fake-access", "fake-id", None,
        time.time() + 600, True,
    )


def completed(text='{"action":"read","path":"notes.txt"}'):
    return {"type": "response.completed", "response": {
        "status": "completed", "output": [{
            "type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": text}],
        }],
    }}


def event_bytes(*events):
    return b"".join(b"data: " + json.dumps(event).encode() + b"\n\n" for event in events)


def response(body, content_type):
    result = BytesIO(body)
    result.headers = Message()
    result.headers["Content-Type"] = content_type
    return result


class StreamTests(unittest.TestCase):
    def test_uses_completed_text_instead_of_partial_deltas(self):
        delta = {"type": "response.output_text.delta", "delta": "misleading partial text"}
        stream = BytesIO(b": heartbeat\n\nevent: response.output_text.delta\n" + event_bytes(delta, completed()))
        self.assertEqual(read_completed_text(stream), '{"action":"read","path":"notes.txt"}')

    def test_deltas_followed_by_failure_are_never_success(self):
        for kind in ("response.failed", "response.incomplete", "error"):
            with self.subTest(kind=kind):
                events = event_bytes(
                    {"type": "response.output_text.delta", "delta": '{"action":"read","path":"notes.txt"}'},
                    {"type": kind, "message": "private provider detail"},
                )
                with self.assertRaises(ModelRequestError) as caught:
                    read_completed_text(BytesIO(events))
                self.assertNotIn("private provider detail", str(caught.exception))

    def test_done_or_eof_without_completion_is_a_failure(self):
        for data in (b"", b"data: [DONE]\n\n", event_bytes({"type": "response.output_text.delta", "delta": "{}"})):
            with self.subTest(data=data), self.assertRaises(ModelRequestError):
                read_completed_text(BytesIO(data))

    def test_rejects_bad_encoding_json_structure_and_oversized_streams(self):
        examples = [
            b"data: \xff\n\n", b"data: nope\n\n", b"data: []\n\n",
            event_bytes({}), b"data: " + b"x" * 65_536,
            (b": keepalive\n" * (MAX_RESPONSE_BYTES // 12 + 1)),
        ]
        for data in examples:
            with self.subTest(length=len(data)), self.assertRaises(ModelRequestError):
                read_completed_text(BytesIO(data))

    def test_rejects_refusals_tool_calls_and_incomplete_final_status(self):
        examples = [
            {"status": "incomplete", "output": []},
            {"status": "completed", "output": [{"type": "function_call"}]},
            {"status": "completed", "output": [{
                "type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "refusal", "refusal": "no"}],
            }]},
            {"status": "completed", "output": []},
        ]
        for output in examples:
            with self.subTest(output=output), self.assertRaises(ModelRequestError):
                read_completed_text(BytesIO(event_bytes({"type": "response.completed", "response": output})))

    def test_reasoning_items_are_ignored_but_text_is_preserved(self):
        event = completed("not valid JSON")
        event["response"]["output"].insert(0, {"type": "reasoning", "summary": []})
        self.assertEqual(read_completed_text(BytesIO(event_bytes(event))), "not valid JSON")


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.transport = Mock()
        self.transport.catalog.return_value = {"models": [
            {"slug": "first", "display_name": "First model", "visibility": "list"},
            {"slug": "hidden", "display_name": "Hidden", "visibility": "hide"},
            {"slug": "second", "display_name": "Second model", "visibility": "list"},
        ]}
        self.client = ModelClient(session(), self.transport)

    def test_catalog_preserves_visible_choices_and_account_order(self):
        choices = self.client.list_models()
        self.assertEqual([(m.slug, m.display_name) for m in choices], [
            ("first", "First model"), ("second", "Second model"),
        ])
        self.transport.catalog.assert_called_once_with("fake-access")
        choices.clear()
        self.client.propose("Read notes.txt", "first")
        self.transport.propose.assert_called_once()

    def test_request_uses_account_model_streaming_and_no_tools(self):
        self.client.list_models()
        self.transport.propose.return_value = "a completed proposal"
        self.assertEqual(self.client.propose("Write secrets.txt", "second"), "a completed proposal")
        token, payload = self.transport.propose.call_args.args
        self.assertEqual(token, "fake-access")
        self.assertEqual(payload["model"], "second")
        self.assertEqual(payload["input"], [{"role": "user", "content": "Write secrets.txt"}])
        self.assertIs(payload["store"], False)
        self.assertIs(payload["stream"], True)
        self.assertEqual(set(payload), {"model", "instructions", "input", "store", "stream"})

    def test_missing_permission_or_expired_session_stops_before_network(self):
        for account in (replace(session(), plan_usage_enabled=False), replace(session(), expires_at=0)):
            with self.subTest(account=account):
                client = ModelClient(account, self.transport)
                with self.assertRaises(ModelRequestError):
                    client.list_models()
                with self.assertRaises(ModelRequestError):
                    client.propose("Read notes.txt", "first")
        self.transport.catalog.assert_not_called()
        self.transport.propose.assert_not_called()

    def test_unknown_models_or_bad_instructions_do_not_consume_inference(self):
        with self.assertRaises(ModelRequestError):
            self.client.propose("Read notes.txt", "first")
        self.client.list_models()
        for instruction, model in [("Read notes.txt", "hidden"), ("", "first"), ("x" * 4001, "first")]:
            with self.subTest(model=model), self.assertRaises(ModelRequestError):
                self.client.propose(instruction, model)
        self.transport.propose.assert_not_called()

    def test_bad_catalog_clears_previous_selection(self):
        self.client.list_models()
        examples = [{}, {"models": []}, {"models": [None]}, {"models": [
            {"visibility": "list", "slug": "one", "display_name": None},
        ]}]
        for data in examples:
            self.transport.catalog.return_value = data
            with self.subTest(data=data), self.assertRaises(ModelRequestError):
                self.client.list_models()
        with self.assertRaises(ModelRequestError):
            self.client.propose("Read notes.txt", "first")


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.transport = ModelTransport()
        self.transport._opener = Mock()

    def test_pins_urls_and_keeps_bearer_out_of_the_json_body(self):
        self.transport._opener.open.return_value = response(b'{"models":[]}', "application/json")
        self.assertEqual(self.transport.catalog("fake-access"), {"models": []})
        request = self.transport._opener.open.call_args.args[0]
        self.assertEqual(request.full_url, MODELS_URL)
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Authorization"), "Bearer fake-access")
        self.transport._opener.open.return_value = response(event_bytes(completed()), "text/event-stream")
        self.transport.propose("fake-access", {"model": "first"})
        request = self.transport._opener.open.call_args.args[0]
        self.assertEqual(request.full_url, RESPONSES_URL)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data), {"model": "first"})
        self.assertNotIn(b"fake-access", request.data)

    def test_http_errors_are_redacted_and_not_retried(self):
        self.transport._opener.open.side_effect = HTTPError(
            RESPONSES_URL, 429, "private detail", {}, BytesIO(b"private body"),
        )
        with self.assertRaises(ModelRequestError) as caught:
            self.transport.propose("fake-access", {})
        self.assertIn("429", str(caught.exception))
        self.assertNotIn("private", str(caught.exception))
        self.transport._opener.open.assert_called_once()

    def test_rejects_unexpected_content_type_and_oversized_catalog(self):
        for body, kind in [(b"{}", "text/html"), (b"x" * (MAX_RESPONSE_BYTES + 1), "application/json")]:
            self.transport._opener.open.return_value = response(body, kind)
            with self.subTest(kind=kind), self.assertRaises(ModelRequestError):
                self.transport.catalog("fake-access")
