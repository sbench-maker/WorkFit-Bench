package com.google.android.libraries.ads.mobile.sdk.banner;

public final class AdSize {
    public enum Format {
        INLINE_CURRENT_ORIENTATION,
        LARGE_ANCHORED,
        ANCHORED_CURRENT_ORIENTATION
    }

    private final Format format;
    private final int width;

    private AdSize(Format format, int width) {
        if (width <= 0) {
            throw new IllegalArgumentException("Banner width must be positive");
        }
        this.format = format;
        this.width = width;
    }

    public static AdSize getCurrentOrientationInlineAdaptiveBannerAdSize(Object context, int width) {
        return new AdSize(Format.INLINE_CURRENT_ORIENTATION, width);
    }

    public static AdSize getLargeAnchoredAdaptiveBannerAdSize(Object context, int width) {
        return new AdSize(Format.LARGE_ANCHORED, width);
    }

    public static AdSize getCurrentOrientationAnchoredAdaptiveBannerAdSize(Object context, int width) {
        return new AdSize(Format.ANCHORED_CURRENT_ORIENTATION, width);
    }

    public Format getFormat() {
        return format;
    }

    public int getWidth() {
        return width;
    }
}
