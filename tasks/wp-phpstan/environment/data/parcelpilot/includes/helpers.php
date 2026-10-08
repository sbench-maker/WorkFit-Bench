<?php

declare(strict_types=1);

/**
 * Normalize a carrier code stored in post meta.
 */
function parcelpilot_normalize_carrier(string $carrier): string
{
    return strtolower(trim($carrier));
}
