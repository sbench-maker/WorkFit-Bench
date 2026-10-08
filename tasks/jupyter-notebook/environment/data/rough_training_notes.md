# Rough notes: weekly first-response SLA walkthrough

Audience: newly hired support operations analysts who know lists, dictionaries, loops, and simple functions but have not worked with service-level data.

By the end they should be able to load the ticket export without extra packages, normalize the fields used by the policy, classify one ticket, and build a compact summary that a team lead can audit.

Possible flow (rewrite and organize this; do not preserve the rough wording):

1. Orient the reader to the fixed snapshot and why eligibility comes before SLA math.
2. Load `tickets.csv` with `csv.DictReader`; show only a tiny preview, not the full export.
3. Parse UTC timestamps and booleans. Keep the target mapping in one visible configuration object.
4. Use small helpers for eligibility and classification. Demonstrate one exact-target response and one unanswered ticket so the two common mistakes are concrete.
5. Produce the policy-requested priority summary and briefly interpret the result.
6. Exercise: ask the learner to adapt the grouping to `channel`, predict which channel has the strongest compliance, then provide a usable answer scaffold in the following code cell. The scaffold should run and reveal the channel summary rather than leaving a blank TODO.
7. Close with a short pitfall recap and one extension idea, such as grouping by team or topic.

Keep displayed results compact: a few example records and small summary rows are enough. Avoid a wall of raw dictionaries.
