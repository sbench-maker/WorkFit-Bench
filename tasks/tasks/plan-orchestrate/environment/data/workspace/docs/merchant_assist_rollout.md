# Merchant Assist Gateway — staged rollout plan

Owner: Enterprise Automation
Target window: 2026 Q4
Status: Approved for implementation

## Context

Support operators use the Merchant Assist gateway to look up account state and initiate a
small set of recovery actions. The current prototype has no reliable tenant boundary, its
PyTorch intent model is packaged differently in developer and release images, and the
release process is not yet repeatable.

The rollout must leave the existing support console available while the gateway moves
through internal, preview, and pilot cohorts. Each phase below is independently reversible.

## Outcomes

- Tenant-bound operator actions with clear denial behavior.
- A reproducible CPU-only image for the intent model.
- Evidence that the main checkout recovery journey works across service boundaries.
- An operator-facing runbook and a documented go/no-go decision.

## Step 1 — Choose gateway boundaries and record the architecture RFC

### Intent

Choose the ownership boundary between the support console, Merchant Assist gateway, and
commerce services. Record the architecture decision before behavior changes begin.

### Deliverables

- A short RFC covering request ownership, synchronous dependencies, and failure isolation.
- A sequence diagram for allowed and denied operator actions.
- A decision on whether intent inference remains in-process for the pilot.

### Completion evidence

- Platform and Commerce owners agree on the service boundary.
- The RFC records the rejected alternative and its operational trade-off.
- Every synchronous dependency has a timeout owner.

## Step 2 — Implement tenant authorization guards for operator actions

### Intent

Implement tenant authorization at the gateway boundary. Every operator request must bind
the authenticated actor, requested tenant, and action before any merchant data is loaded.
The role named "operator" may use only the recovery actions listed in policy.

### Deliverables

- A tenant guard shared by account-read and recovery handlers.
- Denial responses that do not reveal whether another tenant's account exists.
- A structured activity record containing tenant, actor, action, and decision.

### Completion evidence

- Same-tenant allowed actions proceed normally.
- Cross-tenant requests return 403 without account details.
- Each allow or deny decision emits one complete activity record.

Out of scope: replacing the enterprise identity provider.

## Step 3 — Resolve PyTorch image compilation failures in the release pipeline

### Intent

Resolve the intermittent release-image compile failure caused by incompatible PyTorch wheel
selection. The pilot image is CPU-only and must use the dependency versions declared by
the project rather than developer-machine state.

### Deliverables

- A deterministic dependency resolution for the CPU-only image.
- A release image that imports the intent model and starts the gateway.
- Failure output that identifies dependency conflicts without hiding the original cause.

### Completion evidence

- Two clean pipeline runs produce the same locked dependency set.
- The resulting image starts without a CUDA library.
- A conflicting wheel version fails with a concise diagnostic.

## Step 4 — Run the end-to-end checkout recovery integration test

### Intent

Run an end-to-end integration test from the support console through the gateway to the
checkout recovery endpoint. Cover both an allowed recovery and a tenant-bound denial.

### Deliverables

- A repeatable pilot-environment scenario with stable fictional merchant IDs.
- Captured correlation IDs across the console, gateway, and commerce service.
- A concise failure bundle suitable for service-owner triage.

### Completion evidence

- The allowed journey reaches a completed recovery state.
- The denied journey makes no downstream recovery call.
- Correlation IDs connect every hop in each journey.

Out of scope: load testing and browser compatibility coverage.

## Step 5 — Refresh the operator README and release changelog

### Intent

Refresh the operator README with the pilot workflow, denial interpretation, and rollback
contact. Include a changelog entry that distinguishes operator-visible behavior from internal
packaging work.

### Deliverables

- A short pilot procedure with prerequisites and rollback contact.
- Examples of an allowed response and a tenant-bound denial.
- A changelog entry grouped by operator impact and internal maintenance.

### Completion evidence

- An on-call operator can follow the procedure without engineering context.
- The denial example does not imply that a foreign account exists.
- The changelog identifies the first pilot release that contains the behavior.

## Step 6 — Review release-candidate readiness and record the decision

### Intent

Review the release candidate against the prior completion evidence and record a go, hold,
or rollback decision. Any hold must name an owner and a date for the next decision.

### Deliverables

- A release-readiness note linking each earlier evidence item.
- A decision with owner, timestamp, and unresolved risks.
- A rollback signal that on-call staff can observe during the pilot.

### Completion evidence

- No unresolved tenant-boundary defect is accepted for pilot traffic.
- Every hold has one accountable owner and review date.
- The final decision names the observable rollback signal.

Out of scope: approving general availability.

## Step 7 — Ramp the pilot cohort in three traffic increments

### Intent

Ramp the pilot cohort from internal operators to two merchant-support groups, pausing
between increments long enough to observe denial rate and recovery completion rate.

### Deliverables

- Three named cohort increments with start and pause conditions.
- A single owner for advancing or pausing each increment.
- A brief cohort note after each pause window.

### Completion evidence

- Each increment starts only after its prior pause window closes.
- Denial and recovery-completion rates remain inside the approved pilot bands.
- Any pause records the affected cohort and the deciding owner.

## Operating notes

The support console remains the operator entry point throughout the pilot. Cohort changes
are reversible through the existing feature-control surface. All sample identifiers used
in evidence must remain fictional and contain no production merchant data.
