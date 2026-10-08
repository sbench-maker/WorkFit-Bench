import 'inventory_database.dart';

class ReservationRequest {
  const ReservationRequest({
    required this.requestId,
    required this.sku,
    required this.quantity,
  });

  final String requestId;
  final String sku;
  final int quantity;
}

enum ReservationStatus { approved, rejected, duplicate }

enum RejectionReason { unknownSku, inactiveSku, insufficientStock }

class ReservationResult {
  const ReservationResult({
    required this.status,
    this.reason,
    this.entry,
  });

  final ReservationStatus status;
  final RejectionReason? reason;
  final ReservationEntry? entry;
}

class ReservationService {
  const ReservationService(this.database, this.clock);

  final InventoryDatabase database;
  final TimeSource clock;

  Future<ReservationResult> reserve(ReservationRequest request) async {
    if (request.quantity <= 0) {
      throw ArgumentError.value(request.quantity, 'quantity', 'must be positive');
    }

    final existing = await database.findReservation(request.requestId);
    if (existing != null) {
      return ReservationResult(
        status: ReservationStatus.duplicate,
        entry: existing,
      );
    }

    final stock = await database.findStock(request.sku);
    if (stock == null) {
      return const ReservationResult(
        status: ReservationStatus.rejected,
        reason: RejectionReason.unknownSku,
      );
    }
    if (!stock.active) {
      return const ReservationResult(
        status: ReservationStatus.rejected,
        reason: RejectionReason.inactiveSku,
      );
    }

    final available = stock.onHand - stock.reserved;
    if (available < request.quantity) {
      return const ReservationResult(
        status: ReservationStatus.rejected,
        reason: RejectionReason.insufficientStock,
      );
    }

    final createdAt = clock.now();
    final entry = ReservationEntry(
      requestId: request.requestId,
      sku: request.sku,
      quantity: request.quantity,
      createdAt: createdAt,
    );
    final newReserved = stock.reserved + request.quantity;

    await database.updateReserved(request.sku, newReserved);
    try {
      await database.insertReservation(entry);
    } catch (_) {
      await database.updateReserved(request.sku, stock.reserved);
      rethrow;
    }
    await database.appendAudit(
      AuditEvent(
        requestId: request.requestId,
        sku: request.sku,
        quantity: request.quantity,
        recordedAt: createdAt,
      ),
    );

    return ReservationResult(
      status: ReservationStatus.approved,
      entry: entry,
    );
  }
}
