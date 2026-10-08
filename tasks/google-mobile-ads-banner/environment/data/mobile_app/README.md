# Shopwave Mobile (offline fixture)

This repository is a compact Android-shaped Java project for the fictional Shopwave catalog. It includes local UI and Google Mobile Ads interfaces so banner integration can be built and exercised without Android Studio, a device, credentials, or network access.

The implementation target is `app/src/main/java/com/shopwave/browse/BrowseActivity.java`. Product-feed behavior lives in `ProductFeedAdapter.java`, and the product-team constraints are in `docs/banner_integration_brief.md`.

Build from the project root with:

```bash
./gradlew build -x test
```

The launcher compiles all Java sources into `build/classes` and packages `build/shopwave-mobile.jar` using only the JDK bundled in the task image.
