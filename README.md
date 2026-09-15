# MacBookPro14,1 Linux Wi-Fi PCI Reset Fix

A small boot-time workaround for the 2017 **MacBookPro14,1** where the internal Broadcom Wi-Fi works in Linux live USBs but fails after installing Linux.

The failure can show up in `dmesg` as `brcmfmac` PCI/MMIO errors such as:

```text
brcmfmac: ... MMIO read failed: 0xffffffff
```

The workaround is the same thing that fixes it manually: remove the Broadcom Wi-Fi PCI device from sysfs, rescan the PCI bus, and let `brcmfmac` probe it again.

## Supported distros

- Arch Linux / EndeavourOS
- Fedora
- Ubuntu / Linux Mint
- Debian
- Most other systemd-based distros

## Supported boot methods

- GRUB
- systemd-boot
- rEFInd
- EFISTUB

The bootloader itself does **not** need to be modified. The workaround runs as a systemd oneshot during boot, so it stays the same when you distro-hop or change bootloaders.

## Install

Clone the repo:

```bash
git clone https://github.com/YoYoStudios/MacBook-14-1-Linux-WiFi-Fix.git
cd MacBook-14-1-Linux-WiFi-Fix
```

Then run the script for your distro:

```bash
sudo bash distros/arch.sh
sudo bash distros/fedora.sh
sudo bash distros/ubuntu.sh
sudo bash distros/debian.sh
```

Ubuntu's script also covers Linux Mint and other Ubuntu-based distros.

Or just use the universal installer:

```bash
sudo bash install.sh
```

## Bootloader wrappers

These all install the same systemd workaround; they do not rewrite your bootloader configuration.

```bash
sudo bash bootloaders/grub.sh
sudo bash bootloaders/systemd-boot.sh
sudo bash bootloaders/refind.sh
sudo bash bootloaders/efistub.sh
```

## What it does

The installed helper:

1. Refuses to run on anything other than `MacBookPro14,1`.
2. Finds the internal Broadcom PCI wireless controller automatically instead of hardcoding `02:00.0`.
3. Removes that PCI device from sysfs.
4. Rescans the PCI bus.
5. Loads `brcmfmac` again if needed.

The service runs automatically on every boot.

## Status / logs

```bash
systemctl status macbookpro14-1-wifi-fix.service
journalctl -u macbookpro14-1-wifi-fix.service -b
```

## Manual workaround

If the card is at `02:00.0`, the original manual fix is:

```bash
echo 1 | sudo tee /sys/bus/pci/devices/0000:02:00.0/remove
echo 1 | sudo tee /sys/bus/pci/rescan
```

## Uninstall

```bash
sudo bash uninstall.sh
```

## Safety

This project intentionally limits itself to `MacBookPro14,1` and a Broadcom PCI wireless-class device. If either check fails, it exits without removing a PCI device.
