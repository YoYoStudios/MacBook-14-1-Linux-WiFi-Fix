#!/usr/bin/env python3
from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

APP_NAME = "MacBookPro14,1 Wi-Fi Fix"
MODEL = "MacBookPro14,1"
SERVICE_NAME = "macbookpro14-1-wifi-fix.service"
HELPER_NAME = "macbookpro14-1-wifi-fix"

LINUX_HELPER = r'''#!/usr/bin/env bash
set -euo pipefail

MODEL="$(cat /sys/class/dmi/id/product_name 2>/dev/null || true)"
if [[ "$MODEL" != "MacBookPro14,1" ]]; then
    echo "Not MacBookPro14,1 ($MODEL); skipping."
    exit 0
fi

find_wifi() {
    local dev vendor class device
    for dev in /sys/bus/pci/devices/*; do
        [[ -r "$dev/vendor" && -r "$dev/class" ]] || continue
        vendor="$(cat "$dev/vendor")"
        class="$(cat "$dev/class")"
        device="$(cat "$dev/device" 2>/dev/null || true)"
        if [[ "$vendor" == "0x14e4" && "$class" == 0x0280* ]]; then
            if [[ "$device" == "0x43a3" ]]; then
                printf '%s\n' "$dev"
                return 0
            fi
        fi
    done
    for dev in /sys/bus/pci/devices/*; do
        [[ -r "$dev/vendor" && -r "$dev/class" ]] || continue
        vendor="$(cat "$dev/vendor")"
        class="$(cat "$dev/class")"
        if [[ "$vendor" == "0x14e4" && "$class" == 0x0280* ]]; then
            printf '%s\n' "$dev"
            return 0
        fi
    done
    return 1
}

TARGET="$(find_wifi || true)"
if [[ -z "$TARGET" ]]; then
    echo 1 > /sys/bus/pci/rescan
    sleep 1
    TARGET="$(find_wifi || true)"
fi

if [[ -z "$TARGET" ]]; then
    echo "Broadcom wireless PCI device not found."
    exit 0
fi

echo "Resetting $(basename "$TARGET")"
if [[ -w "$TARGET/remove" ]]; then
    echo 1 > "$TARGET/remove"
    sleep 2
fi

echo 1 > /sys/bus/pci/rescan
sleep 2
modprobe brcmfmac 2>/dev/null || true
echo "Wi-Fi PCI reset complete."
'''

SYSTEMD_SERVICE = r'''[Unit]
Description=MacBookPro14,1 Broadcom Wi-Fi PCI reset
After=systemd-udev-trigger.service
Before=NetworkManager.service iwd.service systemd-networkd.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/macbookpro14-1-wifi-fix

[Install]
WantedBy=multi-user.target
'''

OPENRC_SERVICE = r'''#!/sbin/openrc-run
description="MacBookPro14,1 Broadcom Wi-Fi PCI reset"

depend() {
    need localmount
    before net
}

start() {
    ebegin "Resetting MacBookPro14,1 Broadcom Wi-Fi"
    /usr/local/sbin/macbookpro14-1-wifi-fix
    eend $?
}
'''

WINDOWS_REPAIR = r'''param([switch]$Quiet)

$ErrorActionPreference = "Stop"
$model = (Get-CimInstance Win32_ComputerSystemProduct).Name
if ($model -ne "MacBookPro14,1") {
    if (-not $Quiet) { Write-Host "Not MacBookPro14,1 ($model); skipping." }
    exit 0
}

$devices = Get-PnpDevice -Class Net -PresentOnly | Where-Object {
    $_.InstanceId -match '^PCI\\VEN_14E4&'
}

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
$task = "MacBookPro14_1-WiFi-Fix"
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

PORTABLE_INSTALL = r'''#!/usr/bin/env bash
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
'''

PORTABLE_UNINSTALL = r'''#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo bash "$0" "$@"
fi

if command -v systemctl >/dev/null 2>&1; then
    systemctl disable --now macbookpro14-1-wifi-fix.service 2>/dev/null || true
    rm -f /etc/systemd/system/macbookpro14-1-wifi-fix.service
    systemctl daemon-reload
fi

if command -v rc-update >/dev/null 2>&1; then
    rc-update del macbookpro14-1-wifi-fix boot 2>/dev/null || true
    rm -f /etc/init.d/macbookpro14-1-wifi-fix
fi

rm -f /usr/local/sbin/macbookpro14-1-wifi-fix
echo "Removed."
'''

PORTABLE_README = r'''MacBookPro14,1 Linux Wi-Fi Fix - Portable Bundle

Linux:
  sudo bash install.sh

Windows (only if Windows itself has the same adapter-startup issue):
  Right-click PowerShell -> Run as administrator
  powershell -ExecutionPolicy Bypass -File windows\Install-WindowsFix.ps1

The Windows workaround restarts the Broadcom PCI network adapter at startup.
Native macOS normally does not need this workaround.

The Linux workaround targets MacBookPro14,1 and Broadcom PCI wireless devices.
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
        script = f'do shell script "{apple_string}" with administrator privileges'
        subprocess.Popen(["osascript", "-e", script])
        return True
    raise RuntimeError("Privilege elevation is not supported on this OS.")


def require_target_model() -> None:
    current = model_name()
    if current != MODEL:
        raise RuntimeError(f"This system is {current}, not {MODEL}.")


def find_linux_wifi() -> Path | None:
    devices = Path("/sys/bus/pci/devices")
    if not devices.exists():
        return None
    preferred = None
    fallback = None
    for dev in devices.iterdir():
        try:
            vendor = (dev / "vendor").read_text().strip().lower()
            dev_class = (dev / "class").read_text().strip().lower()
            device = (dev / "device").read_text().strip().lower()
        except OSError:
            continue
        if vendor == "0x14e4" and dev_class.startswith("0x0280"):
            fallback = fallback or dev
            if device == "0x43a3":
                preferred = dev
                break
    return preferred or fallback


def apply_linux_now() -> str:
    if platform.system() != "Linux":
        raise RuntimeError("The Linux PCI reset can only run from Linux.")
    require_target_model()
    target = find_linux_wifi()
    if target is None:
        Path("/sys/bus/pci/rescan").write_text("1")
        target = find_linux_wifi()
    if target is None:
        raise RuntimeError("No Broadcom PCI wireless controller was found.")
    remove = target / "remove"
    if remove.exists():
        remove.write_text("1")
    import time
    time.sleep(2)
    Path("/sys/bus/pci/rescan").write_text("1")
    subprocess.run(["modprobe", "brcmfmac"], check=False)
    return f"Reset {target.name}. Wi-Fi should appear in a few seconds."


def write_text(path: Path, content: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    if mode is not None:
        path.chmod(mode)


def install_linux_root(root: Path, local: bool = False) -> str:
    helper = root / "usr/local/sbin" / HELPER_NAME
    write_text(helper, LINUX_HELPER, 0o755)

    has_systemd = bool(shutil.which("systemctl")) if local else (root / "etc/systemd").exists()
    has_openrc = bool(shutil.which("rc-update")) if local else ((root / "etc/init.d").exists() and (root / "sbin/openrc-run").exists())

    if has_systemd:
        service = root / "etc/systemd/system" / SERVICE_NAME
        write_text(service, SYSTEMD_SERVICE, 0o644)
        if local:
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "enable", SERVICE_NAME], check=True)
            subprocess.run(["systemctl", "start", SERVICE_NAME], check=False)
        else:
            wants = root / "etc/systemd/system/multi-user.target.wants"
            wants.mkdir(parents=True, exist_ok=True)
            link = wants / SERVICE_NAME
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(f"/etc/systemd/system/{SERVICE_NAME}")
        return "Installed systemd workaround."

    if has_openrc:
        service = root / "etc/init.d" / HELPER_NAME
        write_text(service, OPENRC_SERVICE, 0o755)
        if local:
            subprocess.run(["rc-update", "add", HELPER_NAME, "boot"], check=True)
            subprocess.run([str(service), "start"], check=False)
        else:
            runlevel = root / "etc/runlevels/boot"
            runlevel.mkdir(parents=True, exist_ok=True)
            link = runlevel / HELPER_NAME
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(f"/etc/init.d/{HELPER_NAME}")
        return "Installed OpenRC workaround."

    raise RuntimeError("Could not detect systemd or OpenRC on the target Linux root.")


def uninstall_linux_local() -> str:
    if shutil.which("systemctl"):
        subprocess.run(["systemctl", "disable", "--now", SERVICE_NAME], check=False)
        Path(f"/etc/systemd/system/{SERVICE_NAME}").unlink(missing_ok=True)
        subprocess.run(["systemctl", "daemon-reload"], check=False)
    if shutil.which("rc-update"):
        subprocess.run(["rc-update", "del", HELPER_NAME, "boot"], check=False)
        Path(f"/etc/init.d/{HELPER_NAME}").unlink(missing_ok=True)
    Path(f"/usr/local/sbin/{HELPER_NAME}").unlink(missing_ok=True)
    return "Linux workaround removed."


def windows_apply() -> str:
    require_target_model()
    run_powershell(WINDOWS_REPAIR)
    return "Windows Broadcom adapter restarted."


def run_powershell(content: str, args: list[str] | None = None) -> None:
    args = args or []
    with tempfile.TemporaryDirectory(prefix="mbwifi-") as tmp:
        script = Path(tmp) / "script.ps1"
        write_text(script, content)
        subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args], check=True)


def windows_install() -> str:
    require_target_model()
    with tempfile.TemporaryDirectory(prefix="mbwifi-") as tmp:
        root = Path(tmp)
        write_text(root / "MacBookWifiFix.ps1", WINDOWS_REPAIR)
        write_text(root / "Install-WindowsFix.ps1", WINDOWS_INSTALL)
        subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "Install-WindowsFix.ps1")], check=True)
    return "Windows startup workaround installed."


def windows_uninstall() -> str:
    with tempfile.TemporaryDirectory(prefix="mbwifi-") as tmp:
        root = Path(tmp)
        write_text(root / "MacBookWifiFix.ps1", WINDOWS_REPAIR)
        write_text(root / "Install-WindowsFix.ps1", WINDOWS_INSTALL)
        subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "Install-WindowsFix.ps1"), "-Uninstall"], check=True)
    return "Windows startup workaround removed."


def make_portable(destination: Path) -> Path:
    bundle = destination / "MacBook-WiFi-Fix-Portable"
    write_text(bundle / "install.sh", PORTABLE_INSTALL, 0o755)
    write_text(bundle / "uninstall.sh", PORTABLE_UNINSTALL, 0o755)
    write_text(bundle / "src" / HELPER_NAME, LINUX_HELPER, 0o755)
    write_text(bundle / "src" / SERVICE_NAME, SYSTEMD_SERVICE, 0o644)
    write_text(bundle / "src" / f"{HELPER_NAME}.openrc", OPENRC_SERVICE, 0o755)
    write_text(bundle / "windows" / "MacBookWifiFix.ps1", WINDOWS_REPAIR)
    write_text(bundle / "windows" / "Install-WindowsFix.ps1", WINDOWS_INSTALL)
    write_text(bundle / "README.txt", PORTABLE_README)
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
        print(apply_linux_now())
    elif action == "--install-linux":
        require_target_model()
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
    root.geometry("620x430")
    root.minsize(560, 390)

    outer = ttk.Frame(root, padding=22)
    outer.pack(fill="both", expand=True)

    ttk.Label(outer, text=APP_NAME, font=("", 18, "bold")).pack(anchor="w")
    ttk.Label(outer, text=f"Host: {platform.system()} {platform.machine()}    Model: {model_name()}").pack(anchor="w", pady=(4, 16))
    ttk.Label(outer, text="Fixes the MacBookPro14,1 Broadcom Wi-Fi PCI startup bug on Linux. The same app can create a portable USB/folder bundle from Windows, macOS, or Linux.", wraplength=560, justify="left").pack(anchor="w", pady=(0, 16))

    status = tk.StringVar(value="Ready.")

    def launch(args: list[str]) -> None:
        try:
            if not is_admin():
                elevate(args)
                status.set("Started elevated helper. Reopen/refresh after it finishes.")
            else:
                subprocess.run(self_command(args), check=True)
                status.set("Done.")
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    system = platform.system()
    if system == "Linux":
        ttk.Button(outer, text="Apply Wi-Fi Fix Now", command=lambda: launch(["--apply-linux"])).pack(fill="x", pady=4)
        ttk.Button(outer, text="Install on This Linux System", command=lambda: launch(["--install-linux"])).pack(fill="x", pady=4)
        ttk.Button(outer, text="Uninstall from This Linux System", command=lambda: launch(["--uninstall-linux"])).pack(fill="x", pady=4)
    elif system == "Windows":
        ttk.Button(outer, text="Restart Broadcom Wi-Fi Now (Windows)", command=lambda: launch(["--windows-apply"])).pack(fill="x", pady=4)
        ttk.Button(outer, text="Install Windows Startup Workaround", command=lambda: launch(["--windows-install"])).pack(fill="x", pady=4)
        ttk.Button(outer, text="Uninstall Windows Startup Workaround", command=lambda: launch(["--windows-uninstall"])).pack(fill="x", pady=4)
    else:
        ttk.Label(outer, text="Native macOS normally does not need the PCI reset. Use the portable/offline options below.", wraplength=560).pack(anchor="w", pady=(0, 8))

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
    ttk.Label(outer, textvariable=status, wraplength=560, justify="left").pack(anchor="w", pady=(18, 0))
    ttk.Label(outer, text="Safety: local installs are model-checked. Offline-drive installs only write the boot helper/service to the selected Linux root.", wraplength=560, justify="left").pack(anchor="w", pady=(10, 0))

    root.mainloop()


if __name__ == "__main__":
    if not cli():
        gui()
