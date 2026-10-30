param([string]$PackagePath = 'dist/STCKR')
$ErrorActionPreference = 'Stop'
$report = @()
foreach ($name in @('python.exe', 'pythonw.exe')) {
    $path = Join-Path $PackagePath "runtime/$name"
    $signature = Get-AuthenticodeSignature -LiteralPath $path
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
        throw "Expected an unchanged, valid PSF signature on $path; got $($signature.Status)"
    }
    $report += [ordered]@{
        path = "runtime/$name"
        signature = [string]$signature.Status
        signer = $signature.SignerCertificate.Subject
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    }
}
$report | ConvertTo-Json -Depth 4 | Set-Content 'interpreter-signatures.json' -Encoding utf8
