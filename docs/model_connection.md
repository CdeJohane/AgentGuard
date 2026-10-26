# Model connection: selected route and first exercise

Status, 26 October 2026: the learner completed a live Sign in with ChatGPT check
using an existing Plus subscription. The reported terminal output confirmed
verified identity and the required plan-usage permission. The command then exited,
discarding in-memory tokens. No model request or inference eligibility has been
verified yet.

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

In that environment, all 88 tests pass, with none skipped. Without the optional
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

Identity and granted scope are now manually verified. Model inference access
and available allowance remain unverified. The next demo must sign in again,
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
