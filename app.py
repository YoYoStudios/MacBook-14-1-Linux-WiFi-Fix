#!/usr/bin/env python3
from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

APP_NAME = "MacBook Wi-Fi Fix"
SERVICE_NAME = "macbook-wifi-fix.service"
HELPER_NAME = "macbook-wifi-fix"

LINUX_HELPER = r'''#!/usr/bin/env bash
set -euo pipefail

MODE="apply"
case "${1:-}" in
    --boot) MODE="boot" ;;
    --check) MODE="check" ;;
    --diagnose) MODE="diagnose" ;;
    "") ;;
    *) echo "Usage: $0 [--boot|--check|--diagnose]"; exit 2 ;;
esac

MODEL="$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)"
VENDOR="$(cat /sys/class/dmi/id/sys_vendor 2>/dev/null || true)"
ARCH="$(uname -m)"
DISTRO="unknown"
if [[ -r /etc/os-release ]]; then
    . /etc/os-release
    DISTRO="${PRETTY_NAME:-${ID:-unknown}}"
fi

log() { echo "${MODE:+macbook-wifi-fix: }$*"; }
is_apple() { [[ "$VENDOR" == Apple* || "$MODEL" == MacBook* ]]; }
is_t2_model() {
    case "$MODEL" in
        MacBookPro15,*|MacBookPro16,*|MacBookAir8,*|MacBookAir9,1) return 0 ;;
        *) return 1 ;;
    esac
}
is_sta_common_id() {
    case "${1,,}" in 43a0|43b1) return 0 ;; *) return 1 ;; esac
}
is_known_brcmfmac_id() {
    case "${1,,}" in
        43a3|43df|43ec|43d3|43d9|43e9|43ef|43ba|43bb|43bc|aa52|43ca|43cb|43cc|43c3|43c4|43c5|440d|43dc|4464|4488) return 0 ;;
        *) return 1 ;;
    esac
}
wireless_broadcom_devices() {
    local dev vendor class
    for dev in /sys/bus/pci/devices/*; do
        [[ -r "$dev/vendor" && -r "$dev/class" ]] || continue
        vendor="$(cat "$dev/vendor")"
        class="$(cat "$dev/class")"
        [[ "$vendor" == "0x14e4" && "$class" == 0x0280* ]] || continue
        printf '%s\n' "$dev"
    done
}
current_driver() {
    local dev="$1"
    if [[ -L "$dev/driver" ]]; then basename "$(readlink -f "$dev/driver")"; else echo none; fi
}
available_modules() {
    local dev="$1" alias
    [[ -r "$dev/modalias" ]] || return 0
    alias="$(cat "$dev/modalias")"
    modprobe -R "$alias" 2>/dev/null || true
}
has_netdev() { compgen -G "$1/net/*" >/dev/null 2>&1; }
kernel_log() { dmesg --color=never 2>/dev/null || dmesg 2>/dev/null || true; }
mmio_failure_seen() {
    local bdf="$1"
    kernel_log | grep -Ei "($bdf.*(MMIO read failed|brcmf_chip_recognition|brcmf_pcie_probe)|brcmf.*(MMIO read failed|brcmf_chip_recognition))" >/dev/null 2>&1
}
firmware_failure_seen() {
    local bdf="$1"
    kernel_log | grep -Ei "($bdf.*(Direct firmware load.*failed|firmware.*(not found|failed)|Firmware has halted)|brcmf.*Direct firmware load.*failed)" >/dev/null 2>&1
}
brcmfmac_capable() {
    local dev="$1" id="$2" driver modules
    driver="$(current_driver "$dev")"
    [[ "$driver" == brcmfmac ]] && return 0
    modules="$(available_modules "$dev")"
    grep -qx brcmfmac <<<"$modules" && return 0
    is_known_brcmfmac_id "$id"
}
print_device() {
    local dev="$1" bdf id driver modules ifaces
    bdf="$(basename "$dev")"
    id="$(cat "$dev/device" 2>/dev/null || echo unknown)"; id="${id#0x}"
    driver="$(current_driver "$dev")"
    modules="$(available_modules "$dev" | paste -sd, -)"
    ifaces="$(find "$dev/net" -mindepth 1 -maxdepth 1 -printf '%f\n' 2>/dev/null | paste -sd, -)"
    printf '  %s 14e4:%s driver=%s modules=%s interfaces=%s\n' "$bdf" "$id" "$driver" "${modules:-none}" "${ifaces:-none}"
}

if ! is_apple; then log "Not an Apple MacBook; no action."; exit 1; fi
if [[ "$ARCH" == aarch64 || "$ARCH" == arm64 ]]; then
    log "Apple Silicon detected. Intel PCI recovery is disabled; use the Asahi platform Wi-Fi stack."
    exit 0
fi

mapfile -t DEVICES < <(wireless_broadcom_devices)

if [[ "$MODE" == diagnose ]]; then
    echo "MacBook Linux Wi-Fi Fix diagnostics"
    echo "Model:        ${MODEL:-unknown}"
    echo "Vendor:       ${VENDOR:-unknown}"
    echo "Architecture: $ARCH"
    echo "Distro:       $DISTRO"
    if is_t2_model; then echo "T2 family:    yes"; else echo "T2 family:    no/unknown"; fi
    echo "Broadcom PCI Wi-Fi:"
    if ((${#DEVICES[@]} == 0)); then echo "  none detected"; else for dev in "${DEVICES[@]}"; do print_device "$dev"; done; fi
    echo
    echo "Relevant kernel messages:"
    kernel_log | grep -Ei 'brcm|b43|wl:|firmware|wifi|wlan' | tail -n 80 || true
    exit 0
fi

if ((${#DEVICES[@]} == 0)); then log "No Broadcom PCI wireless controller detected."; exit 0; fi

if [[ "$MODE" == check ]]; then
    log "Detected ${MODEL:-unknown}:"
    for dev in "${DEVICES[@]}"; do print_device "$dev"; done
    if is_t2_model; then log "T2-family Mac: Apple firmware + a T2-capable kernel may still be required."; fi
    exit 0
fi

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then exec sudo "$0" "${1:-}"; fi

changed=0
for dev in "${DEVICES[@]}"; do
    [[ -d "$dev" ]] || continue
    bdf="$(basename "$dev")"
    id="$(cat "$dev/device" 2>/dev/null || echo 0x0000)"; id="${id#0x}"
    driver="$(current_driver "$dev")"

    if is_sta_common_id "$id"; then log "$bdf (14e4:$id) is a common Broadcom STA/wl device; brcmfmac PCI reset skipped."; continue; fi
    if [[ "$driver" != none && "$driver" != brcmfmac ]]; then log "$bdf is bound to $driver, not brcmfmac; leaving it alone."; continue; fi
    if ! brcmfmac_capable "$dev" "$id"; then log "$bdf (14e4:$id) is not identified as a brcmfmac PCI device; leaving it alone."; continue; fi
    if has_netdev "$dev"; then log "$bdf already has a network interface; no recovery needed."; continue; fi
    if firmware_failure_seen "$bdf" && ! mmio_failure_seen "$bdf"; then
        log "$bdf looks like a missing/failed firmware case; PCI reset skipped."
        if is_t2_model; then log "T2 Mac detected: follow the t2linux firmware/kernel setup."; fi
        continue
    fi

    log "Recovering Broadcom Wi-Fi at $bdf (14e4:$id) by PCI remove/rescan..."
    echo 1 > "$dev/remove"
    sleep 2
    echo 1 > /sys/bus/pci/rescan
    modprobe brcmfmac 2>/dev/null || true
    command -v udevadm >/dev/null 2>&1 && udevadm settle --timeout=5 2>/dev/null || true
    sleep 2
    changed=1
done

if ((changed)); then log "PCI recovery completed."; else log "No safe automatic PCI recovery was needed."; fi
'''

SYSTEMD_SERVICE = r'''[Unit]
Description=MacBook Linux Wi-Fi recovery
After=systemd-udev-trigger.service
Before=NetworkManager.service iwd.service wpa_supplicant.service systemd-networkd.service
ConditionVirtualization=!container

[Service]
Type=oneshot
ExecStartPre=/bin/sleep 2
ExecStart=/usr/local/sbin/macbook-wifi-fix --boot
TimeoutStartSec=20

[Install]
WantedBy=multi-user.target
'''

OPENRC_SERVICE = r'''#!/sbin/openrc-run
description="MacBook Linux Wi-Fi recovery"

depend() {
    need localmount
    before net
}

start() {
    ebegin "Checking MacBook Broadcom Wi-Fi"
    /usr/local/sbin/macbook-wifi-fix --boot
    eend $?
}
'''

WINDOWS_REPAIR = r'''param([switch]$Quiet)
$ErrorActionPreference = "Stop"
$model = (Get-CimInstance Win32_ComputerSystemProduct).Name
if ($model -notmatch '^MacBook') {
    if (-not $Quiet) { Write-Host "Not an Apple MacBook ($model); skipping." }
    exit 0
}
$devices = Get-PnpDevice -Class Net -PresentOnly | Where-Object { $_.InstanceId -match '^PCI\\VEN_14E4&' }
if (-not $devices) {
    if (-not $Quiet) { Write-Host "No Broadcom PCI network adapter found." }
    exit 0
}
foreach ($device in $devices) {
    if (-not $Quiet) { Write-Host "Restarting $($device.FriendlyName)" }
    & pnputil.exe /restart-device "$($device.InstanceId)" | Out-Null
}
& pnputil.exe /scan-devices | Out-Null
if (-not $Quiet) { Write-Host "Windows Wi-Fi device restart complete." }
'''

WINDOWS_INSTALL = r'''param([switch]$Uninstall)
$ErrorActionPreference = "Stop"
$task = "MacBook-WiFi-Fix"
$dir = Join-Path $env:ProgramData "MacBookWiFiFix"
$script = Join-Path $dir "MacBookWifiFix.ps1"
if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item $dir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Windows startup workaround removed."
    exit 0
}
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Copy-Item -Force "$PSScriptRoot\MacBookWifiFix.ps1" $script
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -Quiet"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
Write-Host "Windows startup workaround installed."
'''


def model_name() -> str:
    system = platform.system()
    try:
        if system == "Linux":
            return Path("/sys/class/dmi/id/product_name").read_text().strip()
        if system == "Darwin":
            return subprocess.check_output(["sysctl", "-n", "hw.model"], text=True).strip()
        if system == "Windows":
            cmd = ["powershell.exe", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystemProduct).Name"]
            return subprocess.check_output(cmd, text=True, creationflags=0x08000000).strip()
    except Exception:
        pass
    return "Unknown"


def is_macbook(name: str | None = None) -> bool:
    return (name or model_name()).startswith("MacBook")


def is_apple_silicon() -> bool:
    return platform.machine().lower() in {"arm64", "aarch64"}


def require_macbook() -> None:
    current = model_name()
    if not is_macbook(current):
        raise RuntimeError(f"This system is {current}, not an Apple MacBook.")


def is_admin() -> bool:
    if os.name == "nt":
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return os.geteuid() == 0


def self_command(extra: list[str]) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *extra]
    return [sys.executable, str(Path(__file__).resolve()), *extra]


def elevate(extra: list[str]) -> bool:
    cmd = self_command(extra)
    system = platform.system()
    if system == "Windows":
        exe, *args = cmd
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, subprocess.list2cmdline(args), None, 1)
        return rc > 32
    if system == "Linux":
        if shutil.which("pkexec"):
            subprocess.Popen(["pkexec", *cmd])
            return True
        raise RuntimeError("pkexec was not found. Run the app from a terminal with sudo.")
    if system == "Darwin":
        import shlex
        shell_cmd = " ".join(shlex.quote(part) for part in cmd)
        apple_string = shell_cmd.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.Popen(["osascript", "-e", f'do shell script "{apple_string}" with administrator privileges'])
        return True
    raise RuntimeError("Privilege elevation is not supported on this OS.")


def write_text(path: Path, content: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    if mode is not None:
        path.chmod(mode)


def run_helper_now() -> str:
    if platform.system() != "Linux":
        raise RuntimeError("The Linux recovery can only run from Linux.")
    require_macbook()
    if is_apple_silicon():
        raise RuntimeError("Apple Silicon uses the Asahi platform Wi-Fi stack; this Intel PCI recovery is intentionally disabled.")
    with tempfile.TemporaryDirectory(prefix="mbwifi-") as tmp:
        helper = Path(tmp) / HELPER_NAME
        write_text(helper, LINUX_HELPER, 0o755)
        proc = subprocess.run([str(helper)], text=True, capture_output=True)
        output = (proc.stdout + proc.stderr).strip()
        if proc.returncode:
            raise RuntimeError(output or "Wi-Fi recovery failed.")
        return output or "Wi-Fi recovery completed."


def install_linux_root(root: Path, local: bool = False) -> str:
    helper = root / "usr/local/sbin" / HELPER_NAME
    write_text(helper, LINUX_HELPER, 0o755)
    has_systemd = bool(shutil.which("systemctl")) if local else (root / "etc/systemd").exists()
    has_openrc = bool(shutil.which("rc-update")) if local else ((root / "etc/init.d").exists() and (root / "sbin/openrc-run").exists())

    if has_systemd:
        service = root / "etc/systemd/system" / SERVICE_NAME
        write_text(service, SYSTEMD_SERVICE, 0o644)
        if local:
            subprocess.run(["systemctl", "disable", "--now", "macbookpro14-1-wifi-fix.service"], check=False)
            Path("/etc/systemd/system/macbookpro14-1-wifi-fix.service").unlink(missing_ok=True)
            Path("/usr/local/sbin/macbookpro14-1-wifi-fix").unlink(missing_ok=True)
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "enable", SERVICE_NAME], check=True)
            subprocess.run(["systemctl", "restart", SERVICE_NAME], check=False)
        else:
            wants = root / "etc/systemd/system/multi-user.target.wants"
            wants.mkdir(parents=True, exist_ok=True)
            link = wants / SERVICE_NAME
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(f"/etc/systemd/system/{SERVICE_NAME}")
        return "Installed systemd MacBook Wi-Fi recovery."

    if has_openrc:
        service = root / "etc/init.d" / HELPER_NAME
        write_text(service, OPENRC_SERVICE, 0o755)
        if local:
            subprocess.run(["rc-update", "del", "macbookpro14-1-wifi-fix", "boot"], check=False)
            Path("/etc/init.d/macbookpro14-1-wifi-fix").unlink(missing_ok=True)
            Path("/usr/local/sbin/macbookpro14-1-wifi-fix").unlink(missing_ok=True)
            subprocess.run(["rc-update", "add", HELPER_NAME, "boot"], check=True)
            subprocess.run([str(service), "start"], check=False)
        else:
            runlevel = root / "etc/runlevels/boot"
            runlevel.mkdir(parents=True, exist_ok=True)
            link = runlevel / HELPER_NAME
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(f"/etc/init.d/{HELPER_NAME}")
        return "Installed OpenRC MacBook Wi-Fi recovery."

    raise RuntimeError("Could not detect systemd or OpenRC on the target Linux root.")


def uninstall_linux_local() -> str:
    for service in (SERVICE_NAME, "macbookpro14-1-wifi-fix.service"):
        if shutil.which("systemctl"):
            subprocess.run(["systemctl", "disable", "--now", service], check=False)
            Path(f"/etc/systemd/system/{service}").unlink(missing_ok=True)
    if shutil.which("systemctl"):
        subprocess.run(["systemctl", "daemon-reload"], check=False)
    if shutil.which("rc-update"):
        for helper in (HELPER_NAME, "macbookpro14-1-wifi-fix"):
            subprocess.run(["rc-update", "del", helper, "boot"], check=False)
            Path(f"/etc/init.d/{helper}").unlink(missing_ok=True)
    for helper in (HELPER_NAME, "macbookpro14-1-wifi-fix"):
        Path(f"/usr/local/sbin/{helper}").unlink(missing_ok=True)
    return "Linux workaround removed."


def run_powershell(content: str, args: list[str] | None = None) -> None:
    with tempfile.TemporaryDirectory(prefix="mbwifi-") as tmp:
        script = Path(tmp) / "script.ps1"
        write_text(script, content)
        subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *(args or [])], check=True)


def windows_apply() -> str:
    require_macbook()
    run_powershell(WINDOWS_REPAIR)
    return "Windows Broadcom adapter restarted."


def windows_install() -> str:
    require_macbook()
    with tempfile.TemporaryDirectory(prefix="mbwifi-") as tmp:
        root = Path(tmp)
        write_text(root / "MacBookWifiFix.ps1", WINDOWS_REPAIR)
        write_text(root / "Install-WindowsFix.ps1", WINDOWS_INSTALL)
        subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "Install-WindowsFix.ps1")], check=True)
    return "Windows startup workaround installed."


def windows_uninstall() -> str:
    run_powershell(WINDOWS_INSTALL, ["-Uninstall"])
    return "Windows startup workaround removed."


def portable_install() -> str:
    return r'''#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then exec sudo bash "$0" "$@"; fi
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODEL="$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)"
ARCH="$(uname -m)"
if [[ "$ARCH" == aarch64 || "$ARCH" == arm64 ]]; then echo "Apple Silicon: use Asahi platform Wi-Fi support."; exit 0; fi
[[ "$MODEL" == MacBook* ]] || { echo "Not an Apple MacBook: ${MODEL:-unknown}"; exit 1; }
install -Dm755 "$ROOT/src/macbook-wifi-fix" /usr/local/sbin/macbook-wifi-fix
if command -v systemctl >/dev/null 2>&1; then
  install -Dm644 "$ROOT/src/macbook-wifi-fix.service" /etc/systemd/system/macbook-wifi-fix.service
  systemctl daemon-reload; systemctl enable macbook-wifi-fix.service; systemctl restart macbook-wifi-fix.service || true
elif command -v rc-update >/dev/null 2>&1; then
  install -Dm755 "$ROOT/src/macbook-wifi-fix.openrc" /etc/init.d/macbook-wifi-fix
  rc-update add macbook-wifi-fix boot; /etc/init.d/macbook-wifi-fix start || true
fi
echo "Installed."
'''


def portable_uninstall() -> str:
    return r'''#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then exec sudo bash "$0" "$@"; fi
if command -v systemctl >/dev/null 2>&1; then systemctl disable --now macbook-wifi-fix.service 2>/dev/null || true; rm -f /etc/systemd/system/macbook-wifi-fix.service; systemctl daemon-reload; fi
if command -v rc-update >/dev/null 2>&1; then rc-update del macbook-wifi-fix boot 2>/dev/null || true; rm -f /etc/init.d/macbook-wifi-fix; fi
rm -f /usr/local/sbin/macbook-wifi-fix
echo "Removed."
'''


def make_portable(destination: Path) -> Path:
    bundle = destination / "MacBook-WiFi-Fix-Portable"
    write_text(bundle / "install.sh", portable_install(), 0o755)
    write_text(bundle / "uninstall.sh", portable_uninstall(), 0o755)
    write_text(bundle / "src" / HELPER_NAME, LINUX_HELPER, 0o755)
    write_text(bundle / "src" / SERVICE_NAME, SYSTEMD_SERVICE, 0o644)
    write_text(bundle / "src" / f"{HELPER_NAME}.openrc", OPENRC_SERVICE, 0o755)
    write_text(bundle / "windows" / "MacBookWifiFix.ps1", WINDOWS_REPAIR)
    write_text(bundle / "windows" / "Install-WindowsFix.ps1", WINDOWS_INSTALL)
    write_text(bundle / "README.txt", "MacBook Wi-Fi Fix portable bundle\n\nLinux: sudo bash install.sh\n\nThe Intel Linux recovery is hardware-aware and will not apply itself to Apple Silicon.\n")
    return bundle


def cli() -> bool:
    if len(sys.argv) <= 1:
        return False
    action = sys.argv[1]
    privileged = {"--apply-linux", "--install-linux", "--uninstall-linux", "--install-root", "--windows-apply", "--windows-install", "--windows-uninstall"}
    if action in privileged and not is_admin():
        elevate(sys.argv[1:])
        return True
    if action == "--apply-linux":
        print(run_helper_now())
    elif action == "--install-linux":
        require_macbook()
        if is_apple_silicon():
            raise RuntimeError("Apple Silicon uses the Asahi platform Wi-Fi stack; this Intel PCI workaround is disabled.")
        print(install_linux_root(Path("/"), local=True))
    elif action == "--uninstall-linux":
        print(uninstall_linux_local())
    elif action == "--install-root":
        target = Path(sys.argv[2]).resolve()
        if not (target / "etc").exists():
            raise RuntimeError("That folder does not look like a mounted Linux root.")
        print(install_linux_root(target, local=False))
    elif action == "--portable":
        print(make_portable(Path(sys.argv[2]).resolve()))
    elif action == "--windows-apply":
        print(windows_apply())
    elif action == "--windows-install":
        print(windows_install())
    elif action == "--windows-uninstall":
        print(windows_uninstall())
    else:
        return False
    return True


def gui() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("640x455")
    root.minsize(580, 410)
    outer = ttk.Frame(root, padding=22)
    outer.pack(fill="both", expand=True)
    ttk.Label(outer, text=APP_NAME, font=("", 18, "bold")).pack(anchor="w")
    ttk.Label(outer, text=f"Host: {platform.system()} {platform.machine()}    Model: {model_name()}").pack(anchor="w", pady=(4, 16))
    ttk.Label(outer, text="Hardware-aware Broadcom Wi-Fi recovery for Intel MacBooks. It detects the adapter/driver first, avoids Apple Silicon, and does not blindly apply the same fix to every Broadcom generation.", wraplength=590, justify="left").pack(anchor="w", pady=(0, 16))
    status = tk.StringVar(value="Ready.")

    def launch(args: list[str]) -> None:
        try:
            if not is_admin():
                elevate(args)
                status.set("Started elevated helper.")
            else:
                proc = subprocess.run(self_command(args), text=True, capture_output=True)
                if proc.returncode:
                    raise RuntimeError((proc.stdout + proc.stderr).strip() or "Operation failed.")
                status.set((proc.stdout + proc.stderr).strip() or "Done.")
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    system = platform.system()
    if system == "Linux":
        if is_apple_silicon():
            ttk.Label(outer, text="Apple Silicon detected: use Asahi/Fedora Asahi Wi-Fi support. The Intel PCI fix is disabled here.", wraplength=590).pack(anchor="w", pady=(0, 8))
        else:
            ttk.Button(outer, text="Apply Safe Wi-Fi Recovery Now", command=lambda: launch(["--apply-linux"])).pack(fill="x", pady=4)
            ttk.Button(outer, text="Install on This Linux System", command=lambda: launch(["--install-linux"])).pack(fill="x", pady=4)
            ttk.Button(outer, text="Uninstall from This Linux System", command=lambda: launch(["--uninstall-linux"])).pack(fill="x", pady=4)
    elif system == "Windows":
        ttk.Button(outer, text="Restart Broadcom Wi-Fi Now (Windows)", command=lambda: launch(["--windows-apply"])).pack(fill="x", pady=4)
        ttk.Button(outer, text="Install Windows Startup Workaround", command=lambda: launch(["--windows-install"])).pack(fill="x", pady=4)
        ttk.Button(outer, text="Uninstall Windows Startup Workaround", command=lambda: launch(["--windows-uninstall"])).pack(fill="x", pady=4)
    else:
        ttk.Label(outer, text="Native macOS normally does not need this Linux PCI recovery. Use the portable/offline options below.", wraplength=590).pack(anchor="w", pady=(0, 8))

    def install_drive() -> None:
        folder = filedialog.askdirectory(title="Select mounted Linux root")
        if folder:
            launch(["--install-root", folder])

    def portable() -> None:
        folder = filedialog.askdirectory(title="Select USB drive or destination folder")
        if not folder:
            return
        try:
            bundle = make_portable(Path(folder))
            status.set(f"Portable bundle created: {bundle}")
            messagebox.showinfo(APP_NAME, f"Portable bundle created:\n{bundle}")
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    ttk.Separator(outer).pack(fill="x", pady=14)
    ttk.Button(outer, text="Install Fix to Mounted Linux Drive / Root", command=install_drive).pack(fill="x", pady=4)
    ttk.Button(outer, text="Create Portable Fix on USB / Folder", command=portable).pack(fill="x", pady=4)
    ttk.Label(outer, textvariable=status, wraplength=590, justify="left").pack(anchor="w", pady=(18, 0))
    ttk.Label(outer, text="T2 Macs may additionally require a T2-capable kernel and Apple firmware; this tool will not replace those requirements.", wraplength=590, justify="left").pack(anchor="w", pady=(10, 0))
    root.mainloop()


if __name__ == "__main__":
    if not cli():
        gui()
