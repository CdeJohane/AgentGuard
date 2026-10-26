# Model connection: selected route and first exercise

Status, 26 October 2026: the learner chose to pursue the supported Sign in with
ChatGPT route using an existing Plus subscription. The app is not authenticated
and no model request has been made. Account eligibility is unverified.

## Expected connection behaviour

1. Start a local loopback callback listener, then open the system browser for
   Continue with ChatGPT. The user signs in and authorizes plan usage there.
2. Follow the documented OAuth flow: a stable host identifier, per-attempt state,
   nonce, and PKCE protection. Use the issued client ID for the code exchange.
3. Verify the returned identity and granted plan-usage permission before inference.
   Credentials must stay out of source files, terminal output, and audit records.
   The first version will keep tokens in memory; a validation library still needs
   selecting. Persist only non-secret installation and registration metadata.
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

Four sign-in preparation tests and five callback-state tests pass. Token exchange,
identity validation, and live account access remain unimplemented or unverified.

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
No browser-opening command or token exchange is wired up yet.

```powershell
python -m unittest tests.test_oauth_callback -v
```

All ten listener tests pass using fake codes and local HTTP only. They do not
contact OpenAI or establish account eligibility.

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

All four host-ID tests and all fifty-five tests overall pass. Fixtures use
temporary subdirectories of ignored `.agent_guard/test-tmp/`, with verified
workspace paths before cleanup. The application's real host metadata has not
been created. Host IDs are identifiers, not authentication credentials.

## Local state and secrets

| Value | First-version storage |
| --- | --- |
| OAuth state, nonce, and PKCE verifier | Memory for one login attempt; discarded afterward |
| Access, refresh, and ID tokens | Memory for the running session; fresh sign-in after restart |
| Host ID | `.agent_guard/host.json` when the helper is called; no tokens |
| Issued client registration metadata | Planned local JSON under `.agent_guard/`; no tokens |
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

The sign-in guide covers dynamic client registration and validation. The inference
guide requires the public Responses API, an authorized OAuth token, streaming,
`store=false`, and a completed response before treating a request as successful.
This is distinct from separately billed API-key access.
