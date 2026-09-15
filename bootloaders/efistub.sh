#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
echo "EFISTUB selected. No EFI boot entry changes are needed."
exec bash "$ROOT/install.sh"
