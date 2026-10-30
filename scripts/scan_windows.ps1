# Defender CLI scan. No exclusions or security preference changes.
param(
    [Parameter(Mandatory=$true)][string]$PackagePath,
    [Parameter(Mandatory=$true)][string]$ReportPath,
    [switch]$AllowDetections
)
$ErrorActionPreference = 'Stop'
$target = (Resolve-Path -LiteralPath $PackagePath).Path
$reportFile = [IO.Path]::GetFullPath($ReportPath)
$report = [ordered]@{ path = $target; verdict = 'not-scanned'; signatureUpdated = $false; stage = 'initializing' }
$failure = $null
function Find-Scanner {
    $platform = "$env:ProgramData\Microsoft\Windows Defender\Platform"
    $candidate = if (Test-Path $platform) {
        Get-ChildItem "$platform\*\MpCmdRun.exe" | Sort-Object FullName -Descending | Select-Object -First 1
    }
    if ($candidate) { return $candidate.FullName }
    $fallback = "$env:ProgramFiles\Windows Defender\MpCmdRun.exe"
    if (-not (Test-Path $fallback)) { throw 'Microsoft Defender scanner not installed.' }
    return $fallback
}
function Invoke-Scanner([string]$Executable, [string[]]$Options, [string]$Suffix) {
    $stdout = "$reportFile.$Suffix.stdout.txt"
    $stderr = "$reportFile.$Suffix.stderr.txt"
    $process = Start-Process -FilePath $Executable -ArgumentList $Options -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $output = (Get-Content -LiteralPath $stdout -Raw -ErrorAction SilentlyContinue) + `
              (Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue)
    Write-Host $output
    return @{ exitCode = $process.ExitCode; output = $output }
}
try {
    $report.stage = 'start-service'
    Start-Service WinDefend -ErrorAction Stop
    (Get-Service WinDefend).WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
    $scanner = Find-Scanner
    $report.stage = 'signature-update'
    # Use the native CLI, avoiding Defender's WinPSCompat/CIM remoting layer.
    $update = Invoke-Scanner $scanner @('-SignatureUpdate') 'update'
    $report.updateOutput = $update.output
    if ($update.exitCode -ne 0) { throw "Defender signature update failed (exit $($update.exitCode))." }
    $report.signatureUpdated = $true
    $scanner = Find-Scanner
    $report.scannerVersion = (Get-Item $scanner).VersionInfo.FileVersion
    $report.stage = 'custom-scan'
    # DisableRemediation applies ONLY to this scan: detect/report without quarantining.
    # Preferences, real-time protection and exclusions are never modified.
    $scan = Invoke-Scanner $scanner @('-Scan', '-ScanType', '3', '-File', ('"' + $target + '"'), '-DisableRemediation') 'scan'
    $report.exitCode = $scan.exitCode
    $report.scanOutput = $scan.output
    $report.verdict = if ($scan.exitCode -eq 0) { 'clean' } elseif ($scan.exitCode -eq 2) { 'detected-or-scan-error' } else { 'scan-error' }
    if ($scan.exitCode -ne 0 -and -not ($AllowDetections -and $scan.exitCode -eq 2)) {
        throw "Defender scan failed or reported a detection (exit $($scan.exitCode))."
    }
    $report.stage = 'finished'
} catch {
    $report.error = $_.Exception.Message
    $failure = $_
} finally {
    $json = $report | ConvertTo-Json -Depth 8
    $json | Set-Content -LiteralPath $reportFile -Encoding utf8
    Write-Output $json
}
if ($failure) { throw $failure }
