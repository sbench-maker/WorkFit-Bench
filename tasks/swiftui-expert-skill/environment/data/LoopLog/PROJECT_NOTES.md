# LoopLog activity feed

LoopLog is a fictional, dependency-free iOS 17 SwiftUI app. The app owns one
`ActivityStore` and passes it into the feed. Server sync may replace, insert, or
reorder activities while the feed is on screen.

The feed supports text search, newest/oldest sorting, a favorites-only filter,
detail navigation, and an empty-search state. A favorite tap must mutate the
activity with that UUID, even when titles or timestamps repeat and the visible
list is filtered or reordered. The heart change uses the existing short scale
animation. Every row exposes one clear VoiceOver favorite/remove-favorite
action.

All interface copy and dynamic date, distance, and count text must follow the
active locale. English and Japanese are the supported localizations. Product
copy lives in `Localizable.xcstrings`; activity titles are user content and
must not be translated. The bundled `Activities.json` is deterministic preview
and regression data, not a live service.

Keep the existing type names and minimum iOS version so the fixture tests remain
meaningful. Files may be reorganized, but do not add packages or UIKit bridges.
