<?php

declare(strict_types=1);

namespace ParcelPilot\Hooks;

use WC_Order;

final class OrderStatusHooks
{
    /**
     * Queue a carrier sync after a WooCommerce status change.
     *
     * @param int    $orderId WooCommerce order identifier.
     * @param object $order   Order object supplied by WooCommerce.
     */
    public static function syncOrderStatus(int $orderId, $order): void
    {
        if ($order->get_id() !== $orderId) {
            return;
        }

        as_schedule_single_action(
            time() + 60,
            'parcelpilot_sync_carrier',
            [
                'order_id' => $orderId,
                'carrier' => (string) $order->get_meta('_parcelpilot_carrier'),
                'attempt' => 1,
            ]
        );
    }
}
