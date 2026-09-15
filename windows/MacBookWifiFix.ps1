param([switch]$Quiet)

$ErrorActionPreference = "Stop"
$model = (Get-CimInstance Win32_ComputerSystemProduct).Name
if ($model -notmatch '^MacBook') {
    if (-not $Quiet) { Write-Host "Not an Apple MacBook ($model); skipping." }
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
