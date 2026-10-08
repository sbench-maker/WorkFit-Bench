<?php

declare(strict_types=1);

namespace ParcelPilot\Jobs;

final class CarrierSyncJob
{
    /**
     * Send an order to its selected carrier.
     *
     * @param array<string, mixed> $args Scheduler arguments.
     */
    public function __invoke(array $args): void
    {
        $orderId = $args['order_id'];
        $carrier = $args['carrier'];
        $attempt = $args['attempt'];

        do_action('parcelpilot_before_carrier_sync', $orderId, $carrier, $attempt);

        update_post_meta($orderId, '_parcelpilot_last_carrier', $carrier);
        update_post_meta($orderId, '_parcelpilot_sync_attempt', $attempt);
    }
}
