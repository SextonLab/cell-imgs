import struct
import zlib

import numpy as np
import pytest

from cellimgs import c01


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16])
def test_roundtrip(tmp_path, dtype, rng):
    original = rng.integers(0, np.iinfo(dtype).max, size=(24, 32)).astype(dtype)
    path = tmp_path / "img.C01"
    path.write_bytes(c01.encode(original))

    decoded = c01.read(path)
    assert decoded.dtype == dtype
    assert decoded.shape == (24, 32)
    np.testing.assert_array_equal(decoded, original)


def test_header_fields(tmp_path):
    img = np.zeros((10, 40), dtype=np.uint16)
    data = zlib.decompress(c01.encode(img)[4:])
    header = c01.read_header(data)
    assert header == {
        "width": 40,
        "height": 10,
        "planes": 1,
        "bits": 16,
        "bottom_up": False,
    }


def test_bottom_up_rows_are_flipped(tmp_path):
    """A negative biHeight means the DIB is stored bottom-up."""
    img = np.arange(6 * 4, dtype=np.uint16).reshape(6, 4)
    payload = bytearray(52)
    struct.pack_into("<i", payload, 0, 40)
    struct.pack_into("<iihhiiiiii", payload, 4, 4, -6, 1, 16, 0, img.nbytes, 0, 0, 0, 0)
    path = tmp_path / "flip.C01"
    path.write_bytes(b"\x00" * 4 + zlib.compress(bytes(payload) + img.tobytes()))

    np.testing.assert_array_equal(c01.read(path), img[::-1])


def test_uncompressed_dib_is_accepted(tmp_path):
    img = np.full((8, 8), 7, dtype=np.uint8)
    payload = bytearray(52)
    struct.pack_into("<i", payload, 0, 40)
    struct.pack_into("<iihhiiiiii", payload, 4, 8, 8, 1, 8, 0, img.nbytes, 0, 0, 0, 0)
    path = tmp_path / "raw.C01"
    path.write_bytes(bytes(payload) + img.tobytes())

    np.testing.assert_array_equal(c01.read(path), img)


def test_truncated_pixel_data_raises(tmp_path):
    img = np.zeros((16, 16), dtype=np.uint16)
    encoded = c01.encode(img)
    truncated = zlib.decompress(encoded[4:])[: 52 + 100]
    path = tmp_path / "short.C01"
    path.write_bytes(b"\x00" * 4 + zlib.compress(truncated))

    with pytest.raises(c01.C01Error, match="only 100 remain"):
        c01.read(path)


def test_bad_bit_depth_raises(tmp_path):
    payload = bytearray(52)
    struct.pack_into("<i", payload, 0, 40)
    struct.pack_into("<iihhiiiiii", payload, 4, 8, 8, 1, 24, 0, 0, 0, 0, 0, 0)
    path = tmp_path / "rgb.C01"
    path.write_bytes(b"\x00" * 4 + zlib.compress(bytes(payload) + b"\x00" * 192))

    with pytest.raises(c01.C01Error, match="unsupported bit depth 24"):
        c01.read(path)


def test_garbage_is_rejected(tmp_path):
    path = tmp_path / "junk.C01"
    path.write_bytes(b"not an image")
    with pytest.raises(c01.C01Error):
        c01.read(path)
