# Q4 prioritization notes

All entities and observations are fictional. Treat 2026-08-31 23:59:59 as the frozen research cutoff.

## Customer-problem scoring

1. Keep rows whose account is `active`, response is `complete`, submission is on or before the cutoff, both ratings are integers from 1 through 5, and the problem and segment IDs exist in their catalogues.
2. Apply those validity checks before de-duplication. For each respondent/problem pair, retain the valid row with the latest `submitted_at` (break an exact timestamp tie by the greatest `response_id`).
3. Convert each rating to 0-1 with `(rating - 1) / 4`. Within each problem and segment, average importance and satisfaction separately. Combine the three segment averages using `segment_weights.csv`; all three segment weights are represented for every problem.
4. Calculate Opportunity Score from those weighted normalized importance and satisfaction values. Rank customer problems from highest score to lowest, breaking a tie by higher weighted importance and then `problem_id`.

## Initiative scoring and the Q4 set

Only `candidate` initiatives are eligible to rank or enter the Q4 set. A withdrawn idea may be mentioned as excluded but must never be recommended.

For each candidate, total reach is the sum of its rows in `initiative_problem_reach.csv`. Impact is the reach-weighted mean Opportunity Score of its mapped customer problems. Interpret confidence as `confidence_pct / 100`, and use the supplied effort in person-months. Calculate RICE from those four factors and rank candidates by descending RICE, then lower effort, then `initiative_id`.

The Q4 capacity is 14.0 person-months. Walk the ranked candidate list from top to bottom. Add an initiative when it and all still-unselected transitive dependencies fit the remaining capacity and it does not conflict with an already selected member of the same nonblank `exclusive_group`; add required dependencies at the same time. Otherwise skip it and continue. The final set must remain within capacity, dependency-complete, and exclusive-group safe.

Round only for presentation; use unrounded values for ranking and capacity decisions.
