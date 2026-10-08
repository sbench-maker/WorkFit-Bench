<?php

declare(strict_types=1);

namespace ParcelPilot\Rest;

use WP_Error;
use WP_REST_Request;
use WP_REST_Response;

final class OrdersController
{
    /**
     * Return orders for the dispatch board.
     *
     * @param WP_REST_Request $request Request details.
     * @return WP_REST_Response|WP_Error
     */
    public function getItems($request)
    {
        $customerId = $request->get_param('customer_id');
        $includeArchived = $request->get_param('include_archived');
        $status = $request->get_param('status');

        if ($customerId !== null && $customerId < 1) {
            return new WP_Error('invalid_customer', 'Customer IDs must be positive.');
        }

        $query = [
            'customer_id' => $customerId,
            'include_archived' => $includeArchived ?? false,
            'status' => $status ?? 'open',
        ];

        return new WP_REST_Response($query, 200);
    }
}
