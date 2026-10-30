"""Reproducible RSS/time benchmark. Fusion-only reuses a bounded eight-frame corpus.

The fusion-only mode measures N full-size fusion passes, NOT RAW decode/alignment
or the disk footprint of N unique images. End-to-end mode needs ample SSD space.
"""
import argparse
from pathlib import Path
import json
import tempfile
from threading import Event, Thread
import time
import cv2
import numpy as np
import psutil
from PIL import Image
from stckr.engine import run_stack
from stckr.fusion import fuse
from stckr.models import Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--frames', type=int, default=100)
    parser.add_argument('--width', type=int, default=6000)
    parser.add_argument('--height', type=int, default=4000)
    parser.add_argument('--method', choices=['A','B','C'], default='C')
    parser.add_argument('--fusion-only', action='store_true')
    parser.add_argument('--root', default=None)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(dir=args.root) as directory:
        root = Path(directory)
        rng = np.random.default_rng(731)
        # Repeated detail is deliberately synthetic, not a quality benchmark.
        texture = rng.random((250,250,3), dtype=np.float32) * .5 + .1
        base = np.tile(texture, (int(np.ceil(args.height / 250)), int(np.ceil(args.width / 250)), 1))[:args.height,:args.width]
        count = min(args.frames, 8) if args.fusion_only else args.frames
        paths = []
        for i in range(count):
            frame = cv2.GaussianBlur(base, (0,0), .3 + i / max(1,count-1) * 2)
            path = root / f'frame{i:04d}.npy'
            if args.fusion_only:
                np.save(path, frame)
            else:
                path = path.with_suffix('.png')
                Image.fromarray(np.rint(frame*255).astype(np.uint8)).save(path)
            paths.append(str(path))
        del frame, base
        paths = [paths[i % count] for i in range(args.frames)]
        done = Event()
        peak = [0]
        process = psutil.Process()
        def monitor():
            while not done.wait(.03):
                peak[0] = max(peak[0], process.memory_info().rss)
        thread = Thread(target=monitor, daemon=True)
        thread.start()
        cv2.setNumThreads(4)
        start = time.monotonic()
        settings = Settings(method=args.method, align=False)
        try:
            if args.fusion_only:
                image, _ = fuse(paths, settings, output_path=str(root/'result.npy'))
            else:
                result = run_stack(paths, settings, root/'cache')
                image = np.load(result.image_path, mmap_mode='r')
            assert np.isfinite(image).all()
        finally:
            done.set()
            thread.join()
        print(json.dumps({'mode': 'fusion-only-repeated-corpus' if args.fusion_only else 'end-to-end-no-align',
                          'frames':args.frames,'width':args.width,'height':args.height,'method':args.method,
                          'elapsed_seconds':round(time.monotonic()-start,2),'peak_rss_mb':round(peak[0]/2**20,1)},indent=2))


if __name__ == '__main__':
    main()
