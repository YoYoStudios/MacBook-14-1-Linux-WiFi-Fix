# MacBook Wi-Fi Fix

A hardware-aware Wi-Fi recovery toolkit for Apple MacBooks running Linux.

This project started on a 2017 `MacBookPro14,1` with Broadcom BCM4350 (`14e4:43a3`). Wi-Fi worked in every live USB, but installed Linux systems could boot with `brcmfmac` unable to access the PCI device and errors such as `MMIO read failed: 0xffffffff`. Removing the Wi-Fi PCI function and rescanning the PCI bus immediately recovered it.

The project is now generalized so it does **not** assume every MacBook has that exact chip, PCI address, driver, or failure mode.

## What it does

On Intel MacBooks it detects the Apple model, Broadcom PCI wireless controller, PCI ID, currently bound driver, kernel modules matching the device modalias, network interfaces, and relevant firmware/MMIO failures before deciding whether the PCI remove/rescan workaround is safe.

For a `brcmfmac` device that failed to create a network interface and does not simply look like missing firmware, it performs the recovery automatically at boot.

If Wi-Fi is already working, the service does nothing.

If the device belongs to a different Broadcom driver family, the service leaves it alone instead of blindly resetting it.

## Mac generations

### Intel MacBooks using `brcmfmac`

This is the main automatic-recovery path. The tool discovers the adapter dynamically; it does not hardcode `02:00.0` or BCM4350.

### Older Broadcom Macs

Older MacBooks can use `b43`, `brcmsmac`, or Broadcom STA/`wl` instead of `brcmfmac`. Common BCM4360/BCM4352 STA IDs are explicitly excluded from the `brcmfmac` PCI recovery path. The distro wrappers can install the normal firmware package and, when appropriate, the distro's STA package.

### T2 MacBooks

2018–2020 Intel MacBook Pro/Air models with Apple's T2 chip need more than a generic Broadcom package. t2linux documents that these machines require a T2-capable kernel plus Apple/macOS Wi-Fi firmware and should use `brcmfmac`, not Broadcom STA/`wl`.

The tool detects the common T2 MacBook model families. It will never auto-install STA on them, and it will not pretend a PCI rescan can replace missing Apple firmware.

See: https://wiki.t2linux.org/guides/wifi-bluetooth/

### Apple Silicon

Apple Silicon uses a different Linux platform/firmware stack. The installer and GUI detect ARM64 and deliberately **do not** apply the Intel Broadcom workaround. Use Asahi Linux / Fedora Asahi Remix support instead.

See: https://asahilinux.org/

## Distros

The core recovery works with Linux sysfs and supports both systemd and OpenRC. Convenience wrappers are included for:

- Arch Linux / EndeavourOS
- Fedora
- Ubuntu / Linux Mint
- Debian

The wrappers try to install the distro's normal Broadcom firmware package when repositories are available. They only try the STA driver for common STA-only Broadcom IDs and never do that on detected T2 Macs.

## Bootloaders

- GRUB
- systemd-boot
- rEFInd
- EFISTUB

No bootloader modification is required. The recovery runs after the kernel enumerates PCI devices, so changing bootloaders does not change the fix.

## Install

```bash
git clone https://github.com/YoYoStudios/MacBook-14-1-Linux-WiFi-Fix.git
cd MacBook-14-1-Linux-WiFi-Fix
sudo bash install.sh
```

Or use a distro wrapper:

```bash
sudo bash distros/arch.sh
sudo bash distros/fedora.sh
sudo bash distros/ubuntu.sh
sudo bash distros/debian.sh
```

Ubuntu's wrapper also covers Linux Mint and most Ubuntu derivatives.

## Diagnose

After installation:

```bash
sudo /usr/local/sbin/macbook-wifi-fix --diagnose
```

From the repo without installing:

```bash
sudo bash src/macbook-wifi-fix --diagnose
```

This prints the model, architecture, distro, Broadcom PCI IDs, active driver, matching kernel modules, interfaces, and recent Broadcom/firmware kernel messages.

## Original MacBookPro14,1 recovery

The command that started this project was:

```bash
echo 1 | sudo tee /sys/bus/pci/devices/0000:02:00.0/remove
echo 1 | sudo tee /sys/bus/pci/rescan
```

The current service finds the correct Wi-Fi PCI function dynamically instead.

## Service status

systemd:

```bash
systemctl status macbook-wifi-fix.service
journalctl -u macbook-wifi-fix.service -b
```

OpenRC:

```bash
rc-service macbook-wifi-fix status
```

## GUI / portable release

The cross-platform GUI can apply the Linux recovery, install/uninstall it locally, install it into a mounted Linux root for distro hopping, or create a portable folder/USB bundle.

Linux ARM64 builds are still produced so an Apple Silicon user can create/manage a portable bundle, but the app will not apply the Intel PCI recovery to the Apple Silicon host.

Native macOS normally does not need the Linux workaround. A Windows Broadcom adapter restart option remains available for Intel MacBooks where Windows itself has an adapter-startup issue.

## Uninstall

```bash
sudo bash uninstall.sh
```

The installer/uninstaller also clean up the old `macbookpro14-1-wifi-fix` service/helper names from v1.

## Research / upstream references

- Linux Wireless Broadcom `brcmfmac` / `brcmsmac`: https://wireless.docs.kernel.org/en/latest/en/users/drivers/brcm80211.html
- Linux Wireless `b43`: https://wireless.docs.kernel.org/en/latest/en/users/drivers/b43.html
- Linux `brcmfmac` PCI driver source: https://github.com/torvalds/linux/blob/master/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c
- t2linux Wi-Fi/Bluetooth: https://wiki.t2linux.org/guides/wifi-bluetooth/
- t2linux post-install/kernel guide: https://wiki.t2linux.org/guides/postinstall/
- Apple T2 model list: https://support.apple.com/103265
- Asahi Linux: https://asahilinux.org/
- Arch `linux-firmware-broadcom`: https://archlinux.org/packages/core/any/linux-firmware-broadcom/
- Fedora `brcmfmac-firmware`: https://packages.fedoraproject.org/pkgs/linux-firmware/brcmfmac-firmware/
- Debian `firmware-brcm80211`: https://packages.debian.org/stable/firmware-brcm80211
- Ubuntu `linux-firmware`: https://packages.ubuntu.com/linux-firmware

## Safety

The project intentionally does **not**:

- hardcode one MacBook model or PCI bus address;
- reset every network device it finds;
- replace an already-working/non-`brcmfmac` driver;
- install Broadcom STA/`wl` on T2 Macs;
- redistribute Apple's proprietary T2 firmware;
- apply Intel Broadcom quirks to Apple Silicon;
- rewrite GRUB, rEFInd, systemd-boot, or EFI variables.

If it cannot identify a safe automatic path, it prints diagnostics and leaves the adapter alone.

## Releases

`VERSION` controls the release version. Updating it triggers the cross-platform GitHub Actions release build.
