<?php

class WC_Order
{
    public function get_id(): int { return 1; }
    public function get_order_number(): string { return '1'; }
    public function get_meta(string $key) { return null; }
}
