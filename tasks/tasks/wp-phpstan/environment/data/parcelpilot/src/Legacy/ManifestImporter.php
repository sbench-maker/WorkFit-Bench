<?php

declare(strict_types=1);

namespace ParcelPilot\Legacy;

final class ManifestImporter
{
    private $decoder;

    public function readRows($payload)
    {
        return $this->decoder->decode($payload);
    }
}
