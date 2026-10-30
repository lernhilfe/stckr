"""Exercise the self-contained application, including GUI child-process start."""
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np
from stckr.demo import create_demo
from stckr.export import export_image
from stckr.models import ColorInfo


def main():
    package = Path('dist/STCKR').resolve()
    if (package / 'runtime' / 'python.exe').exists():
        command = [str(package / 'runtime' / 'python.exe'), '-I', str(package / 'start.pyw')]
        gui_command = [str(package / 'runtime' / 'pythonw.exe'), '-I', str(package / 'start.pyw')]
    else:
        command = [str(package / ('STCKR.exe' if sys.platform == 'win32' else 'STCKR'))]
        gui_command = command
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        create_demo(root, 320, 240)
        output = root / 'stack.tif'
        subprocess.run([*command, 'stack', *map(str, sorted(root.glob('focus-*.png'))),
                        '--no-align', '-o', str(output), '--cache', str(root / 'cache')], check=True, timeout=120)
        assert output.is_file()
        subprocess.run([*gui_command, 'gui', '--smoke-test', str(root)], check=True, timeout=120)
        color = ColorInfo(True, 'STCKR', 'Test camera', [[.7,-.1,-.1],[-.2,1.2,.1],[-.01,.1,.6]], [.5,1,.7])
        for i in range(2):
            export_image(root / f'raw{i}.dng', np.full((48,64,3), .2 + .01*i, np.float32), color)
        subprocess.run([*command, 'stack', str(root/'raw0.dng'), str(root/'raw1.dng'),
                        '--no-align', '-o', str(root/'stack.dng'), '--cache', str(root/'rawcache')], check=True, timeout=120)
        assert (root / 'stack.dng').stat().st_size > 1000
    print('Packaged CLI/RAW smoke passed')


if __name__ == '__main__':
    main()
