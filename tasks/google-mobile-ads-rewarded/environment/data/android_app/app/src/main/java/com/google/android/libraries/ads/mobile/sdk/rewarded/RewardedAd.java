package com.google.android.libraries.ads.mobile.sdk.rewarded;

import com.google.android.libraries.ads.mobile.sdk.common.AdLoadCallback;
import com.google.android.libraries.ads.mobile.sdk.common.AdRequest;
import com.google.android.libraries.ads.mobile.sdk.rewarded.testing.RewardedAdTestDriver;

/** Offline GMA rewarded-ad stand-in used by this fixture. */
public class RewardedAd {
    private RewardedAdEventCallback eventCallback;
    private OnUserEarnedRewardListener rewardListener;
    private int showCount;

    public static void load(AdRequest adRequest, AdLoadCallback<RewardedAd> callback) {
        RewardedAdTestDriver.captureLoad(adRequest, callback);
    }

    public void setAdEventCallback(RewardedAdEventCallback callback) {
        this.eventCallback = callback;
    }

    public RewardedAdEventCallback getAdEventCallback() {
        return eventCallback;
    }

    public void show(OnUserEarnedRewardListener listener) {
        showCount += 1;
        rewardListener = listener;
    }

    public int getShowCount() {
        return showCount;
    }

    public void emitReward(RewardItem item) {
        if (rewardListener == null) {
            throw new IllegalStateException("ad has not been shown");
        }
        RewardedAdTestDriver.invokeSdkCallback(() -> rewardListener.onUserEarnedReward(item));
    }

    public void emitDismissed() {
        if (eventCallback == null) {
            throw new IllegalStateException("event callback was not registered");
        }
        RewardedAdTestDriver.invokeSdkCallback(eventCallback::onAdDismissedFullScreenContent);
    }

    public void emitFailedToShow(String message) {
        if (eventCallback == null) {
            throw new IllegalStateException("event callback was not registered");
        }
        RewardedAdTestDriver.invokeSdkCallback(
                () -> eventCallback.onAdFailedToShowFullScreenContent(
                        new com.google.android.libraries.ads.mobile.sdk.common.FullScreenContentError(message)));
    }
}
