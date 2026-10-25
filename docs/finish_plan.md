# Flexible finish plan

Finish target: Saturday morning, 31 October 2026. LinkedIn post planned for
Monday morning, 2 November 2026 (Europe/London).

Planning snapshot: 25 October 2026. Dates and proposed feature topics are subject to change.

The first working milestone is complete: the demo runs and all twenty-six tests
pass. The remaining week is for focused improvements and release preparation.
The feature topics below are proposed; their behaviour will be discussed before
implementation, with the same small-step pair-programming approach.

| Day | Proposed focus |
| --- | --- |
| Monday, 26 October | Review the visitor experience and refine the docs. The README first pass, walkthrough, and plan split were completed on 25 October. |
| Tuesday, 27 October | Discuss and build a small configurable permission policy, keeping default-deny behaviour. |
| Wednesday, 28 October | Discuss operation-failure behaviour and test what happens when an allowed operation raises an error. |
| Thursday, 29 October | Review any friend feedback, check fresh setup instructions, and address concrete gaps. |
| Friday, 30 October | Freeze features, finish the code and documentation review, run release checks, and prepare the post draft. |
| Saturday morning, 31 October | Final demo and test run, then verify the release checkpoint. |

At the end of each session, review that session's changes, update the relevant
documentation and learning log, and run checks appropriate to the changes. The
final review happens after the last changes; daily checkpoints support it.
The plan can adapt to progress and availability without adding features just
to fill the remaining days.

This version stays focused on simulated file operations with no model connection
or real filesystem access.

See the [README](../README.md) for the current project and the [learning log](learning_log.txt) for completed work.
