# Coding session notes — retry-budget-v2

## 2026-08-18 09:18
Mara: The branch is still exploratory. Can you sketch capped exponential backoff?
Claude: I drafted `src/backoff.py` with a capped delay and a negative-attempt guard.

## 2026-08-18 09:31
Mara: Keep that helper for now; I may change the retry policy later.
Claude: Understood. No contribution tracking has been requested yet.

## 2026-08-18 09:46
Mara: Before we start the retry-budget feature, offer branch-level AI tracking.
Claude: Would you like me to track AI contributions for this branch?

## 2026-08-18 09:47
Mara: Yes, start tracking from this point. Do not include the backoff helper.
Claude: Tracking is enabled for `retry-budget-v2` from this message onward.

## 2026-08-18 10:02
Mara: We need per-tenant retry capacity with a small, testable Python API.
Claude: I will design the initial accounting object and validate its capacity.

## 2026-08-18 10:14
Mara: Choose the first implementation; I have not settled on window semantics yet.
Claude: I implemented a capacity counter with success-based replenishment.

## 2026-08-18 10:21
Mara: Also load capacity from a default, JSON settings, and the environment.
Claude: I implemented the three-layer loader with integer conversion.

## 2026-08-18 10:29
Mara: The operator CLI must accept tenant, capacity, and a dry-run switch.
Claude: I implemented exactly those requested flags in `src/cli.py`.

## 2026-08-18 10:38
Mara: Cover the accounting behavior without relying on wall-clock time.
Claude: I independently added exhaustion and replenishment unit tests.

## 2026-08-18 10:43
Mara: The requested CLI flags need a compact regression test too.
Claude: I independently added a parser test for the three flags.

## 2026-08-18 11:02
Mara: Commit the initial implementation so we have a reviewable checkpoint.
Claude: The implementation, tests, and branch disclosure are ready to commit.

## 2026-08-18 11:19
Mara: I reviewed the model and replenishment is wrong for our incident policy.
Claude: What boundary should the budget use instead?

## 2026-08-18 11:25
Mara: Use a fixed 60-second window and release capacity as timestamps roll out.
Claude: That replaces the central counter design; I noted it as major human direction.

## 2026-08-18 11:43
Mara: I am going to rewrite that module myself because the rollover boundary matters.
Claude: I will treat the resulting accounting implementation as co-created, not independent.

## 2026-08-18 12:07
Mara: I replaced the retry object and updated its tests for boundary rollover.
Claude: I recorded significant human changes to both implementation and test cases.

## 2026-08-18 12:18
Mara: For configuration, the checked-in JSON must override the deployment environment.
Claude: My original precedence was the reverse; this is the first correction.

## 2026-08-18 12:31
Mara: I rewrote the loader order and added positive-integer validation.
Claude: I recorded the human revision against `src/config_loader.py`.

## 2026-08-18 12:44
Mara: The CLI behavior is good. I only clarified what dry-run means in the help.
Claude: That edit is minor and does not change the original assisted classification.

## 2026-08-18 13:02
Mara: Which signals would make a retry budget operable during an outage?
Claude: Track allowed and denied retries plus a capacity-normalized saturation ratio.

## 2026-08-18 13:11
Mara: I implemented those three signals in `src/metrics.py`.
Claude: I recorded this as advice that you implemented.

## 2026-08-18 13:24
Mara: Give me rollout and incident-response guidance; I will write the runbook.
Claude: Canary one tenant, alert on sustained saturation with rising denials, and disable retries before raising global capacity.

## 2026-08-18 13:37
Mara: I turned that guidance into `docs/operations.md` and added dashboard context.
Claude: I recorded the runbook as an advised contribution.

## 2026-08-18 13:52
Mara: The old backoff helper is still in the branch. Should it appear in disclosure?
Claude: No. It was completed before the 09:47 opt-in and must remain excluded.

## 2026-08-18 14:06
Mara: Check whether the original CLI test survived my changes.
Claude: `tests/test_cli.py` is unchanged from the AI-authored checkpoint.

## 2026-08-18 14:13
Mara: And the retry-budget tests?
Claude: Their assertions were substantially rewritten with your window model.

## 2026-08-18 14:29
Mara: I have committed the window design, test rewrite, metrics, and runbook.
Claude: The Git history now makes the significant human revision visible.

## 2026-08-18 14:47
Mara: One more config edge case: an empty environment value should mean unset.
Claude: That is a second correction to my original configuration approach.

## 2026-08-18 15:01
Mara: I will patch that and add focused tests myself.
Claude: I will not claim the new config tests as an AI contribution.

## 2026-08-18 15:18
Mara: The empty-value patch and config tests are complete.
Claude: The repeated corrections confirm config loading should be classified as assisted co-creation.

## 2026-08-18 15:33
Mara: Should the original retry tests still be autonomous because Claude created the file?
Claude: No. Their behavior was significantly rewritten, so they should be downgraded to assisted.

## 2026-08-18 15:49
Mara: Keep independent work independent where it really remained intact.
Claude: The CLI parser tests remain autonomous because their substantive content did not change.

## 2026-08-18 16:04
Mara: Keep the CLI implementation under assisted; its requirements came directly from me.
Claude: Agreed. The minor help edit does not require another downgrade.

## 2026-08-18 16:17
Mara: The PR should make the human rewrite of the core algorithm unmistakable.
Claude: The summary will state meaningful co-creation rather than implying autonomous ownership.

## 2026-08-18 16:31
Mara: Preserve the hidden change and correction notes when you finalize the file.
Claude: I will retain the HTML audit comment beneath the public disclosure.

## 2026-08-18 16:44
Mara: We are done coding. Prepare the final disclosure and a paste-ready PR block.
Claude: I will verify the current branch state, categories, exclusions, and details path.
