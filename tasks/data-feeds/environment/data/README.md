# Offline structured-feed sandbox

`feed_requests.json` is the collection queue. Each request provides the dataset type, target URL, and an `args` array accepted by the available dataset wrapper. The container's `curl` command is a deterministic local emulator for the wrapper's trigger and snapshot calls; it never connects to the network.

Set `BRIGHTDATA_API_KEY` to any non-empty placeholder such as `offline` when running the wrapper (the emulator does not authenticate or retain it), and set `BRIGHTDATA_POLLING_TIMEOUT=4` so the deliberately unfinished request returns promptly. Run requests separately because every trigger creates its own snapshot. The emulator returns `starting`, `building`, or `running` before a terminal payload; it also includes a trigger rejection, a terminal collection failure, and one job that never leaves polling.

Completed payloads are arrays of website-specific records. Occasional repeated records model an updated item delivered twice: use `product_id`, `comment_id`, `post_id`, `review_id`, or `job_id` as the stable key for its dataset and retain the last occurrence. Empty text and null optional fields are valid extracted values, not collection failures.
