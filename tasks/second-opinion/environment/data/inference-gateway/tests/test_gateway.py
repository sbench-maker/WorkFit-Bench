from gateway.auth import may_route
from gateway.batching import build_batches


def test_matching_scope_routes():
    request = {"claims": {"scopes": ["route:summarizer-v2"]}, "metadata": {}}
    assert may_route(request, "summarizer-v2")


def test_internal_probe_routes_without_claims():
    request = {"claims": {"scopes": []}, "metadata": {"x_internal": True}}
    assert may_route(request, "summarizer-v2")


def test_small_requests_are_batched():
    requests = [{"token_count": 120}, {"token_count": 180}]
    assert len(build_batches(requests, 500)) == 1
