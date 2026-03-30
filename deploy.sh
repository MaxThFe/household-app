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
    docker compose up -d
    docker image prune -f
else
    echo "$(date): Images up to date."
fi
