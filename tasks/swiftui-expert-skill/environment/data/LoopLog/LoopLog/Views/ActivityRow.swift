import SwiftUI

struct ActivityRow: View {
    @State var activity: Activity
    let onToggleFavorite: () -> Void

    private static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "MM/dd/yyyy"
        return formatter
    }()

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(activity.title)
                    .font(.headline)
                Text(activity.kind.displayName)
                    .foregroundColor(.secondary)
                Text(Self.dateFormatter.string(from: activity.startedAt))
                    .font(.caption)
            }

            Spacer()

            Text(String(format: "%.1f km", activity.distanceKilometers))
                .frame(width: 72, alignment: .right)

            Image(systemName: activity.isFavorite ? "heart.fill" : "heart")
                .foregroundColor(activity.isFavorite ? .red : .secondary)
                .scaleEffect(activity.isFavorite ? 1.12 : 1)
                .onTapGesture {
                    onToggleFavorite()
                }
                .accessibility(label: Text(activity.isFavorite ? "Remove favorite" : "Favorite"))
        }
    }
}
