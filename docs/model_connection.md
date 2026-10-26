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

These helpers do not open a browser, run a listener, save an identifier, exchange
tokens, or call a model yet. The caller will supply the saved UUIDv4 host ID.
Host-ID persistence and the live callback are following implementation steps.

Your `callback_state_matches(expected, received)` implementation in `oauth.py`
accepts matching nonempty ASCII strings using `secrets.compare_digest()`. Our
generator supplies an ASCII expected value; your type, empty-value, and ASCII
checks safely reject missing or malformed returned state before comparison.
This helper ties the callback to the login attempt we started; the future listener
must also enforce attempt expiry and one-time use.

```powershell
python -m unittest tests.test_oauth -v
```

Four sign-in preparation tests and five callback-state tests pass. The full
suite has forty-one passing tests with none skipped. Host-ID persistence, the
callback listener, token exchange, and identity validation are still pending.

## Local state and secrets

| Value | First-version storage |
| --- | --- |
| OAuth state, nonce, and PKCE verifier | Memory for one login attempt; discarded afterward |
| Access, refresh, and ID tokens | Memory for the running session; fresh sign-in after restart |
| Host ID and issued client registration metadata | Planned local JSON under the ignored `.agent_guard/` directory; no tokens |
| Optional local configuration | `.env` may be used later; no `.env` file is currently required or generated |

`.gitignore` excludes `.env`, `.env.*`, and `.agent_guard/`. A deliberately
non-secret `.env.example` template can still be tracked. Ignore rules only affect
untracked files; they do not remove anything already committed.

A `.env` file is ordinary plaintext and does not encrypt its contents. If we
later add remembered sign-in, use protected credential storage such as the
operating system's credential store. Do not store OAuth tokens in `.env`, the
repository, the audit log, or callback request logs. The future callback handler
must suppress the default HTTP request logging because callback URLs contain
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
