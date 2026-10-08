package com.google.android.libraries.ads.mobile.sdk.rewarded;

public final class RewardItem {
    private final String type;
    private final int amount;

    public RewardItem(String type, int amount) {
        this.type = type;
        this.amount = amount;
    }

    public String getType() {
        return type;
    }

    public int getAmount() {
        return amount;
    }
}
