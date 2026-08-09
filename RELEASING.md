# Release checklist

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
