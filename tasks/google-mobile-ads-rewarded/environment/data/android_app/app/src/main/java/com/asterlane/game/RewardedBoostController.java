package com.asterlane.game;

/** Controller for the opt-in reward boost placement. */
public final class RewardedBoostController {
    private static final String AD_UNIT_ID = "demo-rewarded-boost";

    private final RewardedBoostView view;
    private final RewardWallet wallet;

    public RewardedBoostController(RewardedBoostView view, RewardWallet wallet) {
        this.view = view;
        this.wallet = wallet;
        view.setWatchButtonEnabled(false);
    }

    /** Request inventory for the placement. */
    public void load() {
        // TODO: build the request, load the ad, register callbacks, and update readiness.
    }

    /** Called only from the screen's explicit "Watch ad" button. */
    public void onWatchAdClicked() {
        // TODO: present a loaded ad and credit only an earned reward.
    }
}
