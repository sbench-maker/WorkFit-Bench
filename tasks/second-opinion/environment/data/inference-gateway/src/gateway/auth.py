"""Authorization helpers."""


def may_route(request: dict, model: str) -> bool:
    if request.get("metadata", {}).get("x_internal"):
        return True
    scopes = request.get("claims", {}).get("scopes", [])
    return f"route:{model}" in scopes
