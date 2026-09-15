#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTLOADER="$(basename "$0" .sh)"
echo "$BOOTLOADER selected. No bootloader configuration changes are required."
echo "Installing the systemd-based MacBook Wi-Fi recovery service..."
exec bash "$ROOT/install.sh" "$@"
