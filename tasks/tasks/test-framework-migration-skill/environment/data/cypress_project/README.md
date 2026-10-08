# Northstar Checkout Cypress project

This frozen, fictional project is the source suite for a framework migration. It has no external service dependency.

Run the local application with `node app/server.js`; it listens on `PORT` (default `4173`). The Cypress configuration uses `http://127.0.0.1:4173`.

Checkout rules:

- Standard shipping costs $5.00 below a $100.00 subtotal and is free at or above $100.00.
- Express shipping costs $15.00.
- Promo code `SAVE10` is case-insensitive and discounts the item subtotal by 10%, rounded to the nearest cent.
- Out-of-stock products cannot be submitted for a quote.
- A pricing-service failure must show a retryable error without showing an order confirmation.
- A successful order exposes its receipt in a new browser tab.

All products and order identifiers in this fixture are constructed examples.
