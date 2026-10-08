<?php

declare(strict_types=1);

namespace ParcelPilot;

use ParcelPilot\Hooks\OrderStatusHooks;

final class Plugin
{
    /**
     * Register the plugin hooks.
     */
    public static function boot(): void
    {
        add_action('woocommerce_order_status_changed', [OrderStatusHooks::class, 'syncOrderStatus'], 10, 2);
    }
}
