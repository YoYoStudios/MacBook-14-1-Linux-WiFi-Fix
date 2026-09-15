# Windows helper

Windows normally does not need the Linux PCI recovery. This optional helper is for Intel MacBooks where Windows itself has a Broadcom adapter-startup issue.

It checks that the machine identifies as a MacBook, restarts present Broadcom PCI network adapters, then asks Windows to rescan devices.

Run PowerShell as Administrator:

```powershell
powershell -ExecutionPolicy Bypass -File .\Install-WindowsFix.ps1
```

Remove it with:

```powershell
powershell -ExecutionPolicy Bypass -File .\Install-WindowsFix.ps1 -Uninstall
```
