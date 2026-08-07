[CmdletBinding()]
param(
    [ValidatePattern('^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$')]
    [string]$Version = "0.1.0-dev",
    [ValidatePattern('^[0-9A-Fa-f]{40}$')]
    [string]$SignThumbprint = "",
    [ValidatePattern('^https://')]
    [string]$TimestampUrl = "https://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$InstallerScript = Join-Path $ProjectRoot "installer\2ByteASR.iss"

& (Join-Path $PSScriptRoot "build_launcher.ps1")

$compilerCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
)
$compiler = $compilerCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $compiler) {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) { $compiler = $command.Source }
}
if (-not $compiler) {
    throw "Inno Setup 6 was not found. Run: winget install --id JRSoftware.InnoSetup -e"
}

New-Item -ItemType Directory -Path (Join-Path $ProjectRoot "dist") -Force | Out-Null
$compilerArguments = @("/DMyAppVersion=$Version")
if ($SignThumbprint) {
    $signTool = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if (-not $signTool) {
        throw "signtool.exe was not found. Install the Windows SDK before signing."
    }
    $signCommand = ('"{0}" sign /sha1 {1} /fd SHA256 /tr {2} /td SHA256 /d $q2ByteASR$q $f' -f $signTool.Source, $SignThumbprint, $TimestampUrl)
    $compilerArguments += "/S2ByteASRSign=$signCommand"
    $compilerArguments += "/DMySignTool=2ByteASRSign"
}
$compilerArguments += $InstallerScript
& $compiler @compilerArguments
if ($LASTEXITCODE -ne 0) {
    throw "Installer build failed (ISCC exit code $LASTEXITCODE)."
}

$output = Join-Path $ProjectRoot "dist\2ByteASR-Setup-$Version.exe"
if (-not (Test-Path -LiteralPath $output)) {
    throw "Installer output is missing: $output"
}
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $output).Hash
$checksumPath = "$output.sha256"
"$($hash.ToLowerInvariant())  $([IO.Path]::GetFileName($output))" | Set-Content -Encoding ascii $checksumPath
if ($SignThumbprint) {
    & $signTool.Source verify /pa /all $output
    if ($LASTEXITCODE -ne 0) { throw "Installer signature verification failed." }
}
Write-Host "[OK] $output" -ForegroundColor Green
Write-Host "SHA256 $hash"
Write-Host "[OK] $checksumPath" -ForegroundColor Green
