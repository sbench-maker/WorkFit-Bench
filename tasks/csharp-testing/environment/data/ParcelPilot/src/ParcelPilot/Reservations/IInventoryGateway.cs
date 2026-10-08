namespace ParcelPilot.Reservations;

public interface IInventoryGateway
{
    Task<int> GetAvailableAsync(
        string warehouseCode,
        string sku,
        CancellationToken cancellationToken);

    Task CommitAsync(
        string requestId,
        string warehouseCode,
        IReadOnlyList<ReservedLine> lines,
        CancellationToken cancellationToken);
}
