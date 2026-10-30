from pathlib import Path
from threading import Event
import numpy as np
import cv2
import pytest
import tifffile
import rawpy
from PIL import Image

from stckr.models import Settings, ColorInfo, Cancelled
from stckr.engine import run_stack
from stckr.fusion import fuse
from stckr.alignment import estimate_transform, valid_crop
from stckr.export import export_image
from stckr.imaging import decode
from stckr.retouch import Retoucher
from stckr.project import save_project, load_project


@pytest.fixture
def series(tmp_path):
    rng = np.random.default_rng(42)
    truth = cv2.GaussianBlur(rng.random((192, 256, 3), dtype=np.float32), (0, 0), .6)
    blurred = cv2.GaussianBlur(truth, (0, 0), 3)
    paths = []
    for i in range(3):
        frame = blurred.copy()
        frame[:, i * 85:(i + 1) * 85] = truth[:, i * 85:(i + 1) * 85]
        p = tmp_path / f"frame{i}.npy"
        np.save(p, frame)
        paths.append(str(p))
    return paths, truth


@pytest.mark.parametrize("method", ["A", "B", "C"])
def test_fusion_restores_detail(series, method):
    paths, truth = series
    image, indices = fuse(paths, Settings(method=method, radius=3, smoothing=.5, levels=5))
    # Exclude defocus boundaries when measuring selected focal-plane detail.
    mask = np.ones(truth.shape[:2], bool)
    mask[:, :8] = mask[:, -8:] = False
    for x in [85, 170]:
        mask[:, x - 10:x + 10] = False
    mse = np.mean((image[mask] - truth[mask])**2)
    baseline = min(np.mean((np.load(p)[mask] - truth[mask])**2) for p in paths)
    assert mse < baseline * .6
    assert image.dtype == np.float32
    assert np.isfinite(image).all()
    assert indices.shape == truth.shape[:2]
    assert np.mean(indices[:, 15:70] == 0) > .95


@pytest.mark.parametrize("method", ["A", "B", "C"])
def test_uniform_color_no_nan(tmp_path, method):
    a = np.full((48, 64, 3), [.1, .25, .7], np.float32)
    p = tmp_path / "a.npy"
    np.save(p, a)
    result, _ = fuse([str(p)] * 3, Settings(method=method))
    assert np.max(np.abs(result - a)) < 1e-6


def test_registration_subpixel_similarity():
    rng = np.random.default_rng(6)
    ref = cv2.GaussianBlur(rng.random((384, 512, 3), dtype=np.float32), (0, 0), .8)
    transform = cv2.getRotationMatrix2D((256, 192), 1.4, 1.015)
    transform[:, 2] += [.65, -1.35]
    cur = cv2.warpAffine(ref, transform, (512, 384), borderMode=cv2.BORDER_REFLECT)
    estimated = estimate_transform(ref, cur)
    forward = np.vstack([transform, [0, 0, 1]])
    points = np.array([[70, 60, 1], [400, 70, 1], [256, 192, 1], [410, 320, 1]]).T
    errors = np.linalg.norm(((estimated @ forward @ points) - points)[:2], axis=0)
    assert np.median(errors) < .5


def test_crop_is_entirely_valid():
    mask = np.ones((101, 173), bool)
    mask[:7] = False
    mask[:, :13] = False
    mask[60:, 130:] = False
    x0, y0, x1, y1 = valid_crop(mask)
    assert mask[y0:y1, x0:x1].all()
    assert (x1 - x0) * (y1 - y0) > 7000


def test_dng_independent_decoder_and_precision(tmp_path):
    a = np.linspace(.001, .8, 64 * 48 * 3, dtype=np.float32).reshape(48, 64, 3)
    color = ColorInfo(True, "STCKR", "Test camera", [[.7, -.1, -.1], [-.2, 1.2, .1], [-.01, .1, .6]], [.5, 1, .7])
    out = tmp_path / "linear.dng"
    export_image(out, a, color)
    with tifffile.TiffFile(out) as tf:
        assert tf.pages[0].photometric == 34892
        assert tf.pages[0].tags[254].value == 0
        assert tf.pages[0].tags[50717].count == 3
        assert tf.pages[0].subifds
        assert 338 not in tf.pages[0].tags
        assert tf.pages[0].tags[50706].value == bytes([1, 4, 0, 0])
        assert tf.pages[0].tags[50728].count == 3
        assert tf.pages[0].asarray().dtype == np.uint16
        assert np.max(np.abs(tf.pages[0].asarray() / 65535 - a)) < 1 / 65535
    with rawpy.imread(str(out)) as raw:
        rgb = raw.postprocess(output_color=rawpy.ColorSpace.raw, output_bps=16, gamma=(1, 1),
                              user_wb=[1, 1, 1, 1], no_auto_bright=True, adjust_maximum_thr=0)
        assert rgb.shape == a.shape
        assert np.max(np.abs(rgb / 65535 - a)) < .001
    # Camera RGB and as-shot metadata can also be ingested through the normal RAW pipeline.
    image, info = decode(out)
    assert image.shape == a.shape and info.raw


def test_dng_not_allowed_for_developed_input(tmp_path):
    with pytest.raises(ValueError, match="RAW"):
        export_image(tmp_path / "fake.dng", np.zeros((20, 20, 3), np.float32), ColorInfo())
    assert not list(tmp_path.iterdir())


def test_export_does_not_overwrite_by_default(tmp_path):
    out = tmp_path / "result.jpg"
    out.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        export_image(out, np.zeros((20, 20, 3), np.float32), ColorInfo())
    assert out.read_bytes() == b"original"


def test_retouch_overlapping_dabs_and_persistent_redo(tmp_path):
    a = np.full((40, 60, 3), .125, np.float32)
    np.save(tmp_path / "result.npy", a)
    np.save(tmp_path / "original.npy", a)
    retouch = Retoucher(tmp_path)
    source = np.full_like(a, .8)
    retouch.dab(source, 20, 20, 10, .5, .5)
    retouch.dab(source, 24, 20, 10, .5, .5)
    retouch.end()
    edited = retouch.image.copy()
    assert edited[20, 24, 0] > .5
    retouch.undo()
    np.testing.assert_array_equal(retouch.image, a)
    reopened = Retoucher(tmp_path)
    reopened.redo()
    np.testing.assert_array_equal(reopened.image, edited)
    reopened.dab(reopened.original, 24, 20, 5, 1, 1)
    reopened.end()
    assert reopened.image[20, 24, 0] == a[20, 24, 0]


@pytest.mark.parametrize("method", ["A", "B", "C"])
def test_pipeline_and_project_round_trip(tmp_path, series, method):
    paths, _ = series
    files = []
    for i, p in enumerate(paths):
        png = tmp_path / f"source{i}.png"
        Image.fromarray(np.rint(np.load(p) * 255).astype(np.uint8)).save(png)
        files.append(str(png))
    result = run_stack(files, Settings(method=method, align=False), tmp_path / "cache")
    assert Path(result.image_path).exists()
    assert result.width == 256
    project = save_project(tmp_path / "saved", [{"path": f, "enabled": True} for f in files], [result.to_dict()])
    loaded = load_project(project)
    saved = np.load(Path(loaded["results"][0]["directory"]) / "result.npy")
    np.testing.assert_array_equal(saved, np.load(result.image_path))
    assert loaded["results"][0]["settings"]["method"] == method


def test_cancellation_cleans_incomplete_results(tmp_path, series):
    event = Event()
    event.set()
    with pytest.raises(Cancelled):
        run_stack(series[0], Settings(), tmp_path / "cache", cancel=event)
    assert not list((tmp_path / "cache" / "results").iterdir())


def test_mismatched_sizes_are_rejected(tmp_path):
    files = []
    for i in range(2):
        p = tmp_path / f"image{i}.png"
        Image.fromarray(np.full((32 + i, 32, 3), 100, np.uint8)).save(p)
        files.append(str(p))
    with pytest.raises(ValueError, match="Bildgröße"):
        run_stack(files, Settings(), tmp_path / "cache")


def test_16bit_tiff_input_preserves_precision(tmp_path):
    p = tmp_path / "source.tif"
    source = np.arange(32 * 32 * 3, dtype=np.uint16).reshape(32, 32, 3) * 20
    tifffile.imwrite(p, source, photometric="rgb")
    image, info = decode(p)
    assert not info.raw and image.dtype == np.float32
    assert len(np.unique(image)) > 256


def test_project_path_escape_rejected(tmp_path):
    import json
    (tmp_path / "project.json").write_text(json.dumps({"version": 1, "sources": [], "results": [{"directory": "../../escape"}]}))
    with pytest.raises(ValueError, match="Ergebnispfad"):
        load_project(tmp_path)


def test_low_disk_space_leaves_no_partial_result(tmp_path, monkeypatch):
    from collections import namedtuple
    import stckr.engine
    Disk = namedtuple('Disk', 'total used free')
    monkeypatch.setattr(stckr.engine.shutil, 'disk_usage', lambda path: Disk(100, 100, 0))
    files = []
    for i in range(2):
        p = tmp_path / f'source{i}.png'
        Image.fromarray(np.zeros((32,32,3),np.uint8)).save(p)
        files.append(str(p))
    with pytest.raises(ValueError, match='Platz'):
        run_stack(files, Settings(align=False), tmp_path/'cache')
    assert not list((tmp_path/'cache'/'results').iterdir())


def test_cancellation_during_fusion_cleans_job(tmp_path):
    files = []
    for i in range(3):
        p = tmp_path / f'source{i}.png'
        Image.fromarray(np.full((32,32,3),70+i,np.uint8)).save(p)
        files.append(str(p))
    cancel = Event()
    def progress(phase, value):
        if value > .65:
            cancel.set()
    with pytest.raises(Cancelled):
        run_stack(files, Settings(align=False), tmp_path/'cache', progress, cancel)
    assert not list((tmp_path/'cache'/'results').iterdir())
