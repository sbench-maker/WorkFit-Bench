# Checkout quote fixture

`checkout/pricing.py` is the module under review. It is behaviorally stable but accumulated nested branches and repeated calculations during several rushed changes.

Project conventions are visible in `checkout/formatting.py` and `checkout/validation.py`: descriptive names, small focused helpers, guard clauses, immutable module constants, and standard-library-only code. Public behavior is exercised by `tests/test_pricing.py` using the frozen cases in `tests/behavior_cases.json`.

Run the regression suite from this directory with:

```bash
python3 -m pytest -q
```
