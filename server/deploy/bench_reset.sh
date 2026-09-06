#!/usr/bin/env bash
# Open Network Experience (ONE) - CMP Bench Reset Tool
# Copyright (C) 2026 Open Network Experience Authors.
# Licensed under GNU AGPLv3.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

DOCKER_COMPOSE="docker compose"
if ! docker compose version &>/dev/null; then
    if command -v docker-compose &>/dev/null; then
        DOCKER_COMPOSE="docker-compose"
    else
        echo "Error: Neither 'docker compose' nor 'docker-compose' found in PATH." >&2
        exit 1
    fi
fi

echo "=== 1. Spinning down CMP docker containers and volumes ==="
(cd "${SCRIPT_DIR}" && ${DOCKER_COMPOSE} down -v || true)

echo "=== 2. Clearing out test database volumes and files ==="
rm -rf "${ROOT_DIR}/server/data"/*

echo "=== 3. Spinning environment back up fresh ==="
(cd "${SCRIPT_DIR}" && ${DOCKER_COMPOSE} up -d || true)

echo "Reset complete."
