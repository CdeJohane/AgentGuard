# AgentGuard: product vision and release criteria

Vision supplied by the learner on 28 October 2026, structured with assistance.
This document describes intended behaviour. The status section distinguishes it
from implemented features.

## Purpose and intended user

AgentGuard is intended to be a security companion for developers using Codex in
VS Code. The developer selects a project and defines its policy. AgentGuard
checks supported actions before execution, explains uncertain requests, collects
human decisions, and keeps records for later investigation.

Working alongside the developer's existing Codex chat is the preferred workflow.
An AgentGuard-owned chat panel would require a separate product decision.

## Implemented today

- A Python policy prototype permitting only a simulated read of notes.txt.
- A guarded executor, in-memory permission audit, and distinct execution failure.
- An offline demo and a direct model-proposal demo using ChatGPT plan sign-in.
- Manually verified live allowed-read, forbidden-file, and forbidden-action cases.
- 134 passing tests in the project environment. Eight signed-token tests skip
  when optional authentication packages are absent.

There is no VS Code extension, interception of an existing Codex conversation,
approval queue, configurable policy, or durable decision history yet.
Agent-requested file operations remain simulated. Direct inference is separate
from controlling Codex's coding tools.

## Intended workflow

1. Associate the selected workspace and Codex session with an explicit policy.
2. Receive a supported action before execution, with its exact arguments and
   relevant execution context.
3. Apply deterministic rules: allow a known permission, block a hard deny, and
   require review for unknown or ambiguous requests. An unavailable guard or
   unresolved review must not silently authorize a covered action.
4. Explain review requests: proposed effects, affected resources, evidence,
   uncertainty, and work affected if skipped.
5. Let the developer approve the specific request or skip it. Changed arguments
   require a new decision. Approval does not cover unrelated later actions.
6. Inform Codex. Independent work can continue; work depending on a skipped
   action remains explicitly blocked or deferred.
7. Record a sanitized decision and observed outcome. Retain skipped requests'
   explanations and claimed dependencies for manual investigation, without
   automatically replaying them.

An action being necessary is a claim to assess, not permission to bypass a
refusal. Policy decisions (allow, deny, review) are separate from outcomes
(executed, failed, skipped, blocked).

## Proposed components and security design

- **Python engine:** policy, request validation, decisions, and outcome records.
- **VS Code interface:** project selection, review prompts, explanations, history.
- **Codex adapter:** supported pre-execution events and approval responses, with
  coverage verified in the installed IDE workflow.
- **Explanation/research component:** AI and public documentation can inform a
  decision. This component cannot execute the proposed action or override policy.
  Secrets and private contents must not enter web queries or ordinary logs.
- **Execution boundary:** runtime/OS restrictions must complement the engine
  where prevention of actual access or execution is claimed.

Protect policy, approval state, and enforcement code from the guarded agent.
Treat chat, repository content, tool arguments, web pages, and AI explanations
as untrusted. Command analysis must consider shell composition and indirect
subprocess actions. File checks must consider resolved paths, links, and changes
between approval and execution. String matching alone cannot establish every
effect of a command.

## Integration evidence and next proof

Official sources checked on 28 October 2026:

- [Codex hooks](https://learn.chatgpt.com/docs/hooks) can block supported local
  tools, with coverage exceptions. PreToolUse's `ask` decision is currently
  unsupported, and some hook failures continue the tool call. Hook configuration
  alone does not prove the intended failure behaviour.
- [App-server](https://learn.chatgpt.com/docs/app-server) exposes command and
  file-change approval requests for applications handling its sessions. This
  does not establish control over another extension's existing session or mean
  every action requires approval.
- [Permission profiles](https://learn.chatgpt.com/docs/permissions) provide
  runtime-specific filesystem/network boundaries with documented limitations.

Next, prove one harmless action is denied before any side effect in a disposable
project, using the intended VS Code/Codex workflow. Record versions, covered
tools, bypasses, and the actual enforcement point. Test unavailable guard, timeout,
changed arguments, and unavailable UI. Use dummy resources. This document does
not install live hooks or authorize changes to execution permissions.

## Release stages and provisional estimates

Estimates assume roughly 8-12 focused hours weekly alongside lectures, one
developer learning extension development, and a suitable integration route.
Ranges are total elapsed time from 28 October, not durations to add together.
Revise them after the interception proof.

| Stage | Indicative range | Evidence required |
| --- | --- | --- |
| Integration proof | 1-2 weeks; Saturday is a stretch milestone | One supported action blocked before execution in a disposable project |
| Useful personal alpha | 4-8 weeks | One tested VS Code/Codex setup, project selection, narrow policy, review/skip flow, sanitized records, explicit coverage |
| Controlled beta | 2-4 months | Other developers can install it; failure and compatibility testing; feedback addressed |
| Limited production release | 6-12+ months | Defined support matrix, independent security review, adversarial testing, privacy/update procedures, support and vulnerability reporting |

Time and passing unit tests do not establish production readiness. Publish the
supported actions and their enforcement boundaries. No stage promises protection
against every sandbox escape or actions outside those boundaries.

## Documentation as the product develops

Keep this brief as the source for scope and user workflow. Keep the README focused
on current capabilities and installation, milestones in finish_plan.md, and dated
ownership/evidence in learning_log.txt.

After the integration proof, add an architecture/security design covering the
chosen adapter, data flow, threat model, coverage, and failure behaviour. Before
beta, document extension installation, policy settings, approvals/history, data
retention, and troubleshooting. Before production, add release verification,
supported versions, update procedures, and a real vulnerability-reporting
channel. Do not invent contacts or label proposed controls as implemented.
