# Reward boost Android sample

This directory is a small, offline-compilable model of the reward boost screen. The Google Mobile Ads classes under `com/google/...` preserve the rewarded-ad objects and callback lifecycle while replacing the remote ad service with a deterministic test driver.

Complete `app/src/main/java/com/asterlane/game/RewardedBoostController.java`. Keep its package, public class name, constructor, and public methods unchanged; the completed file is intended to replace that source file directly.

## Screen contract

- The placement uses ad unit ID `demo-rewarded-boost` from `placement.properties`.
- The watch button starts disabled and remains disabled while an ad is loading or unavailable.
- `load()` requests a rewarded ad. A successful load registers its full-screen event callback before enabling the watch button. A failed load leaves no usable ad.
- `onWatchAdClicked()` is the opt-in action. It presents at most one currently loaded ad and disables the button while that ad is being used. Loading an ad must never present it automatically.
- Credit `RewardWallet` only through the ad's earned-reward callback, using the `RewardItem` type and amount supplied by the SDK unchanged. Do not grant a reward merely because the ad was shown, dismissed, or failed.
- When full-screen content is dismissed or fails to present, discard that ad and immediately start loading a replacement.
- GMA load, reward, and full-screen event callbacks run on a background thread in this fixture. Every call that changes `RewardedBoostView` must therefore execute inside `RewardedBoostView.runOnUiThread(...)` when it originates in one of those callbacks.

## Offline compile check

From this directory, after placing the completed controller back at its source path:

```sh
find app/src/main/java -name '*.java' -print0 | xargs -0 javac -d /tmp/rewarded-build
```

No network service or credential is used by this sample.
