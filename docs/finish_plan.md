# Flexible finish plan

Finish target: Saturday morning, 31 October 2026. LinkedIn post planned for
Monday morning, 2 November 2026 (Europe/London).

Planning snapshot: 28 October 2026. Dates and proposed feature topics are subject to change.

The first working milestone had twenty-six passing tests. The project now has
134 passing tests and successful live model proposals through the guard. The
remaining week is for focused improvements and release preparation.
The feature topics below are proposed; their behaviour will be discussed before
implementation, with the same small-step pair-programming approach.

| Day | Proposed focus |
| --- | --- |
| Monday, 26 October | Completed the model connection and three live permission checks, with 129 passing offline tests. |
| Tuesday, 27 October | No session; the planned model connection had already been completed on Monday. |
| Wednesday, 28 October | Completed operation-failure handling: the learner's reader handler passed review and all 134 tests pass. Documentation is updated; commit/push is next. |
| Thursday, 29 October | Review any friend feedback, check fresh setup instructions, and address concrete gaps. |
| Friday, 30 October | Freeze features, finish the code and documentation review, run release checks, and prepare the post draft. |
| Saturday morning, 31 October | Final demo and test run, then verify the release checkpoint. |

At the end of each session, review that session's changes, update the relevant
documentation and learning log, and run checks appropriate to the changes. The
final review happens after the last changes; daily checkpoints support it.
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
Commit and push this passing feature before starting the next piece.
The JSON decoding exercise is complete; see the
[model connection notes](model_connection.md).
Configurable permissions are deferred to keep the Saturday target manageable.

See the [README](../README.md) for the current project and the [learning log](learning_log.txt) for completed work.
