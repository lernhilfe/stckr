import multiprocessing as mp
from pathlib import Path
from queue import Empty
import numpy as np
from PIL import Image
from stckr.engine import worker
from stckr.models import Settings
from dataclasses import asdict


def test_windows_compatible_spawn_worker(tmp_path):
    paths = []
    for i in range(2):
        path = tmp_path / f'frame{i}.png'
        Image.fromarray(np.full((48,64,3), 90 + i, np.uint8)).save(path)
        paths.append(str(path))
    ctx = mp.get_context('spawn')
    queue, cancel = ctx.Queue(), ctx.Event()
    process = ctx.Process(target=worker, args=(paths, asdict(Settings(align=False)), str(tmp_path/'cache'),queue,cancel))
    process.start()
    result = None
    try:
        while True:
            message = queue.get(timeout=30)
            assert message[0] != 'error', message
            if message[0] == 'result':
                result = message[1]
                break
    except Empty:
        raise AssertionError('Worker timeout')
    finally:
        process.join(5)
        if process.is_alive():
            process.terminate()
            process.join()
        queue.close()
    assert process.exitcode == 0
    assert Path(result['directory'], 'result.npy').is_file()
