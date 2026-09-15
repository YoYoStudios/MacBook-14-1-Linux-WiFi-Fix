#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo bash "$0" "$@"
fi

systemctl disable --now macbookpro14-1-wifi-fix.service 2>/dev/null || true
rm -f /etc/systemd/system/macbookpro14-1-wifi-fix.service
rm -f /usr/local/sbin/macbookpro14-1-wifi-fix
systemctl daemon-reload
systemctl reset-failed

echo "Removed MacBookPro14,1 Wi-Fi fix."
