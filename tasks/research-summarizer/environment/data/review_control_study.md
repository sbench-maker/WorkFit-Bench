# Human Review as a Safety Control for Generated Handoff Notes

Corpus source ID: REVIEWLAB-2024
Authors: Talia Iqbal and Jonah Mensah
Publication: Proceedings of the Applied Service Science Conference, 2024, pages 113–129
Document type: Peer-reviewed conference paper
Funding: Larkspur University Service Systems Initiative
Conflicts of interest: None declared

--- Page 113 ---

## Abstract

Generated handoff notes can save composition time, but automation may introduce plausible statements unsupported by the source conversation. We compare manual notes, unreviewed generated notes, and generated notes reviewed by the assigned agent.

Ninety-six experienced support agents completed a controlled crossover study using 2,304 synthetic tickets. Reviewed generation saved 9 percent of total handoff-task time relative to manual writing.

Critical factual-error rates were 8.6 percent for unreviewed generated notes, 1.9 percent for reviewed generated notes, and 1.2 percent for manual notes. Review reduced but did not eliminate the gap.

--- Page 116 ---

## Study design

Each agent completed 24 scenarios: eight manual, eight generated without review, and eight generated with a required review checklist. Condition order was randomized.

Tickets were synthetic but constructed from recurring billing, delivery, device, and account-access patterns. Each scenario included a transcript, account timeline, and target escalation queue.

Agents had at least one year of support experience. They received two hours of study training but did not use the system with live customers.

The required review checklist asked agents to verify identity, customer goal, completed actions, current state, and promised next step.

--- Page 119 ---

## Outcomes

The primary safety outcome was a critical statement not supported by, or contradicting, the transcript or account timeline. Two blinded raters adjudicated disagreements.

Total handoff-task time included reading, composing or reviewing, and submitting the note. This differs from a measure limited to typing or draft preparation.

Raters also scored completeness on a five-item scale. Participants completed a workload survey after each block.

--- Page 122 ---

## Results

Mean total handoff-task time was 6.7 minutes for manual notes, 6.1 minutes for reviewed generated notes, and 4.8 minutes for unreviewed generated notes. Reviewed generation was 9 percent faster than manual writing.

Critical factual-error rates were 1.2 percent for manual notes, 1.9 percent for reviewed generated notes, and 8.6 percent for unreviewed generated notes.

Mean completeness scores were 4.42 for manual notes, 4.68 for reviewed generated notes, and 4.61 for unreviewed generated notes out of five.

The largest unreviewed errors involved incorrect promised refunds and completed troubleshooting steps. Reviewers corrected most identity and product errors but sometimes accepted plausible invented commitments.

--- Page 125 ---

## Analysis

Removing review maximized speed but produced a seven-fold critical-error rate relative to manual writing. That trade-off is unacceptable for direct deployment without additional safeguards.

Reviewed generation retained a modest speed benefit and improved completeness. Its 1.9 percent error rate was not statistically distinguishable from the 1.2 percent manual rate, but the confidence interval was wide and does not establish equivalence.

The study supports review as a safety control. It does not prove the same effect in live queues where interruptions, policy complexity, and customer stakes differ.

--- Page 127 ---

## Limitations

Synthetic tickets improve experimental control but limit field generalizability. Participants knew they were being studied, and the session lasted less than one workday.

No multilingual scenarios, accessibility cases, or privacy and retention outcomes were included. The study did not measure end-to-end resolution time or customer satisfaction.

The system used one model configuration. Results may not transfer to other configurations without fresh evaluation.

--- Page 129 ---

## Conclusion

Human review sharply reduced the factual risk of generated handoff notes while preserving a smaller efficiency benefit. The evidence argues against automatic publication and for measuring final-note error rates during any field pilot.
