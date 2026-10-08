# Ticket checkout acceptance notes

The bundled Rack application is a frozen local test double for Northstar Tickets. All names and events are fictional.

## Completed purchase

- Start at `/events` and search for `Starlight Sessions`.
- Two events share that title. Choose the listing at **Harbor Hall**, not the one at Pine Loft.
- On checkout, select 2 tickets, enter attendee `Alex Rowan` and `alex.rowan@example.test`, then apply promo code `NIGHT5`.
- The promo reduces the $70.00 subtotal by $5.00. The page shows `Promo NIGHT5 applied` and `Total: $65.00`.
- Placing the order ends at `/orders/EVT-007`. The confirmation identifies Harbor Hall, 2 tickets, and $65.00.

## Sold-out event

- Searching for `Riverglass Matinee` returns the Willow Pavilion listing.
- The listing is visibly marked `Sold out` and cannot be selected for checkout.

## Invalid promotion

- `SUNSET10` is not a valid promotion for EVT-007.
- Applying it shows `Promo code isn't valid`, leaves the total at $70.00 for 2 tickets, and does not show an applied-promo message.
