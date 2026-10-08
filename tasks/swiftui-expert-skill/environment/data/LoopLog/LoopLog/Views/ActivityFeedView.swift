import SwiftUI

struct ActivityFeedView: View {
    @State var store: ActivityStore
    @State var query = ""
    @State var favoritesOnly = false
    @State var newestFirst = true

    private var filteredActivities: [Activity] {
        store.activities
            .filter { activity in
                (!favoritesOnly || activity.isFavorite)
                    && (query.isEmpty || activity.title.localizedCaseInsensitiveContains(query))
            }
            .sorted { lhs, rhs in
                newestFirst ? lhs.startedAt > rhs.startedAt : lhs.startedAt < rhs.startedAt
            }
    }

    var body: some View {
        NavigationView {
            VStack {
                Toggle("Favorites only", isOn: $favoritesOnly)

                HStack {
                    Text("\(filteredActivities.count) activities")
                    Spacer()
                    Button(newestFirst ? "Oldest first" : "Newest first") {
                        newestFirst.toggle()
                    }
                }

                List {
                    ForEach(filteredActivities.indices, id: \.self) { index in
                        let activity = filteredActivities[index]
                        NavigationLink(destination: ActivityDetailView(activity: activity)) {
                            ActivityRow(activity: activity) {
                                store.toggleFavorite(id: store.activities[index].id)
                            }
                        }
                    }
                }
                .overlay {
                    if filteredActivities.isEmpty {
                        Text("No matching activities")
                    }
                }
                .animation(.easeInOut(duration: 0.2))
            }
            .padding(.horizontal)
            .navigationBarTitle("Activity Feed")
            .searchable(text: $query, prompt: "Search activities")
        }
    }
}

#Preview("Japanese") {
    ActivityFeedView(store: .preview)
        .environment(\.locale, Locale(identifier: "ja"))
}
