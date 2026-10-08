package com.google.android.libraries.ads.mobile.sdk.rewarded;

import com.google.android.libraries.ads.mobile.sdk.common.FullScreenContentError;

public interface RewardedAdEventCallback {
    default void onAdShowedFullScreenContent() {}

    default void onAdDismissedFullScreenContent() {}

    default void onAdFailedToShowFullScreenContent(FullScreenContentError adError) {}
}
