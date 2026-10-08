"""Model dispatch with a narrow availability fallback."""


def dispatch(client, request: dict, model: str, fallback_model: str):
    try:
        return client.invoke(model, request)
    except Exception:
        return client.invoke(fallback_model, request)
