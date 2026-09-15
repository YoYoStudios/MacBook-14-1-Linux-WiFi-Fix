#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Preparing Broadcom firmware for Arch/EndeavourOS..."
MWF_DISTRO=arch bash "$ROOT/src/install-firmware-packages" || true
exec bash "$ROOT/install.sh" "$@"
