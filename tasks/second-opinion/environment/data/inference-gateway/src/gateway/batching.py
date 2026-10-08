"""Batch construction helpers."""


def build_batches(requests: list[dict], max_tokens: int) -> list[list[dict]]:
    batches: list[list[dict]] = []
    current: list[dict] = []
    used = 0
    for request in requests:
        token_count = int(request["token_count"])
        if current and used + token_count > max_tokens:
            batches.append(current)
            current = []
            used = 0
        current.append(request)
        used += token_count
    if current:
        batches.append(current)
    return batches
