"""Optional ChatGPT-plan model connection. No tools or file access are supplied."""

from dataclasses import dataclass
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .auth_tokens import AuthenticatedSession


MODELS_URL = "https://api.openai.com/v1/models"
RESPONSES_URL = "https://api.openai.com/v1/responses"
MAX_RESPONSE_BYTES = 1_048_576
# Display only documented codes, never arbitrary service text that might echo input.
SERVICE_ERROR_CODES = {
    "subscription_sharing_user_not_eligible",
    "subscription_sharing_usage_limit_exceeded",
    "subscription_sharing_usage_unavailable",
    "subscription_sharing_unsupported_capability",
    "subscription_sharing_route_not_supported",
    "subscription_sharing_invalid_user",
    "subscription_sharing_user_unavailable",
    "chatpass_v2_scope_not_authorized",
    "chatpass_v2_invalid_authorization_context",
}
INSTRUCTIONS = (
    'Translate the user instruction into one JSON object with string keys '
    '"action" and "path", or null if no single file operation is specified. '
    'Use lowercase operation names, for example read or write. Preserve the '
    'requested path exactly. Preserve forbidden operations and paths too: a '
    'separate Python guard decides permission. Do not substitute a safer action '
    'or path. Output JSON only, without Markdown or commentary. Do not claim '
    'that an operation was executed.'
)


class ModelRequestError(Exception):
    """Safe-to-display failure without credentials or raw service responses."""


@dataclass(frozen=True)
class ModelChoice:
    slug: str
    display_name: str


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _service_failure(response, expected: str) -> ModelRequestError:
    """Describe a failed response using bounded, non-content diagnostics only."""
    status = getattr(response, "status", None)
    if type(status) is not int or not 100 <= status <= 599:
        status = getattr(response, "code", None)
    status_text = str(status) if type(status) is int and 100 <= status <= 599 else "unknown"
    headers = response.headers
    if headers is None or headers.get("Content-Type") is None:
        media_type = "missing"
    else:
        media_type = headers.get_content_type()
        if media_type not in {
            "application/json", "application/problem+json", "text/event-stream",
            "text/plain", "text/html", "application/octet-stream",
        }:
            media_type = "unrecognized (value omitted)"
    raw = response.read(MAX_RESPONSE_BYTES + 1)
    code = None
    if len(raw) > MAX_RESPONSE_BYTES:
        shape = "too large"
    elif not raw:
        shape = "empty"
    else:
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            shape = "non-JSON"
        else:
            if isinstance(body, dict):
                error = body.get("error")
                if isinstance(error, dict):
                    shape = "JSON object with error"
                    candidate = error.get("code")
                    if isinstance(candidate, str) and candidate in SERVICE_ERROR_CODES:
                        code = candidate
                else:
                    shape = "JSON object with detail" if "detail" in body else "JSON object"
            else:
                shape = "JSON array" if isinstance(body, list) else "JSON scalar"
    details = f"HTTP {status_text}; expected {expected}; received {media_type}; body: {shape}"
    if code is not None:
        details += f"; code: {code}"
    return ModelRequestError(
        f"The model service response was rejected ({details}). "
        "No action was attempted; no automatic retry was made."
    )


def _decode_object(raw: bytes | str) -> dict:
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError):
        raise ModelRequestError("The model service returned invalid JSON.") from None
    if not isinstance(data, dict):
        raise ModelRequestError("The model service returned an invalid response structure.")
    return data


def _completed_text(response: object) -> str:
    if not isinstance(response, dict) or response.get("status") != "completed":
        raise ModelRequestError("The model response was not completed.")
    output = response.get("output")
    if not isinstance(output, list):
        raise ModelRequestError("The completed response had no usable proposal.")
    texts = []
    for item in output:
        if not isinstance(item, dict):
            raise ModelRequestError("The completed response had an invalid output item.")
        if item.get("type") == "reasoning":
            continue
        if (
            item.get("type") != "message" or item.get("role") != "assistant"
            or item.get("status") != "completed"
        ):
            raise ModelRequestError("The model returned an unsupported output item.")
        content = item.get("content")
        if not isinstance(content, list):
            raise ModelRequestError("The completed response had invalid message content.")
        for part in content:
            if (
                not isinstance(part, dict) or part.get("type") != "output_text"
                or not isinstance(part.get("text"), str)
            ):
                raise ModelRequestError("The model did not return a text proposal.")
            texts.append(part["text"])
    # One proposal may span several text parts or assistant messages. Preserve
    # their order and contents; the JSON parser still checks the combined text.
    text = "".join(texts)
    if not text.strip():
        raise ModelRequestError(
            "The completed response contained no nonempty text "
            f"(output items: {len(output)}; text parts: {len(texts)}; "
            f"text characters: {len(text)}). No action was attempted."
        )
    return text


def _restore_stream_output(response: object, item_events: list, text_events: list) -> object:
    """Fill an empty terminal output from finalized stream items, after success.

    Text-done events carry complete text, not deltas. Their indexes and item IDs
    let us assemble parts without duplication or combining different items.
    """
    if (
        not isinstance(response, dict) or response.get("status") != "completed"
        or response.get("output") != []
    ):
        return response
    items = {}
    for event in item_events:
        index, item = event.get("output_index"), event.get("item")
        if type(index) is not int or index < 0 or not isinstance(item, dict) or index in items:
            raise ModelRequestError("The stream contained invalid or duplicate completed output items.")
        items[index] = item

    parts = {}
    identities = {}
    for event in text_events:
        index, content_index = event.get("output_index"), event.get("content_index")
        item_id, text = event.get("item_id"), event.get("text")
        if (
            type(index) is not int or index < 0 or type(content_index) is not int or content_index < 0
            or not isinstance(item_id, str) or not item_id or not isinstance(text, str)
        ):
            raise ModelRequestError("Completed stream text lacked valid item identifiers or indexes.")
        key = (index, content_index)
        if key in parts or (index in identities and identities[index] != item_id):
            raise ModelRequestError("The stream contained duplicate or conflicting completed text parts.")
        parts[key] = text
        identities[index] = item_id
        if index in items:
            item = items[index]
            content = item.get("content")
            if (
                item.get("id") != item_id or item.get("type") != "message"
                or not isinstance(content, list) or content_index >= len(content)
                or not isinstance(content[content_index], dict)
                or content[content_index].get("type") != "output_text"
                or content[content_index].get("text") != text
            ):
                raise ModelRequestError("Completed stream text conflicted with its output item.")

    for index, item_id in identities.items():
        if index in items:
            continue  # The complete output item already includes these parts.
        indexes = sorted(content_index for output_index, content_index in parts if output_index == index)
        if indexes != list(range(len(indexes))):
            raise ModelRequestError("The completed stream text had missing content parts.")
        items[index] = {
            "id": item_id, "type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": parts[index, part]} for part in indexes],
        }
    return {**response, "output": [items[index] for index in sorted(items)]}


def read_completed_text(stream, *, require_sse_fields: bool = False) -> str:
    """Read bounded server-sent events; partial text never becomes a proposal.

    SSE separates events with blank lines. Each event's data lines contain JSON.
    Deltas are deliberately ignored. Finalized items/text remain buffered until
    successful response completion, then can fill an empty terminal output list.
    When the content-type header is absent, require recognized SSE fields on
    every nonempty line as an additional format check.
    """
    data_lines = []
    total = 0
    text_done_events = 0
    text_done_characters = 0
    completed_items = []
    completed_text = []
    deadline = time.monotonic() + 120
    while True:
        raw = stream.readline(65_537)
        total += len(raw)
        if len(raw) > 65_536 or total > MAX_RESPONSE_BYTES:
            raise ModelRequestError("The model stream exceeded the demo's size limit.")
        if time.monotonic() >= deadline:
            raise ModelRequestError("The model stream exceeded the demo's time limit.")
        if not raw:
            break
        try:
            line = raw.decode("utf-8").rstrip("\r\n")
        except UnicodeError:
            raise ModelRequestError("The model stream was not valid UTF-8.") from None
        if require_sse_fields and line and not line.startswith(("data:", "event:", ":", "id:", "retry:")):
            raise ModelRequestError(
                "The HTTP 200 response had no Content-Type header and its body was not "
                "a recognized event stream; no action was attempted."
            )
        if line.startswith("data:"):
            value = line[5:]
            data_lines.append(value[1:] if value.startswith(" ") else value)
        elif line == "" and data_lines:
            data = "\n".join(data_lines)
            data_lines.clear()
            if data == "[DONE]":
                break
            event = _decode_object(data)
            kind = event.get("type")
            if not isinstance(kind, str):
                raise ModelRequestError("The model stream contained an invalid event.")
            if kind in ("response.failed", "response.incomplete", "error"):
                raise ModelRequestError("Model inference failed or was incomplete; no action was attempted.")
            if kind in ("response.output_item.added", "response.output_item.done"):
                item = event.get("item")
                if (
                    not isinstance(item, dict) or item.get("type") not in ("message", "reasoning")
                    or (item.get("type") == "message" and item.get("role") != "assistant")
                ):
                    raise ModelRequestError("The model streamed an unsupported output item.")
                if kind == "response.output_item.done":
                    completed_items.append(event)
            if kind.startswith("response.refusal."):
                raise ModelRequestError("The model refused to return a text proposal.")
            if kind == "response.output_text.done":
                text_done_events += 1
                completed_text.append(event)
                if isinstance(event.get("text"), str):
                    text_done_characters += len(event["text"])
            if kind == "response.completed":
                try:
                    final_response = _restore_stream_output(
                        event.get("response"), completed_items, completed_text,
                    )
                    return _completed_text(final_response)
                except ModelRequestError as error:
                    # Counts diagnose stream shape without printing model text.
                    raise ModelRequestError(
                        f"{error} Stream text-done events: {text_done_events}; "
                        f"text-done characters: {text_done_characters}; "
                        f"output-item-done events: {len(completed_items)}."
                    ) from None
    raise ModelRequestError("The stream ended without a completed response; no action was attempted.")


class ModelTransport:
    """Fixed HTTPS endpoints, bounded reads, no redirects and no automatic retries."""

    def __init__(self):
        self._opener = build_opener(_NoRedirects())

    def _request(self, token: str, payload: dict | None = None):
        headers = {"Authorization": f"Bearer {token}"}
        body = None
        if payload is None:
            url = MODELS_URL
            headers["Accept"] = "application/json"
        else:
            url = RESPONSES_URL
            headers.update({"Accept": "text/event-stream", "Content-Type": "application/json"})
            body = json.dumps(payload).encode("utf-8")
        return Request(url, data=body, headers=headers)

    def catalog(self, token: str) -> dict:
        return self._read(self._request(token), streaming=False)

    def propose(self, token: str, payload: dict) -> str:
        return self._read(self._request(token, payload), streaming=True)

    def _read(self, request, *, streaming: bool):
        try:
            with self._opener.open(request, timeout=30) as response:
                expected = "text/event-stream" if streaming else "application/json"
                if (
                    streaming and response.status == 200
                    and response.headers.get("Content-Type") is None
                ):
                    # Some responses omit the header. Validate the event framing
                    # and completed payload instead of accepting arbitrary text.
                    return read_completed_text(response, require_sse_fields=True)
                if response.headers.get_content_type() != expected:
                    raise _service_failure(response, expected)
                if streaming:
                    return read_completed_text(response)
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ModelRequestError("The model catalog was too large.")
                return _decode_object(raw)
        except HTTPError as error:
            try:
                failure = _service_failure(error, "text/event-stream" if streaming else "application/json")
            finally:
                error.close()
            raise failure from None
        except (URLError, OSError, ValueError):
            raise ModelRequestError("The model connection failed; no action was attempted.") from None


class ModelClient:
    def __init__(self, session: AuthenticatedSession, transport=None):
        self._session = session
        self._transport = transport if transport is not None else ModelTransport()
        self._models: list[ModelChoice] = []

    def _check_session(self):
        if self._session.plan_usage_enabled is not True:
            raise ModelRequestError("ChatGPT plan usage permission was not granted.")
        if self._session.expires_at <= time.time():
            raise ModelRequestError("The session has expired. Sign in again.")

    def list_models(self) -> list[ModelChoice]:
        self._check_session()
        self._models = []
        data = self._transport.catalog(self._session.access_token)
        models = data.get("models")
        if not isinstance(models, list):
            raise ModelRequestError("The model catalog had an invalid structure.")
        choices = []
        for model in models:
            if not isinstance(model, dict):
                raise ModelRequestError("The model catalog contained an invalid entry.")
            if model.get("visibility") != "list":
                continue
            slug, name = model.get("slug"), model.get("display_name")
            if not isinstance(slug, str) or not slug.strip() or not isinstance(name, str) or not name.strip():
                raise ModelRequestError("The model catalog contained an invalid model choice.")
            if slug in [choice.slug for choice in choices]:
                raise ModelRequestError("The model catalog contained duplicate model choices.")
            choices.append(ModelChoice(slug, name))
        if not choices:
            raise ModelRequestError("No selectable models were returned for this account.")
        self._models = choices
        return choices.copy()

    def propose(self, instruction: str, model: str) -> str:
        self._check_session()
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 4_000:
            raise ModelRequestError("Enter a nonempty instruction of at most 4000 characters.")
        if model not in [choice.slug for choice in self._models]:
            raise ModelRequestError("Choose a model from this session's current catalog first.")
        return self._transport.propose(self._session.access_token, {
            "model": model,
            "instructions": INSTRUCTIONS,
            "input": [{"role": "user", "content": instruction}],
            "store": False,
            "stream": True,
        })
