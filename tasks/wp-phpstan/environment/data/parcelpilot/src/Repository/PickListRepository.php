<?php

declare(strict_types=1);

namespace ParcelPilot\Repository;

final class PickListRepository
{
    /**
     * Load the open pick-list rows for a route.
     *
     * @return array<object>
     */
    public function findOpenByRoute(string $route): array
    {
        global $wpdb;

        $sql = $wpdb->prepare(
            "SELECT order_id, route, priority FROM {$wpdb->prefix}parcelpilot_pick WHERE route = %s AND packed_at IS NULL",
            $route
        );

        return $wpdb->get_results($sql, OBJECT);
    }
}
