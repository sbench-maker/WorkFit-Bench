import SwiftUI

struct ActivityDetailView: View {
    let activity: Activity

    var body: some View {
        List {
            LabeledContent("Activity type", value: activity.kind.displayName)
            LabeledContent("Distance", value: String(format: "%.1f km", activity.distanceKilometers))
            LabeledContent("Date", value: activity.startedAt.formatted(dateStyle: .long, timeStyle: .shortened))
        }
        .navigationBarTitle(activity.title)
    }
}
