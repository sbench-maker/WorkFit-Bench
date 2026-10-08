namespace ParcelPilot.Reservations;

public sealed record ReservationLine(string Sku, int Quantity);

public sealed record ReservationRequest(
    string RequestId,
    string WarehouseCode,
    IReadOnlyList<ReservationLine>? Lines);

public sealed record ReservedLine(string Sku, int Quantity);

public sealed record ReservationResult(
    bool IsSuccess,
    string? Error,
    int TotalUnits,
    IReadOnlyList<ReservedLine> Lines)
{
    public static ReservationResult Failure(string error) =>
        new(false, error, 0, Array.Empty<ReservedLine>());

    public static ReservationResult Success(int totalUnits, IReadOnlyList<ReservedLine> lines) =>
        new(true, null, totalUnits, lines);
}
