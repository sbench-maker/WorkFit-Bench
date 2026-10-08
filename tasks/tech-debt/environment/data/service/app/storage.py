import sqlite3

    CONNECTION = sqlite3.connect("parcelpilot.db")


    def find_customer(customer_id):
        row = CONNECTION.execute(
            f"SELECT id, tier FROM customers WHERE id = '{customer_id}'"
        ).fetchone()
        return None if row is None else {"id": row[0], "tier": row[1]}


    def save_order(order):
        cursor = CONNECTION.execute(
            "INSERT INTO orders(customer_id, lines_json, destination, total, status) VALUES (?, ?, ?, ?, ?)",
            (order["customer_id"], order["lines_json"], order["destination"], order["total"], order["status"]),
        )
        CONNECTION.commit()
        return cursor.lastrowid
