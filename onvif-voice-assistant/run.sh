#!/usr/bin/env bash
set -e

CONFIG_PATH=/data/options.json

echo "Starting ONVIF Voice Assistant..."

# Executar aplicação Python
python3 /app/app.py
