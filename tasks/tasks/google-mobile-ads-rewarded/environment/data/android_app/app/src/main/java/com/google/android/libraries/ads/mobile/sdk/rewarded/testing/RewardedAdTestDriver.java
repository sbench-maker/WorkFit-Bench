package com.google.android.libraries.ads.mobile.sdk.rewarded.testing;

import com.google.android.libraries.ads.mobile.sdk.common.AdLoadCallback;
import com.google.android.libraries.ads.mobile.sdk.common.AdRequest;
import com.google.android.libraries.ads.mobile.sdk.common.LoadAdError;
import com.google.android.libraries.ads.mobile.sdk.rewarded.RewardedAd;

/** Deterministic load driver; callbacks deliberately execute as SDK background callbacks. */
public final class RewardedAdTestDriver {
    private static AdRequest pendingRequest;
    private static AdLoadCallback<RewardedAd> pendingCallback;
    private static int loadCount;
    private static final ThreadLocal<Boolean> IN_SDK_CALLBACK = ThreadLocal.withInitial(() -> false);

    private RewardedAdTestDriver() {}

    public static void reset() {
        pendingRequest = null;
        pendingCallback = null;
        loadCount = 0;
        IN_SDK_CALLBACK.set(false);
    }

    public static void captureLoad(AdRequest request, AdLoadCallback<RewardedAd> callback) {
        pendingRequest = request;
        pendingCallback = callback;
        loadCount += 1;
    }

    public static int getLoadCount() {
        return loadCount;
    }

    public static AdRequest getPendingRequest() {
        return pendingRequest;
    }

    public static boolean isInSdkCallback() {
        return IN_SDK_CALLBACK.get();
    }

    public static void completeLoad(RewardedAd ad) {
        AdLoadCallback<RewardedAd> callback = takeCallback();
        invokeSdkCallback(() -> callback.onAdLoaded(ad));
    }

    public static void failLoad(String message) {
        AdLoadCallback<RewardedAd> callback = takeCallback();
        invokeSdkCallback(() -> callback.onAdFailedToLoad(new LoadAdError(message)));
    }

    public static void invokeSdkCallback(Runnable action) {
        boolean previous = IN_SDK_CALLBACK.get();
        IN_SDK_CALLBACK.set(true);
        try {
            action.run();
        } finally {
            IN_SDK_CALLBACK.set(previous);
        }
    }

    private static AdLoadCallback<RewardedAd> takeCallback() {
        if (pendingCallback == null) {
            throw new IllegalStateException("no pending load callback");
        }
        AdLoadCallback<RewardedAd> callback = pendingCallback;
        pendingCallback = null;
        pendingRequest = null;
        return callback;
    }
}
