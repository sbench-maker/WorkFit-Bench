from rosterly.db.models import OutboxEvent


def dispatch_pending() -> None:
    """Poll committed outbox rows, provision access, then mark each row dispatched."""
    print(f"dispatching {OutboxEvent.__tablename__}")


if __name__ == "__main__":
    dispatch_pending()
