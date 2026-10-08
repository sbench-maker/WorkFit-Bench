package com.google.android.libraries.ads.mobile.sdk.common;

public final class LoadAdError {
    private final String message;

    public LoadAdError(String message) {
        this.message = message;
    }

    public String getMessage() {
        return message;
    }
}
