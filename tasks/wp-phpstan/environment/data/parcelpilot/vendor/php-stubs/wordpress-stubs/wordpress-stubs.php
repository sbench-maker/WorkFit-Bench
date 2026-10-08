<?php

class WP_REST_Request {}
class WP_REST_Response {}
class WP_Error {}
class wpdb {}

function add_action(string $hook, $callback, int $priority = 10, int $accepted_args = 1): void {}
function do_action(string $hook, ...$args): void {}
function update_post_meta(int $post_id, string $key, $value): void {}
function as_schedule_single_action(int $timestamp, string $hook, array $args): int { return 1; }
