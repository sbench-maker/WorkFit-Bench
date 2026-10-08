<?php

declare(strict_types=1);

namespace ParcelPilot\Integration;

use WC_Order;

final class WooCommerceBridge
{
    public function trackingLabel(WC_Order $order): string
    {
        $number = $order->get_order_number();
        $carrier = (string) $order->get_meta('_parcelpilot_carrier');

        return sprintf('%s:%s', $carrier, $number);
    }
}
