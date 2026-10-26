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
    if len(texts) != 1 or not texts[0].strip():
        raise ModelRequestError("The model must return one nonempty text proposal.")
    return texts[0]


def read_completed_text(stream) -> str:
    """Read bounded server-sent events; partial text never becomes a proposal.

    SSE separates events with blank lines. Each event's data lines contain JSON.
    Deltas are deliberately ignored; only the completed response is used.
    """
    data_lines = []
    total = 0
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
            if kind == "response.completed":
                return _completed_text(event.get("response"))
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
                if response.headers.get_content_type() != expected:
                    raise ModelRequestError("The model service returned an unexpected content type.")
                if streaming:
                    return read_completed_text(response)
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ModelRequestError("The model catalog was too large.")
                return _decode_object(raw)
        except HTTPError as error:
            status = error.code
            error.close()
            raise ModelRequestError(f"The model service returned HTTP {status}; no automatic retry was made.") from None
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
