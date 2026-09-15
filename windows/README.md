# Windows helper

Windows normally does not need the Linux PCI reset. This optional helper restarts the Broadcom network device at boot on a MacBookPro14,1 if Windows ever shows the same adapter-startup problem.

Run PowerShell as Administrator:

```powershell
powershell -ExecutionPolicy Bypass -File .\Install-WindowsFix.ps1
```

Remove it with:

```powershell
powershell -ExecutionPolicy Bypass -File .\Install-WindowsFix.ps1 -Uninstall
```
