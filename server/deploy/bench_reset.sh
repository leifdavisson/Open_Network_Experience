#!/bin/bash
set -e
echo "Spinning down docker-compose..."
docker-compose down -v || true
echo "Clearing out test database volumes and files..."
rm -rf server/data/*
echo "Spinning environment back up fresh..."
docker-compose up -d || true
echo "Reset complete."
