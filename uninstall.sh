#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo bash "$0" "$@"
fi

if command -v systemctl >/dev/null 2>&1; then
    systemctl disable --now macbook-wifi-fix.service 2>/dev/null || true
    systemctl disable --now macbookpro14-1-wifi-fix.service 2>/dev/null || true
    rm -f /etc/systemd/system/macbook-wifi-fix.service
    rm -f /etc/systemd/system/macbookpro14-1-wifi-fix.service
    systemctl daemon-reload
    systemctl reset-failed 2>/dev/null || true
fi

if command -v rc-update >/dev/null 2>&1; then
    rc-update del macbook-wifi-fix boot 2>/dev/null || true
    rc-update del macbookpro14-1-wifi-fix boot 2>/dev/null || true
    rm -f /etc/init.d/macbook-wifi-fix
    rm -f /etc/init.d/macbookpro14-1-wifi-fix
fi

rm -f /usr/local/sbin/macbook-wifi-fix
rm -f /usr/local/sbin/macbookpro14-1-wifi-fix

echo "Removed MacBook Linux Wi-Fi Fix."
