# MacBookPro14,1 Linux Wi-Fi Fix

A workaround for the 2017 **MacBookPro14,1** Broadcom Wi-Fi bug where wireless works in Linux live media but an installed Linux system can boot with `brcmfmac` unable to talk to the PCI device.

The working reset is:

```bash
echo 1 | sudo tee /sys/bus/pci/devices/0000:02:00.0/remove
echo 1 | sudo tee /sys/bus/pci/rescan
```

This project makes that automatic without hardcoding `02:00.0`.

## GUI release

The release app can:

- apply the Linux PCI reset immediately;
- install/uninstall the boot workaround on the current Linux system;
- install the workaround into a mounted Linux root/drive for distro hopping;
- create a portable USB/folder bundle from Linux, Windows, or macOS;
- optionally install a Windows startup adapter-restart workaround if Windows itself ever has the same problem.

The GUI is built by GitHub Actions for:

- Linux x86_64
- Linux ARM64
- Windows x64
- macOS Intel
- macOS Apple Silicon

The **Intel macOS build** is the one for MacBookPro14,1.

> Native macOS and normal Boot Camp Windows usually do not need the Linux PCI workaround. Their builds are mainly useful for preparing a portable/offline fix. The Windows local workaround is opt-in.

## Linux support

The boot installer supports:

- systemd
- OpenRC

Tested in CI for shell compatibility against Ubuntu, Debian, Fedora, and Arch containers.

The bootloader does not matter. GRUB, systemd-boot, rEFInd, and EFISTUB all work because the reset runs after the kernel boots.

## Install from source

```bash
git clone https://github.com/YoYoStudios/MacBook-14-1-Linux-WiFi-Fix.git
cd MacBook-14-1-Linux-WiFi-Fix
sudo bash install.sh
```

The existing distro wrappers also work:

```bash
sudo bash distros/arch.sh
sudo bash distros/fedora.sh
sudo bash distros/ubuntu.sh
sudo bash distros/debian.sh
```

## Portable/offline install

Run the GUI and choose **Create Portable Fix on USB / Folder**, or place the repository on a USB drive and run:

```bash
sudo bash install.sh
```

The GUI can also choose **Install Fix to Mounted Linux Drive / Root** to write the helper/service directly to another Linux installation.

## Windows

If Windows itself has a Broadcom startup problem, run PowerShell as Administrator:

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\Install-WindowsFix.ps1
```

Remove it with:

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\Install-WindowsFix.ps1 -Uninstall
```

This creates a startup task that restarts the Broadcom PCI network device and rescans hardware. It is not required when Windows Wi-Fi already works.

## Logs

systemd:

```bash
systemctl status macbookpro14-1-wifi-fix.service
journalctl -u macbookpro14-1-wifi-fix.service -b
```

## Safety

Local Linux/Windows actions check that the machine identifies as `MacBookPro14,1`.

Linux device discovery only targets a Broadcom (`14e4`) PCI wireless-class device and prefers the BCM4350 device used by this MacBook. Offline-drive installation only writes the helper and init service to the root you select.

## Releases

`VERSION` controls the release version. Updating it triggers the cross-platform GitHub Actions build and creates/updates the GitHub Release automatically.

The GUI binaries are currently unsigned, so Windows SmartScreen or macOS Gatekeeper may warn on first launch.
