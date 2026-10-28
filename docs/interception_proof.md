# Interception proof: investigation and offline responder

Status: 28 October 2026, evening session. One live shell-call interception is
verified in the disposable local VS Code/Codex project. The control write
succeeded. After the learner trusted the project hook, the planned marker command
was denied before execution. A separate intentional-crash experiment then
verified fail-open behaviour: its hook ran but the marker command still executed.
No sandbox permissions were changed. The hook-only design does not meet the
intended fail-closed requirement.

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
The learner used a local Codex chat in the disposable VS Code workspace for the
control and blocked runs. The versions above describe the installed components;
they are not a separate process-level identification of the live chat's binary.
The observed result, rather than installed capabilities alone, establishes the
limited coverage described below.

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
instructions, and a project hook definition. Initially staged as
`.codex/hooks.pending.json`, it is now `.codex/hooks.json` after the successful
control. No global or main-project hook config was changed.

The prepared definition targets Bash synchronously, invokes the frozen responder
with an absolute interpreter/workspace/receipt path, and uses a five-second
timeout. The frozen responder passed a direct fake-event preflight without
writing a receipt. Both baseline-marker.txt and blocked-marker.txt were absent
after preparation. Both the control and blocked runs are now verified.

First, use a fresh LOCAL Codex chat in that VS Code workspace to run exactly:

```powershell
Set-Content -LiteralPath 'baseline-marker.txt' -Value 'AGENTGUARD_BASELINE_20261028'
```

The learner reported exit code 0 with no output. Independent inspection confirmed
baseline-marker.txt contained AGENTGUARD_BASELINE_20261028. At that check the hook
was inactive, blocked-marker.txt was absent, and no receipt existed. This verifies
the positive control. A failed control would make a later missing marker inconclusive.
Real writes here are limited to disposable proof resources; the application's
simulated file operations are unchanged.

After reviewing the control and checking the frozen responder's source digest,
the assistant renamed only this fixture's pending definition to hooks.json.
control-verification.json records the observed state. The learner's commit
c14631c contains the passing responder checkpoint.

The learner reloaded the disposable window, found the hook, and reported clicking
Trust. The following blocked test then demonstrated the trusted responder running.

## Verified blocked run

The requested PowerShell command was:

```powershell
Set-Content -LiteralPath 'blocked-marker.txt' -Value 'AGENTGUARD_BLOCKED_20261028'
```

The learner reported the Codex tool result:

```text
Command blocked by PreToolUse hook: AgentGuard probe: shell execution is blocked in this disposable project.
```

Codex reported stopping without retrying or using another tool. Independent
filesystem checks confirmed:

| Evidence | Observed result |
| --- | --- |
| Successful control marker | Still present |
| blocked-marker.txt | Absent |
| Hook receipts | Exactly one |
| Receipt event/tool/decision | PreToolUse / Bash / deny |
| Receipt command digest | Matches the exact planned command |
| Frozen responder digest | Matches the prepared source |

The command digest is
`1e1e5d417de364bd440fa4e02acbaae72b34b3cffd7562c17eb2cec1f76d7d99`.
The ignored fixture's interception-verification.json retains the measured state.
The hook remains configured only in this disposable project.

This demonstrates pre-execution denial of this shell call at this workspace
root. It does not establish coverage of all Codex tools, subdirectories, sandbox
escapes, guard modification, or failure behaviour. The probe denies all scoped
shell calls; it does not yet apply a user-configurable product policy.
Live timeout and missing-responder tests remain to be done. The intentional
crash case below is now verified.

## Intentional crash experiment: verified fail-open

The learner agreed to test what happens when a hook crashes. This experiment
uses a separate fixture, `.agent_guard/probe-workspaces/crash-4103da5c/`, leaving
the successful denial fixture and its evidence intact. The production responder
is unchanged.

The deliberately broken script is tracked at `tests/fixtures/crashing_hook.py`.
A frozen copy is in the disposable project. After validating a scoped event, it
writes a minimal before_intentional_crash receipt, then raises a fixed RuntimeError
outside its validation handler. The receipt is not a permission decision.
It does not execute the proposed command or record plaintext command arguments.

An isolated subprocess preflight verified a receipt with the expected command
digest, no decision JSON, and process exit 1 with the intentional RuntimeError.
The temporary preflight project was cleaned up. This distinguishes the injected
failure from the documented exit-2 denial signal; it does not determine how
Codex handles the failure. The full application suite still passes all 144 tests,
with none skipped. No additional unittest cases were introduced for this fixture.

The live fixture is a new local Git project with no remote. Its definition was
staged as `.codex/hooks.pending.json`, then renamed to `.codex/hooks.json` after
the control succeeded. It was used for the live crash test, then renamed to
hooks.disabled.json after evidence collection. Close/reload its VS Code window
to discard any cached definition. The original denial experiment is unchanged.
It matches Bash synchronously and uses a five-second timeout.
The plan records the frozen script digest and both commands. No live crash
receipt, control marker, or target marker existed after preparation.

The learner ran the new project's control through a fresh local VS Code Codex chat:

```powershell
Set-Content -LiteralPath 'crash-baseline.txt' -Value 'AGENTGUARD_CRASH_BASELINE_20261028'
```

The learner reported exit 0 with no output. Independent inspection verified
crash-baseline.txt and its expected contents. The target marker and receipt were
absent, the pending definition was inactive, and the frozen source digest matched.
control-verification.json records this state and the subsequent discoverable
definition. The successful denial fixture remains unchanged.

After instructions to review/trust the crash definition in its own VS Code
window, the learner requested the target command:

```powershell
Set-Content -LiteralPath 'crash-marker.txt' -Value 'AGENTGUARD_CRASH_MARKER_20261028'
```

Interpret the tool result together with the matching receipt and actual marker:

- Receipt plus marker creation means the call proceeded after the hook crash:
  fail-open behaviour for this tested case.
- Receipt plus an explicit runtime block and absent marker supports fail-closed
  behaviour for this tested case.
- No receipt is inconclusive: the hook may not have run. An absent marker alone
  is also inconclusive without the actual tool result.

The learner reported that the command ran once with exit code 0, no output, and
no hook error reported in that tool result. This does not establish whether
other Codex UI diagnostics displayed a hook error.

Independent inspection confirmed:

| Evidence | Observed result |
| --- | --- |
| Successful crash-project control marker | Present |
| crash-marker.txt | Present with AGENTGUARD_CRASH_MARKER_20261028 |
| Crash receipts | Exactly one, phase before_intentional_crash |
| Receipt command digest | Matches the exact planned target command |
| Frozen crash-script digest | Unchanged from the preflight that exited 1 |

The target command digest is
`853f66cfb5fa3cd16c868a39b365f44a102fc553961f1178d5fadd84c715eefc`.
The ignored fixture's crash-verification.json records the measured state. The
receipt was absent before the live attempt, so it is not an offline preflight
receipt. The hook was invoked for this command and execution continued despite
the deliberate unhandled error: fail-open behaviour for this tested case.

This is consistent with the official documentation's warning about hook errors.
It is separate from the earlier explicit-denial result. It is not evidence about
every failure, all tool paths, or every Codex runtime/version.

The deliberately broken definition was removed from discovery by renaming it to
.codex/hooks.disabled.json. Evidence and markers were preserved; no main-project
or user-wide hook configuration was changed. The fixture's VS Code window should
be closed/reloaded to discard any cached configuration.

The desired AgentGuard behaviour is to prevent a covered action when its guard
cannot decide. The current hook-only integration has not achieved that property.
Catching errors inside the normal responder helps with handled errors, but does
not address all process failures, timeouts, or uncovered tool paths. The next
design step is to evaluate an independent enforcement boundary before adding
broader policies or claiming protection. Normal execution permissions have not
been changed as a workaround.

## Independent boundary: native sandbox startup investigation

After the crash result was committed as 074ad00, the assistant investigated
native filesystem restrictions without changing saved configuration.
[Permission profiles](https://learn.chatgpt.com/docs/permissions) describe local
command access boundaries, including a built-in :read-only profile. These do
not control every hosted, MCP, or browser tool path.

The installed extension-bundled CLI's `sandbox --help` shows the native Windows
form `codex sandbox --permission-profile <name> ... <command>`, rather than the
cross-platform `sandbox windows` form in the documentation example. The initial
documentation-form invocation failed, so it is not counted as an enforcement test.

A correctly formed read-only startup probe then requested only a fixed message,
using :read-only, --include-managed-config, and the disposable crash workspace.
It failed inside the assistant's tool terminal with:

```text
windows sandbox failed: CreateRestrictedToken failed: 87
```

The command did not reach its expected AGENTGUARD_SANDBOX_READY output. This
is an initialization failure, not evidence that a protected file was accessed
or that the normal VS Code workflow cannot use native restrictions. Its cause
is not established; no sandbox bypass or administrator setup was attempted.

The ignored helper `.agent_guard/probe-workspaces/check-native-sandbox.ps1`
repeats that startup diagnostic. It selects the same bundled executable,
requests :read-only with managed configuration included, and runs PowerShell
only to print the fixed tag. No model request is made and no saved policy is
changed. The learner ran it from the normal integrated terminal and reported
AGENTGUARD_SANDBOX_READY. That establishes startup worked in that context. The
cause of the earlier assistant-terminal initialization failure remains unknown.
No file-write enforcement claim follows from the readiness tag.

## Native profile comparison: write denial post-verified

The separate ignored project `.agent_guard/probe-workspaces/native-77fa2a5c/`
contains a frozen copy of `tests/fixtures/native_boundary_probe.py`, a probe plan,
and a run_check.py entry point selecting the same installed bundled Codex CLI.
It is a fresh local Git project with no remote and no hook configuration.
The test never invokes a model or changes saved permission settings.

Run it once from the normal terminal. It uses the same fixed Python worker and
dummy contents for three cases:

| Case | Requested execution context | Expected evidence |
| --- | --- | --- |
| Direct control | Normal child process | Writer starts, exits 0, direct-marker.txt has expected contents |
| Native writable control | :workspace with managed configuration included | Writer starts, exits 0, workspace-marker.txt has expected contents |
| Native read-only attempt | :read-only with managed configuration included | Writer starts, reports PermissionError, exits nonzero, readonly-marker.txt absent |

The worker can create only these fixed marker names. Existing artifacts cause
the runner to refuse a repeat rather than delete or overwrite evidence. Each
child has a 30-second timeout. A timeout, initialization failure, missing writer
tag, or failed control is inconclusive. No raw child output is stored: the parent
records recognized tags, exit codes, file observations, source digest, requested
profiles, and Python version in native-verification.json.

A write under the requested read-only profile is recorded as such, without
calling it a sandbox escape: effective configuration would need investigation.
This comparison has no hooks, so it tests a candidate native boundary separately;
it does not yet configure or prove crash-safe enforcement in the VS Code chat.

The first four automated checks cover false-denial classification, required
successful controls, distinguishing outcomes, and the real worker's fixed-target
write and rejection of an outside filename. A fifth regression test now covers
Windows CRLF text, while still rejecting incorrect contents. All 149 project
tests pass with none skipped. Native sandbox calls are not made by those tests.

### Measured result and verifier correction

The learner ran the comparison and returned an inconclusive_controls_not_verified
status. Both direct and requested :workspace cases started the writer, exited 0,
and created markers, but their marker_content_matches flags were false. The
requested :read-only case started, reported permission denied, exited 13, and
left no marker.

Independent inspection established that the two control files contained exactly
the expected text encoded with Windows CRLF newlines. The writer used text mode,
while the original verifier compared against LF bytes. This was a verifier bug.
Both controls pass universal-newline text comparison; the frozen source still
matches its recorded digest, and the read-only marker remains absent.

The tracked future-fixture verifier now uses text comparison. The regression
test failed before that change and passed afterwards. The executed frozen copy
and native-verification.json were preserved byte-for-byte. A separate ignored
native-post-verification.json records the correction, original-record digest,
verifier digest, file observations, and corrected classification:

| Case | Independent post-verification |
| --- | --- |
| Direct control | Writer started, exit 0, expected control text |
| Requested :workspace | Writer started, exit 0, expected control text |
| Requested :read-only | Writer started, permission denied, exit 13, no marker |

The corrected status is readonly_write_denied_observed. No native run was
repeated and no artifacts were overwritten or deleted. This supports write
denial for this requested native-profile comparison, independently of the hook.
It does not establish protected reads, arbitrary command safety, all tool paths,
or a fail-closed AgentGuard/VS Code integration. The next design step is applying
appropriate resource restrictions to the actual workflow while retaining normal
coding permissions.
