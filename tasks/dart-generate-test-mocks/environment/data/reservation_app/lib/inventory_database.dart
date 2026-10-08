class StockItem {
  const StockItem({
    required this.sku,
    required this.onHand,
    required this.reserved,
    required this.active,
  });

  final String sku;
  final int onHand;
  final int reserved;
  final bool active;
}

class ReservationEntry {
  const ReservationEntry({
    required this.requestId,
    required this.sku,
    required this.quantity,
    required this.createdAt,
  });

  final String requestId;
  final String sku;
  final int quantity;
  final DateTime createdAt;
}

class AuditEvent {
  const AuditEvent({
    required this.requestId,
    required this.sku,
    required this.quantity,
    required this.recordedAt,
  });

  final String requestId;
  final String sku;
  final int quantity;
  final DateTime recordedAt;
}

abstract class InventoryDatabase {
  Future<ReservationEntry?> findReservation(String requestId);

  Future<StockItem?> findStock(String sku);

  Future<void> updateReserved(String sku, int reserved);

  Future<void> insertReservation(ReservationEntry entry);

  Future<void> appendAudit(AuditEvent event);
}

abstract class TimeSource {
  DateTime now();
}
