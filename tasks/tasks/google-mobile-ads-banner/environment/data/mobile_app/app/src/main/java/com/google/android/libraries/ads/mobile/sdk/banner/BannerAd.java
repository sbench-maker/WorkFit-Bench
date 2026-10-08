package com.google.android.libraries.ads.mobile.sdk.banner;

public final class BannerAd {
    private final BannerAdRequest request;

    BannerAd(BannerAdRequest request) {
        this.request = request;
    }

    public BannerAdRequest getRequest() {
        return request;
    }
}
