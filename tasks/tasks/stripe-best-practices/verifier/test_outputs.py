from __future__ import annotations

from contextlib import contextmanager, redirect_stderr, redirect_stdout
import hashlib
import hmac
import importlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time

import pytest


SUBMISSION = Path(os.environ.get("SUBMISSION_ROOT", "/root/results/checkout_service"))
SOURCE = Path(os.environ.get("DATA_ROOT", "/root/data/checkout_service"))
CURRENT_API_VERSION = "2026-06-24.dahlia"
REQUIRED_FILES = (
    "README.md",
    "HANDOFF.md",
    "store_config.json",
    "catalog.json",
    "orders.jsonl",
    "webhook_samples.jsonl",
    "webhook_state.json",
    "checkout_service/__init__.py",
    "checkout_service/service.py",
    "checkout_service/stripe_mock.py",
)


def _usable_submission() -> tuple[bool, str]:
    if not SUBMISSION.is_dir():
        return False, f"missing submitted repository: {SUBMISSION}"
    missing = [name for name in REQUIRED_FILES if not (SUBMISSION / name).is_file()]
    if missing:
        return False, "missing repository files: " + ", ".join(missing)
    try:
        orders = [
            json.loads(line)
            for line in (SUBMISSION / "orders.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        json.loads((SUBMISSION / "store_config.json").read_text(encoding="utf-8"))
        json.loads((SUBMISSION / "webhook_state.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return False, f"repository data is unreadable: {exc}"
    if not orders:
        return False, "orders.jsonl is empty"
    return True, ""


def _require_usable() -> None:
    usable, reason = _usable_submission()
    if not usable:
        pytest.skip(f"artifact usability root failure already covers semantic checks: {reason}")


def _reset_imports() -> None:
    for name in list(sys.modules):
        if name == "checkout_service" or name.startswith("checkout_service."):
            sys.modules.pop(name, None)


@contextmanager
def _fresh_repo():
    _require_usable()
    temp_root = Path(tempfile.mkdtemp(prefix="checkout-service-"))
    repo = temp_root / "checkout_service"
    try:
        shutil.copytree(SUBMISSION, repo)
        for name in (
            "store_config.json",
            "catalog.json",
            "orders.jsonl",
            "webhook_samples.jsonl",
            "webhook_state.json",
        ):
            shutil.copy2(SOURCE / name, repo / name)
        _reset_imports()
        sys.path.insert(0, str(repo))
        module = importlib.import_module("checkout_service.service")
        yield repo, module
    finally:
        if str(repo) in sys.path:
            sys.path.remove(str(repo))
        _reset_imports()
        shutil.rmtree(temp_root, ignore_errors=True)


def _orders(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _order(path: Path, order_id: str) -> dict:
    return next(row for row in _orders(path) if row["order_id"] == order_id)


class _Sessions:
    def __init__(self, owner):
        self.owner = owner

    def create(self, **params):
        self.owner.calls.append({"resource": "checkout.sessions", "params": params})
        return {"id": f"cs_spy_{len(self.owner.calls):04d}", **params}


class _ForbiddenResource:
    def create(self, **params):
        raise AssertionError("one-time web checkout must not use this lower-level resource")


class _Checkout:
    def __init__(self, owner):
        self.sessions = _Sessions(owner)


class _SpyClient:
    def __init__(self):
        self.calls = []
        self.checkout = _Checkout(self)
        self.charges = _ForbiddenResource()
        self.payment_intents = _ForbiddenResource()


def _environment() -> dict[str, str]:
    return {
        "STRIPE_API_KEY": "<REDACTED_API_KEY>",
        "STRIPE_WEBHOOK_SECRET": "<REDACTED_WEBHOOK_SECRET>",
    }


def _signature(raw_body: bytes, secret: str, timestamp: int) -> str:
    message = str(timestamp).encode("ascii") + b"." + raw_body
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def _event(order: dict, *, event_id: str, event_type: str = "checkout.session.completed", **changes):
    obj = {
        "id": f"cs_for_{order['order_id']}",
        "client_reference_id": order["order_id"],
        "metadata": {"order_id": order["order_id"]},
        "amount_total": order["total_minor"],
        "currency": order["currency"],
        "payment_status": "paid",
    }
    obj.update(changes.pop("object_changes", {}))
    payload = {
        "id": event_id,
        "type": event_type,
        "created": changes.pop("created", 1784548800),
        "data": {"object": obj},
    }
    payload.update(changes)
    return payload


def _raw_event(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_artifact_usability():
    """The runnable repository and handoff artifact are complete and importable."""
    usable, reason = _usable_submission()
    assert usable, reason
    with _fresh_repo() as (_, module):
        assert callable(getattr(module, "build_service", None)), (
            "the documented build_service entry point is unavailable"
        )
        service = module.build_service(_environment(), SOURCE / "orders.jsonl", _SpyClient())
        assert callable(getattr(service, "create_checkout", None)), "create_checkout is unavailable"
        assert callable(getattr(service, "handle_webhook", None)), "handle_webhook is unavailable"


@pytest.mark.parametrize("order_id", ["ord_0001", "ord_0028", "ord_0097", "ord_0179"])
def test_checkout_session_semantics(order_id):
    """Pending orders create reconciled one-time Checkout Sessions with dynamic methods."""
    with _fresh_repo() as (repo, module):
        client = _SpyClient()
        service = module.build_service(_environment(), repo / "orders.jsonl", client)
        source_order = _order(repo / "orders.jsonl", order_id)
        first = service.create_checkout(order_id)
        second = service.create_checkout(order_id)

        assert first.get("id") and second.get("id"), "checkout calls must return usable session mappings"
        assert len(client.calls) == 2, "each checkout request must create exactly one session"
        params = client.calls[0]["params"]
        assert client.calls[0]["resource"] == "checkout.sessions"
        assert params.get("mode") == "payment", "this order flow is a one-time payment"
        assert "payment_method_types" not in params, (
            "hardcoded payment method types disable the required dynamic selection"
        )
        config = json.loads((repo / "store_config.json").read_text(encoding="utf-8"))
        assert params.get("success_url") == config["success_url"]
        assert params.get("cancel_url") == config["cancel_url"]
        assert params.get("client_reference_id") == order_id
        assert params.get("metadata", {}).get("order_id") == order_id

        actual_lines = []
        for line in params.get("line_items", []):
            price = line.get("price_data", {})
            actual_lines.append(
                (
                    price.get("product_data", {}).get("name"),
                    price.get("unit_amount"),
                    str(price.get("currency", "")).lower(),
                    line.get("quantity"),
                )
            )
        expected_lines = [
            (item["name"], item["unit_amount"], source_order["currency"], item["quantity"])
            for item in source_order["items"]
        ]
        assert sorted(actual_lines) == sorted(expected_lines), (
            "Checkout line items do not preserve the stored order products, amounts, currency, and quantities"
        )
        total = sum(amount * quantity for _, amount, _, quantity in actual_lines)
        assert total == source_order["total_minor"], "the customer would be charged the wrong order total"

        labels = [call["params"].get("integration_identifier", "") for call in client.calls]
        pattern = re.compile(rf"^{re.escape(config['tracking_prefix'])}-[A-Za-z]{{8}}$")
        assert all(pattern.fullmatch(label) for label in labels), (
            "Checkout tracking labels must use the configured prefix and an eight-letter suffix"
        )
        assert len(set(labels)) == 2, "separate Checkout flows must not reuse one tracking label"


def test_checkout_rejects_nonpending_orders():
    """Paid, cancelled, and unknown orders cannot start a new checkout."""
    with _fresh_repo() as (repo, module):
        client = _SpyClient()
        service = module.build_service(_environment(), repo / "orders.jsonl", client)
        for order_id in ("ord_0181", "ord_0221", "ord_missing"):
            with pytest.raises((KeyError, ValueError, LookupError)):
                service.create_checkout(order_id)
        assert client.calls == [], "rejected orders must not create remote payment objects"


def test_configuration_boundary():
    """Credentials fail closed and the default client receives the supplied key and current version."""
    with _fresh_repo() as (repo, module):
        orders_path = repo / "orders.jsonl"
        for environment in (
            {},
            {"STRIPE_API_KEY": "", "STRIPE_WEBHOOK_SECRET": "<REDACTED_WEBHOOK_SECRET>"},
            {"STRIPE_API_KEY": "<REDACTED_API_KEY>"},
            {"STRIPE_API_KEY": "<REDACTED_API_KEY>", "STRIPE_WEBHOOK_SECRET": "   "},
        ):
            with pytest.raises((KeyError, ValueError)):
                module.build_service(environment, orders_path)

        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()
        with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
            service = module.build_service(_environment(), orders_path)
            service.create_checkout("ord_0001")
        assert getattr(service, "client", None) is not None, "the configured client is not exposed"
        assert getattr(service.client, "api_key", None) == _environment()["STRIPE_API_KEY"], (
            "the client must use the supplied deployment credential"
        )
        assert getattr(service.client, "api_version", None) == CURRENT_API_VERSION, (
            "the client is not pinned to the current version supported by the bundled mock"
        )

        text = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in repo.rglob("*")
            if path.is_file() and path.suffix.lower() in {".py", ".md", ".json"}
        )
        credential_shape = re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{8,}")
        assert not credential_shape.search(text), "the submitted repository contains a credential-shaped value"
        emitted = captured_stdout.getvalue() + captured_stderr.getvalue()
        assert _environment()["STRIPE_API_KEY"] not in emitted
        assert _environment()["STRIPE_WEBHOOK_SECRET"] not in emitted


@pytest.mark.parametrize(
    ("case", "expected_change", "expects_error"),
    [
        ("invalid_signature", False, True),
        ("stale_signature", False, True),
        ("amount_mismatch", False, True),
        ("currency_mismatch", False, True),
        ("unknown_order", False, True),
        ("missing_order_id", False, True),
        ("unpaid_completion", False, False),
        ("valid_completion", True, False),
        ("valid_async_success", True, False),
    ],
)
def test_webhook_authenticity_and_order_binding(case, expected_change, expects_error):
    """Only current, authentic, order-bound paid events may mark an order paid."""
    with _fresh_repo() as (repo, module):
        orders_path = repo / "orders.jsonl"
        source_order = _order(orders_path, "ord_0042")
        state_path = repo / "webhook_state.json"
        state_before = state_path.read_bytes()
        event_type = (
            "checkout.session.async_payment_succeeded"
            if case == "valid_async_success"
            else "checkout.session.completed"
        )
        payload = _event(source_order, event_id=f"evt_{case}", event_type=event_type)
        if case == "amount_mismatch":
            payload["data"]["object"]["amount_total"] += 1
        elif case == "currency_mismatch":
            payload["data"]["object"]["currency"] = "cad"
        elif case == "unknown_order":
            payload["data"]["object"]["metadata"]["order_id"] = "ord_unknown"
        elif case == "missing_order_id":
            payload["data"]["object"]["metadata"] = {}
        elif case == "unpaid_completion":
            payload["data"]["object"]["payment_status"] = "unpaid"

        raw_body = _raw_event(payload)
        now = int(time.time())
        timestamp = now - 301 if case == "stale_signature" else now
        signature = _signature(raw_body, _environment()["STRIPE_WEBHOOK_SECRET"], timestamp)
        if case == "invalid_signature":
            signature = f"t={timestamp},v1=" + "0" * 64

        service = module.build_service(_environment(), orders_path)
        if expects_error:
            with pytest.raises((KeyError, ValueError)):
                service.handle_webhook(raw_body, signature)
        else:
            service.handle_webhook(raw_body, signature)

        updated = _order(orders_path, source_order["order_id"])
        assert (updated["status"] == "paid") is expected_change, (
            f"{case} produced the wrong order state; untrusted or mismatched events must not fulfill orders"
        )
        if expected_change:
            assert updated.get("paid_event_id") == payload["id"]
            assert isinstance(updated.get("paid_at"), str) and updated["paid_at"], (
                "a paid transition needs an auditable event and timestamp"
            )
        if expects_error:
            assert state_path.read_bytes() == state_before, (
                f"{case} mutated webhook processing state even though the event was rejected"
            )


def test_retry_safe_state_transitions():
    """Event IDs persist across service reconstruction and terminal orders never regress."""
    with _fresh_repo() as (repo, module):
        orders_path = repo / "orders.jsonl"
        environment = _environment()
        now = int(time.time())
        pending = _order(orders_path, "ord_0075")
        completed = _event(pending, event_id="evt_retry_across_restart")
        completed_raw = _raw_event(completed)
        completed_sig = _signature(completed_raw, environment["STRIPE_WEBHOOK_SECRET"], now)

        first_service = module.build_service(environment, orders_path)
        first_service.handle_webhook(completed_raw, completed_sig)
        after_first = _order(orders_path, pending["order_id"])

        rebuilt_service = module.build_service(environment, orders_path)
        duplicate_result = rebuilt_service.handle_webhook(completed_raw, completed_sig)
        after_retry = _order(orders_path, pending["order_id"])
        assert after_retry == after_first, "a delivery retry changed an already-applied payment transition"
        assert isinstance(duplicate_result, dict), "webhook retries must remain acknowledgeable"
        state = json.loads((repo / "webhook_state.json").read_text(encoding="utf-8"))
        assert state.get("processed_event_ids", []).count(completed["id"]) == 1, (
            "processed event IDs must be persisted exactly once across service reconstruction"
        )

        expired = _event(
            after_retry,
            event_id="evt_late_expiration",
            event_type="checkout.session.expired",
        )
        expired_raw = _raw_event(expired)
        expired_sig = _signature(expired_raw, environment["STRIPE_WEBHOOK_SECRET"], now)
        rebuilt_service.handle_webhook(expired_raw, expired_sig)
        assert _order(orders_path, pending["order_id"]) == after_retry, (
            "a later non-payment event regressed a paid order"
        )

        cancelled = _order(orders_path, "ord_0225")
        late_payment = _event(cancelled, event_id="evt_cancelled_order_payment")
        late_raw = _raw_event(late_payment)
        late_sig = _signature(late_raw, environment["STRIPE_WEBHOOK_SECRET"], now)
        rebuilt_service.handle_webhook(late_raw, late_sig)
        assert _order(orders_path, cancelled["order_id"])["status"] == "cancelled", (
            "a terminal cancelled order must not be silently reopened or fulfilled"
        )
