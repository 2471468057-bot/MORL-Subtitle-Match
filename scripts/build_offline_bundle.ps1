[CmdletBinding()]
param(
    [string]$OutputDir = "",
    [switch]$Lite
)

# 打包便携版 2ByteASR：程序文件 + models/（模型）+ third_party/（固定版本源码）
# + tools/（git/ffmpeg/python/uv 安装器）+ wheels/（Python 依赖，离线安装）。
# 解压到任意目录即可作为完整程序使用（首次运行 setup_2byteasr.bat 安装 Python 环境）。
# 适合国内网络下载模型困难的环境：一次性下载，解压即用。
#
# -Lite：精简版（用于 GitHub Releases，<2GB）——不含模型，只带程序 + 源码 + 内置工具；
# 首次配置时模型自动下载（约 7 GB 默认 / 11.7 GB 含 Qwen，可断点续传）。
#
# 用法：powershell -ExecutionPolicy Bypass -File scripts/build_offline_bundle.ps1 [-Lite]
# 产物：dist/2ByteASR-portable-<日期>.7z（完整版，约 10-12 GB）
#       或 dist/2ByteASR-lite-<日期>.7z（精简版，约 1.5 GB；需要 7-Zip）

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputDir) { $OutputDir = Join-Path $ProjectRoot "dist" }
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$models = Join-Path $ProjectRoot "models"
$thirdParty = Join-Path $ProjectRoot "third_party"
foreach ($required in @((Join-Path $thirdParty "MOSS-Transcribe-Diarize"), (Join-Path $thirdParty "FireRedASR2S"))) {
    if (-not (Test-Path $required)) {
        throw "缺少打包内容：$required（请先运行 setup_environment.bat）"
    }
}
if (-not $Lite -and -not (Test-Path $models)) {
    throw "缺少打包内容：$models（请先运行 download_models.bat）"
}

# 校验模型完整性（与 download_models.bat -VerifyOnly 相同口径）；精简版不含模型
if (-not $Lite) {
    & (Join-Path $PSScriptRoot "download_models.ps1") -VerifyOnly
    if ($LASTEXITCODE -ne 0) {
        throw "模型完整性校验未通过，请先修复模型再打包。"
    }
}

$sevenZipPath = ""
$sevenZipCommand = Get-Command 7z -ErrorAction SilentlyContinue
if ($sevenZipCommand) { $sevenZipPath = $sevenZipCommand.Source }
if (-not $sevenZipPath) {
    foreach ($candidate in @("C:\Program Files\7-Zip\7z.exe", "C:\Program Files (x86)\7-Zip\7z.exe", "G:\VMWARE\7za.exe")) {
        if (Test-Path $candidate) { $sevenZipPath = $candidate; break }
    }
}
if (-not $sevenZipPath) {
    throw "未找到 7-Zip。请安装（winget install 7zip.7zip）后重试。"
}

# 组装便携目录：程序文件（排除运行环境/缓存/产物）+ models + third_party
$staging = Join-Path $OutputDir "staging-2byteasr"
Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $staging -Force | Out-Null

$excludeDirs = @(
    ".venv-main", ".venv-moss", ".venv", ".uv-python", ".uv-cache",
    "tmp", "dist", "backups", "archive", "outputs", "output", "reports",
    "review_tracks", "__pycache__", ".pytest_cache", ".git", ".mimosa", ".zcode",
    "models", "third_party", "2byteasr.setup-complete"
)
Get-ChildItem $ProjectRoot -Force | Where-Object { $_.Name -notin $excludeDirs } |
    ForEach-Object { Copy-Item $_.FullName (Join-Path $staging $_.Name) -Recurse -Force }
if (-not $Lite) {
    Copy-Item $models (Join-Path $staging "models") -Recurse -Force
}
Copy-Item $thirdParty (Join-Path $staging "third_party") -Recurse -Force
Write-Host "[打包] 便携目录已组装：$staging" -ForegroundColor Cyan


function Invoke-Download {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$OutFile
    )
    # 部分站点（download.pytorch.org）会拒绝 PowerShell 默认 UA，先试
    # Invoke-WebRequest，失败改用 curl 回退；多次尝试以对抗网络抖动。
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing -TimeoutSec 300 `
                -UserAgent "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" -ErrorAction Stop
            if ((Get-Item $OutFile).Length -gt 50KB) { return }
            Write-Warning "文件不完整（$Url），重试..."
        } catch {
            Write-Warning "下载失败（$Url）：$($_.Exception.Message)，改用 curl ..."
        }
        if (-not ((Test-Path $OutFile) -and (Get-Item $OutFile).Length -gt 50KB)) {
            Remove-Item $OutFile -Force -ErrorAction SilentlyContinue
            & curl.exe -L --fail --silent --show-error `
                -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" -o $OutFile $Url
            if ($LASTEXITCODE -eq 0 -and (Test-Path $OutFile) -and (Get-Item $OutFile).Length -gt 50KB) {
                return
            }
            Write-Warning "curl 下载失败（$Url），重试（$attempt/3）..."
        }
        Start-Sleep -Seconds 5
    }
    throw "下载失败：$Url"
}

# 收集内置工具（tools/）：ffmpeg、minGit、Python 安装器、uv —— 便携包免联网安装依赖
$tools = Join-Path $staging "tools"
$tmpDownload = Join-Path $OutputDir "tools-tmp"
New-Item -ItemType Directory -Path $tools -Force | Out-Null
New-Item -ItemType Directory -Path $tmpDownload -Force | Out-Null

# FFmpeg（gyan.dev essentials，含 ffmpeg/ffprobe）
Write-Host "[工具] 下载 FFmpeg ..." -ForegroundColor Cyan
$ffmpegZip = Join-Path $tmpDownload "ffmpeg.zip"
Invoke-Download "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" $ffmpegZip
Expand-Archive $ffmpegZip (Join-Path $tmpDownload "ffmpeg") -Force
$ffBin = Get-ChildItem (Join-Path $tmpDownload "ffmpeg") -Recurse -Directory | Where-Object { $_.Name -eq "bin" } | Select-Object -First 1
if (-not $ffBin) { throw "FFmpeg 解压后未找到 bin 目录。" }
New-Item -ItemType Directory -Path (Join-Path $tools "ffmpeg\bin") -Force | Out-Null
Copy-Item (Join-Path $ffBin.FullName "ffmpeg.exe") (Join-Path $tools "ffmpeg\bin") -Force
Copy-Item (Join-Path $ffBin.FullName "ffprobe.exe") (Join-Path $tools "ffmpeg\bin") -Force

# minGit（Git for Windows 精简便携版，含 git）
Write-Host "[工具] 下载 minGit ..." -ForegroundColor Cyan
$gitZip = Join-Path $tmpDownload "mingit.zip"
Invoke-Download "https://ghfast.top/https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.3/MinGit-2.55.0.3-64-bit.zip" $gitZip
Expand-Archive $gitZip (Join-Path $tools "git") -Force
if (-not (Test-Path (Join-Path $tools "git\cmd\git.exe"))) { throw "minGit 解压后未找到 git.exe。" }

# uv
Write-Host "[工具] 下载 uv ..." -ForegroundColor Cyan
$uvZip = Join-Path $tmpDownload "uv.zip"
Invoke-Download "https://ghfast.top/https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" $uvZip
Expand-Archive $uvZip (Join-Path $tmpDownload "uv") -Force
Copy-Item (Join-Path $tmpDownload "uv\uv.exe") (Join-Path $tools "uv.exe") -Force

# Python 官方安装器（3.10 / 3.12）
foreach ($py in @("3.10.11", "3.12.10")) {
    Write-Host "[工具] 下载 Python $py 安装器 ..." -ForegroundColor Cyan
    $pyInstaller = Join-Path $tools "python-$py-amd64.exe"
    $ok = $false
    foreach ($url in @(
        "https://www.python.org/ftp/python/$py/python-$py-amd64.exe",
        "https://mirrors.huaweicloud.com/python/$py/python-$py-amd64.exe"
    )) {
        try { Invoke-Download $url $pyInstaller; $ok = $true; break } catch { Write-Warning "Python $py 下载失败（$url），尝试镜像..." }
    }
    if (-not $ok) { throw "Python $py 安装器下载失败。" }
}

Remove-Item $tmpDownload -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "[工具] 内置工具收集完成：$tools" -ForegroundColor Green

# 思源黑体 Heavy（SIL OFL 开源）：随包分发保证所有机器字体一致；
# 同时放进项目 assets/fonts 供本机开发预览使用。
$fontDir = Join-Path $staging "assets\fonts"
New-Item -ItemType Directory -Path $fontDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $ProjectRoot "assets\fonts") -Force | Out-Null
$fontLocal = Join-Path $ProjectRoot "assets\fonts\SourceHanSansSC-Heavy.otf"
$fontStaged = Join-Path $fontDir "SourceHanSansSC-Heavy.otf"
if (-not (Test-Path $fontLocal)) {
    Write-Host "[字体] 下载思源黑体 Heavy ..." -ForegroundColor Cyan
    Invoke-Download "https://github.com/adobe-fonts/source-han-sans/raw/release/OTF/SimplifiedChinese/SourceHanSansSC-Heavy.otf" $fontLocal
}
Copy-Item $fontLocal $fontStaged -Force
Write-Host "[字体] 思源黑体 Heavy 已就绪：$fontStaged" -ForegroundColor Green

# 依赖 wheel 集（wheels/）：首次配置时离线安装 Python 依赖，无需联网下载。
# 版本来源：本地两个 venv（python -m venv 自带 pip）的精确冻结列表；
# 剔除 torch 家族（离线装 CPU 版，GPU 机器安装后由 setup 自动升级 CUDA 版）。
$WheelsDir = Join-Path $staging "wheels"
New-Item -ItemType Directory -Path $WheelsDir -Force | Out-Null
New-Item -ItemType Directory -Path $tmpDownload -Force | Out-Null
$uvExe = (Get-Command uv).Source
$wheelSpecs = @(
    @{ Label = "主流程(3.10)"; Py = Join-Path $ProjectRoot ".venv-main\Scripts\python.exe" },
    @{ Label = "MOSS(3.12)"; Py = Join-Path $ProjectRoot ".venv-moss\Scripts\python.exe" }
)
foreach ($spec in $wheelSpecs) {
    if (-not (Test-Path $spec.Py)) {
        throw "缺少本地环境 $($spec.Label)（$($spec.Py)），无法收集依赖 wheel。请先运行 setup_environment.bat。"
    }
    Write-Host "[依赖] 冻结 $($spec.Label) 版本清单 ..." -ForegroundColor Cyan
    $freezeFile = Join-Path $tmpDownload "freeze-$($spec.Label).txt"
    # uv 会向 stderr 打印解释器提示，PS 5.1 在 EAP=Stop 下会把它当 NativeCommandError，
    # 调用期间临时降级为 Continue 并丢弃 stderr。
    $previousEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $freezeLines = & $uvExe pip freeze --python $spec.Py 2>$null
    $ErrorActionPreference = $previousEap
    $freezeLines |
        Where-Object {
            $_ -and $_ -notmatch '^(torch|torchaudio|torchvision|nvidia-|pip==)' `
                -and $_ -notmatch '^-e '
        } |
        Set-Content $freezeFile -Encoding ascii
    if ((Get-Item $freezeFile).Length -lt 50) {
        throw "冻结 $($spec.Label) 版本清单为空，请先运行 setup_environment.bat。"
    }
    Write-Host "[依赖] 下载 $($spec.Label) 依赖 wheel（本地 pip 缓存命中，无需网络）..." -ForegroundColor Cyan
    $previousEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    # uv 创建的 venv 可能不带 pip；ensurepip 离线补装
    & $spec.Py -m ensurepip --upgrade --default-pip 2>$null | Out-Null
    # MOSS 以可编辑方式从源码安装（setuptools 构建后端）；离线构建隔离环境
    # 需要 setuptools/wheel 在 wheels/ 里，否则报 “failed to build moss”。
    & $spec.Py -m pip download setuptools wheel --no-deps -d $WheelsDir --quiet --disable-pip-version-check
    # 不用 --only-binary：jieba / sox 等包在 PyPI 只有 sdist（pip download 只下载归档、
    # 不构建）；保留 setuptools/wheel 以便离线安装时构建这些 sdist。
    & $spec.Py -m pip download -r $freezeFile --no-deps `
        -d $WheelsDir --quiet --disable-pip-version-check
    $pipExit = $LASTEXITCODE
    $ErrorActionPreference = $previousEap
    if ($pipExit -ne 0) {
        throw "pip download 失败（$($spec.Label)，退出码 $pipExit）。"
    }
}
# CPU torch / torchaudio（cp310 + cp312），离线安装用；GPU 机器安装后自动升级 CUDA 版。
# 注意：PyTorch 索引对路径中的字面 '+' 返回 403，必须用 %2B 编码。
foreach ($tag in @("cp310", "cp312")) {
    foreach ($pkg in @("torch-2.13.0%2Bcpu", "torchaudio-2.11.0%2Bcpu")) {
        $url = "https://download.pytorch.org/whl/cpu/$pkg-$tag-$tag-win_amd64.whl"
        $out = Join-Path $WheelsDir ($pkg.Replace("%2B", "+") + "-$tag-$tag-win_amd64.whl")
        Invoke-Download $url $out
    }
}
$wheelBytes = (Get-ChildItem $WheelsDir -File | Measure-Object Length -Sum).Sum
Write-Host "[依赖] wheels/ 就绪：$([math]::Round($wheelBytes / 1MB)) MB（首次配置零依赖下载）" -ForegroundColor Green

$stamp = Get-Date -Format "yyyyMMdd"
$baseName = if ($Lite) { "2ByteASR-lite" } else { "2ByteASR-portable" }
$output = Join-Path $OutputDir "$baseName-$stamp.7z"
Remove-Item $output -Force -ErrorAction SilentlyContinue
# 精简版受 GitHub 2GB 单文件限制：超限时自动剔除 wheels/（依赖退回联网安装）
if ($Lite) {
    $stagingBytes = (Get-ChildItem $staging -Recurse -File | Measure-Object Length -Sum).Sum
    if ($stagingBytes -gt 1.9GB) {
        Remove-Item $WheelsDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Warning "精简版打包内容超过 1.9GB，已剔除 wheels/（Python 依赖将联网安装）。"
    }
}
$label = if ($Lite) { "精简版（不含模型，约 300-500 MB）" } else { "完整版（约 9-12 GB）" }
Write-Host "[打包] 正在压缩（$label，可能需要一段时间）..." -ForegroundColor Cyan
$logOut = Join-Path $OutputDir "portable-bundle.log"
$logErr = Join-Path $OutputDir "portable-bundle.err.log"
$p = Start-Process -FilePath $sevenZipPath -ArgumentList @(
    "a", "-t7z", "-mx=1", "-mmt=on", $output, (Join-Path $staging "*")
) -Wait -PassThru -NoNewWindow -RedirectStandardOutput $logOut -RedirectStandardError $logErr
if ($p.ExitCode -ne 0) {
    $tail = ""
    if (Test-Path $logErr) { $tail = "`n" + ((Get-Content $logErr -Tail 10) -join "`n") }
    throw "7-Zip 打包失败（退出码 $($p.ExitCode)）。$tail"
}
Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $logOut, $logErr -Force -ErrorAction SilentlyContinue

Write-Host "[OK] 便携包已生成：$output" -ForegroundColor Green
if ($Lite) {
    Write-Host "用法：解压到任意目录，双击 setup_2byteasr.bat —— 内置 git/ffmpeg/python/uv 无需联网安装，模型会自动下载（约 7 GB，可续传）。" -ForegroundColor Yellow
} else {
    Write-Host "用法：解压到任意目录（如 D:\2ByteASR），双击 setup_2byteasr.bat 完成环境配置后即可使用。" -ForegroundColor Yellow
}
