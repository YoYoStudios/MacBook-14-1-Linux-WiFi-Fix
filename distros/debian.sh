#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Preparing Broadcom firmware for Debian..."
MWF_DISTRO=debian bash "$ROOT/src/install-firmware-packages" || true
exec bash "$ROOT/install.sh" "$@"
