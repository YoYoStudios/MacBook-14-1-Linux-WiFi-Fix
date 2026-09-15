#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
echo "GRUB selected. No GRUB config changes are needed."
exec bash "$ROOT/install.sh"
