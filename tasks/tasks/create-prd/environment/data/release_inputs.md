# Release planning inputs

Use relative timeframes; no calendar launch date has been committed.

- Discovery review is complete at kickoff.
- Product Analytics needs one week to lock event names, cohort rules, and the baseline readout.
- Design and Accessibility need two weeks for the end-to-end prototype and moderated keyboard/screen-reader review.
- Engineering estimates four to six weeks after prototype approval for the single-queue, 50-ticket path and its audit records.
- Security review can start when the permission and data-flow design is written. Approval is a gate before any external pilot.
- An internal dogfood should run for one week before external enrollment.
- The external pilot should run for six weeks so the approved week-six targets can be read honestly.
- The launch review must include target results, audit completeness, accessibility findings, support load, and interview feedback. It may extend the pilot instead of launching.
- Work on a durable job service can begin in parallel, but it does not put larger batches into v1 automatically.

Release owners want explicit gates, rollback signals, and decisions. A pilot must pause if an unauthorized edit is applied, an audit event is missing, or repeated retries apply a duplicate change. Performance misses can reduce the batch cap without invalidating the whole pilot.
