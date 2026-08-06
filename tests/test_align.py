import numpy as np
import pytest
import tifffile as tif

from cellimgs import align_all


def make_mask(shape=(96, 120), shift=(0, 0)):
    mask = np.zeros(shape, dtype=np.uint16)
    for index, (cy, cx) in enumerate([(25, 30), (60, 80), (40, 55)], start=1):
        mask[cy - 8:cy + 8, cx - 8:cx + 8] = index
    return np.roll(np.roll(mask, shift[0], axis=0), shift[1], axis=1)


@pytest.mark.parametrize("dy,dx", [(0, 6), (4, 0), (4, 6), (-3, -7)])
def test_align_pair_recovers_a_known_shift(tmp_path, dy, dx):
    """The old step schedule stalled on offsets it overshot: a 6 pixel shift
    was attacked with 10 pixel steps that could never be refined."""
    first = tmp_path / "first.tif"
    second = tmp_path / "second.tif"
    tif.imwrite(first, make_mask())
    tif.imwrite(second, make_mask(shift=(dy, dx)))

    result = align_all.align_pair(str(first), str(second))
    record = result["record"]

    net_x = record["right_correction"] - record["left_correction"]
    net_y = record["bottom_correction"] - record["top_correction"]
    assert (net_y, net_x) == (dy, dx)
    assert record["ending_alignment"] >= align_all.TARGET_OVERLAP


def test_align_pair_reports_mismatched_shapes(tmp_path):
    first, second = tmp_path / "a.tif", tmp_path / "b.tif"
    tif.imwrite(first, make_mask((32, 32)))
    tif.imwrite(second, make_mask((48, 48)))
    assert align_all.align_pair(str(first), str(second)) is None


def test_align_pair_on_already_aligned_images(tmp_path):
    """This case used to raise NameError: the loop never ran, so the variable
    the result was written from was never bound."""
    first, second = tmp_path / "a.tif", tmp_path / "b.tif"
    tif.imwrite(first, make_mask())
    tif.imwrite(second, make_mask())

    result = align_all.align_pair(str(first), str(second))
    assert result["record"]["iterations"] == 0
    assert result["record"]["ending_alignment"] == 1.0
    np.testing.assert_array_equal(result["second"], (make_mask() > 0).astype(np.uint8))


def test_align_pair_on_empty_mask_is_skipped(tmp_path):
    first, second = tmp_path / "a.tif", tmp_path / "b.tif"
    tif.imwrite(first, np.zeros((32, 32), dtype=np.uint16))
    tif.imwrite(second, make_mask((32, 32)))
    assert align_all.align_pair(str(first), str(second)) is None


def test_apply_pad_handles_non_square_images(tmp_path):
    """Height and width were both taken from shape[0]."""
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    img = np.arange(20 * 50, dtype=np.uint16).reshape(20, 50)
    tif.imwrite(src / "img.tif", img)

    align_all.apply_pad([str(src / "img.tif")], str(out), right=0, left=3, top=2, bot=0)
    shifted = tif.imread(out / "img.tif")

    assert shifted.shape == img.shape
    np.testing.assert_array_equal(shifted[2:, 3:], img[:-2, :-3])


@pytest.mark.parametrize(
    "how,axis,sign", [("left", 1, 1), ("right", 1, -1), ("up", 0, 1), ("down", 0, -1)]
)
def test_pad_image_shifts_in_the_named_direction(how, axis, sign):
    img = np.zeros((20, 20), dtype=np.uint8)
    img[10, 10] = 1
    shifted = align_all.pad_image(img, how, 3)

    assert shifted.shape == img.shape
    position = np.argwhere(shifted == 1)[0]
    assert position[axis] == 10 + sign * 3
