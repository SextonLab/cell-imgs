"""Shared filesystem and image IO helpers.

Centralises three things that were previously copy-pasted (and subtly
different) in every command: creating output directories, globbing an input
directory for a channel, and building a stack without silently promoting the
data to float64.
"""

import os
from glob import glob

import click
import numpy as np
import tifffile as tif

TIF_EXTENSIONS = (".tif", ".tiff")

#: Every TIF this package writes is LZW compressed. It is lossless, readable
#: by CellProfiler 4 and ImageJ, and never larger than uncompressed. Label
#: masks shrink roughly 30x (8.0 MB -> 0.27 MB for a 1996x1996 uint16 mask);
#: raw microscope images shrink around 20%.
COMPRESSION = "lzw"


def ensure_dir(path):
    """Create ``path`` if needed, including parents.

    The old code used ``os.mkdir``, which fails on any nested output path and
    races when two commands start at once.
    """
    os.makedirs(path, exist_ok=True)
    return path


def find_images(directory, channel="*", bulk=False, extensions=TIF_EXTENSIONS):
    """Find images in ``directory``, optionally one level deeper (``bulk``).

    ``channel`` is a filename fragment such as ``C01`` or ``d0``; the default
    matches every channel.
    """
    # ClickException so the CLIs print a one-line error instead of a traceback.
    if not os.path.isdir(directory):
        raise click.ClickException(f"Image directory does not exist: {directory}")

    pattern_dir = os.path.join(directory, "*") if bulk else directory
    files = []
    for extension in extensions:
        files.extend(glob(os.path.join(pattern_dir, f"*{channel}{extension}")))
    return sorted(set(files))


def read_stack(files):
    """Read ``files`` into a 3D array, preserving the source dtype.

    ``stacker``, ``full_smash`` and ``merger`` all allocated with ``np.zeros``
    or ``np.ones``, which defaults to float64 — writing 8x the necessary bytes
    and discarding the uint16 dtype that CellProfiler expects.
    """
    if not files:
        raise ValueError("cannot build a stack from an empty file list")

    first = tif.imread(files[0])
    if first.ndim != 2:
        raise ValueError(
            f"{files[0]} has shape {first.shape}; expected a single 2D plane"
        )

    stack = np.empty((len(files),) + first.shape, dtype=first.dtype)
    stack[0] = first
    for index, path in enumerate(files[1:], start=1):
        plane = tif.imread(path)
        if plane.shape != first.shape:
            raise ValueError(
                f"{path} has shape {plane.shape} but the stack expects {first.shape}"
            )
        stack[index] = plane
    return stack


def write_image(path, data, photometric=None):
    """Write a TIF using the package-wide compression setting.

    Every output in this package goes through here or :func:`write_stack`, so
    the compression choice lives in exactly one place.
    """
    kwargs = {"compression": COMPRESSION}
    if photometric is not None:
        kwargs["photometric"] = photometric
    tif.imwrite(path, data, **kwargs)


def write_stack(path, stack):
    """Write a 3D stack as a plain grayscale volume.

    Without an explicit photometric hint, tifffile stores a 3-plane stack as
    an RGB image with separate components -- so a Z-stack that happens to have
    exactly three planes comes back as a colour image.
    """
    write_image(path, stack, photometric="minisblack")


def max_project(stack, axis=0):
    """Maximum intensity projection along ``axis``, keeping the input dtype."""
    return np.max(stack, axis=axis)


def count_labels(mask):
    """Number of distinct objects in a label mask.

    Counts unique non-zero labels. The old code called
    ``len(cellpose.utils.outlines_list(mask))``, which traces every boundary
    just to length-check the result -- orders of magnitude slower, and it
    drops objects whose outline cannot be traced.
    """
    return int(np.count_nonzero(np.unique(mask)))
