#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Installing MacBookPro14,1 Wi-Fi fix for Debian..."
exec bash "$ROOT/install.sh"
