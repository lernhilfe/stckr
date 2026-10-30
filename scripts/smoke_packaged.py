"""Exercise the frozen application's CLI without an installed Python at runtime."""
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np
from stckr.demo import create_demo
from stckr.export import export_image
from stckr.models import ColorInfo


def main():
    executable = Path('dist/STCKR/STCKR.exe' if sys.platform == 'win32' else 'dist/STCKR/STCKR').resolve()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        create_demo(root, 320, 240)
        output = root / 'stack.tif'
        subprocess.run([str(executable), 'stack', *map(str, sorted(root.glob('focus-*.png'))),
                        '--no-align', '-o', str(output), '--cache', str(root / 'cache')], check=True, timeout=120)
        assert output.is_file()
        subprocess.run([str(executable), 'gui', '--smoke-test', str(root)], check=True, timeout=120)
        color = ColorInfo(True, 'STCKR', 'Test camera', [[.7,-.1,-.1],[-.2,1.2,.1],[-.01,.1,.6]], [.5,1,.7])
        for i in range(2):
            export_image(root / f'raw{i}.dng', np.full((48,64,3), .2 + .01*i, np.float32), color)
        subprocess.run([str(executable), 'stack', str(root/'raw0.dng'), str(root/'raw1.dng'),
                        '--no-align', '-o', str(root/'stack.dng'), '--cache', str(root/'rawcache')], check=True, timeout=120)
        assert (root / 'stack.dng').stat().st_size > 1000
    print('Packaged CLI/RAW smoke passed')


if __name__ == '__main__':
    main()
