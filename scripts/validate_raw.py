"""Decode real M50 samples, stack RAW+C-RAW and validate with Adobe's SDK.

No sample photographs are copied into the source repository.
"""
import argparse
from pathlib import Path
import json
import subprocess
import numpy as np
import rawpy
from stckr.engine import run_stack
from stckr.models import Settings, ColorInfo
from stckr.export import export_image
from stckr.imaging import decode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('samples', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--validator')
    args = parser.parse_args()
    files = [args.samples / 'IMG_0482_raw.CR3', args.samples / 'IMG_0483_craw.CR3']
    result = run_stack(list(map(str,files)), Settings(), args.output / 'cache')
    image = np.load(result.image_path,mmap_mode='r')
    out = args.output / 'm50-stack.dng'
    export_image(out,image,ColorInfo(**result.color),overwrite=True)
    with rawpy.imread(str(out)) as raw:
        pixels = raw.postprocess(output_color=rawpy.ColorSpace.raw, output_bps=16, gamma=(1,1),
                                 user_wb=[1,1,1,1],no_auto_bright=True,adjust_maximum_thr=0)
        assert pixels.shape == image.shape
        assert np.max(np.abs(pixels/65535-np.clip(image,0,1))) < .001
    for source in files:
        _, color = decode(str(source), preview=True)
        assert color.raw and 'M50' in color.model
    if args.validator:
        import sys
        subprocess.run([sys.executable,str(Path(__file__).with_name('validate_dng.py')),args.validator,str(out)],check=True)
    print(json.dumps({'result':result.to_dict(),'raw_roundtrip':'passed'},indent=2))


if __name__ == '__main__':
    main()
