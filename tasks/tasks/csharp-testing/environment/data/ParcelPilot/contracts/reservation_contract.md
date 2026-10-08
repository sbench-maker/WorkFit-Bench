# `InventoryReservationService.ReserveAsync` contract

`ReserveAsync` validates a request, checks stock for each distinct SKU, and commits one reservation only when all requested units are available.

## Validation

- A null request throws `ArgumentNullException`.
- `RequestId` and `WarehouseCode` are required after trimming.
- At least one line is required.
- Every SKU is required after trimming, and every line quantity must be from 1 through 50 inclusive.
- Validation failures return an unsuccessful `ReservationResult` and must not call the inventory gateway.

## Normalization and availability

- Warehouse codes are trimmed and converted to upper case.
- SKUs are trimmed, converted to upper case, and grouped case-insensitively. One availability lookup is made per distinct normalized SKU, in first-appearance order.
- Duplicate quantities are summed before stock is checked. Availability equal to the requested quantity is sufficient.
- The first shortage returns an unsuccessful result naming the normalized SKU. No commit is made after a shortage.

## Successful commit

- A successful request is committed exactly once with the trimmed request ID, normalized warehouse, normalized grouped lines in first-appearance order, and the original cancellation token.
- `TotalUnits` is the sum of all submitted quantities. The successful result exposes the same normalized grouped lines sent to the commit.

## Cancellation

- An already-cancelled token throws `OperationCanceledException` before any gateway interaction.
- The original token is passed unchanged to availability lookups and the commit. Cancellation exceptions from the gateway propagate; they are not converted into a failure result, and a cancelled availability check must not lead to a commit.
