# Roadmap and Saturday milestone

Proof-of-concept milestone: Saturday morning, 31 October 2026. LinkedIn post
planned for Monday morning, 2 November 2026 (Europe/London).
The broader AgentGuard product continues beyond Saturday; its vision and
provisional release estimates are in [product_vision.md](product_vision.md).

Planning snapshot: 28 October 2026. Dates and proposed feature topics are subject to change.

The first working milestone had twenty-six passing tests. The completed Python
prototype had 134 passing tests and successful live model proposals through the guard.
The completed hook responder and receipts bring the suite to 144 passing tests. The
remaining week is for proving integration toward the newly clarified VS Code
product direction. The existing Python prototype remains the verified baseline.
The feature topics below are proposed; their behaviour will be discussed before
implementation, with the same small-step pair-programming approach.

| Day | Proposed focus |
| --- | --- |
| Monday, 26 October | Completed the model connection and three live permission checks, with 129 passing offline tests. |
| Tuesday, 27 October | No session; the planned model connection had already been completed on Monday. |
| Wednesday, 28 October | Completed operation-failure handling and setup review. Evening: completed/committed the responder; 144 tests pass. Verified control and one trusted project-hook denial in local VS Code with a matching receipt and no blocked marker. |
| Thursday, 29 October | Record coverage and test failure behaviour in the disposable setup before choosing the next adapter step. |
| Friday, 30 October | Review the verified integration slice and its limits. Address concrete gaps and prepare an accurate progress-post draft. |
| Saturday morning, 31 October | Demonstrate the verified scope, run applicable checks, and record achieved results and unresolved integration limits. |

At the end of each session, review that session's changes, update the relevant
documentation and learning log, and run checks appropriate to the changes. The
review of each milestone happens after its last changes; daily checkpoints support it.
The plan can adapt to progress and availability without adding features just
to fill the remaining days.

The offline demo remains available alongside the optional real model connection.
File operations stay simulated. The selected route is supported Sign in with
ChatGPT plan usage. On 26 October, the learner reported a successful live run:
GPT-6.1-Sol proposed reading notes.txt, the Python guard permitted it, the simulated
reader returned contents, and one audit record was displayed. Stream handling
fixes resolved the observed missing header and empty terminal output list.
The learner's pipeline exercise is complete and reviewed; its passing checkpoint
had 129 tests in the authentication environment. The learner also verified a live secrets.txt
proposal: the model preserved the path, the guard denied it, and one denied audit
record appeared. The learner committed and pushed this connection milestone, then
verified a live write proposal on notes.txt: the guard denied the action and
recorded it once. All three planned live checks for this session now match their
expected behaviour. The final documentation update was committed as
`77ae1c9` before the Wednesday session; the working tree was clean on resuming.

Wednesday's agreed addition handles a permitted read failing with `OSError`.
The assistant added a safe exception, demo handling, and tests. The learner
completed the reader handler, and review confirmed the narrow OSError catch and
suppressed exception context. All 134 tests pass with none skipped in the project
environment. See the [walkthrough](walkthrough.md#seventh-exercise-completed-operation-failure).
File operations remain simulated and the existing permission audit is preserved.
The learner committed this feature as `951d823`; the working tree was clean
before the setup review.

Fresh-checkout verification used only committed files and a new environment
without optional authentication packages. The offline demo produced one execution
and three denials; the suite ran 134 tests, with 126 passing and the expected
eight signed-token tests skipped. The temporary checkout and environment were
removed. This verifies dependency-free setup; a fresh installation of the
optional authentication packages was not repeated.
The learner added environment activation to the README. Review corrected a path
typo from `.venv` to `.\venv` to match the created folder. The assistant grouped
environment creation, activation, dependency installation, and tests into one
copyable block and shortened subsequent commands to `python`. This setup
clarification was committed as `9892647`. Its setup-verification notes are
retained in the current documentation update.
The JSON decoding exercise is complete; see the
[model connection notes](model_connection.md).
The first narrow interception proof has succeeded. Selecting a project, configurable
policies, human review, and deferred records are product requirements, not current
capabilities. No live hooks or execution-policy changes have been installed by
this documentation pass.

Production readiness is a separate milestone after a useful alpha and controlled
beta. The product brief assumes 8-12 focused hours weekly and gives provisional
total elapsed ranges: personal alpha 4-8 weeks, controlled beta 2-4 months, and
a limited production release 6-12+ months. These are estimates to revisit after
the integration proof, not release promises. The release must demonstrate its
enforcement boundaries, failure behaviour, privacy controls, and compatibility;
the current 134 tests alone do not establish those broader guarantees.

See the [README](../README.md) for the current project and the [learning log](learning_log.txt) for completed work.

Evening investigation: the installed extension bundles Codex 0.164.0-alpha.11.1
and its CLI reports hooks enabled. This does not prove the active chat's runtime
or interception support by itself. The subsequent [live proof](interception_proof.md)
demonstrated one explicit denial at the disposable workspace root. Commit the
recorded evidence, then agree the next failure/coverage checks before extending
the adapter. The result supports only the tested action and scope.
