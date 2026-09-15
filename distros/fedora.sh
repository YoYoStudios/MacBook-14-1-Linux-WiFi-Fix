#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Preparing Broadcom firmware for Fedora..."
MWF_DISTRO=fedora bash "$ROOT/src/install-firmware-packages" || true
exec bash "$ROOT/install.sh" "$@"
