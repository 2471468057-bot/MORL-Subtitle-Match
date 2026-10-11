# Release checklist

## 当前发布流程（2026-10-11 起，0.6.5）

全部在受控建置机上执行；签名私钥只在这台机器（`%USERPROFILE%\.2byteasr-release`，DPAPI 加密），从不进仓库、安装包或 CI。脚本拒绝覆盖已有输出，也拒绝替换已经公开的 Release 附件；修正一律走新版本号。

1. 改 `2byteasr_version.json` 的 `version`（stable 渠道 `channel: "stable"`），运行
   `python scripts/sync_product_version.py` 同步 EXE 版本资源与 renderer 版本。
2. `python -B scripts/release_pipeline.py freeze --version X.Y.Z --output tmp/release-XYZ/build-r1`
   ：固定快照 → PyInstaller → 编译 `2ByteASRUpdater.exe` → 写 `2byteasr_components.json` → 载荷扫描（只有已复核例外可放行）→ Build Truth → Setup。
3. `python -B scripts/release_pipeline.py feed --build <build> --assets releases/X.Y.Z --notes-json docs/releases/X.Y.Z.in-app.json --previous-manifest https://github.com/NOTBAD314/2ByteASR/releases/download/v<上一版>/2ByteASR-update.json`
   ：内容没变的元件直接引用上一版已公开的固定附件，只为变化的元件生成新包；生成并签名 `2ByteASR-update.json(.sig)`。
4. `python -B scripts/release_pipeline.py sources --build <build> --assets releases/X.Y.Z --review-commit <commit> --extra <固定第三方源码包>`，然后 `sums --assets releases/X.Y.Z`。
5. 用 `scripts/verify_release_install.py`（隔离 profile、AUDIT 安装）做全新安装、旧版覆盖升级、卸载；用 `scripts/qa_update_feed.py` 做只在本机的下一版更新与故障测试（渠道 `qa-local`，永不上传）。
6. `python -B scripts/release_public_tree.py --stage <build>/source --base origin/main --branch release/vX.Y.Z ...`：以公开线为父提交、只更新程序源码路径，并扫描密钥/个人路径；`git push origin release/vX.Y.Z`（提交信息带 `[skip ci]`）。
7. `python -B scripts/release_pipeline.py upload --assets releases/X.Y.Z --tag vX.Y.Z --target <release commit> --title ... --notes-file docs/releases/X.Y.Z.md`
   ：建立**草稿**并上传，逐件核对大小与服务端 SHA-256，认证读回小文件。
8. 所有者检查后手动 Publish。之后运行 `python -B scripts/release_pipeline.py verify-public --tag vX.Y.Z --assets releases/X.Y.Z`（不带任何凭据），或在 GitHub Actions 手动运行 `verify-public-release`，确认 Setup、更新清单及其引用的全部附件都能匿名下载。

`.github/workflows/release.yml` 不再在推送 tag 时构建或创建 Release，只做手动匿名校验。仓库仍为私有时，匿名下载必然失败；这不是发布脚本的问题。

公开门：`licenses/DISTRIBUTION-STATUS.md`、`licenses/GPL3_ROUTE.md` 所列对应源码与第三方组合权利问题未关闭前，不应把二进制宣称为已满足公开分发条件。

## 旧流程（历史记录，勿再使用）

2026-09-29 的冻结流程已被上面的流程取代；下方 `build_installer.ps1` / tag CI 是更早的源码式流程。

## Before the first public push

1. Choose the final GitHub owner, repository name, visibility, description, and topics.
2. Review `README.md`, `LICENSE`, `THIRD_PARTY_NOTICES.md`, and `SECURITY.md` with the repository owner identity filled in where appropriate.
3. Run the offline checks:

   ```powershell
   .\.venv-main\Scripts\python.exe -m pytest -q tests
   .\.venv-main\Scripts\python.exe scripts\check_release_hygiene.py
   ```

4. Inspect the exact Git candidate set before committing:

   ```powershell
   git status --short
   git ls-files --others --exclude-standard
   ```

The model weights, virtual environments, third-party checkouts, media, reports, backups, generated binaries, and installer output must remain ignored.

## Build a local installer

Install Inno Setup 6, then run:

```powershell
.\scripts\build_installer.ps1 -Version 0.1.0
```

The result is `dist\2ByteASR-Setup-0.1.0.exe`. The build script prints its SHA-256 digest.

## Publish a release

After the main branch has been pushed and CI is green:

```powershell
git tag -a v0.1.0 -m "2ByteASR 0.1.0"
git push origin main
git push origin v0.1.0
```

The `build-release-installer` workflow reruns tests on Windows, builds the installer, and attaches it to a GitHub Release.

For routine updates, increment only the patch version and keep the installer `AppId`, install directory, and unchanged model revisions stable. Users should install over the previous version rather than uninstalling it. See [UPDATING.md](UPDATING.md) for the preservation and model-download rules.

## Code signing

Without a certificate, the installer and launcher are unsigned and Windows SmartScreen may warn users. When a code-signing certificate is installed in the current user's certificate store and the Windows SDK `signtool.exe` is available, build with its 40-character SHA-1 thumbprint:

```powershell
.\scripts\build_installer.ps1 -Version 0.1.0 -SignThumbprint "<certificate-thumbprint>"
```

The build signs the installer and generated uninstaller with SHA-256, adds an HTTPS timestamp, then verifies the installer signature. Do not place a signing certificate or password in the repository; use a protected release environment or an external signing service.

## Release notes

Every release should state:

- supported Windows and GPU requirements;
- that first-time setup downloads pinned models (~7 GB by default, ~11.7 GB with the optional Qwen reviewer);
- whether the executables are signed;
- cloud text-processing behavior and the configured provider;
- noteworthy compatibility or model changes.
