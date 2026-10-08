package com.asterlane.game;

/** Domain service that applies an earned reward to the current player. */
public interface RewardWallet {
    void credit(String rewardType, int amount);
}
