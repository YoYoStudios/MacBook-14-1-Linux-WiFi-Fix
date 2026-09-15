#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo bash "$0" "$@"
fi

MODEL="$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)"
if [[ "$MODEL" != "MacBookPro14,1" ]]; then
    echo "This fix is only for MacBookPro14,1. Detected: ${MODEL:-unknown}"
    exit 1
fi

install -Dm755 "$ROOT/src/macbookpro14-1-wifi-fix" /usr/local/sbin/macbookpro14-1-wifi-fix
install -Dm644 "$ROOT/src/macbookpro14-1-wifi-fix.service" /etc/systemd/system/macbookpro14-1-wifi-fix.service

systemctl daemon-reload
systemctl enable macbookpro14-1-wifi-fix.service
systemctl restart macbookpro14-1-wifi-fix.service || systemctl start macbookpro14-1-wifi-fix.service

echo "Installed. The Wi-Fi PCI reset fix will run automatically on every boot."
