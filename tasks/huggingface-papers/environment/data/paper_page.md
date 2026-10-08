# CedarSwitch: Budget-Aware Sparse Summarization for Multilingual Support Tickets

**Paper ID:** 2608.04721v2

**Authors:** Lina Ortez, Pavel Ilyin, Mei Harrow, Noor Abeni

**Revision date:** 2026-08-18

## Abstract

Customer-support summaries must preserve identifiers and proposed actions while meeting strict latency budgets.
CedarSwitch is a 1.31B-parameter encoder-decoder with eight feed-forward experts and top-two routing.
Only 0.62B parameters are active for a typical token, and an auxiliary budget loss discourages expensive routes.
A terminology-preservation loss targets product names, error codes, dates, and requested remedies.
At inference time, a confidence gate can replace the generated summary with an extractive fallback.
On the AuroraSupport English and Spanish test sets, the 4-bit model improves ROUGE-L over Dense-1.3B.
The v2 gains are 5.1 points in English and 5.7 points in Spanish.
On a 16 GB Lattice E16 development unit, median latency falls by 38.0% in English and 37.8% in Spanish.
The largest measured model allocation is 7.4 GB, but the serving stack requires at least 9 GB of free memory.
We therefore do not claim that the published configuration fits an 8 GB physical-memory device.

## 1. Introduction

A useful support summary should identify the customer's problem, the evidence already collected, and the next action.
Generic summarizers often omit error codes or convert tentative agent suggestions into completed actions.
Larger dense models improve fluency but increase memory use and tail latency on local support appliances.
Our goal is a multilingual model that allocates capacity only where difficult tokens require it.
We focus on English and Spanish because those languages have reviewed in-domain data in our collection.
We make no claims for code-switched tickets or languages not represented in the training mixture.
The reported experiments use a maximum input length of 1,024 tokens and a maximum output length of 128 tokens.
Tickets longer than 1,024 tokens are truncated from the oldest message first.
This truncation policy can remove early troubleshooting context and is not evaluated separately.

### 1.1 Contributions

1. A budget-aware top-two router for a sparse encoder-decoder summarizer.
2. A span-level terminology loss for identifiers and requested actions.
3. A confidence-gated extractive fallback calibrated per language.
4. An evaluation of quality, factuality, latency, energy, and memory on one edge development unit.

## 2. Task and data

AuroraSupport contains fictionalized software-account and device-setup conversations from two product lines.
The collection excludes regulated financial, medical, and public-safety support domains.
All examples used in the experiments were transformed and reviewed for release-study purposes.
The full training collection is not distributed with this snapshot.
A smaller redacted evaluation subset is represented by a linked dataset entry.

### 2.1 Split sizes

| Language | Train | Validation | Test | Median input tokens | 95th percentile input tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| English | 96,000 | 8,000 | 12,000 | 286 | 811 |
| Spanish | 24,000 | 3,000 | 4,000 | 301 | 846 |

Spanish training data contains 40% translated conversations followed by bilingual reviewer correction.
The Spanish validation and test sets contain only originally authored conversations.
Conversation threads are grouped by account before splitting to prevent thread leakage.
Exact duplicate detection uses normalized message text and timestamps.
Near-duplicate templates are retained when the user-provided details differ.

### 2.2 Reference summaries

Reference summaries contain three labeled spans: issue, evidence, and next action.
Annotators must copy error codes exactly and keep uncertain diagnoses explicitly uncertain.
Two annotators draft each test summary and a third resolves disagreements.
Agreement measured on required-span inclusion is 0.82 Krippendorff alpha for English.
Agreement is 0.78 for Spanish.

## 3. Method

### 3.1 Sparse encoder-decoder

The base network has 18 encoder layers and 12 decoder layers.
Every third layer replaces its dense feed-forward block with eight experts.
The router selects two experts per token and combines their outputs with normalized gate weights.
The total parameter count is 1.31B, while the mean active parameter count is 0.62B per token.
The dense comparison model has 1.29B parameters and uses the same tokenizer and attention dimensions.

### 3.2 Budget-aware routing

We assign each route a latency proxy measured during a short calibration pass.
The budget loss penalizes batches whose expected route cost exceeds a language-specific target.
English and Spanish share experts, but use separate calibration temperatures.
The router is not allowed to use the language label as a direct feature.
A load-balancing term prevents collapse onto one expert.

### 3.3 Terminology preservation

A lightweight tagger identifies product names, error codes, dates, quantities, and imperative action spans.
The auxiliary loss increases probability mass on exact source tokens for tagged spans.
This mechanism is trained jointly and does not call an external dictionary at inference time.
The tagger recall is 96.1% for English error codes and 94.3% for Spanish error codes on held-out data.
The tagger was not evaluated on personally identifying spans.

### 3.4 Confidence-gated fallback

The gate combines normalized sequence likelihood, router entropy, and unsupported-entity detection.
If confidence is below the per-language threshold, the system returns three extracted source sentences.
Thresholds are selected on the validation split to minimize hallucination subject to a ROUGE-L floor.
Fallback activates for 6.2% of English test examples and 9.8% of Spanish test examples.
A fallback output is less concise, but keeps every sentence traceable to the source ticket.

## 4. Experimental setup

Models are trained for 120,000 updates with batches balanced 70:30 between English and Spanish.
Results are the mean of three random seeds unless a table states otherwise.
Quality intervals use paired bootstrap resampling with 10,000 samples.
Latency uses 1,000 requests after 100 warm-up requests, batch size one.
The test harness pins the runtime to performance mode.
No network calls occur during timing.

### 4.1 Deployment hardware

All latency, energy, and peak-allocation measurements use one Lattice E16 development unit.
The unit has 16 GB unified memory and runtime build 4.7.2.
The operating system and ticket-ingestion process reserve between 2.1 GB and 2.6 GB outside the reported model allocation.
Peak allocation is the maximum attributed to model weights, caches, and temporary tensors.
It excludes the operating system, ingestion queue, telemetry buffer, and rollback copy.
For reliable serving, we recommend at least 9 GB free before the model process starts.
We did not run the system on an 8 GB physical-memory device.

### 4.2 Baselines

Dense-1.3B matches the total scale of CedarSwitch without sparse experts.
Extract-3 selects three sentences with a multilingual relevance encoder.
The dense and sparse generators use 4-bit weight-only quantization for device measurements.
The linked full-precision checkpoint is supplied for research reproduction, not the device measurements.

## 5. Results

### 5.1 Automatic quality and factuality

| Language | System | ROUGE-L | BERTScore | Unsupported-claim rate | Error-code exact match |
| --- | --- | ---: | ---: | ---: | ---: |
| English | Extract-3 | 28.6 | 0.842 | 1.9% | 99.1% |
| English | Dense-1.3B | 31.8 | 0.861 | 8.4% | 91.8% |
| English | CedarSwitch-4bit | 36.9 | 0.884 | 5.6% | 96.7% |
| Spanish | Extract-3 | 25.2 | 0.816 | 2.4% | 98.6% |
| Spanish | Dense-1.3B | 27.4 | 0.837 | 10.9% | 89.7% |
| Spanish | CedarSwitch-4bit | 33.1 | 0.868 | 7.1% | 95.2% |

CedarSwitch improves ROUGE-L by 5.1 points in English and 5.7 points in Spanish over Dense-1.3B.
The 95% confidence interval for the English improvement is [4.6, 5.6].
The 95% confidence interval for the Spanish improvement is [5.1, 6.3].
Unsupported-claim rate improves over the dense generator but remains worse than Extract-3.
Exact error-code copying improves by 4.9 points in English and 5.5 points in Spanish over Dense-1.3B.

### 5.2 Human evaluation

Three support specialists compare outputs blindly against the reference and source conversation.
The sample contains 240 English tickets and 180 Spanish tickets.
CedarSwitch is preferred to Dense-1.3B on 62% of English tickets, with 21% ties.
It is preferred on 58% of Spanish tickets, with 24% ties.
Reviewers most often cite better retention of requested actions.
They also note that fallback outputs are sometimes too long for the agent console.

### 5.3 Device efficiency

| Language | System | p50 latency (ms) | p95 latency (ms) | Energy/request (J) | Peak model allocation (GB) |
| --- | --- | ---: | ---: | ---: | ---: |
| English | Extract-3 | 124 | 171 | 0.7 | 0.9 |
| English | Dense-1.3B-4bit | 820 | 1,130 | 4.8 | 8.9 |
| English | CedarSwitch-4bit | 508 | 715 | 3.1 | 7.4 |
| Spanish | Extract-3 | 131 | 182 | 0.8 | 0.9 |
| Spanish | Dense-1.3B-4bit | 845 | 1,171 | 5.0 | 8.9 |
| Spanish | CedarSwitch-4bit | 526 | 742 | 3.3 | 7.4 |

The median latency reduction is 38.0% for English and 37.8% for Spanish.
Peak model allocation falls from 8.9 GB to 7.4 GB.
These values are model-process measurements on the 16 GB unit, not whole-device requirements.
The 7.4 GB allocation should not be interpreted as evidence of safe operation on an 8 GB device.

### 5.4 Ablations

| Variant | English ROUGE-L | Spanish ROUGE-L | English unsupported claims | Spanish unsupported claims |
| --- | ---: | ---: | ---: | ---: |
| Full CedarSwitch | 36.9 | 33.1 | 5.6% | 7.1% |
| Without budget loss | 37.0 | 33.2 | 5.7% | 7.2% |
| Without terminology loss | 35.8 | 31.9 | 7.0% | 8.8% |
| Without fallback | 37.4 | 33.7 | 8.9% | 11.8% |

The budget loss changes quality little but reduces median latency by 11% relative to the no-budget variant.
The terminology loss and fallback contribute most directly to factuality.
Removing fallback improves ROUGE-L while sharply increasing unsupported claims.

## 6. Version history and corrections

Version 1 reported Spanish ROUGE-L of 33.5 and a 6.1-point gain over Dense-1.3B.
After publication, we found 400 duplicate Spanish test records created during export.
Version 2 removes those records and reports Spanish ROUGE-L of 33.1 and a 5.7-point gain.
English scores are unchanged between versions.
The energy column label in version 1 incorrectly read watt-hours; the values were joules.
No latency or memory experiment was rerun for version 2.
The paper-page AI summary was generated from version 1 and still contains the 6.1-point Spanish claim.
One linked community adapter also declares paper revision v1 in its metadata.
The main author checkpoints tagged revision v2 correspond to the corrected paper.

## 7. Limitations

The deployment evaluation uses a single 16 GB development unit and one runtime build.
We do not measure 8 GB devices, concurrent requests, thermal throttling, or 24-hour stability.
The study does not include code-switched conversations.
The Spanish training set is smaller and partially translated.
Evaluation covers only software-account and device-setup support from two product lines.
Tickets longer than 1,024 tokens are truncated and not analyzed as a separate cohort.
The terminology tagger is not a personally identifying information detector.
Unsupported-claim rate is based on sentence-level specialist review and may miss subtle pragmatic errors.
The released evaluation subset is smaller than the data used to report the primary test results.

## 8. Reproducibility notes

The int4 author checkpoint corresponds to revision v2 and the device table.
The full-precision checkpoint corresponds to revision v2 and is intended for quality reproduction.
The router-ablation checkpoint omits the budget loss and is not the reported production candidate.
The public evaluation subset includes 2,000 English and 1,000 Spanish examples.
A separate terminology lexicon dataset contains synthetic product names and error-code patterns.
The benchmark harness records latency but does not emulate an 8 GB memory ceiling.
The qualitative explorer Space displays sampled outputs and does not run the model live.
The quantization demo Space uses cached requests and must not be used for latency validation.

## 9. Conclusion

CedarSwitch demonstrates that routing, terminology preservation, and fallback can improve a compact support summarizer.
The strongest evidence is improved English and Spanish quality with lower latency than a similarly sized dense generator.
The results do not establish compatibility with an 8 GB physical-memory deployment.
A device-specific pilot should measure whole-process memory, concurrency, long-ticket behavior, and stability before adoption.

## Appendix A. Training details

The tokenizer has 48,000 subword entries shared across both languages.
Optimization uses a peak learning rate of 0.00018 and 4,000 warm-up steps.
The router temperature begins at 1.5 and anneals to 0.7.
The load-balancing coefficient is 0.01.
The budget-loss coefficient is 0.04.
The terminology-loss coefficient is 0.12.
Dropout is 0.1 in attention and dense blocks.
Training consumes eight accelerator-days across four identical accelerators.
Checkpoint selection uses the mean of English and Spanish validation ROUGE-L minus unsupported-claim rate.

## Appendix B. Confidence thresholds

The English fallback threshold is 0.41.
The Spanish fallback threshold is 0.46.
Calibration error is 0.037 for English and 0.052 for Spanish.
Threshold sensitivity is larger for Spanish because its validation split is smaller.
Using one shared threshold raises Spanish unsupported claims by 0.8 points.

## Appendix C. Evaluation protocol

Automatic metrics are computed after normalizing whitespace but before lowercasing error codes.
Human raters see the full source conversation and are unaware of system identity.
A ticket is marked unsupported when any declarative sentence lacks support in the source conversation.
Preference ties are allowed and are not split between systems.
Bootstrap samples are drawn at the ticket level.
All three training seeds use the same data splits.

## Appendix D. Deployment checklist from the authors

Measure memory with the intended ingestion process and telemetry enabled.
Reserve space for one rollback checkpoint during upgrades.
Recalibrate confidence thresholds after domain adaptation.
Audit code-switched and long-ticket cohorts before multilingual launch.
Do not treat cached demo latency as a device benchmark.

## Appendix E. Error-analysis observations

### E.1 missing_action (English)

The next action was omitted although the issue was captured.
This observation is qualitative and is not an additional aggregate metric.

### E.2 code_mutation (English)

One character in an error code changed during generation.
This observation is qualitative and is not an additional aggregate metric.

### E.3 certainty_shift (Spanish)

A tentative diagnosis was presented as confirmed.
This observation is qualitative and is not an additional aggregate metric.

### E.4 actor_swap (English)

An action proposed for the customer was attributed to the agent.
This observation is qualitative and is not an additional aggregate metric.

### E.5 overlong_fallback (English)

The extractive fallback exceeded the console's preferred length.
This observation is qualitative and is not an additional aggregate metric.

### E.6 early_context_loss (Spanish)

Oldest-first truncation removed an earlier troubleshooting result.
This observation is qualitative and is not an additional aggregate metric.

### E.7 missing_action (English)

The next action was omitted although the issue was captured.
This observation is qualitative and is not an additional aggregate metric.

### E.8 code_mutation (English)

One character in an error code changed during generation.
This observation is qualitative and is not an additional aggregate metric.

### E.9 certainty_shift (Spanish)

A tentative diagnosis was presented as confirmed.
This observation is qualitative and is not an additional aggregate metric.

### E.10 actor_swap (English)

An action proposed for the customer was attributed to the agent.
This observation is qualitative and is not an additional aggregate metric.

### E.11 overlong_fallback (English)

The extractive fallback exceeded the console's preferred length.
This observation is qualitative and is not an additional aggregate metric.

### E.12 early_context_loss (Spanish)

Oldest-first truncation removed an earlier troubleshooting result.
This observation is qualitative and is not an additional aggregate metric.

### E.13 missing_action (English)

The next action was omitted although the issue was captured.
This observation is qualitative and is not an additional aggregate metric.

### E.14 code_mutation (English)

One character in an error code changed during generation.
This observation is qualitative and is not an additional aggregate metric.

### E.15 certainty_shift (Spanish)

A tentative diagnosis was presented as confirmed.
This observation is qualitative and is not an additional aggregate metric.

### E.16 actor_swap (English)

An action proposed for the customer was attributed to the agent.
This observation is qualitative and is not an additional aggregate metric.

### E.17 overlong_fallback (English)

The extractive fallback exceeded the console's preferred length.
This observation is qualitative and is not an additional aggregate metric.

### E.18 early_context_loss (Spanish)

Oldest-first truncation removed an earlier troubleshooting result.
This observation is qualitative and is not an additional aggregate metric.

### E.19 missing_action (English)

The next action was omitted although the issue was captured.
This observation is qualitative and is not an additional aggregate metric.

### E.20 code_mutation (English)

One character in an error code changed during generation.
This observation is qualitative and is not an additional aggregate metric.

### E.21 certainty_shift (Spanish)

A tentative diagnosis was presented as confirmed.
This observation is qualitative and is not an additional aggregate metric.

### E.22 actor_swap (English)

An action proposed for the customer was attributed to the agent.
This observation is qualitative and is not an additional aggregate metric.

### E.23 overlong_fallback (English)

The extractive fallback exceeded the console's preferred length.
This observation is qualitative and is not an additional aggregate metric.

### E.24 early_context_loss (Spanish)

Oldest-first truncation removed an earlier troubleshooting result.
This observation is qualitative and is not an additional aggregate metric.

### E.25 missing_action (English)

The next action was omitted although the issue was captured.
This observation is qualitative and is not an additional aggregate metric.

### E.26 code_mutation (English)

One character in an error code changed during generation.
This observation is qualitative and is not an additional aggregate metric.

### E.27 certainty_shift (Spanish)

A tentative diagnosis was presented as confirmed.
This observation is qualitative and is not an additional aggregate metric.

### E.28 actor_swap (English)

An action proposed for the customer was attributed to the agent.
This observation is qualitative and is not an additional aggregate metric.

### E.29 overlong_fallback (English)

The extractive fallback exceeded the console's preferred length.
This observation is qualitative and is not an additional aggregate metric.

### E.30 early_context_loss (Spanish)

Oldest-first truncation removed an earlier troubleshooting result.
This observation is qualitative and is not an additional aggregate metric.
