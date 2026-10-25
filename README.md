# Agent guard: first exercise

A simulation of an agent proposing file operations and a guard checking them.
There is no AI model or real file access in this exercise. Python's standard
library is sufficient; no packages need installing.

## Run

```powershell
python simulate.py
```

The original simulation produced the decisions below after the permission rule
and input validation were implemented. The current simulation also displays a
reason; see the completed decision-reasons exercise below.

```text
Simulated requests only; no files will be accessed.

ALLOW: {'action': 'read', 'path': 'notes.txt'}
DENY: {'action': 'write', 'path': 'notes.txt'}
DENY: {'action': 'read', 'path': 'secrets.txt'}
DENY: {'action': 'delete', 'path': 'notes.txt'}
DENY: {}
DENY: {'action': 'read'}
DENY: {'path': 'notes.txt'}
DENY: {'action': 123, 'path': 'notes.txt'}
DENY: {'action': 'read', 'path': None}
DENY: None
DENY: []
```

## First exercise (completed): permissions

The initial exercise was to initialize Git and implement a permission check:

- Return `True` only for reading `notes.txt`.
- Return `False` for every other action/path pair, including unknown actions.
- Treat paths as exact strings for this exercise.

`request["action"]` and `request["path"]` give you the two values to check.
Run the simulation again and compare its decisions with the output above.
You can also add requests to the list in `simulate.py` to explore your rule.

## Second exercise (completed): input validation

The validation helper in `guard.py` has this signature:

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

The simulator reports `KeyError` and `TypeError` as `ERROR` so it can show all
samples even before validation is complete. These errors should disappear once
your guard handles malformed requests; the guard itself should return `False`.

Safely resolving real filesystem paths is a later feature.

## Automated tests

Run the tests with Python's built-in unittest module; no installation is needed:

```powershell
python -m unittest -v
```

`test_guard.py` contains five permission tests, three validation tests, and six
decision-reason tests. All fourteen should run and pass, with none skipped.
`test_executor.py` adds four execution tests. All eighteen tests should now pass,
with none skipped. A skipped test means
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

`learning_log.txt` records dated progress and learning points for future reference
or LinkedIn posts. Add a new entry as you complete each exercise.

## Third exercise (completed): decision reasons

`check_request()` in `guard.py` returns a tuple containing a boolean decision and
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

`executor.py` adds a simulated reader and your execution function:

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
python -m unittest test_executor -v
```

The four execution tests pass. The full suite has eighteen passing tests. The
fourteen guard tests can also be run with `python -m unittest test_guard -v`.

The new tests use `unittest.mock.patch` to temporarily replace the reader with
a mock that records calls. `assert_not_called()` checks denied requests never
reach it. `assert_called_once_with("notes.txt")` checks an allowed request reaches
it exactly once with the correct path. The success test also checks that the
executor returns the reader's actual result.

The original `simulate.py` still demonstrates permission decisions only. The
reader and executor are ordinary Python functions, not an operating-system
sandbox; the exercise demonstrates enforcing a guard at an execution entry point.
