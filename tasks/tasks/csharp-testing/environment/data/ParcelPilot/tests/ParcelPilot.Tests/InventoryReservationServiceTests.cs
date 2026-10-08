using FluentAssertions;
using NSubstitute;
using ParcelPilot.Reservations;
using Xunit;

namespace ParcelPilot.Tests;

public sealed class InventoryReservationServiceTests
{
    [Fact]
    public async Task ReserveAsync_ReturnsSuccess_ForOneAvailableLine()
    {
        var gateway = Substitute.For<IInventoryGateway>();
        gateway.GetAvailableAsync("NORTH", "BOX-1", Arg.Any<CancellationToken>())
            .Returns(3);
        var service = new InventoryReservationService(gateway);
        var request = new ReservationRequest(
            "req-001",
            "north",
            new[] { new ReservationLine("box-1", 2) });

        var result = await service.ReserveAsync(request, CancellationToken.None);

        result.IsSuccess.Should().BeTrue();
    }
}
