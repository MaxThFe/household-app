#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

# Get image IDs for the tags before pulling
before=$(docker compose config --images | xargs -I{} docker inspect --format '{{.Id}}' {} 2>/dev/null | sort)

docker compose pull --quiet 2>&1

# Get image IDs for the tags after pulling
after=$(docker compose config --images | xargs -I{} docker inspect --format '{{.Id}}' {} 2>/dev/null | sort)

if [ "$before" != "$after" ]; then
    echo "$(date): New images found, restarting containers..."
    backend_before=$(docker compose ps -q backend)
    docker compose up -d
    docker image prune -f

    # Recreating the backend mid-scan leaves BlueZ's discovery stuck, and the
    # new scanner never receives an advertisement. Only restarting bluetoothd
    # clears it, and the backend then needs a fresh scanner on the healthy daemon.
    if [ "$(docker compose ps -q backend)" != "$backend_before" ]; then
        echo "$(date): Backend recreated, restarting bluetooth and the BLE scanner..."
        sudo systemctl restart bluetooth
        sleep 3
        docker compose restart backend
    fi
else
    echo "$(date): Images up to date."
fi
