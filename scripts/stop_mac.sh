#!/usr/bin/env bash
# Stop FinAlly (macOS/Linux). Removes the container but keeps the data volume. Safe to run repeatedly.
set -euo pipefail

CONTAINER="finally"

if ! docker info >/dev/null 2>&1; then
  echo "Error: Docker is not running." >&2
  exit 1
fi

if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "Stopping and removing container '$CONTAINER'..."
  docker rm -f "$CONTAINER" >/dev/null
  echo "Stopped. Your data is preserved in the 'finally-data' volume."
else
  echo "Container '$CONTAINER' is not running. Nothing to do."
fi
