param([switch]$Uninstall)

$ErrorActionPreference = "Stop"
$task = "MacBook-WiFi-Fix"
$legacyTask = "MacBookPro14_1-WiFi-Fix"
$dir = Join-Path $env:ProgramData "MacBookWiFiFix"
$script = Join-Path $dir "MacBookWifiFix.ps1"

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $legacyTask -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item $dir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Windows startup workaround removed."
    exit 0
}

Unregister-ScheduledTask -TaskName $legacyTask -Confirm:$false -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Copy-Item -Force "$PSScriptRoot\MacBookWifiFix.ps1" $script

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -Quiet"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
Write-Host "Windows startup workaround installed."
