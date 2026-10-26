# Agent guard

A Python learning project that checks an agent's proposed file operation before
letting it run, explains its decision, and records it in an audit trail.

The demo uses simulated requests and pretend file contents. You can explore the
permission flow without an AI account, API key, or real file access.

## Quick start

Clone or download this repository, then open a terminal in its root directory
(the folder containing this README).

Python is required. Development and verification used **Python 3.14.3**; other
versions have not been verified. The offline demo uses the Python standard library
and needs no dependencies or environment variables. Optional sign-in verification
uses PyJWT with its cryptography extra; see the authentication setup below.

Run the demo:

```powershell
python -m agent_guard.simulate
```

Run the tests:

```powershell
python -m unittest -v
```

Run both commands from the repository root. `-m` runs a module within its package,
so imports between the application modules resolve correctly.

## What the demo shows

The guard uses default deny: only reading `notes.txt` is permitted.
`notes.txt` and `secrets.txt` are example names; neither file needs to exist.

| Proposed request | Result |
| --- | --- |
| Read `notes.txt` | Execute the simulated reader and return its contents |
| Write `notes.txt` | Deny the action |
| Read `secrets.txt` | Deny the file |
| `None` | Deny the malformed request |

The demo prints:

```text
Simulated requests only; no files will be accessed.

EXECUTED: {'action': 'read', 'path': 'notes.txt'}
  Simulated contents of notes.txt
DENIED: {'action': 'write', 'path': 'notes.txt'}
  Action is not permitted.
DENIED: {'action': 'read', 'path': 'secrets.txt'}
  File is not permitted.
DENIED: None
  Malformed request.

Audit trail:
  {'action': 'read', 'path': 'notes.txt', 'allowed': True, 'reason': 'Reading notes.txt is permitted.'}
  {'action': 'write', 'path': 'notes.txt', 'allowed': False, 'reason': 'Action is not permitted.'}
  {'action': 'read', 'path': 'secrets.txt', 'allowed': False, 'reason': 'File is not permitted.'}
  {'action': None, 'path': None, 'allowed': False, 'reason': 'Malformed request.'}
```

## How it works

An agent proposes an action; the guard applies rules written in Python. This
prototype supplies example requests directly, so the permission and execution
behaviour can be examined independently of a model.

```mermaid
flowchart TD
    A[Proposed request] --> B[execute_request]
    B --> C[Validate structure and check permissions]
    C --> D[Record the permission decision]
    D --> E{Allowed?}
    E -->|No| F[Return the denial reason]
    E -->|Yes| G[Run the simulated reader]
    G --> H[Return simulated contents]
    F --> I[Display result and audit trail]
    H --> I
```

1. **Validate:** the request must be a dictionary containing string `action` and
   `path` values. A well-formed request can still be forbidden.
2. **Decide:** check structure first, action second, and path third. The first
   failed check determines the denial reason. Matching is exact and case sensitive.
3. **Record:** append one permission record before executing anything. Missing or
   non-string action/path fields become `None`; valid fields are kept independently.
   Extra request fields and file contents are omitted from records.
4. **Execute:** only permitted requests reach the reader. Denied requests return
   their reason without calling it.

`check_request()` returns `(allowed, reason)`. `execute_request()` returns
`(True, contents)` on success or `(False, reason)` on denial. `is_allowed()` is a
boolean-only wrapper around `check_request()`.

## Code map

| File or directory | Responsibility |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Working agreements for coding assistants and pair programming |
| [agent_guard/guard.py](agent_guard/guard.py) | Request validation, permission decisions, and reasons |
| [agent_guard/executor.py](agent_guard/executor.py) | Guarded entry point and simulated reader |
| [agent_guard/audit.py](agent_guard/audit.py) | In-memory permission records |
| [agent_guard/simulate.py](agent_guard/simulate.py) | Four-request demo and displayed output |
| [agent_guard/model_requests.py](agent_guard/model_requests.py) | Decode model proposals as JSON before guard checks |
| [agent_guard/oauth.py](agent_guard/oauth.py) | Sign-in URL preparation, PKCE, and callback-state checks |
| [agent_guard/oauth_callback.py](agent_guard/oauth_callback.py) | One-use loopback callback listener |
| [agent_guard/local_state.py](agent_guard/local_state.py) | Create, validate, and reuse the non-secret installation host ID |
| [agent_guard/auth_tokens.py](agent_guard/auth_tokens.py) | Optional token exchange and signed identity verification |
| [agent_guard/sign_in.py](agent_guard/sign_in.py) | Browser sign-in controller and account-verification command |
| [tests/](tests/) | Unit tests and integration tests |
| [docs/](docs/) | Learning walkthrough, personal log, and flexible finish plan |

Start with the loop in `simulate.py`, follow its call to `execute_request()`, then
read the guard and audit helpers. Inside the package, `.guard` in an import means
"the sibling guard module"; tests use full names such as `agent_guard.guard`.

## Tests

The tests cover allowed and forbidden requests,
malformed input, denial-reason priority, and the boolean wrapper. Mock readers
verify that permitted requests execute once and denied requests never execute.
Audit tests check record fields, snapshots, order, and logging before execution.
Integration tests exercise the demo and verify a fresh log on repeated runs.

Six model-response tests verify JSON decoding and denial of malformed or
forbidden proposals through the guarded executor. All tests are offline; they
do not call a model or authenticate an account. See the
[model connection notes](docs/model_connection.md).

OAuth tests cover sign-in URL preparation, fresh temporary values, PKCE,
and callback-state validation. Callback-listener tests send fake responses
over local loopback HTTP, checking validation, cancellation, one-time use,
deadlines, and suppressed request logs. No tests launch a browser or call OpenAI.

In the authentication virtual environment, **all 88 tests pass**, with none
skipped. Eight signed-token tests are skipped if the optional
authentication dependency is absent. The signed-token tests use locally generated
keys and fake responses; they do not contact OpenAI. Host-ID tests verify creation,
reuse, and rejection of invalid saved data without overwriting it. Filesystem fixtures
live temporarily under the ignored
`.agent_guard/test-tmp/` directory and are removed after each test.

Run an individual area when working on it:

```powershell
python -m unittest tests.test_guard -v
python -m unittest tests.test_executor -v
python -m unittest tests.test_audit -v
python -m unittest tests.test_simulate -v
python -m unittest tests.test_model_requests -v
python -m unittest tests.test_oauth -v
python -m unittest tests.test_oauth_callback -v
python -m unittest tests.test_local_state -v
```

## Optional authentication setup and sign-in check

On Windows/PowerShell, use a virtual environment for the optional authentication dependency. If you do
not already have one, create it with `python -m venv venv`, then run:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-auth.txt
.\venv\Scripts\python.exe -m unittest -v
```

`has_plan_scope()` in `agent_guard/oauth.py` rejects non-string input, splits the
scope string into individual names, and checks for the complete name
`chatgpt.tokens.use.direct`. A substring is not enough.

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_oauth.PlanScopeTests -v
```

To try a live sign-in, run this command and complete Continue with ChatGPT in
your browser:

```powershell
.\venv\Scripts\python.exe -m agent_guard.sign_in
```

The check reports verified identity and whether the required plan permission was
granted. It makes no model request and does not verify remaining allowance or
inference eligibility. It exits after the check, discarding in-memory tokens;
later processes sign in again using the saved client registration.

Exit status 0 means identity and permission were verified; 2 means identity was
verified without the plan permission; 1 means failure; 130 means cancellation
with Ctrl+C. Only non-token registration metadata is saved. A manual sign-in
check succeeded on 26 October 2026, as reported by the learner: identity and
plan-usage permission were verified. No model request has been verified yet;
automated tests continue to use fake responses.

## Current scope

This is an educational prototype with one hard-coded permission rule and no
completed AI model connection. Agent-requested file operations remain simulated;
installation and registration metadata use local filesystem storage. Requested
paths are compared as strings; real path resolution and filesystem isolation
are outside this version.

Checks apply to requests sent through `execute_request()`. These are ordinary
Python functions, not an operating-system sandbox; code in the same process can
call the reader directly or modify the shared audit list.

Audit records describe **permission**, not completion. Reader exceptions currently
propagate to the caller. Records live only in memory, are lost when the process
ends, and are cleared when the demo starts.

Local `.env` files and `.agent_guard/` state are ignored by Git. The sign-in
controller keeps temporary values and tokens in memory; only the host ID, issued
client ID, and verified subject are persisted as registration metadata. A pending
client ID can be retained before exchange with a null subject; it is not a login.
Tokens are not persisted. A `.env` file is plaintext, not encrypted storage.
See the [storage plan](docs/model_connection.md#local-state-and-secrets).

## Learning and next steps

This project was built through pair programming, with implementation exercises
and tests added in small steps. The completed exercises are preserved in the
[learning walkthrough](docs/walkthrough.md). The dated
[learning log](docs/learning_log.txt) records progress, challenges, and where help
was used.

The [flexible finish plan](docs/finish_plan.md) records proposed next steps.
The next milestone is an optional real model connection that proposes requests
for the existing guard, while file operations remain simulated. The selected
route is supported Sign in with ChatGPT plan usage. Authentication code is now
present, the scope exercise is complete, and the manual sign-in check succeeded;
the first model request and inference-access check are next.
The current demo remains offline. Details and
the first parsing exercise are in the [connection notes](docs/model_connection.md).
Configurable permissions are deferred. Each feature's expected behaviour will
be discussed before implementation.
