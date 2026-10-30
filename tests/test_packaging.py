"""Distribution checks independent of a Windows machine or AV signature database."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('portable_build', ROOT / 'scripts' / 'build_portable.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def test_runtime_copy_preserves_originals_and_excludes_host_packages(tmp_path):
    source = tmp_path / 'standard CPython'
    (source / 'DLLs').mkdir(parents=True)
    (source / 'Lib' / 'site-packages').mkdir(parents=True)
    (source / 'Lib' / 'test').mkdir()
    for name in ('python.exe', 'pythonw.exe', 'python313.dll', 'LICENSE.txt'):
        (source / name).write_bytes(('original ' + name).encode())
    (source / 'DLLs' / '_ssl.pyd').write_bytes(b'native extension')
    (source / 'Lib' / 'os.py').write_text('# standard library')
    (source / 'Lib' / 'site-packages' / 'unrelated.py').write_text('# host environment')
    (source / 'Lib' / 'test' / 'test_os.py').write_text('# development only')
    target = tmp_path / 'portable app' / 'runtime'
    build.copy_runtime(source, target)
    assert (target / 'pythonw.exe').read_bytes() == (source / 'pythonw.exe').read_bytes()
    assert (target / 'python313.dll').read_bytes() == (source / 'python313.dll').read_bytes()
    assert (target / 'DLLs' / '_ssl.pyd').exists()
    assert not (target / 'Lib' / 'site-packages').exists()
    assert not (target / 'Lib' / 'test').exists()


def test_manifest_covers_source_and_runtime_and_ignores_generated_cache(tmp_path):
    (tmp_path / 'app' / 'stckr').mkdir(parents=True)
    (tmp_path / 'runtime').mkdir()
    (tmp_path / 'app' / 'stckr' / '__init__.py').write_bytes(b'# readable application')
    (tmp_path / 'runtime' / 'pythonw.exe').write_bytes(b'original interpreter')
    (tmp_path / '__pycache__').mkdir()
    (tmp_path / '__pycache__' / 'generated.pyc').write_bytes(b'generated')
    build.write_manifest(tmp_path)
    hashes = json.loads((tmp_path / 'SHA256SUMS.json').read_text())
    assert set(hashes) == {'app/stckr/__init__.py', 'runtime/pythonw.exe'}
    for name, expected in hashes.items():
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == expected


def test_launcher_is_readable_and_uses_isolated_unmodified_interpreter():
    assert 'runtime\\pythonw.exe' in build.LAUNCHER
    assert '-I "%~dp0start.pyw"' in build.LAUNCHER
    assert 'multiprocessing.freeze_support()' in build.ENTRYPOINT
    assert 'sys.path.insert' in build.ENTRYPOINT
    assert 'powershell' not in build.LAUNCHER.lower()
