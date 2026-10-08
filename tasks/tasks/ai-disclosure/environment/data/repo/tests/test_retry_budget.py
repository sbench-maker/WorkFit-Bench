from src.retry_budget import RetryBudget


def test_budget_exhausts_at_capacity():
    budget = RetryBudget(capacity=2)
    assert budget.allow_retry(now=10)
    assert budget.allow_retry(now=11)
    assert not budget.allow_retry(now=12)


def test_window_rollover_releases_capacity():
    budget = RetryBudget(capacity=2, window_seconds=60)
    assert budget.allow_retry(now=10)
    assert budget.allow_retry(now=11)
    assert budget.allow_retry(now=70)


def test_remaining_is_a_non_negative_snapshot():
    budget = RetryBudget(capacity=1)
    assert budget.allow_retry(now=5)
    assert budget.remaining_at(now=6) == 0
