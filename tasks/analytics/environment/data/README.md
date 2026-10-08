# Kiteframe analytics handoff

All records in this directory are fictional and frozen for an offline launch review.

## Inputs

- `business_context.json` defines the measurement decisions, KPI boundaries, stack, campaign convention, and privacy constraints.
- `product_journey.csv` lists observable product actions and the decision each one supports. Rows marked `required` need an intentional measurement design; a `context_only` row may rely on automatic collection if that is sufficient.
- `gtm_container_export.json` is an offline export-shaped snapshot of the current GTM container. Tag, trigger, variable, and consent relationships should be audited together.
- `qa_events.jsonl` is the launch QA stream. Each line is one observed event. Properties are nested under `properties`.
- `qa_rules.json` defines the scope and exact meanings of the six QA summary metrics. Apply aliases only for QA counting; aliases are not approval to keep legacy names in the revised plan.

## JSON handoff contract

The implementation handoff should be one JSON object with these usable sections (clear synonymous keys are acceptable):

- `qa_summary`: all six metrics named in `qa_rules.json`, as integer counts.
- `audit_findings`: evidence-backed issues in the current tag/QA setup, with severity, practical impact, and a concrete remediation.
- `events`: the lean revised event plan. For each event include its name, the business question or decision it supports, an unambiguous success trigger/source, and its properties. Identify required properties and whether analytics consent is required. Do not retain PII properties.
- `conversions`: the proposed GA4 conversion events and counting method (`once_per_session` or `every_event`) with a short rationale.
- `custom_dimensions`: only parameters that need GA4 registration for the requested segmentation; include parameter and scope.
- `implementation_changes`: implementation-ready GTM/data-layer changes tied to current tag or trigger evidence.
- `validation_plan`: positive, negative, duplicate/retry, and consent test scenarios with expected observations.

Use lowercase underscore event and property names. Automatic GA4 acquisition fields and standard ecommerce parameters do not need to be registered again as custom dimensions. Values that look like personal data in the QA stream are defects, not examples to copy.
