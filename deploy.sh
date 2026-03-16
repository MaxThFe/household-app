#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

pull_output=$(docker compose pull 2>&1)

if echo "$pull_output" | grep -q "Downloaded newer image"; then
    echo "$(date): New images found, restarting containers..."
    docker compose up -d
    docker image prune -f
else
    echo "$(date): Images up to date."
fi
