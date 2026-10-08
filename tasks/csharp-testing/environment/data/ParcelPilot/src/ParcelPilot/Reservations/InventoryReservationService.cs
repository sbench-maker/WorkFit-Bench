namespace ParcelPilot.Reservations;

public sealed class InventoryReservationService
{
    private readonly IInventoryGateway _gateway;

    public InventoryReservationService(IInventoryGateway gateway)
    {
        _gateway = gateway ?? throw new ArgumentNullException(nameof(gateway));
    }

    public async Task<ReservationResult> ReserveAsync(
        ReservationRequest request,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        cancellationToken.ThrowIfCancellationRequested();

        if (string.IsNullOrWhiteSpace(request.RequestId))
        {
            return ReservationResult.Failure("RequestId is required.");
        }

        if (string.IsNullOrWhiteSpace(request.WarehouseCode))
        {
            return ReservationResult.Failure("WarehouseCode is required.");
        }

        if (request.Lines is null || request.Lines.Count == 0)
        {
            return ReservationResult.Failure("At least one reservation line is required.");
        }

        foreach (var line in request.Lines)
        {
            if (string.IsNullOrWhiteSpace(line.Sku))
            {
                return ReservationResult.Failure("SKU is required.");
            }

            if (line.Quantity is < 1 or > 50)
            {
                return ReservationResult.Failure("Quantity must be between 1 and 50.");
            }
        }

        var warehouse = request.WarehouseCode.Trim().ToUpperInvariant();
        var grouped = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        foreach (var line in request.Lines)
        {
            var sku = line.Sku.Trim().ToUpperInvariant();
            grouped[sku] = grouped.GetValueOrDefault(sku) + line.Quantity;
        }

        foreach (var line in grouped)
        {
            var available = await _gateway.GetAvailableAsync(
                warehouse,
                line.Key,
                cancellationToken);
            if (available < line.Value)
            {
                return ReservationResult.Failure($"Insufficient inventory for {line.Key}.");
            }
        }

        var reservedLines = grouped
            .Select(pair => new ReservedLine(pair.Key, pair.Value))
            .ToArray();
        await _gateway.CommitAsync(
            request.RequestId.Trim(),
            warehouse,
            reservedLines,
            cancellationToken);

        return ReservationResult.Success(grouped.Values.Sum(), reservedLines);
    }
}
