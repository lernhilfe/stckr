# Read-only Defender custom scan. No exclusions or security preference changes.
param(
    [Parameter(Mandatory=$true)][string]$PackagePath,
    [Parameter(Mandatory=$true)][string]$ReportPath,
    [switch]$AllowDetections
)
$ErrorActionPreference = 'Stop'
$target = (Resolve-Path -LiteralPath $PackagePath).Path
$report = [ordered]@{ path = $target; verdict = 'not-scanned'; signatureUpdated = $false }
$scannerOutput = ''
$failure = $null
try {
    Import-Module Defender -ErrorAction Stop
    Start-Service WinDefend -ErrorAction Stop
    Update-MpSignature -ErrorAction Stop
    $status = Get-MpComputerStatus
    if (-not $status.AMServiceEnabled -or -not $status.AntivirusEnabled) {
        throw 'Microsoft Defender is not available for a verified scan.'
    }
    $report.signatureUpdated = $true
    $report.engineVersion = $status.AMEngineVersion
    $report.signatureVersion = $status.AntivirusSignatureVersion
    $report.signatureUpdatedAt = [string]$status.AntivirusSignatureLastUpdated
    $scanner = Get-ChildItem "$env:ProgramData\Microsoft\Windows Defender\Platform\*\MpCmdRun.exe" |
        Sort-Object FullName -Descending | Select-Object -First 1
    $executable = if ($scanner) { $scanner.FullName } else { "$env:ProgramFiles\Windows Defender\MpCmdRun.exe" }
    # DisableRemediation applies ONLY to this scan: detect/report without quarantining.
    # Preferences, real-time protection and exclusions are never modified.
    $scannerOutput = (& $executable -Scan -ScanType 3 -File $target -DisableRemediation 2>&1 | Out-String)
    $exitCode = $LASTEXITCODE
    $report.exitCode = $exitCode
    $report.scanOutput = $scannerOutput
    $report.verdict = if ($exitCode -eq 0) { 'clean' } elseif ($exitCode -eq 2) { 'detected-or-scan-error' } else { 'scan-error' }
    if ($exitCode -ne 0 -and -not ($AllowDetections -and $exitCode -eq 2)) {
        throw "Defender scan failed or reported a detection (exit $exitCode)."
    }
} catch {
    $report.error = $_.Exception.Message
    $failure = $_
} finally {
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding utf8
    Write-Output $scannerOutput
}
if ($failure) { throw $failure }
