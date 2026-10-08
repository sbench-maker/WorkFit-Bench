# Reservation service test brief

`ReservationService` reserves inventory through an asynchronous database gateway. Tests must isolate that gateway; they must never connect to a real database.

Business rules:

1. Quantities must be positive. Invalid requests fail before any database call.
2. A previously stored request is idempotent: return it as `duplicate` without reading stock or writing anything.
3. Missing or inactive stock is rejected with the corresponding reason and no writes.
4. The available quantity is `onHand - reserved`. A request for exactly the available quantity is allowed; insufficient requests are rejected without writes.
5. Approval updates the reserved quantity, inserts the reservation, then appends an audit event, in that order. All persisted records use the injected clock value.
6. If inserting the reservation fails after the stock update, restore the original reserved quantity, do not append an audit event, and rethrow the original error.
7. If the first stock update itself fails, do not attempt an insert, audit, or compensating update.

The checked-in test file is only a placeholder. Replace it with a focused Mockito suite and generate its `.mocks.dart` companion with `build_runner`.
