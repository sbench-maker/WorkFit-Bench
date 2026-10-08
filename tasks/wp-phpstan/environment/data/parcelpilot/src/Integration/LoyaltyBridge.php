<?php

declare(strict_types=1);

namespace ParcelPilot\Integration;

final class LoyaltyBridge
{
    public function balanceForCustomer(int $customerId): ?int
    {
        if (!class_exists('Vendor_Loyalty_Card')) {
            return null;
        }

        $card = new \Vendor_Loyalty_Card($customerId);

        return $card->rewardBalance();
    }
}
