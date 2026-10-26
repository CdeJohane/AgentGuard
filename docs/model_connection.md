# Model connection: selected route and first exercise

Status, 26 October 2026: the learner reported a successful live run using an
existing Plus subscription and GPT-6.1-Sol (`gpt-6.1-sol`). Sign-in, account model
discovery, completed inference, proposal parsing, guarded simulated execution,
and one audit record all succeeded. A live forbidden-path check also succeeded:
the model proposed reading secrets.txt, which the guard denied and audited once.
The learner's pipeline exercise is complete
and reviewed. All 129 automated tests pass in the project environment.

Earlier runs exposed an omitted content-type header and an empty terminal output
list despite finalized text in the stream. The adapter now validates headerless
event streams and retains finalized output until successful response completion.
The successful rerun confirms these fixes for the observed flow; the reason for
the omitted header and the account's remaining allowance were not measured.

## Expected connection behaviour

1. Start a local loopback callback listener, then open the system browser for
   Continue with ChatGPT. The user signs in and authorizes plan usage there.
2. Follow the documented OAuth flow: a stable host identifier, per-attempt state,
   nonce, and PKCE protection. Use the issued client ID for the code exchange.
3. Verify the returned identity and granted plan-usage permission before inference.
   Credentials must stay out of source files, terminal output, and audit records.
   Tokens stay in memory. PyJWT with its cryptography extra verifies signed
   identity tokens. Persist only installation and registration metadata, never tokens.
4. Discover available models for the authorized account; do not assume a particular
   model is entitled merely because it appears in a client catalog.
5. Ask the model to propose exactly one action/path request as JSON. The model
   proposes an action; the Python guard decides permission.
6. Consume inference through successful completion before using the model text.
   Decode the JSON and pass the resulting value through `execute_request()`.
   Malformed text must not reach the simulated reader.

The existing offline demo and tests stay available. File operations remain
simulated. Live sign-in and model requests are separate from offline tests.

## Completed exercise: connect completed text to the guard

Expected behaviour, agreed before implementation:

- The model proposes one action/path as JSON from one user instruction. It has
  no tools or file access. Python decides whether the proposal is permitted.
- Discovery uses the signed-in account's model catalog, preserving visible model
  order. The command defaults to the first visible model; `--model` selects a
  catalog slug. An unavailable choice lists the available choices without inference.
- Only a successful `response.completed` event supplies text to the pipeline.
  Failed, incomplete, interrupted, oversized, or malformed service responses stop
  before parsing or execution. Partial text is never executed.
- Completed text containing invalid JSON is a different case: the parser returns
  `None`, and the executor records a malformed-request denial.
- Only reading `notes.txt` reaches the simulated reader. Forbidden proposals
  retain their original action/path and receive the usual permission denial.
- There are no automatic retries or API-key billing fallbacks. Tokens remain in
  memory for the sign-in and inference process, then are discarded on exit.

The assistant implemented `model_client.py`, the `live_demo.py` command,
and fake-response tests. The transport pins the public HTTPS endpoints, refuses
redirects, limits catalog/stream size, uses a 30-second socket timeout, and checks
a 120-second stream budget between line reads. A blocked read can extend beyond
that budget until the socket timeout. This is a small demo adapter, not a general
Responses API client. Reasoning items are ignored; completed assistant text parts
are combined in order, and refusals or tool calls are rejected. The parser and
guard then decide whether the combined text represents one permitted request.

You completed `execute_model_response(text)` in `agent_guard/agent.py`:

1. Decode the supplied text using the existing parser.
2. Pass that decoded value unchanged to the existing executor and return its result.

Your implementation stores the parser's result in `parsed` and returns
`execute_request(parsed)`. It preserves the original proposal and returns the
executor's `(bool, str)` tuple, without duplicating permission rules or audit calls.
With the authentication environment activated:

```powershell
python -m unittest tests.test_agent -v
```

All four pipeline tests pass. The full authentication-environment suite has
129 passing tests, with none skipped. All automated model checks use fake
responses; they do not spend model allowance.

The exercise has passed review and the temporary command gate has been removed.
At this passing checkpoint, commit and push before trying the first live request:

```powershell
python -m agent_guard.live_demo "Read notes.txt"
```

The command signs in again using saved registration,
discovers models, requests one proposal, and displays its result and audit trail.
Status 0 means a proposal was processed (including a guard denial), 1 means a
connection/inference failure, 2 means model-selection needs attention, and
130 means keyboard cancellation. Live allowed and forbidden requests have now succeeded;
remaining allowance has not been measured.

### First live attempt: response format diagnosis

The learner's first run completed sign-in and account model discovery, selecting
`gpt-6.1-sol`, then reported an unexpected content type before the proposal
pipeline ran. The original error hid the HTTP status and actual media type, so
it does not establish whether the service returned JSON, HTML, or another format.

The assistant added bounded diagnostics for rejected formats and HTTP failures:
status, a recognized media type, response-body shape, and a documented service
error code if present. Raw body text, arbitrary codes, and arbitrary media-type
values are omitted. This improves diagnosis; it does not yet fix the live failure.
Four offline regression tests cover diagnostic redaction, documented error codes,
and acceptance of normal SSE content-type parameters. The diagnostic rerun reported
HTTP 200, a missing Content-Type header, and a non-JSON body. That body could be
an event stream; these diagnostics alone do not establish its format.

The transport now attempts bounded SSE parsing for inference responses with
HTTP 200 and a missing Content-Type header. In this fallback, every nonempty line
must be a recognized SSE field or comment. Successful completion and output
validation are still required. Explicitly conflicting content types, headerless
catalog responses, and other HTTP statuses remain rejected. Four further offline
tests cover completed streams, failed or truncated streams, non-SSE content, and
the fallback's scope. This is an application compatibility choice, not a documented
guarantee that OpenAI omits this header. The next live rerun reached a completed
response, establishing that the fallback handled that run's stream. There are no
automatic retries.

### Completed-text extraction

That rerun stopped with "The model must return one nonempty text proposal."
The old condition covered multiple text parts, no text parts, and whitespace-only
text, so that message did not establish the shape. Requiring exactly one text part was
too restrictive: Responses text can span several content parts or messages.

The adapter now combines completed assistant text in response order, without
adding separators or repairing it, following the SDK text-aggregation approach
described in the [text generation guide](https://developers.openai.com/api/docs/guides/text?lang=python).
Two adjacent JSON proposals still produce a malformed-request denial through
the learner's unchanged parser and executor. Empty combined text still stops
before execution, with counts of output items, text parts, text characters, and
stream text-done events. These diagnostics print no response text. Partial text
deltas are never used to fill an empty final response.

Four new offline tests cover text-part aggregation, message aggregation with one
guarded execution, denial of two proposals, and empty-output diagnostics. The
later successful live run is recorded below.

### Retain finalized stream output until completion

The next diagnostic run established the mismatch: the terminal response contained
zero output items, while one `response.output_text.done` event contained 36 text
characters. The adapter had discarded that finalized stream output.

It now buffers `response.output_item.done` and `response.output_text.done` events
in memory. Only after `response.completed` with status `completed`, and only when
the terminal output list is empty, it assembles finalized items by output index
and text parts by content index. It verifies item identifiers, rejects duplicates,
missing text parts, and conflicts, and avoids counting text twice when a complete
item already contains it. Streamed tools and refusals stop processing.

These finalized event formats are documented in the
[streaming events reference](https://developers.openai.com/api/reference/resources/responses/streaming-events).
Using them to fill the observed empty terminal list is a compatibility choice.
If the terminal list contains items, those remain authoritative. A failed,
incomplete, or interrupted response never releases buffered text. The recovered
text passes through the same parser and guarded executor as before.

Seven new offline tests reproduce the observed headerless/36-character/empty-list
pattern, verify one guarded execution, and check ordering, no duplicate text,
failure before completion, invalid identifiers, conflicting text, and refusals
or tool calls. All 129 tests pass. The learner subsequently reported the successful
live result below.

### First successful live proposal, 26 October 2026

The learner ran `python -m agent_guard.live_demo "Read notes.txt"` and reported:

```text
Model: 'GPT-6.1-Sol' ('gpt-6.1-sol')
Completed model proposal: '{"action":"read","path":"notes.txt"}'
EXECUTED
  Simulated contents of notes.txt

Audit trail:
  {'action': 'read', 'path': 'notes.txt', 'allowed': True, 'reason': 'Reading notes.txt is permitted.'}
```

This manually verifies one completed model proposal passing through the learner's
parser-to-executor function, the Python permission check, simulated reader, and
one audit record. The model proposed the action; Python made the permission
decision. No real agent-requested file access occurred. The subsequent live
forbidden-path result is recorded below; offline tests also cover denials and
failed streams.

### Successful live forbidden-path check, 26 October 2026

The learner subsequently reported this result for `Read secrets.txt`:

```text
Model: 'GPT-6.1-Sol' ('gpt-6.1-sol')
Completed model proposal: '{"action":"read","path":"secrets.txt"}'
DENIED
  File is not permitted.

Audit trail:
  {'action': 'read', 'path': 'secrets.txt', 'allowed': False, 'reason': 'File is not permitted.'}
```

The proposal preserved the requested forbidden path. The Python guard denied it,
the reader did not run, and the audit trail contained one denied decision. The
learner clarified that the earlier repeated notes.txt output was a paste mistake.
Both manual checks now match their expected behaviour. Commit and push the
connection fixes and documentation at this passing checkpoint.

## Completed exercise: decode the model's proposal

Your `parse_model_request(text: str) -> object` implementation in
`agent_guard/model_requests.py` uses `json.loads()` and a
`json.JSONDecodeError` handler. Invalid JSON returns `None`; valid JSON returns
the decoded Python value. Lists and strings are still invalid requests to the
guard, even though they are valid JSON. A JSON `null` decodes to Python `None`.

For example, a decoded write request stays a write request. The parser does not
convert it into a read, grant it permission, or decide which files are allowed.
Plain prose and Markdown-fenced JSON are rejected rather than repaired.

```powershell
python -m unittest tests.test_model_requests -v
```

All six parser tests pass. These are offline tests; they do not verify live
authentication or model access.

## Completed exercise: prepare sign-in and validate callback state

`agent_guard/oauth.py` now prepares a first-registration URL with fresh random
state, nonce, and PKCE verifier values. PKCE uses a secret verifier and its hash
to bind a later authorization-code exchange to the process that started it.
The URL includes only that hash, not the verifier. The callback URI is fixed to
`http://127.0.0.1:<port>/auth/callback`, using the listener's actual bound port.

The helpers in `oauth.py` prepare values without opening a browser, saving an
identifier, exchanging tokens, or calling a model. The listener lives in
`oauth_callback.py`; host-ID persistence is implemented in `local_state.py`.

Your `callback_state_matches(expected, received)` implementation in `oauth.py`
accepts matching nonempty ASCII strings using `secrets.compare_digest()`. Our
generator supplies an ASCII expected value; your type, empty-value, and ASCII
checks safely reject missing or malformed returned state before comparison.
The listener reuses this helper and enforces attempt expiry and one-time use.

```powershell
python -m unittest tests.test_oauth -v
```

Sign-in preparation and callback-state tests pass. Token exchange and identity
verification are implemented and tested with fake responses. A manual identity
and permission check also succeeded, as reported by the learner.

## Callback listener: implemented with simulated responses

`CallbackListener` in `agent_guard/oauth_callback.py` is a context manager. It
binds `127.0.0.1` on a free port before preparing the authorization URL. Its
`attempt` property provides that URL and the pending login values. `wait()` may
be called once and returns an `AuthorizationCode` containing the code and issued
client ID. That result is not a verified login; token validation comes later.

Missing, duplicate, or mismatched state is rejected without consuming the attempt.
A matching callback consumes it once, including when consent was declined or
required fields are malformed. The default deadline is three minutes, measured
from entering the context, and also bounds slow, unfinished HTTP requests.
The context closes the listener on exit.

Default HTTP request logs are disabled, responses do not echo codes, and the
returned object's repr hides its code. Cancellation and malformed matching
callbacks raise `CallbackError`; an expired attempt raises `TimeoutError`.
The browser controller and token exchange are implemented in `sign_in.py` and
`auth_tokens.py`; the live sign-in check is now available after scope review.

```powershell
python -m unittest tests.test_oauth_callback -v
```

The listener tests pass using fake codes and local HTTP only, including returning
registrations whose callback omits the saved client ID. A different returned ID
is rejected. These tests do not contact OpenAI or establish account eligibility.

## Completed exercise: persist the installation host ID

`load_or_create_host_id()` is implemented in `agent_guard/local_state.py`. Its optional
`path` argument is a `pathlib.Path`, defaulting to `.agent_guard/host.json`.

The creation branch and file reading were scaffolded; you completed validation
of the loaded `data` and returning the host-ID string. The function requires a
dictionary containing a string `host_id`, raising `ValueError` otherwise. It then
parses the UUID and checks its version and canonical URN.

- If the file exists, decode its JSON and read `host_id`. Require a string that
  parses with `UUID()`, has `.version == 4`, and equals the parsed UUID's `.urn`.
  Return the existing value without rewriting the file.
- If the saved JSON, structure, or host ID is invalid, raise `ValueError`. Keep
  the original file untouched; do not silently generate a replacement.
- If missing, create the parent directory and generate `uuid4().urn`. Write only
  `{"host_id": value}` as UTF-8 JSON, then return the value. File mode `"x"`
  refuses to overwrite a file if another process created it in the meantime.
- Let filesystem errors, such as a directory in place of the file, propagate.

```powershell
python -m unittest tests.test_local_state -v
```

All four host-ID tests pass. Fixtures use
temporary subdirectories of ignored `.agent_guard/test-tmp/`, with verified
workspace paths before cleanup. The application's real host metadata has not
been created. Host IDs are identifiers, not authentication credentials.

## Implemented authentication components

- `auth_tokens.py` fetches public discovery metadata, checks the expected issuer
  and endpoints, and exchanges an accepted code with its issued client ID, exact
  redirect URI, and PKCE verifier. HTTP errors are displayed without raw bodies.
  Redirects are refused, HTTP reads are bounded, and requests have timeouts.
- Identity verification requires an RS256 signature from the issuer's JWKS,
  matching issuer and audience, required claims, valid timestamps, the original
  nonce, and a nonempty subject. Returning registrations must match the saved
  subject. Unfamiliar key IDs trigger one refresh before failure.
- `sign_in.py` prepares the listener before opening the browser, closes it on
  completion or failure, and returns an in-memory session after verification.
  It does not call models or run agent tools.
- `local_state.py` saves the issued client ID before exchange with `subject: null`
  for an initial pending registration. Successful verification supplies the
  subject. Existing verified registration data is preserved on failed sign-in.
  Metadata is written atomically and never contains tokens.
- Returning authorization URLs reuse the issued client ID and omit the initial
  agent-name hint. The stable host ID is reused. Tokens are not persisted, so a
  new process requires browser sign-in again. Multiple-account switching, token
  refresh, and remote logout are outside this first version.

The public discovery document was checked against the expected issuer, endpoints,
and RS256 signing algorithm. This does not establish personal account eligibility.

## Completed exercise: check the granted permission scope

Your `has_plan_scope(scope: object) -> bool` implementation in `agent_guard/oauth.py`:

- Non-string input returns `False`.
- Split a string into individual scope names.
- Return `True` only when `chatgpt.tokens.use.direct` is a complete scope name.
  `chatgpt.tokens.use.direct.extra` must return `False`.

A verified identity without this permission remains signed in with
`plan_usage_enabled=False`; it must not make model requests. The token response
provides the scope, not the browser callback's untrusted query parameters. The
flag records granted permission, not a successful inference or remaining quota.

Authentication uses the optional dependency in `requirements-auth.txt`, already
installed in the project's current `venv`. For a fresh checkout:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-auth.txt
.\venv\Scripts\python.exe -m unittest -v
```

At the completed authentication checkpoint, all 88 tests passed, with none skipped.
See the completed pipeline exercise above for the expanded suite's present status. Without the optional
dependency, eight signed-token tests are explicitly skipped. Fake responses and
generated keys exercise verification without live sign-in or model usage.

## Try the live account check

```powershell
.\venv\Scripts\python.exe -m agent_guard.sign_in
```

The command opens Continue with ChatGPT in the system browser, waits for the
local callback, exchanges the code, and verifies identity and granted scope.
It prints only the result, not tokens, codes, or account identifiers. The tests
cover success, missing permission, expected failures, redaction of unexpected
errors, and Ctrl+C cancellation.

The command exits after checking the connection; its tokens are not saved.
Only installation and registration metadata remains. Status 0 means verified
identity and plan permission, 2 means verified identity without plan permission,
1 means failure, and 130 means keyboard cancellation. No model inference is run,
so a successful check does not prove inference eligibility or remaining quota.
The learner reported this successful live result on 26 October 2026:

```text
Account verified. ChatGPT plan usage permission granted.
No model request was made. This check does not save login tokens.
```

Identity, granted scope, and one live model inference are now manually verified.
Remaining allowance has not been measured. Each new demo process signs in again,
using the saved client registration, because tokens are not persisted.

## Local state and secrets

| Value | First-version storage |
| --- | --- |
| OAuth state, nonce, and PKCE verifier | Memory for one login attempt; discarded afterward |
| Access, refresh, and ID tokens | Memory for the running session; fresh sign-in after restart |
| Host ID | `.agent_guard/host.json` when the helper is called; no tokens |
| Issued client registration metadata | `.agent_guard/registration.json`: client ID and subject, initially null until verified; no tokens |
| Optional local configuration | `.env` may be used later; no `.env` file is currently required or generated |

`.gitignore` excludes `.env`, `.env.*`, and `.agent_guard/`. A deliberately
non-secret `.env.example` template can still be tracked. Ignore rules only affect
untracked files; they do not remove anything already committed.

A `.env` file is ordinary plaintext and does not encrypt its contents. If we
later add remembered sign-in, use protected credential storage such as the
operating system's credential store. Do not store OAuth tokens in `.env`, the
repository, the audit log, or callback request logs. The callback handler
suppresses default HTTP request logging because callback URLs contain
authorization codes.

## Official OpenAI references checked on 26 October 2026

- [Registration and sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [Models and inference, including a Python example](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [Accounts, sessions, and credential security](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
- [Local and open-source project integration overview](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt)
- [Identity validation guidance](https://developers.openai.com/siwc/website#6-verify-the-id-token)
- [PyJWT API reference](https://pyjwt.readthedocs.io/en/stable/api.html)

The sign-in guide covers dynamic client registration and validation. The inference
guide requires the public Responses API, an authorized OAuth token, streaming,
`store=false`, and a completed response before treating a request as successful.
This is distinct from separately billed API-key access.
