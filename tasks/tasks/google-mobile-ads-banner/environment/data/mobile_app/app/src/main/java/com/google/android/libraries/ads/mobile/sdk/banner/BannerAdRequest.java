package com.google.android.libraries.ads.mobile.sdk.banner;

public final class BannerAdRequest {
    private final String adUnitId;
    private final AdSize adSize;

    private BannerAdRequest(String adUnitId, AdSize adSize) {
        this.adUnitId = adUnitId;
        this.adSize = adSize;
    }

    public String getAdUnitId() {
        return adUnitId;
    }

    public AdSize getAdSize() {
        return adSize;
    }

    public static final class Builder {
        private final String adUnitId;
        private final AdSize adSize;

        public Builder(String adUnitId, AdSize adSize) {
            if (adUnitId == null || adUnitId.isBlank() || adSize == null) {
                throw new IllegalArgumentException("Ad unit and size are required");
            }
            this.adUnitId = adUnitId;
            this.adSize = adSize;
        }

        public BannerAdRequest build() {
            return new BannerAdRequest(adUnitId, adSize);
        }
    }
}
