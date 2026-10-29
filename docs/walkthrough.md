# Learning walkthrough

Completed pair-programming exercises for the first working prototype. Code paths and commands below are relative to the repository root.

Start with the [project README](../README.md) for setup and the demo. Personal progress is recorded in the [learning log](learning_log.txt).

These exercises record the evolving implementation. The executor's former tuple
result in earlier exercises was replaced by the dictionary in the
[completed twelfth exercise](#twelfth-exercise-completed-structured-execution-results).
The optional project-policy execution mode is the completed thirteenth exercise;
default execution and the existing demonstrations retain their original policy.

## First exercise (completed): permissions

The initial exercise was to initialize Git and implement a permission check:

- Return `True` only for reading `notes.txt`.
- Return `False` for every other action/path pair, including unknown actions.
- Treat paths as exact strings for this exercise.

`request["action"]` and `request["path"]` give you the two values to check.
Run the simulation again and compare its decisions with the output above.
You can also add requests to the list in `simulate.py` to explore your rule.

## Second exercise (completed): input validation

The validation helper in `agent_guard/guard.py` has this signature:

```python
def is_valid_request(request: object) -> bool:
```

It should return `True` only when the request is a dictionary containing both
`action` and `path`, with string values for both. Additional keys are allowed.
It checks structure; a well-formed request to write a file is still valid input,
even though the permission rule denies it.

`check_request()` calls this helper before checking permissions. Invalid requests
are denied. Its request annotation is `object`, since it deliberately accepts
arbitrary input for checking. `is_allowed()` now delegates to `check_request()`.

The guard denies malformed requests before dictionary lookups, so these requests
do not raise missing-key or invalid-container errors in the demo.

Safely resolving real filesystem paths is a later feature.

## Automated tests

Run the tests with Python's built-in unittest module; no installation is needed:

```powershell
python -m unittest -v
```

`tests/test_guard.py` contains five permission tests, three validation tests, and six
decision-reason tests. All fourteen should run and pass, with none skipped.
`tests/test_executor.py` adds four execution tests. These eighteen tests still pass.
`tests/test_audit.py` adds six audit tests. These twenty-four tests pass, with none
skipped. `tests/test_simulate.py` adds two passing integration tests. All twenty-six
tests pass. A skipped test means
the check has not run; it does not mean the behaviour has passed a test.

The `ValidationTests` class contains your completed checks. `assertTrue` checks
that a result is true; `assertFalse` checks that it is false. Each test arranges
a request, calls a function, and checks its result.

The permission tests use `assertIs` to require actual booleans. The reason tests
use `assertEqual` to check the full decision tuple, including its message.

Check that a valid read request passes validation, a well-formed write request
also passes validation, and a request missing its path fails validation. Remember
that validation checks structure, while permissions decide what is allowed.

The malformed-input permission test uses `subTest` to report which input failed
while still checking the other inputs. An unexpected exception fails a test too.

## Learning log

`docs/learning_log.txt` records dated progress and learning points for future reference
or LinkedIn posts. Add a new entry as you complete each exercise.

## Third exercise (completed): decision reasons

`check_request()` in `agent_guard/guard.py` returns a tuple containing a boolean decision and
a string reason. It checks these outcomes in order:

| Condition | Allowed | Reason |
| --- | --- | --- |
| Invalid request structure | `False` | `Malformed request.` |
| Action is not `read` | `False` | `Action is not permitted.` |
| Path is not `notes.txt` | `False` | `File is not permitted.` |
| Otherwise | `True` | `Reading notes.txt is permitted.` |

Reuse `is_valid_request()` to check structure before accessing dictionary keys.
The first matching condition determines the reason, so a request with both a
forbidden action and a forbidden path gets the action reason.

The updated simulation unpacks the tuple into `allowed` and `reason`. Do not
check the whole tuple in an `if`: even `(False, "Denied")` is truthy.

`is_allowed()` unpacks the result of `check_request()` and returns only the
boolean, so the permission rules live in one place. Tests cover the four outcomes
and the priority of structure checks over actions and action checks over paths.

## Fourth exercise (completed): guarded simulated execution

`agent_guard/executor.py` adds a simulated reader and your execution function:

```python
def execute_request(request: object) -> tuple[bool, str]:
```

`execute_request()` calls `check_request()` and unpacks its decision and reason.
Only allowed requests call `simulated_read()` with the requested path. The
function returns `(True, contents)` on success or `(False, reason)` on denial.
Request keys are accessed only after the guard has accepted the request.

Examples:

```text
read notes.txt    -> (True, "Simulated contents of notes.txt")
write notes.txt   -> (False, "Action is not permitted.")
read secrets.txt  -> (False, "File is not permitted.")
None              -> (False, "Malformed request.")
```

Run just the execution tests:

```powershell
python -m unittest tests.test_executor -v
```

The four execution tests and fourteen guard tests pass. The guard tests can also
be run with `python -m unittest tests.test_guard -v`. The completed audit exercise
adds six passing tests.

The new tests use `unittest.mock.patch` to temporarily replace the reader with
a mock that records calls. `assert_not_called()` checks denied requests never
reach it. `assert_called_once_with("notes.txt")` checks an allowed request reaches
it exactly once with the correct path. The success test also checks that the
executor returns the reader's actual result.

Mocks use the full target `agent_guard.executor.simulated_read`, matching where
the executor looks up the reader in the new package layout.

`agent_guard/simulate.py` connects the requests to execution and auditing.
The reader and executor are ordinary Python functions, not an operating-system
sandbox; the exercise demonstrates enforcing a guard at an execution entry point.

## Fifth exercise (completed): an in-memory audit trail

Your `record_decision()` implementation is in `agent_guard/audit.py`:

```python
def record_decision(request: object, allowed: bool, reason: str) -> None:
```

The function appends a fresh dictionary to the shared `audit_log` list with
exactly four keys: `action`, `path`, `allowed`, and `reason`. Action and path keep
string values from dictionary requests; missing or non-string values become
`None`. For non-dictionary requests, both fields are `None`. Each valid field is
preserved independently, even if the other is invalid. The supplied `allowed`
and `reason` arguments are recorded without recalculating the permission decision.

Do not append the original request or copy extra keys. The record must remain
unchanged if the caller later changes the request. No file contents belong in
the audit trail.

The executor now calls your helper once, immediately after checking permission
and before the reader runs. Its `reason` argument is the guard's reason, including
for allowed requests; it is never replaced with the reader's contents in the log.
The record describes permission, not successful execution. Records are only in
memory and reset when this Python process exits.

Run the six new tests:

```powershell
python -m unittest tests.test_audit -v
```

All six audit tests pass. They check allowed and denied attempts, malformed
inputs, exactly one record per attempt, order, snapshots, and logging before
execution. Tests clear the shared list in `setUp()` and `tearDown()` to prevent
records from one test affecting another.

Calls through `execute_request()` add audit records. The completed demo
uses that entry point to connect the components together.

## Sixth exercise (completed): an end-to-end demo

Your loop in `agent_guard/simulate.py` calls `execute_request(request)`, unpacks
its two results, and passes the request, decision, and message to `display_result()`.
The executor already checks permission and records the decision, so the loop
does not call the guard or audit helper separately.

The formatting helpers and final audit display are provided. The demo uses four
representative requests; the unit tests still cover the wider set of malformed
inputs. It clears the in-memory log at the beginning so repeated runs demonstrate
only the requests from that run.

```powershell
python -m unittest tests.test_simulate -v
```

These integration tests exercise the complete flow, checking exactly one reader
call, the contents or reason shown for each request, four audit records without
file contents, and a fresh log when the demo is run again.

## Seventh exercise (completed): operation failure

Behaviour agreed on 28 October 2026: permission and execution are separate.
A permitted operation can fail. Keep its one audit record as `allowed=True`
with the guard's permission reason, then report the execution failure separately.

The assistant added `OperationError` in `agent_guard/executor.py`, with a fixed
message: `The permitted read failed.` The demos catch it and display `FAILED`,
not a denial or success. The live command displays the audit trail and exits
with status 1. The offline demo continues to its other requests without retrying
the failed read. Existing successful and denied `(bool, str)` returns remain.

You completed the permitted branch of `execute_request()`:

1. Put only the reader call inside a `try` block.
2. Caught `OSError`, which also covers common read errors such as
   `FileNotFoundError` and `PermissionError`.
3. Raised `OperationError()` while suppressing the original exception context.
   Python's `from None` syntax prevents a displayed traceback from including
   the original error message.

Keep permission checking and auditing before the reader. Do not add another
audit entry or change the permission decision. Catching only the expected read
error also leaves programming errors visible to the existing outer error handling.

```powershell
python -m unittest tests.test_executor -v
```

Your handler passed review. The expanded full suite has 134 passing tests
with none skipped in the project environment.
Tests fake read failures; no real file access or live model calls are needed.
Other new tests check the demo handlers using an already-translated
`OperationError`. Tests also verify that programming errors are not disguised
as read failures and that an audit error prevents the reader from running.

The normal simulated reader always returns pretend contents; running the usual
demo alone will not trigger this error. The full suite has passed and the notes
are updated; this completed feature is ready for the learner's commit/push.

## Eighth exercise (completed): combine policy decisions

Completed on 29 October 2026, following the learner's proposed global,
language/toolchain, and project policy layers. This exercise combines decisions
already made by applicable layers; it does not implement their rules, select
which layers apply, show approval prompts, or connect to Codex or the executor.

The assistant supplied input validation in `agent_guard/policy.py` and five
tests in `tests/test_policy.py`. The learner implemented the combination logic
in `combine_decisions()`: checking for deny first, then review or an empty list,
and returning allow otherwise. Review confirmed the condition order and the
explicit `decisions == []` check; no logic corrections were necessary.

| Input | Result |
| --- | --- |
| `["allow", "allow", "allow"]` | `"allow"` |
| `["deny", "allow", "review"]` | `"deny"` |
| `["allow", "review", "allow"]` | `"review"` |
| `[]` | `"review"` |
| Malformed input or an unknown decision | `"deny"` (already supplied) |

Check for any denial before checking for review, regardless of layer order.
No decisions requires review; otherwise, only all-allow input can return allow.
Only `allow` would permit execution. `review` means keep the action blocked
pending a human decision; this function does not collect that decision.
These strings are separate from the existing guard's `(bool, reason)` result.
Do not wire them into execution by relying on string truthiness: even `"deny"`
is a truthy Python string.

```powershell
python -m unittest tests.test_policy -v
```

All five focused tests pass. The tests check denial priority across all orders
of allow/review/deny, review priority, all-allow input, empty input, and malformed
values. The full suite passes all 154 tests with none skipped in the project
environment. The initial scaffold's deliberate exercise errors are resolved.
The helper remains separate from request evaluation and execution; there is no
new approval UI or VS Code enforcement integration. This is a passing checkpoint
for the learner to commit and push.

## Ninth exercise (completed): explain policy decisions

Completed on 29 October 2026 after the learner committed the combination helper
as `159962f` and reported pushing it. The next helper, `explain_decisions()` in
`agent_guard/policy.py`, accepts a list of records rather than bare strings:

```python
[
    {"layer": "global", "decision": "allow", "reason": "Within global limits"},
    {"layer": "language", "decision": "review", "reason": "Package approval required"},
]
```

It returns `(decision, explanation)`, for example:
`("review", "language: Package approval required")`.
Layer labels and reasons must be nonblank strings; decision must be exactly
allow, deny, or review. This helper accepts supplied layer labels; it does not
verify that every required policy layer is present or evaluate real rules.

The assistant supplied validation, empty-input handling, a call to the learner's
existing combining function, and six tests. Malformed input returns a fixed
denial without echoing its values; empty input returns a fixed review reason.
Reasons must be policy-authored explanations, not commands, credentials, or
file contents. Valid strings are not automatically sanitized for secrets.

The learner implemented the explanation block:

1. Start an empty string, `my_str`.
2. Iterate over the supplied records without modifying them.
3. Keep records whose decision equals the final `decision` already calculated.
4. Format each as `layer: reason`, keeping input order.
5. Add `"; "` before each subsequent matching reason and return the pair.

This direct string-building approach meets the behaviour. The initially
suggested list plus `join()` was an alternative, not a requirement; review
preserved the learner's implementation without logic changes.

If two layers deny, include both denial reasons; omit lower-priority allow or
review reasons. If the final decision is allow, include all allowing reasons.
This is a plain text summary, not an approval prompt, audit record, or executor
integration. Review continues to mean no permission to execute yet.

```powershell
python -m unittest tests.test_policy -v
```

All 11 policy tests pass, including the six new explanation tests. The full
suite passes all 160 tests with none skipped in the project environment. The
initial scaffold's four deliberate errors are resolved. No integration with
actual layer rules, approvals, auditing, or execution has been added. This is
a passing checkpoint for the learner to commit and push.

## Tenth exercise (completed): evaluate a project request

Completed on 29 October 2026 after clean commit `520018f`, containing the
completed explanation helper. The agreed next step is a fixed project policy
for simulated file requests, followed by an offline policy-flow demonstration.
The global and language/toolchain rules are not implemented by this exercise.

`evaluate_project_request()` in `agent_guard/project_policy.py` returns a new
dictionary with exactly `layer`, `decision`, and `reason`. The layer is always
`project`; policy-authored reasons are fixed strings, never request contents.

| Request | Decision | Reason |
| --- | --- | --- |
| Malformed structure/types or blank action/path | deny | Malformed request. |
| Any action other than exactly `read` | deny | Action is not permitted. |
| Exactly `read` with exactly `notes.txt` | allow | Reading notes.txt is permitted. |
| Another nonempty read label | review | File requires review. |

The assistant supplied structure/type validation using the learner's existing
`is_valid_request()`, rejection of blank strings, a fresh result dictionary,
and six tests. Validation comes first; malformed requests must not reach the
rule branches. Extra request fields cannot supply the layer, decision, or reason.

The learner implemented the rule branches, setting `result["decision"]` and
`result["reason"]`, then returning `result`. Review confirmed the action check
comes before the path, so writing notes is denied despite its matching filename.
The second action comparison is redundant but correct; the assistant preserved
the learner's logic, fixing spacing and removing exercise labels only.
The request is not modified and its values are not copied into reasons.

Paths are literal simulated labels, not resolved filesystem paths. For example,
`./notes.txt` requires review rather than being normalized into an allowed read.
`secrets.txt` also requires review in this isolated layer; no global secret-file
rule is implemented here. Review never authorizes execution. The existing guard,
executor, audit, and demos retain their current behaviour.

```powershell
python -m unittest tests.test_project_policy -v
```

All six project-policy tests pass. They cover allow/review/deny, action priority,
exact path labels, malformed and blank inputs, untrusted permission claims, and
unchanged request data. The full suite passes all 166 tests with none skipped in
the project environment. The initial scaffold's exercise errors are resolved.
Commit/push this passing checkpoint before adding the planned demonstration.

## Eleventh exercise (completed): demonstrate the offline policy flow

Completed on 29 October 2026 after clean commit `9b7d19e`, containing the
project-rule evaluator. `agent_guard/policy_demo.py` demonstrates evaluation
and explanations for reading notes.txt, reading draft.txt, writing notes.txt,
and malformed input. Its expected decisions are allow, review, deny, deny.

The assistant supplied four labeled sample cases, display formatting, imports,
and two integration tests. The learner implemented the loop body:

1. Call `evaluate_project_request(request)` to obtain a layer record.
2. Put that record in a one-element list for `explain_decisions()`.
3. Store the returned pair and access the decision and explanation by index.
4. Pass the label, decision, and explanation to `display_decision()`.

The first attempt passed the layer dictionary directly to `explain_decisions()`.
Its list validation correctly returned a malformed-policy denial for every
case. The assistant identified the input-shape mismatch, and the learner fixed
the call to pass `[result]`, a list containing the project-layer dictionary.
Indexing the returned pair is valid; unpacking it was an optional alternative.

The list represents the one implemented project layer. Global and language
policies have not been evaluated; do not invent allow decisions for them.
The display uses ALLOW/REVIEW/DENY rather than execution statuses. This demo
does not execute requests, access file contents, ask for approval, or change
the existing audit. Even an ALLOW is only a policy decision here. The original
guarded-execution demo remains `python -m agent_guard.simulate`.

Run the focused tests and demonstration:

```powershell
python -m unittest tests.test_policy_demo -v
python -m agent_guard.policy_demo
```

The full suite passes all 168 tests with none skipped in the project environment.
The demonstration was run separately and printed ALLOW/REVIEW/DENY/DENY with
the expected project reasons. The tests cover real evaluator/explanation output
and ensure repeated demonstrations leave existing audit records intact without
calling the executor or reader. The initial scaffold's errors and the subsequent
list-shape bug are resolved. The assistant preserved the learner's working loop,
tidied spacing, removed exercise labels, and updated these notes. This completes
the agreed policy-flow demonstration and is ready for commit/push.

## Twelfth exercise (completed): structured execution results

Completed on 29 October 2026 after the learner committed the policy demonstration
as `7c04761` and reported pushing it. Before connecting the project policy to
execution, the learner agreed to separate the policy decision from execution
in the executor's returned result.

The result is a dictionary with exactly three keys:

| Field | Meaning |
| --- | --- |
| `decision` | `"allow"` or `"deny"` for the existing guard in this checkpoint |
| `executed` | `True` only after the simulated reader returns successfully |
| `message` | Returned simulated contents on execution, or the permission reason on denial |

The `dict[str, bool | str]` annotation describes string keys and values that
are either booleans or strings. The three-key result does not change what the
model can supply. The guard continues returning `(allowed, reason)` internally.
Only reading exactly notes.txt remains permitted. Project-policy review is a
separate future checkpoint, not an implemented executor decision yet.

The assistant updated callers in `simulate.py` and `live_demo.py`, the pipeline's
return annotation, and existing tests for the new result. Callers explicitly
inspect `executed`; they must not treat a nonempty result dictionary as an
approval. The learner implemented both returns in `agent_guard/executor.py`:

1. After the reader succeeds, return decision `allow`, executed `True`, and
   `msg` as the message.
2. For denied requests, return decision `deny`, executed `False`, and `msg`
   as the message.

Each dictionary uses the exact keys `decision`, `executed`, and `message`.
Review confirmed both returns and preserved their logic. The assistant tidied
dictionary spacing/indentation and removed exercise labels. Permission checking,
one audit record before the reader, and the narrow OSError-to-OperationError
handler are preserved. Reader failure still raises the safe exception rather
than returning success. The audit's allowed/reason fields are unchanged.

```powershell
python -m unittest tests.test_executor -v
```

All seven focused executor tests and the full 168-test suite pass with none
skipped in the project environment. The 19 initial scaffold errors are resolved.
Both offline demonstrations were run separately: the original retains its one
execution, three denials, and four audit records; the policy-only demo retains
ALLOW/REVIEW/DENY/DENY without execution. The optional model orchestration is
covered by fake-service tests; no new live model request was made.
Commit/push this checkpoint before the separate policy-to-execution integration.

## Thirteenth exercise (completed): execute with an explicit project policy

Completed on 29 October 2026 after clean commit `a345281`, containing the completed
structured results. The learner agreed to project-policy execution as the next
checkpoint. `execute_request(request, use_project_policy=True)` explicitly selects
the fixed project evaluator and explanation helper. Omitting the keyword retains
the original guard; request fields cannot select the mode.

The assistant supplied mode selection, reuse of the evaluator and explanation
helper, audit wiring, and nine tests. The learner implemented both edits in executor.py:

1. `_allows_execution()` uses a conditional expression to return True only for
   exactly `"allow"`, and False otherwise. Nonempty strings are truthy, so the
   explicit comparison is necessary rather than testing string truthiness.
2. Both result dictionaries preserve the calculated `decision`. Review and
   deny return executed False, but remain different decisions. The successful
   result also preserves the decision; that change is correct.

Review preserved the learner's implementation. The existing reader and safe
OSError handling remain. The
audit receives exactly one record before an allowed read. Review and deny both
record allowed False with their policy reason. The existing audit has no separate
decision field; the returned result retains the explicit review/deny distinction.
This exercise does not add a durable review queue or approval interface.

Only the project layer is evaluated in project mode. Reading notes.txt allows;
other valid read labels require review and do not execute. Paths are simulated
labels, with no real filesystem protection implied. Default model/demo callers
continue using their original policy.

```powershell
python -m unittest tests.test_project_execution -v
```

All nine focused tests and the full 177-test suite pass with none skipped in
the project environment. The eight initial exercise errors are resolved.
A direct four-case project-mode check returned allow/executed True, review/False,
deny/False, and deny/False, with four audit records. Default demo behaviour is
also covered by the passing suite. The assistant removed exercise labels and
updated the documentation without changing the learner's logic. This completes
the two agreed extra checkpoints and is ready for commit/push.
