#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
echo "systemd-boot selected. No boot entry changes are needed."
exec bash "$ROOT/install.sh"
