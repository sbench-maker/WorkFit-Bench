# Escalation Handoff Pilot: Eight-Week Operations Readout

Corpus source ID: CEDAR-OPS-2026
Prepared by: Cedar & Finch Customer Operations Analytics
Named individual authors: not stated
Report date: February 12, 2026
Version: 1.2
Document type: Internal technical report
Review status: Approved by the Support Operations Council; not peer reviewed

--- Page 1 ---

## Executive summary

Cedar & Finch piloted an AI-assisted handoff composer in three support queues for eight weeks. Forty-two agents were eligible, and the analysis includes 4,800 escalation handoffs from the eight weeks before and eight weeks during the pilot.

Median specialist handling time declined 18 percent during the pilot. Notes passing the existing completeness checklist on first review increased by 22 percentage points.

These results are promising enough to continue a guarded pilot, but the design cannot isolate the composer from a routing change launched in the same week. The report should not be read as proof that generated notes caused the full improvement.

--- Page 3 ---

## Operational setting

The pilot covered Returns, Subscription Changes, and Device Setup. Fraud, account recovery, legal escalations, and all non-English queues remained out of scope.

The composer suggested a handoff note after the frontline agent selected “prepare escalation.” Agents were expected to inspect the source conversation and edit the draft before submitting.

The tool did not post notes automatically. Supervisors repeated this instruction at launch and in week four.

During the first pilot week, Operations also replaced round-robin routing with skills-based routing. The two changes shared the same launch date.

--- Page 5 ---

## Measures and data

The pre-period contained 2,310 eligible handoffs; the pilot period contained 2,490. Ticket exports were joined to workforce scheduling and quality-review data.

Handling time was defined as specialist active-work minutes from opening the escalation to the first resolution action. It differs from end-to-end resolution time used in some published studies.

Completeness was the share of final notes containing all five locally required fields. The review team sampled 300 notes per period.

Adoption was defined as opening a generated draft and retaining at least one generated sentence. Overall adoption was 61 percent, ranging from 38 percent in Subscription Changes to 79 percent in Device Setup.

The pilot did not run a blinded factual-error audit. Existing quality reviews record missing fields but do not reliably distinguish incorrect from outdated statements.

--- Page 7 ---

## Findings

Median specialist handling time fell from 16.7 minutes before launch to 13.7 minutes during the pilot, an 18 percent decline.

First-review checklist completeness rose from 63 percent to 85 percent, a gain of 22 percentage points.

Escalations reopened within seven days fell from 8.4 percent to 7.9 percent. The difference was not statistically tested.

The largest time decline occurred in Device Setup, the queue with the highest composer adoption. Subscription Changes had the lowest adoption and a 4 percent time decline.

Agents reported that drafts were most useful when conversations were long and the customer goal was explicit. They reported more editing when several account changes occurred in one conversation.

--- Page 9 ---

## Interpretation

The time and completeness movements are consistent with a useful drafting aid. They are not causal estimates because skills-based routing changed simultaneously, seasonality was not modeled, and agents self-selected whether to retain generated text.

The adoption definition overstates meaningful use when an agent keeps only a boilerplate sentence. Conversely, it misses cases in which a draft prompted a better note but was fully rewritten.

The report offers no direct comparison of reviewed generated notes with manually authored notes on critical factual accuracy.

--- Page 11 ---

## Risks and next step

Continue the pilot for another eight weeks, retain mandatory agent confirmation, and add a blinded weekly error audit. Automatic posting should remain disabled.

Report outcomes separately by queue and case complexity. A future analysis should separate composer effects from routing effects through staggered rollout or random assignment.

Privacy and retention were reviewed by the internal security team, but that assessment is not included in this report. No multilingual evidence is available.

--- Page 12 ---

## Disclosures and limitations

The report was prepared by the team responsible for pilot measurement. Product Engineering supplied usage logs but did not edit the findings.

No external funding was used. Named individual authors are not provided. The report is internal and has not undergone independent peer review.
