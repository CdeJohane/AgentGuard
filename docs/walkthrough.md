# Learning walkthrough

Completed pair-programming exercises for the first working prototype. Code paths and commands below are relative to the repository root.

Start with the [project README](../README.md) for setup and the demo. Personal progress is recorded in the [learning log](learning_log.txt).

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
