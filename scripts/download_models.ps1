[CmdletBinding()]
param(
    [switch]$Yes,
    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LockPath = Join-Path $ProjectRoot "dependencies.lock.json"
$HfExe = Join-Path $ProjectRoot ".venv-moss\Scripts\hf.exe"
$ManifestPath = Join-Path $ProjectRoot "models\.twobyteasr-models.json"

function Resolve-ProjectPath {
    param([string]$RelativePath)
    return Join-Path $ProjectRoot ($RelativePath -replace '/', '\')
}

function Test-ModelFiles {
    param($Spec, [switch]$VerifyHashes)
    $root = Resolve-ProjectPath $Spec.path
    foreach ($relative in $Spec.required_files) {
        if (-not (Test-Path (Join-Path $root ($relative -replace '/', '\')))) {
            return $false
        }
    }
    if ($VerifyHashes -and $Spec.sha256) {
        foreach ($property in $Spec.sha256.PSObject.Properties) {
            $path = Join-Path $root ($property.Name -replace '/', '\')
            if (-not (Test-Path -LiteralPath $path)) { return $false }
            $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
            if ($actual -ne [string]$property.Value) { return $false }
        }
    }
    return $true
}

function Test-ModelRevisionMetadata {
    param($Spec)
    $root = Resolve-ProjectPath $Spec.path
    $treeMetadata = Join-Path $root ".cache\huggingface\trees\$($Spec.revision).json"
    return Test-Path -LiteralPath $treeMetadata
}

function Test-AllRequiredFilesHashed {
    param($Spec)
    if (-not $Spec.sha256) { return $false }
    $hashed = @($Spec.sha256.PSObject.Properties | ForEach-Object { $_.Name })
    foreach ($relative in $Spec.required_files) {
        if ([string]$relative -notin $hashed) { return $false }
    }
    return $true
}

function Read-Manifest {
    if (-not (Test-Path $ManifestPath)) { return @{} }
    try {
        $payload = Get-Content -Raw -Encoding UTF8 $ManifestPath | ConvertFrom-Json
        $result = @{}
        foreach ($property in $payload.models.PSObject.Properties) {
            $result[$property.Name] = [string]$property.Value
        }
        return $result
    } catch {
        return @{}
    }
}

function Write-Manifest {
    param([hashtable]$Installed)
    $models = [ordered]@{}
    foreach ($key in ($Installed.Keys | Sort-Object)) { $models[$key] = $Installed[$key] }
    $payload = [ordered]@{
        schema_version = 1
        updated_at = (Get-Date).ToString("o")
        models = $models
    }
    $directory = Split-Path -Parent $ManifestPath
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $tempPath = "$ManifestPath.tmp"
    $payload | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $tempPath
    Move-Item -Force $tempPath $ManifestPath
}

if (-not (Test-Path $LockPath)) { throw "缺少依赖版本清单：$LockPath" }
$Lock = Get-Content -Raw -Encoding UTF8 $LockPath | ConvertFrom-Json
$Installed = Read-Manifest

$modelSpecs = @()
foreach ($property in $Lock.models.PSObject.Properties) {
    $modelSpecs += [pscustomobject]@{ Name = $property.Name; Spec = $property.Value }
}

if ($VerifyOnly) {
    $failed = @()
    foreach ($entry in $modelSpecs) {
        $filesOk = Test-ModelFiles $entry.Spec -VerifyHashes
        $revisionOk = $Installed[$entry.Name] -eq [string]$entry.Spec.revision `
            -or (Test-ModelRevisionMetadata $entry.Spec) `
            -or (Test-AllRequiredFilesHashed $entry.Spec)
        $status = if ($filesOk -and $revisionOk) { "OK" } elseif ($filesOk) { "文件与哈希正确，版本未登记" } else { "缺文件或哈希不匹配" }
        Write-Host "[$status] $($entry.Spec.repository)"
        if (-not $filesOk) { $failed += $entry.Name }
    }
    if ($failed.Count -gt 0) { exit 1 }
    exit 0
}

if (-not (Test-Path $HfExe)) {
    throw "缺少模型下载工具。请先运行 setup_environment.bat。"
}

$driveName = ([System.IO.Path]::GetPathRoot($ProjectRoot)).TrimEnd('\').TrimEnd(':')
$drive = Get-PSDrive -Name $driveName
$freeGb = [math]::Round($drive.Free / 1GB, 1)
Write-Host "2ByteASR 模型下载" -ForegroundColor Cyan
Write-Host "- 下载量约 11 GB，建议至少保留 15 GB 可用空间。"
Write-Host "- 当前项目盘剩余约 $freeGb GB。"
Write-Host "- 下载可中断；重新运行会复用 Hugging Face 已完成的文件。"
$hasMissingFiles = @($modelSpecs | Where-Object { -not (Test-ModelFiles $_.Spec) }).Count -gt 0
if ($hasMissingFiles -and $drive.Free -lt 15GB) {
    throw "磁盘空间不足 15 GB，请清理空间后重试。"
}

if (-not $Yes) {
    $answer = Read-Host "输入 YES 开始下载"
    if ($answer -ne "YES") {
        Write-Host "已取消，未下载模型。"
        exit 0
    }
}

foreach ($entry in $modelSpecs) {
    $name = $entry.Name
    $spec = $entry.Spec
    $filesAndHashesOk = Test-ModelFiles $spec -VerifyHashes
    $revisionOk = $Installed[$name] -eq [string]$spec.revision `
        -or (Test-ModelRevisionMetadata $spec) `
        -or (Test-AllRequiredFilesHashed $spec)
    if ($filesAndHashesOk -and $revisionOk) {
        if ($Installed[$name] -ne [string]$spec.revision) {
            $Installed[$name] = [string]$spec.revision
            Write-Manifest $Installed
        }
        Write-Host "[跳过] $($spec.repository) 已是固定版本。"
        continue
    }
    $destination = Resolve-ProjectPath $spec.path
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Write-Host "[下载] $($spec.repository) @ $($spec.revision)"
    & $HfExe download ([string]$spec.repository) --revision ([string]$spec.revision) --local-dir $destination
    if ($LASTEXITCODE -ne 0) {
        throw "模型下载失败：$($spec.repository)。重新运行可续传。"
    }
    if (-not (Test-ModelFiles $spec -VerifyHashes)) {
        throw "模型下载结束但关键文件缺失或 SHA-256 不匹配：$($spec.repository)"
    }
    if ($name -eq "speaker_embedding") {
        $customPath = Join-Path $destination "custom.py"
        if (-not (Test-Path $customPath)) { New-Item -ItemType File -Path $customPath | Out-Null }
    }
    $Installed[$name] = [string]$spec.revision
    Write-Manifest $Installed
}

Write-Host ""
Write-Host "[完成] 必需模型已准备好，可以运行 sdewa.bat。" -ForegroundColor Green
