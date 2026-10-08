import Foundation

enum ActivityKind: String, CaseIterable, Codable, Hashable {
    case hike
    case ride
    case run

    var displayName: String {
        switch self {
        case .hike: return "Hike"
        case .ride: return "Ride"
        case .run: return "Run"
        }
    }
}

struct Activity: Identifiable, Codable, Hashable {
    let id: UUID
    var title: String
    let kind: ActivityKind
    let distanceKilometers: Double
    let startedAt: Date
    var isFavorite: Bool
}
