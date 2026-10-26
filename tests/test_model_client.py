"""Fake catalog and SSE responses; no browser, credentials, or model allowance."""

from dataclasses import replace
from email.message import Message
from io import BytesIO
import json
import time
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from agent_guard.auth_tokens import AuthenticatedSession
from agent_guard.agent import execute_model_response
from agent_guard.audit import audit_log
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
    result.status = 200
    result.headers = Message()
    if content_type is not None:
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

    def test_combines_text_parts_in_order_without_adding_or_removing_characters(self):
        event = completed()
        event["response"]["output"][0]["content"] = [
            {"type": "output_text", "text": ""},
            {"type": "output_text", "text": '{"action":"read",'},
            {"type": "output_text", "text": '"path":"notes.txt"}'},
        ]
        self.assertEqual(read_completed_text(BytesIO(event_bytes(event))), '{"action":"read","path":"notes.txt"}')

    def test_combines_completed_messages_then_executes_one_guarded_proposal(self):
        event = completed('{"action":"read",')
        second = completed('"path":"notes.txt"}')["response"]["output"][0]
        event["response"]["output"].append(second)
        audit_log.clear()
        try:
            text = read_completed_text(BytesIO(event_bytes(event)))
            with patch("agent_guard.executor.simulated_read", return_value="Pretend notes") as reader:
                self.assertEqual(execute_model_response(text), (True, "Pretend notes"))
            reader.assert_called_once_with("notes.txt")
            self.assertEqual(len(audit_log), 1)
        finally:
            audit_log.clear()

    def test_two_json_proposals_are_not_silently_reduced_to_one(self):
        event = completed()
        event["response"]["output"].extend(completed()["response"]["output"])
        audit_log.clear()
        try:
            text = read_completed_text(BytesIO(event_bytes(event)))
            with patch("agent_guard.executor.simulated_read") as reader:
                self.assertEqual(execute_model_response(text), (False, "Malformed request."))
            reader.assert_not_called()
            self.assertEqual(len(audit_log), 1)
        finally:
            audit_log.clear()

    def test_whitespace_terminal_output_reports_counts_without_replacing_it(self):
        text_done = {"type": "response.output_text.done", "text": "private model text"}
        for output, parts, characters in ((completed(" \n")["response"]["output"], 1, 2),):
            event = {"type": "response.completed", "response": {"status": "completed", "output": output}}
            with self.subTest(parts=parts), self.assertRaises(ModelRequestError) as caught:
                read_completed_text(BytesIO(event_bytes(text_done, event)))
            message = str(caught.exception)
            self.assertIn(f"text parts: {parts}", message)
            self.assertIn(f"text characters: {characters}", message)
            self.assertIn("Stream text-done events: 1", message)
            self.assertIn("text-done characters: 18", message)
            self.assertNotIn("private model text", message)

    def test_completed_item_restores_empty_terminal_output_without_double_counting_text(self):
        item = completed()["response"]["output"][0]
        item["id"] = "msg-test"
        item_done = {"type": "response.output_item.done", "output_index": 0, "item": item}
        text_done = {"type": "response.output_text.done", "output_index": 0,
                     "content_index": 0, "item_id": "msg-test", "text": item["content"][0]["text"]}
        final = {"type": "response.completed", "response": {"status": "completed", "output": []}}
        self.assertEqual(read_completed_text(BytesIO(event_bytes(text_done, item_done, final))), text_done["text"])

    def test_completed_text_parts_are_restored_in_index_order(self):
        text_events = [{"type": "response.output_text.done", "output_index": 0,
                        "content_index": index, "item_id": "msg-test", "text": text}
                       for index, text in [(1, '"path":"notes.txt"}'), (0, '{"action":"read",')]]
        final = {"type": "response.completed", "response": {"status": "completed", "output": []}}
        self.assertEqual(read_completed_text(BytesIO(event_bytes(*text_events, final))),
                         '{"action":"read","path":"notes.txt"}')

    def test_finalized_text_is_not_success_without_response_completion(self):
        text_done = {"type": "response.output_text.done", "output_index": 0,
                     "content_index": 0, "item_id": "msg-test", "text": "{}"}
        endings = [(), ({"type": "response.failed"},), ({"type": "response.incomplete"},),
                   ({"type": "response.completed", "response": {"status": "incomplete", "output": []}},)]
        for ending in endings:
            with self.subTest(ending=ending), self.assertRaises(ModelRequestError):
                read_completed_text(BytesIO(event_bytes(text_done, *ending)))

    def test_duplicate_conflicting_unindexed_or_missing_text_parts_are_rejected(self):
        text_done = {"type": "response.output_text.done", "output_index": 0,
                     "content_index": 0, "item_id": "msg-test", "text": "{}"}
        final = {"type": "response.completed", "response": {"status": "completed", "output": []}}
        cases = [
            (text_done, text_done),
            (text_done, {**text_done, "content_index": 1, "item_id": "other"}),
            ({**text_done, "content_index": 1},),
            ({"type": "response.output_text.done", "text": "private unassociated text"},),
        ]
        for events in cases:
            with self.subTest(events=events), self.assertRaises(ModelRequestError) as caught:
                read_completed_text(BytesIO(event_bytes(*events, final)))
            self.assertNotIn("private unassociated text", str(caught.exception))

    def test_streamed_tool_calls_and_refusals_cannot_be_hidden_by_empty_final_output(self):
        cases = [
            {"type": "response.output_item.added", "output_index": 0,
             "item": {"type": "function_call", "name": "read"}},
            {"type": "response.refusal.done", "refusal": "private refusal"},
        ]
        final = {"type": "response.completed", "response": {"status": "completed", "output": []}}
        for event in cases:
            with self.subTest(event=event), self.assertRaises(ModelRequestError):
                read_completed_text(BytesIO(event_bytes(event, final)))

    def test_rejects_text_that_conflicts_with_its_completed_item(self):
        item = completed()["response"]["output"][0]
        item["id"] = "msg-test"
        item_done = {"type": "response.output_item.done", "output_index": 0, "item": item}
        text_done = {"type": "response.output_text.done", "output_index": 0,
                     "content_index": 0, "item_id": "msg-test", "text": "conflicting text"}
        final = {"type": "response.completed", "response": {"status": "completed", "output": []}}
        with self.assertRaises(ModelRequestError):
            read_completed_text(BytesIO(event_bytes(text_done, item_done, final)))


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
            RESPONSES_URL, 429, "private detail", Message(), BytesIO(b"private body"),
        )
        with self.assertRaises(ModelRequestError) as caught:
            self.transport.propose("fake-access", {})
        self.assertIn("429", str(caught.exception))
        self.assertNotIn("private", str(caught.exception))
        self.transport._opener.open.assert_called_once()

    def test_wrong_content_type_reports_status_and_shape_without_private_text(self):
        body = b'{"detail":"private account or token detail"}'
        reply = response(body, "application/json; charset=utf-8")
        self.transport._opener.open.return_value = reply
        with self.assertRaises(ModelRequestError) as caught:
            self.transport.propose("fake-access", {})
        message = str(caught.exception)
        self.assertIn("HTTP 200", message)
        self.assertIn("expected text/event-stream", message)
        self.assertIn("received application/json", message)
        self.assertIn("JSON object with detail", message)
        self.assertNotIn("private", message)
        self.assertNotIn("fake-access", message)
        self.assertTrue(reply.closed)
        self.transport._opener.open.assert_called_once()

    def test_documented_error_codes_are_reported_without_raw_messages(self):
        body = json.dumps({"error": {
            "code": "subscription_sharing_usage_limit_exceeded", "message": "private text",
        }}).encode()
        headers = Message()
        headers["Content-Type"] = "application/json"
        self.transport._opener.open.side_effect = HTTPError(
            RESPONSES_URL, 429, "private reason", headers, BytesIO(body),
        )
        with self.assertRaises(ModelRequestError) as caught:
            self.transport.propose("fake-access", {})
        self.assertIn("HTTP 429", str(caught.exception))
        self.assertIn("subscription_sharing_usage_limit_exceeded", str(caught.exception))
        self.assertNotIn("private", str(caught.exception))

    def test_arbitrary_error_codes_and_header_values_are_not_echoed(self):
        body = b'{"error":{"code":"private-token", "message":"private-message"}}'
        self.transport._opener.open.return_value = response(body, "private/header-value")
        with self.assertRaises(ModelRequestError) as caught:
            self.transport.propose("fake-access", {})
        self.assertIn("unrecognized", str(caught.exception))
        self.assertIn("JSON object with error", str(caught.exception))
        self.assertNotIn("private", str(caught.exception))

    def test_sse_with_content_type_parameters_still_requires_completion(self):
        self.transport._opener.open.return_value = response(
            event_bytes(completed()), "text/event-stream; charset=utf-8",
        )
        self.assertEqual(self.transport.propose("fake-access", {}), '{"action":"read","path":"notes.txt"}')

    def test_missing_content_type_accepts_only_a_completed_event_stream(self):
        reply = response(b": heartbeat\n\nevent: response.completed\n" + event_bytes(completed()), None)
        self.transport._opener.open.return_value = reply
        self.assertEqual(self.transport.propose("fake-access", {}), '{"action":"read","path":"notes.txt"}')
        self.assertTrue(reply.closed)
        self.transport._opener.open.assert_called_once()

    def test_observed_headerless_stream_with_empty_terminal_output_reaches_guard_once(self):
        proposal = '{"action":"read","path":"notes.txt"}'
        self.assertEqual(len(proposal), 36)
        text_done = {"type": "response.output_text.done", "output_index": 0,
                     "content_index": 0, "item_id": "msg-test", "text": proposal}
        final = {"type": "response.completed", "response": {"status": "completed", "output": []}}
        self.transport._opener.open.return_value = response(event_bytes(text_done, final), None)
        audit_log.clear()
        try:
            text = self.transport.propose("fake-access", {})
            with patch("agent_guard.executor.simulated_read", return_value="Pretend notes") as reader:
                self.assertEqual(execute_model_response(text), (True, "Pretend notes"))
            reader.assert_called_once_with("notes.txt")
            self.assertEqual(len(audit_log), 1)
        finally:
            audit_log.clear()

    def test_missing_content_type_still_rejects_partial_or_failed_streams(self):
        delta = {"type": "response.output_text.delta", "delta": '{"action":"read","path":"notes.txt"}'}
        for events in ((delta,), (delta, {"type": "response.failed"})):
            self.transport._opener.open.return_value = response(event_bytes(*events), None)
            with self.subTest(events=events), self.assertRaises(ModelRequestError):
                self.transport.propose("fake-access", {})

    def test_missing_content_type_rejects_json_html_and_text_without_echoing_them(self):
        for body in (
            b'{"action":"read","path":"notes.txt"}', b"<html>private text</html>",
            b"private plain text", b": heartbeat\nprivate text\n" + event_bytes(completed()),
        ):
            self.transport._opener.open.return_value = response(body, None)
            with self.subTest(body=body), self.assertRaises(ModelRequestError) as caught:
                self.transport.propose("fake-access", {})
            self.assertNotIn("private", str(caught.exception))
            self.assertIn("not a recognized event stream", str(caught.exception))

    def test_missing_header_fallback_is_limited_to_http_200_inference(self):
        reply = response(event_bytes(completed()), None)
        reply.status = 201
        self.transport._opener.open.return_value = reply
        with self.assertRaises(ModelRequestError):
            self.transport.propose("fake-access", {})
        self.transport._opener.open.return_value = response(b'{"models":[]}', None)
        with self.assertRaises(ModelRequestError):
            self.transport.catalog("fake-access")

    def test_rejects_unexpected_content_type_and_oversized_catalog(self):
        for body, kind in [(b"{}", "text/html"), (b"x" * (MAX_RESPONSE_BYTES + 1), "application/json")]:
            self.transport._opener.open.return_value = response(body, kind)
            with self.subTest(kind=kind), self.assertRaises(ModelRequestError):
                self.transport.catalog("fake-access")
