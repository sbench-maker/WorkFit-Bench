import Foundation
import Observation

@MainActor
@Observable
final class ActivityStore {
    var activities: [Activity]

    init(activities: [Activity]) {
        self.activities = activities
    }

    func toggleFavorite(id: Activity.ID) {
        guard let index = activities.firstIndex(where: { $0.id == id }) else {
            return
        }
        activities[index].isFavorite.toggle()
    }

    static var preview: ActivityStore {
        ActivityStore(activities: [
            Activity(
                id: UUID(uuidString: "00000000-0000-4000-8000-000000000001")!,
                title: "Cedar Loop",
                kind: .hike,
                distanceKilometers: 8.4,
                startedAt: Date(timeIntervalSince1970: 1_735_732_800),
                isFavorite: true
            ),
            Activity(
                id: UUID(uuidString: "00000000-0000-4000-8000-000000000002")!,
                title: "Morning Spin",
                kind: .ride,
                distanceKilometers: 22.75,
                startedAt: Date(timeIntervalSince1970: 1_735_646_400),
                isFavorite: false
            )
        ])
    }
}
