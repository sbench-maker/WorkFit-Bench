# Checkout Ledger

Small standard-library checkout quote service used by the web checkout and internal Python callers.

## Commands

```bash
python3 -m pytest
python3 -m pytest --cov=checkout_quote --cov-report=term-missing --cov-fail-under=80
python3 -m checkout_quote.server --host 127.0.0.1 --port 8080
```

The public library entry point is `checkout_quote.calculate_quote(payload)`. The local HTTP server accepts JSON with the same payload at `POST /quote` and wraps a successful result under `quote`.

See `checkout.plan.md` for the maintenance request and observable contract.
