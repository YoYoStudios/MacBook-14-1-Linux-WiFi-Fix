#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo bash "$0" "$@"
fi

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODEL="$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)"
if [[ "$MODEL" != "MacBookPro14,1" ]]; then
    echo "This workaround is intended for MacBookPro14,1. Detected: ${MODEL:-unknown}"
    exit 1
fi

install -Dm755 "$ROOT/src/macbookpro14-1-wifi-fix" /usr/local/sbin/macbookpro14-1-wifi-fix

if command -v systemctl >/dev/null 2>&1; then
    install -Dm644 "$ROOT/src/macbookpro14-1-wifi-fix.service" /etc/systemd/system/macbookpro14-1-wifi-fix.service
    systemctl daemon-reload
    systemctl enable macbookpro14-1-wifi-fix.service
    systemctl start macbookpro14-1-wifi-fix.service || true
elif command -v rc-update >/dev/null 2>&1; then
    install -Dm755 "$ROOT/src/macbookpro14-1-wifi-fix.openrc" /etc/init.d/macbookpro14-1-wifi-fix
    rc-update add macbookpro14-1-wifi-fix boot
    /etc/init.d/macbookpro14-1-wifi-fix start || true
else
    echo "Installed helper, but your init system is unsupported."
    echo "Run /usr/local/sbin/macbookpro14-1-wifi-fix once during boot."
fi

echo "Installed."
