#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo bash "$0" "$@"
fi

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODEL="$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)"
VENDOR="$(cat /sys/class/dmi/id/sys_vendor 2>/dev/null || true)"
ARCH="$(uname -m)"

if [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]]; then
    echo "Apple Silicon / ARM64 detected."
    echo "This Intel PCI workaround is intentionally not installed on Apple Silicon."
    echo "Use Asahi Linux / Fedora Asahi Remix for the platform-specific Wi-Fi stack."
    exit 0
fi

if [[ "$VENDOR" != Apple* && "$MODEL" != MacBook* ]]; then
    echo "This does not look like an Apple MacBook."
    echo "Detected vendor: ${VENDOR:-unknown}"
    echo "Detected model:  ${MODEL:-unknown}"
    exit 1
fi

install -Dm755 "$ROOT/src/macbook-wifi-fix" /usr/local/sbin/macbook-wifi-fix

# Remove names used by the original MacBookPro14,1-only release.
if command -v systemctl >/dev/null 2>&1; then
    systemctl disable --now macbookpro14-1-wifi-fix.service 2>/dev/null || true
    rm -f /etc/systemd/system/macbookpro14-1-wifi-fix.service
fi
if command -v rc-update >/dev/null 2>&1; then
    rc-update del macbookpro14-1-wifi-fix boot 2>/dev/null || true
    rm -f /etc/init.d/macbookpro14-1-wifi-fix
fi
rm -f /usr/local/sbin/macbookpro14-1-wifi-fix

if command -v systemctl >/dev/null 2>&1; then
    install -Dm644 "$ROOT/src/macbook-wifi-fix.service" /etc/systemd/system/macbook-wifi-fix.service
    systemctl daemon-reload
    systemctl enable macbook-wifi-fix.service
    systemctl restart macbook-wifi-fix.service || {
        echo "Wi-Fi recovery service returned an error. Diagnostics:"
        /usr/local/sbin/macbook-wifi-fix --diagnose || true
        exit 1
    }
elif command -v rc-update >/dev/null 2>&1; then
    install -Dm755 "$ROOT/src/macbook-wifi-fix.openrc" /etc/init.d/macbook-wifi-fix
    rc-update add macbook-wifi-fix boot
    /etc/init.d/macbook-wifi-fix restart 2>/dev/null || /etc/init.d/macbook-wifi-fix start || {
        echo "Wi-Fi recovery service returned an error. Diagnostics:"
        /usr/local/sbin/macbook-wifi-fix --diagnose || true
        exit 1
    }
else
    echo "Installed helper, but systemd/OpenRC was not detected."
    echo "Run /usr/local/sbin/macbook-wifi-fix --boot during startup."
fi

echo
echo "Installed MacBook Linux Wi-Fi Fix for: ${MODEL:-unknown}"
/usr/local/sbin/macbook-wifi-fix --check || true
