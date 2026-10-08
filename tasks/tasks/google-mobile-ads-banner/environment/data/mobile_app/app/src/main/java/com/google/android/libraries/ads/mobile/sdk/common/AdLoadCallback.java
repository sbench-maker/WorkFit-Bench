package com.google.android.libraries.ads.mobile.sdk.common;

public interface AdLoadCallback<T> {
    void onAdLoaded(T ad);
    void onAdFailedToLoad(LoadAdError adError);
}
