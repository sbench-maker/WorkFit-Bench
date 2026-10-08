#!/bin/sh
    python3 scripts/migrate.py
    cp -R app /srv/parcelpilot/app
    systemctl restart parcelpilot
    echo "release complete"
