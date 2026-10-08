package com.google.android.libraries.ads.mobile.sdk.banner;

import com.google.android.libraries.ads.mobile.sdk.common.AdLoadCallback;
import com.google.android.libraries.ads.mobile.sdk.common.LoadAdError;
import com.shopwave.platform.View;

public final class AdView extends View {
    private final Object context;
    private BannerAdRequest lastRequest;
    private int loadCount;

    public AdView(Object context) {
        this.context = context;
        setVisibility(Visibility.GONE);
    }

    public Object getContext() {
        return context;
    }

    public BannerAdRequest getLastRequest() {
        return lastRequest;
    }

    public int getLoadCount() {
        return loadCount;
    }

    public void loadAd(BannerAdRequest adRequest, AdLoadCallback<BannerAd> callback) {
        if (adRequest == null || callback == null) {
            throw new IllegalArgumentException("Request and callback are required");
        }
        lastRequest = adRequest;
        loadCount++;
        MockAdServer.Outcome captured = MockAdServer.outcome();
        Thread worker = new Thread(() -> {
            try {
                if (captured == MockAdServer.Outcome.SUCCESS) {
                    callback.onAdLoaded(new BannerAd(adRequest));
                } else {
                    callback.onAdFailedToLoad(new LoadAdError(3, "No fill in offline fixture"));
                }
            } catch (Throwable failure) {
                MockAdServer.recordCallbackFailure(failure);
            }
        }, "gma-mock-callback");
        MockAdServer.register(worker);
        worker.start();
    }
}
