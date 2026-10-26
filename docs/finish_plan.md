# Flexible finish plan

Finish target: Saturday morning, 31 October 2026. LinkedIn post planned for
Monday morning, 2 November 2026 (Europe/London).

Planning snapshot: 26 October 2026. Dates and proposed feature topics are subject to change.

The first working milestone is complete: the demo runs and all twenty-six tests
pass. The remaining week is for focused improvements and release preparation.
The feature topics below are proposed; their behaviour will be discussed before
implementation, with the same small-step pair-programming approach.

| Day | Proposed focus |
| --- | --- |
| Monday, 26 October | Add the pair-programming working agreements and agree the first real model connection: provider, authentication, request format, and expected behaviour. |
| Tuesday, 27 October | Build the optional model adapter in small steps once its behaviour and authentication route are agreed. Preserve the offline demo and tests. |
| Wednesday, 28 October | Exercise allowed, forbidden, malformed, and failed model responses. Discuss operation-failure handling if time permits. |
| Thursday, 29 October | Review any friend feedback, check fresh setup instructions, and address concrete gaps. |
| Friday, 30 October | Freeze features, finish the code and documentation review, run release checks, and prepare the post draft. |
| Saturday morning, 31 October | Final demo and test run, then verify the release checkpoint. |

At the end of each session, review that session's changes, update the relevant
documentation and learning log, and run checks appropriate to the changes. The
final review happens after the last changes; daily checkpoints support it.
The plan can adapt to progress and availability without adding features just
to fill the remaining days.

The current demo is offline. The next milestone adds one optional real model
connection that proposes a request for the existing guarded executor. File
operations stay simulated. The selected route is supported Sign in with ChatGPT
plan usage. Authentication is implemented, and the learner reported a successful
live identity and permission check on 26 October. The first model request and
inference eligibility are still pending. The JSON decoding exercise is complete; see the
[model connection notes](model_connection.md).
Configurable permissions are deferred to keep the Saturday target manageable.

See the [README](../README.md) for the current project and the [learning log](learning_log.txt) for completed work.
