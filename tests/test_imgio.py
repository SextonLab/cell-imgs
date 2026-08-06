import numpy as np
import pytest

from cellimgs import imgio


def test_read_stack_preserves_dtype(tmp_path, plane_writer):
    files = [str(plane_writer(tmp_path / f"z{i}.tif", value=i)) for i in range(4)]
    stack = imgio.read_stack(files)

    # The old implementation allocated with np.zeros/np.ones, silently
    # promoting uint16 plate data to float64 and quadrupling file sizes.
    assert stack.dtype == np.uint16
    assert stack.shape == (4, 16, 20)
    assert [int(plane[0, 0]) for plane in stack] == [0, 1, 2, 3]


def test_read_stack_rejects_mismatched_shapes(tmp_path, plane_writer):
    a = plane_writer(tmp_path / "a.tif", value=1)
    b = plane_writer(tmp_path / "b.tif", value=2, shape=(8, 8))
    with pytest.raises(ValueError, match="expects"):
        imgio.read_stack([str(a), str(b)])


def test_read_stack_rejects_empty():
    with pytest.raises(ValueError, match="empty file list"):
        imgio.read_stack([])


def test_max_project_keeps_dtype():
    stack = np.arange(3 * 4 * 5, dtype=np.uint16).reshape(3, 4, 5)
    projected = imgio.max_project(stack)
    assert projected.dtype == np.uint16
    np.testing.assert_array_equal(projected, stack[2])


def test_ensure_dir_creates_nested_paths(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    imgio.ensure_dir(str(target))
    imgio.ensure_dir(str(target))  # idempotent, unlike the old os.mkdir
    assert target.is_dir()


def test_find_images_filters_by_channel(tmp_path, plane_writer):
    plane_writer(tmp_path / "img_C01.tif")
    plane_writer(tmp_path / "img_C02.tif")
    assert len(imgio.find_images(str(tmp_path))) == 2
    assert len(imgio.find_images(str(tmp_path), channel="C01")) == 1


def test_find_images_bulk_looks_one_level_deeper(tmp_path, plane_writer):
    plane_writer(tmp_path / "wellA" / "img_C01.tif")
    plane_writer(tmp_path / "wellB" / "img_C01.tif")
    assert imgio.find_images(str(tmp_path)) == []
    assert len(imgio.find_images(str(tmp_path), bulk=True)) == 2


def test_write_image_uses_lzw(tmp_path):
    import tifffile as tif

    path = tmp_path / "mask.tif"
    imgio.write_image(str(path), np.zeros((32, 32), dtype=np.uint16))
    with tif.TiffFile(path) as handle:
        assert handle.pages[0].compression == tif.COMPRESSION.LZW


def test_write_stack_uses_lzw_and_stays_grayscale(tmp_path):
    import tifffile as tif

    path = tmp_path / "stack.tif"
    stack = np.arange(3 * 8 * 8, dtype=np.uint16).reshape(3, 8, 8)
    imgio.write_stack(str(path), stack)

    with tif.TiffFile(path) as handle:
        page = handle.pages[0]
        assert page.compression == tif.COMPRESSION.LZW
        assert page.photometric == tif.PHOTOMETRIC.MINISBLACK
    np.testing.assert_array_equal(tif.imread(path), stack)


def test_lzw_masks_round_trip_losslessly(tmp_path, rng):
    """CellProfiler reads the label values, so compression must be exact."""
    import tifffile as tif

    mask = rng.integers(0, 3000, size=(256, 256)).astype(np.uint16)
    path = tmp_path / "labels.tif"
    imgio.write_image(str(path), mask)

    reloaded = tif.imread(path)
    assert reloaded.dtype == np.uint16
    np.testing.assert_array_equal(reloaded, mask)


def test_lzw_actually_shrinks_label_masks(tmp_path):
    import tifffile as tif

    mask = np.zeros((512, 512), dtype=np.uint16)
    for label in range(1, 200):
        y, x = divmod(label, 20)
        mask[y * 25:y * 25 + 20, x * 25:x * 25 + 20] = label

    compressed, plain = tmp_path / "c.tif", tmp_path / "p.tif"
    imgio.write_image(str(compressed), mask)
    tif.imwrite(plain, mask)
    assert compressed.stat().st_size < plain.stat().st_size / 5


def test_count_labels_ignores_background():
    mask = np.array([[0, 1, 1], [0, 2, 5]], dtype=np.uint16)
    assert imgio.count_labels(mask) == 3
    assert imgio.count_labels(np.zeros((4, 4), dtype=np.uint16)) == 0
