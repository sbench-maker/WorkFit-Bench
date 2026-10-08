# SP-184: move browser-coupled Side Panel coverage

The `side_panel_unittests` shard has become unreliable because some tests build
partial browser and window objects that production never exposes in that state.
Move behavior that needs a committed page, a render process, or a native app
window into `side_panel_browser_tests`. Keep fast guards and formatting logic in
the unit target. The plan must cover ChromeOS setup and shutdown because the
same change will run on Lacros-style bots.

No production behavior change is requested. The implementation owner wants a
test-by-test disposition and enough file/build detail to split the work safely.
