# Windows packaging and the reported antivirus block

The first Windows ZIP used a PyInstaller-generated `STCKR.exe`. A user reported a Windows malware block and two VirusTotal verdicts: Arctic Wolf `Trojan:Win32/Wacatac.C!ml` and SecureAge `Static AI - Suspicious PE`. These names alone do not establish either a confirmed infection or a confirmed false positive. Do not bypass the detection, restore/quarantine-whitelist the EXE, or disable protection to run that artifact.

The default Windows distribution now uses an application-local standard CPython runtime and readable application source, with no generated STCKR executable or PyInstaller bootloader. Double-click **STCKR.cmd** after extracting the entire new ZIP. It invokes the unchanged `runtime/pythonw.exe` with `-I` and `start.pyw`. Python does not need to be installed and the app does not download/install anything at launch.

## Release checks

- Dependency wheels are installed at build time from `uv.lock` with required hashes.
- The original `python.exe` and `pythonw.exe` must retain valid Python Software Foundation Authenticode signatures; otherwise the Windows build fails.
- `BUILD.json` records source commit, interpreter version and packaging type. `SHA256SUMS.json` records every input file before execution.
- The complete packaged application is tested through its own interpreter: TIFF fusion, Linear-DNG import/export, and GUI worker process startup.
- Microsoft Defender signatures are updated, and the entire resulting program folder is custom-scanned before the download artifact is uploaded. A failed/unavailable scan or a nonzero scan result blocks the program download. Reports are uploaded separately, including on failure.
- `scan_windows.ps1` does not alter Defender preferences, exclusions or real-time protection. `-DisableRemediation` is a scan-local diagnostic option so that findings are reported without deleting files during that scan.
- A separate one-off audit downloads the exact previously reported artifact from run `41085697425`, records its SHA-256, and scans it without executing it. The original artifact is not republished by that audit.

These checks document what ran on the build machine; a clean scan does not guarantee that every security product or later signature version will agree. If a new package is blocked, record the exact file, detection name and SHA-256 and keep the block in place for investigation.

The generated app script is not itself code-signed. The original CPython interpreter signature does not sign STCKR's Python source. The old PyInstaller spec remains available for development and Linux packaging; it is no longer the Windows download path.

## Rebuild

Use standard Windows CPython 3.13 (not a virtualenv), uv, and the checked-out source. First run the locked development environment to download the hash-verified ExifTool bundle and collect license texts, then:

```powershell
uv sync --frozen --extra dev
uv run python scripts/vendor_exiftool.py
uv run python scripts/collect_licenses.py
python scripts/build_portable.py
./scripts/check_signatures.ps1
uv run python scripts/smoke_packaged.py
./scripts/scan_windows.ps1 -PackagePath dist/STCKR -ReportPath defender-scan.json
```

The GitHub Actions workflow performs these steps in order. No scanner findings are suppressed to produce the downloadable app.
