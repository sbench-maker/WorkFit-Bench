# Browse banner integration brief

The Browse screen is a scrolling product feed backed by 240 fictional catalog rows. Add one sponsored banner slot after the first six product rows so it scrolls with the feed; it must not be attached as a fixed child of the screen root.

Development validation uses a 360 dp viewport and Google test traffic. The local SDK mock accepts the Android banner test ad unit `ca-app-pub-3940256099942544/9214589741` and invokes both success and failure callbacks from a worker thread.

While loading, the existing status label may remain visible. A successful load should show the banner and communicate that sponsored content is ready. A failed load should keep the banner hidden and communicate that sponsored content is unavailable. UI mutations must remain safe when the callback is not on the UI thread.

Do not change catalog search or refresh behavior. Add a short production handoff note explaining that the test ad unit must be replaced before release; do not add a real ad unit or any credential.
