package com.asterlane.game;

/** UI surface owned by the reward boost screen. */
public interface RewardedBoostView {
    void setWatchButtonEnabled(boolean enabled);

    void showMessage(String message);

    void runOnUiThread(Runnable action);
}
