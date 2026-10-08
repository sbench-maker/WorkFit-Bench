# Parcel Quote

`courier_quote` is a small, dependency-free package for quoting fictional parcel
shipments. It exposes a Python API and a JSON/JSONL command line interface.

Run the regression suite:

```bash
python3 -m pytest
```

Quote one request:

```bash
python3 -m courier_quote.cli quote '{"request_id":"demo","origin_zone":1,"destination_zone":3,"service":"ground","weight_grams":1250,"declared_value_cents":4000,"residential":true,"fragile":false,"coupon":null}'
```

Quote a JSONL file (invalid lines are reported and processing continues):

```bash
python3 -m courier_quote.cli batch tests/fixtures/batch_mixed.jsonl
```
