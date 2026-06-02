# Get all installed software from registry
$paths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
)

$software = foreach ($path in $paths) {
    if (Test-Path $path) {
        Get-ItemProperty $path | Where-Object { $_.DisplayName } | Select-Object `
            DisplayName, DisplayVersion, Publisher, InstallDate
    }
}

$software | Sort-Object DisplayName | Format-Table -AutoSize
Write-Host "Total: $($software.Count) packages"
