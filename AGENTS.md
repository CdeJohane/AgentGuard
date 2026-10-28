# Agent guard: working agreements

## Project and learning approach

This is a Python learning project for checking an AI agent's proposed actions.
The learner knows Python and is new to agents. The project has an offline demo
and an optional real model connection; all agent file operations are simulated.

The product direction is AgentGuard, a security companion for Codex in VS Code.
See `docs/product_vision.md` for intended workflow, scope, and release criteria.
The direct model demo does not intercept an existing Codex conversation. Record
integration coverage and enforcement evidence before claiming protection.

- Work in small steps. Discuss each feature's expected behaviour before implementing it.
- Explain unfamiliar agent concepts in plain language.
- Agree meaningful pieces for the learner to write; preserve that ownership.
- When reviewing an exercise, explain what works and any necessary corrections.
- Label unfinished stubs and intentionally failing tests clearly.
- Keep the finish plan flexible; discuss scope changes instead of adding features silently.

## Layout and commands

- Application code: `agent_guard/`; tests: `tests/`; learning notes and plans: `docs/`.
- Run commands from the repository root.
- Offline demo: `python -m agent_guard.simulate`.
- Full test suite: `python -m unittest -v`.
- Optional authentication dependencies: `requirements-auth.txt`. Use
  `.\venv\Scripts\python.exe -m unittest -v` to include signed-token verification tests.
  Without those dependencies, report the explicitly skipped tests.
- Focused tests: `python -m unittest tests.test_guard -v` (or another test module).
- The learner has activated their virtual environment; use `python` in commands
  shared with them. Tool terminals may need the project interpreter explicitly.
- Follow the existing package imports and standard-library unittest conventions.

## Permission and execution behaviour

- Default deny: only explicitly permitted actions may run.
- Treat model-generated requests as untrusted input; Python code makes permission decisions.
- Send proposed actions through `execute_request()`; denied requests must never reach the reader.
- Keep file operations simulated unless a different scope is explicitly agreed.
- Audit each execution attempt once before running the reader. Record permission reasons, not contents.
- Keep credentials out of tracked files, output, and audit records.

## Session checkpoints

- At each coherent passing checkpoint, remind the learner to commit and push
  with a suggested message before moving to the next feature. The learner normally
  handles Git actions unless they explicitly ask otherwise.
- Check the current files and user changes before editing.
- Run checks appropriate to the change; report intentional exercise failures separately.
- Update relevant documentation and the dated learning log for completed work.
- Distinguish implemented features from proposals. Use `docs/finish_plan.md` for the flexible schedule.
- Preserve the offline demo and offline tests when adding an optional model connection.
