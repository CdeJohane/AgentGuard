# Agent guard: first exercise

A simulation of an agent proposing file operations and a guard checking them.
There is no AI model or real file access in this exercise. Python's standard
library is sufficient; no packages need installing.

## Run

```powershell
python simulate.py
```

The starter guard denies all requests. After implementing the rule, the output
should be:

```text
Simulated requests only; no files will be accessed.

ALLOW: read notes.txt
DENY: write notes.txt
DENY: read secrets.txt
DENY: delete notes.txt
```

## Your part

Initialize your Git repository when ready, then edit `is_allowed()` in `guard.py`.
Replace its placeholder return value with your permission check:

- Return `True` only for reading `notes.txt`.
- Return `False` for every other action/path pair, including unknown actions.
- Treat paths as exact strings for this exercise.

`request["action"]` and `request["path"]` give you the two values to check.
Run the simulation again and compare its decisions with the output above.
You can also add requests to the list in `simulate.py` to explore your rule.

For now, requests are assumed to contain both keys with string values. Handling
malformed requests and safely resolving real filesystem paths are later features.
