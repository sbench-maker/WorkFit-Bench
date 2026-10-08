package com.google.android.libraries.ads.mobile.sdk.common;

import java.util.Objects;

public final class AdRequest {
    private final String adUnitId;

    private AdRequest(String adUnitId) {
        this.adUnitId = adUnitId;
    }

    public String getAdUnitId() {
        return adUnitId;
    }

    public static final class Builder {
        private final String adUnitId;

        public Builder(String adUnitId) {
            this.adUnitId = Objects.requireNonNull(adUnitId, "adUnitId");
        }

        public AdRequest build() {
            if (adUnitId.isBlank()) {
                throw new IllegalArgumentException("adUnitId must not be blank");
            }
            return new AdRequest(adUnitId);
        }
    }
}
