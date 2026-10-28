# Interception proof: investigation and offline responder

Status: 28 October 2026, evening session. Live interception is not verified.
A disposable project and inactive hook definition are prepared. The definition
has not been activated or trusted, and no execution permissions have changed.

## Installed components observed

| Component | Observed version or state |
| --- | --- |
| VS Code CLI version output | 1.143.1, x64 |
| Installed Codex extension | openai.chatgpt 26.1021.22027, win32-x64 |
| Extension-bundled Codex CLI | 0.164.0-alpha.11.1 |
| Bundled CLI feature listing | hooks stable/enabled; unified_exec stable/enabled |
| Separate desktop Codex CLI on PATH | 0.161.0; not assumed to be the extension runtime |

Versions were read from installed files and executable metadata commands.
The CLI commands completed with warnings about shared temporary bookkeeping
directories being inaccessible in the tool environment. No trust or sandbox
configuration was altered. A custom CLI override, WSL/remote workspace, or cloud
task could use a different runtime. The learner believes their workflow is local.
Target a fresh local Codex chat in VS Code as the working assumption, then verify
it during the proof; installed capabilities alone do not establish coverage.

## What the first proof should demonstrate

In a selected disposable project, ask Codex to perform one harmless shell action
that would create a dummy marker. A trusted, synchronous PreToolUse responder
must deny that call before the marker is created. Collect evidence of both the
hook invocation and the absent side effect. A chat statement alone is insufficient.

This first responder deliberately denies all shell calls at the selected
workspace root. It is not a general command analyser or a production policy.
It does not cover subdirectories, apply_patch, other tools, or other workspaces.
It never executes a proposed action or calls the existing file-operation reader.
The core executor and simulated file demo remain separate and unchanged.

## Official protocol checked

[Codex hooks documentation](https://learn.chatgpt.com/docs/hooks), checked on
28 October 2026, documents:

- One JSON event delivered to the hook process on standard input.
- Local shell/unified-exec calls matched as Bash for PreToolUse.
- Denial through hookSpecificOutput with hookEventName PreToolUse,
  permissionDecision deny, and permissionDecisionReason.
- Exit code 2 with a reason on standard error as another supported block signal.
- Explicit trust review for non-managed hooks and project configuration.

Errors, timeouts, unsupported output, and uncovered tool paths can permit calls
to continue. In particular, PreToolUse's ask decision is not currently supported.
The responder's error exit is only a requested denial until the runtime honours
it in a live test. No protection claim follows from these offline checks.

## Completed learner exercise and responder

The assistant added agent_guard/hook_probe.py, which reads bounded JSON input,
checks the selected workspace/event/tool, and emits only the expected protocol.
It returns an empty object for out-of-scope events, leaving their existing policy
unchanged. Invalid input or invalid responder output requests a block via exit 2
with a fixed message. Raw events, commands, and exception text are not printed.

The learner completed make_block_decision() correctly. It returns a nested
dictionary whose outer key is hookSpecificOutput. Its inner keys are:

| Key | Value |
| --- | --- |
| hookEventName | PreToolUse |
| permissionDecision | deny |
| permissionDecisionReason | The provided BLOCK_REASON constant |

The function does not execute a command, add an allow branch, or parse shell text.
The wrapper handles input and output. With the optional --receipt argument, it
appends minimal evidence to workspace/hook-receipts.jsonl: event/tool, requested
deny decision, a command digest, and whether blocked-marker.txt was mentioned.
The proposed command is not executed or logged in plaintext. A receipt records
the responder's decision, not proof that Codex honoured it.

```powershell
python -m unittest tests.test_hook_probe -v
```

All ten responder/receipt checks pass. The full project suite has 144 passing
tests, with none skipped in the project environment. These checks use fake
events, not live Codex calls. The learner's dictionary was preserved.

## Prepared disposable fixture

Fixture: `.agent_guard/probe-workspaces/interception-0d2822d9/` (ignored by Git).
It is a separately initialized local Git project, with no remote configured.
It contains a frozen copy of the responder, probe-plan.json, constrained experiment
instructions, and `.codex/hooks.pending.json`. That pending filename is not the
active hooks.json filename. No global or main-project hook config was changed.

The prepared definition targets Bash synchronously, invokes the frozen responder
with an absolute interpreter/workspace/receipt path, and uses a five-second
timeout. The frozen responder passed a direct fake-event preflight without
writing a receipt. Both baseline-marker.txt and blocked-marker.txt were absent
after preparation. Live control and blocked runs are still pending.

First, use a fresh LOCAL Codex chat in that VS Code workspace to run exactly:

```powershell
Set-Content -LiteralPath 'baseline-marker.txt' -Value 'AGENTGUARD_BASELINE_20261028'
```

This control is expected to succeed while the hook is inactive. Verify the actual
file afterwards. A failed control would make a later missing marker inconclusive.
Real writes here are limited to disposable proof resources; the application's
simulated file operations are unchanged.

After reviewing the control, review the pending hook definition, activate its
project-local filename, and trust the exact definition using Codex's supported
interface. Then test the blocked-marker.txt command in probe-plan.json and
inspect the tool attempt, matching receipt, and absent marker independently.
That activation, trust step, blocked action, and failure-case tests have not run.
