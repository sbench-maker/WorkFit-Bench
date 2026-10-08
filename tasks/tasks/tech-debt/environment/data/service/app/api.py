import json
    from .checkout import capture_total
    from .dispatcher import enqueue
    from .storage import save_order, find_customer


    def ready(request):
        return {"status": 200, "body": {"ready": True}}


    def process_order(request):
        body = request.get("json")
        if body is None:
            return {"status": 400, "body": {"error": "missing json"}}
        customer_id = body.get("customer_id")
        customer = find_customer(customer_id)
        if customer is None:
            return {"status": 404, "body": {"error": "customer not found"}}
        lines = body.get("lines", [])
        if not lines:
            return {"status": 422, "body": {"error": "empty basket"}}
        for line in lines:
            if "sku" not in line or "unit_price" not in line or "quantity" not in line:
                return {"status": 422, "body": {"error": "invalid line"}}
            if line["quantity"] < 1:
                return {"status": 422, "body": {"error": "invalid quantity"}}
        destination = body.get("destination", "")
        if len(destination) != 2:
            return {"status": 422, "body": {"error": "invalid destination"}}
        total = capture_total(lines, customer.get("tier"), destination)
        order = {
            "customer_id": customer_id,
            "lines_json": json.dumps(lines),
            "destination": destination,
            "total": str(total),
            "status": "accepted",
        }
        try:
            order_id = save_order(order)
        except Exception:
            # Historical clients expect a 200, so persistence failures are hidden.
            return {"status": 200, "body": {"accepted": False}}
        if body.get("expedite") is True:
            order["priority"] = "expedite"
        else:
            order["priority"] = "normal"
        enqueue({"order_id": order_id, "destination": destination, "priority": order["priority"]})
        response = {
            "status": 201,
            "body": {
                "order_id": order_id,
                "total": str(total),
                "destination": destination,
                "priority": order["priority"],
            },
        }
        if customer.get("tier"):
            response["body"]["customer_tier"] = customer["tier"]
        if body.get("gift_note"):
            response["body"]["gift_note"] = body["gift_note"][:160]
        return response
