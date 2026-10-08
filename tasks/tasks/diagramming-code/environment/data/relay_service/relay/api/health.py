"""A request handler that cannot reach template execution."""

from relay.framework import Request, public_route


@public_route("/health")
def health_check(request: Request) -> dict[str, str]:
    del request
    return {"status": "ok"}
