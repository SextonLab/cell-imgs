"""Pure-Python reader for Cellomics ``.C01`` images.

This replaces the ``python-javabridge`` + ``python-bioformats`` dependency,
which required a JDK, has no wheels for Python 3.12, and pulled a whole JVM
into the process just to read a zlib-compressed bitmap.

Format, as implemented by Bio-Formats' ``CellomicsReader``:

* The first 4 bytes of the file are a header, and the remainder is a zlib
  (deflate) stream.
* The decompressed buffer opens with a Windows ``BITMAPINFOHEADER`` (40 bytes)
  followed by 12 bytes of Cellomics-specific padding.
* Pixel data starts at offset 52 and is stored top-down, 8 or 16 bits per
  pixel, with no row padding.
"""

import struct
import zlib

import numpy as np

#: Offset of the pixel data within the decompressed buffer.
_PIXEL_OFFSET = 52

#: ``BITMAPINFOHEADER`` minus the leading ``biSize`` field, little endian.
_HEADER = struct.Struct("<iihhiiiiii")


class C01Error(ValueError):
    """Raised when a file cannot be decoded as a Cellomics C01 image."""


def _decompress(raw, path):
    """Inflate the C01 payload, tolerating the few layout variants in the wild."""
    attempts = (
        ("payload after 4-byte header", raw[4:]),
        ("payload at offset 0", raw),
    )
    for _, payload in attempts:
        try:
            return zlib.decompress(payload)
        except zlib.error:
            continue
    # Some exports are stored as a plain uncompressed DIB.
    if len(raw) > _PIXEL_OFFSET:
        return raw
    raise C01Error(f"{path}: not a zlib stream and too small to be a raw DIB")


def read_header(data, path="<buffer>"):
    """Parse the DIB header out of a decompressed C01 buffer."""
    if len(data) < _PIXEL_OFFSET:
        raise C01Error(f"{path}: truncated header ({len(data)} bytes)")

    (
        width,
        height,
        planes,
        bits,
        _compression,
        _size_image,
        _x_ppm,
        _y_ppm,
        _clr_used,
        _clr_important,
    ) = _HEADER.unpack_from(data, 4)

    if bits not in (8, 16):
        raise C01Error(f"{path}: unsupported bit depth {bits} (expected 8 or 16)")
    # biHeight is signed: negative means the rows are stored bottom-up.
    if width <= 0 or height == 0:
        raise C01Error(f"{path}: implausible dimensions {width}x{height}")

    return {
        "width": width,
        "height": abs(height),
        "planes": max(planes, 1),
        "bits": bits,
        "bottom_up": height < 0,
    }


def read(path, plane=0):
    """Read a ``.C01`` file and return it as a 2D numpy array.

    Args:
        path: path to the ``.C01`` file.
        plane: index of the plane to read, for the rare multi-plane file.

    Returns:
        ``numpy.ndarray`` of dtype ``uint8`` or ``uint16``.
    """
    with open(path, "rb") as handle:
        raw = handle.read()

    data = _decompress(raw, path)
    header = read_header(data, path)

    dtype = np.uint8 if header["bits"] == 8 else np.uint16
    count = header["width"] * header["height"]
    itemsize = np.dtype(dtype).itemsize
    plane_bytes = count * itemsize

    if plane >= header["planes"]:
        raise C01Error(
            f"{path}: requested plane {plane} but the file holds {header['planes']}"
        )

    start = _PIXEL_OFFSET + plane * plane_bytes
    available = len(data) - start
    if available < plane_bytes:
        raise C01Error(
            f"{path}: expected {plane_bytes} bytes of pixel data for a "
            f"{header['width']}x{header['height']} {header['bits']}-bit image "
            f"but only {max(available, 0)} remain"
        )

    img = np.frombuffer(data, dtype=dtype, count=count, offset=start)
    img = img.reshape(header["height"], header["width"])

    # A negative biHeight means the rows are stored bottom-up.
    if header["bottom_up"]:
        img = img[::-1]

    return np.ascontiguousarray(img)


def encode(img):
    """Encode a 2D array as C01 bytes. Used by the test suite."""
    img = np.asarray(img)
    if img.ndim != 2:
        raise C01Error("only 2D images can be encoded")
    if img.dtype == np.uint8:
        bits = 8
    elif img.dtype == np.uint16:
        bits = 16
    else:
        raise C01Error(f"unsupported dtype {img.dtype}; use uint8 or uint16")

    height, width = img.shape
    header = bytearray(_PIXEL_OFFSET)
    struct.pack_into("<i", header, 0, 40)
    _HEADER.pack_into(
        header, 4, width, height, 1, bits, 0, img.nbytes, 0, 0, 0, 0
    )
    payload = bytes(header) + img.tobytes()
    return b"\x00\x00\x00\x00" + zlib.compress(payload)
