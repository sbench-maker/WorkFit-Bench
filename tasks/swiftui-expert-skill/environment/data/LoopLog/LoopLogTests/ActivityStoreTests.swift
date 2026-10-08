import XCTest
@testable import LoopLog

@MainActor
final class ActivityStoreTests: XCTestCase {
    func testFavoriteMutationUsesStableIDWithDuplicateTitles() {
        let first = Activity(
            id: UUID(uuidString: "00000000-0000-4000-8000-000000000011")!,
            title: "River Path",
            kind: .run,
            distanceKilometers: 5,
            startedAt: .distantPast,
            isFavorite: false
        )
        let second = Activity(
            id: UUID(uuidString: "00000000-0000-4000-8000-000000000012")!,
            title: "River Path",
            kind: .run,
            distanceKilometers: 10,
            startedAt: .distantFuture,
            isFavorite: false
        )
        let store = ActivityStore(activities: [first, second])

        store.toggleFavorite(id: second.id)

        XCTAssertFalse(store.activities[0].isFavorite)
        XCTAssertTrue(store.activities[1].isFavorite)
    }
}
