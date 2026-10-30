"""Application-local CPython distribution with readable source, no frozen bootloader.

Run on Windows with a standard CPython installation (CI: actions/setup-python).
Dependencies are wheel-installed from the hash-locked uv export into the copied
runtime. The Python launchers are copied byte-for-byte, never modified/repacked.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'dist' / 'STCKR'
ENTRYPOINT = '''"""STCKR portable entry point. Application source is in app/stckr."""
from pathlib import Path
import multiprocessing
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'app'))

if __name__ == '__main__':
    multiprocessing.freeze_support()
    from stckr.__main__ import main
    raise SystemExit(main())
'''
LAUNCHER = '''@echo off
setlocal
rem Application-local, unmodified CPython. No install or network access at launch.
"%~dp0runtime\\pythonw.exe" -I "%~dp0start.pyw" %*
'''


def copy_runtime(base: Path, target: Path):
    target.mkdir(parents=True)
    for name in ('python.exe', 'pythonw.exe'):
        shutil.copy2(base / name, target / name)
    for path in base.glob('*.dll'):
        shutil.copy2(path, target / path.name)
    for name in ('LICENSE.txt', 'LICENSE'):
        if (base / name).exists():
            shutil.copy2(base / name, target / name)
    shutil.copytree(base / 'DLLs', target / 'DLLs',
                    ignore=shutil.ignore_patterns('__pycache__', '_tkinter.pyd', '*_test*'))
    shutil.copytree(base / 'Lib', target / 'Lib',
                    ignore=shutil.ignore_patterns('site-packages', '__pycache__', 'test', 'tests',
                                                 'ensurepip', 'idlelib', 'tkinter', 'turtledemo'))
    for name in ('python.exe', 'pythonw.exe'):
        if (target / name).read_bytes() != (base / name).read_bytes():
            raise ValueError(f'Interpreter copy differs: {name}')


def write_manifest(destination: Path):
    manifest = {}
    for path in sorted(destination.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            with path.open('rb') as handle:
                digest = hashlib.file_digest(handle, 'sha256').hexdigest()
            manifest[path.relative_to(destination).as_posix()] = digest
    (destination / 'SHA256SUMS.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def main():
    if sys.platform != 'win32':
        raise SystemExit('Build the Windows portable package on Windows.')
    if sys.prefix != sys.base_prefix:
        raise SystemExit('Use the standard CPython executable, not a virtualenv, to build the runtime.')
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    DESTINATION.mkdir(parents=True)
    copy_runtime(Path(sys.base_prefix), DESTINATION / 'runtime')
    dependencies = DESTINATION / 'DEPENDENCIES.txt'
    subprocess.run(['uv', 'export', '--frozen', '--no-dev', '--no-emit-project',
                    '--format', 'requirements-txt', '--output-file', str(dependencies)], cwd=ROOT, check=True)
    subprocess.run(['uv', 'pip', 'install', '--python', sys.executable,
                    '--target', str(DESTINATION / 'runtime' / 'Lib' / 'site-packages'),
                    '--require-hashes', '-r', str(dependencies)], check=True)
    shutil.copytree(ROOT / 'src' / 'stckr', DESTINATION / 'app' / 'stckr',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(ROOT / 'vendor', DESTINATION / 'vendor')
    for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT / name, DESTINATION / name)
    (DESTINATION / 'start.pyw').write_text(ENTRYPOINT, encoding='utf-8')
    (DESTINATION / 'STCKR.cmd').write_bytes(LAUNCHER.replace('\n', '\r\n').encode('ascii'))
    (DESTINATION / 'START-HERE.txt').write_text(
        'STCKR fuer Windows\n\nDen gesamten Ordner entpacken, dann STCKR.cmd starten.\n'
        'Python und Adobe DNG Converter muessen nicht installiert sein.\n'
        'Kein Herunterladen oder Installieren beim Start.\n'
        'Anwendungscode: app/stckr. Original-Interpreter: runtime/pythonw.exe.\n'
        'SHA256SUMS.json dokumentiert die Dateien vor dem Start.\n', encoding='utf-8')
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    (DESTINATION / 'BUILD.json').write_text(json.dumps({
        'commit': sha, 'python': sys.version, 'packaging': 'application-local-cpython',
        'launcher': 'STCKR.cmd -> runtime/pythonw.exe -I start.pyw',
    }, indent=2), encoding='utf-8')
    write_manifest(DESTINATION)
    print(DESTINATION)


if __name__ == '__main__':
    main()
