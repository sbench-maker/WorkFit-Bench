import SwiftUI

@main
struct LoopLogApp: App {
    @State private var store = ActivityStore.preview

    var body: some Scene {
        WindowGroup {
            ActivityFeedView(store: store)
        }
    }
}
