# Frozen curation policy

Use only rows whose `review_status` is `approved`. Trim outer whitespace and reject a mapped value that is empty or the case-insensitive placeholder `nan` or `none`. For repeated customer messages, keep one row: prefer the highest `review_revision`, then the lowest `example_id`. This also collapses exact duplicate pairs. Use the confirmed mapping and `messages` chat format without carrying review metadata into the tuning records. Apply the handoff's stable SHA-256 holdout rule after curation. Estimate training cost from the training partition's message content only.
