"""Merge three single-channel TIFs into one RGB TIF."""

import os

import click
import numpy as np
import tifffile as tif
from tqdm import tqdm

from .imgio import ensure_dir, find_images, write_image
from .logger import logger


def channel_key(path, channel):
    """The part of a filename shared by every channel of the same image."""
    stem = os.path.splitext(os.path.basename(path))[0]
    if stem.endswith(channel):
        stem = stem[: -len(channel)]
    return stem.rstrip("_-")


def group_by_key(indir, channels):
    """Map a shared filename key to one path per channel.

    The old version globbed each channel separately and zipped the three lists
    by index. glob order is arbitrary, so red, green and blue could come from
    three different images without any error being raised.
    """
    groups = {}
    for position, channel in enumerate(channels):
        for path in find_images(indir, channel=channel):
            groups.setdefault(channel_key(path, channel), [None, None, None])[position] = path
    return groups


@click.command()
@click.argument("indir")
@click.argument("outdir")
@click.argument("red")
@click.argument("grn")
@click.argument("blu")
@click.option("--replace", "-r", is_flag=True, default=False, help="Overwrite existing merged images")
def merge_channel(indir, outdir, red, grn, blu, replace):
    """Merge single-channel TIFs in INDIR into RGB TIFs in OUTDIR.

    RED, GRN and BLU are channel identifiers such as C01, C02, C03.
    """
    if not os.path.isdir(indir):
        raise click.ClickException(f"Input directory does not exist: {indir}")

    # Create the output directory before logging into it.
    ensure_dir(outdir)
    logger(
        outdir,
        {"indir": indir, "outdir": outdir, "red": red, "green": grn,
         "blue": blu, "replace": replace},
        command="cmerge",
    )

    groups = group_by_key(indir, (red, grn, blu))
    complete = {key: paths for key, paths in groups.items() if all(paths)}
    incomplete = len(groups) - len(complete)
    if incomplete:
        print(f"Warning: skipping {incomplete} image(s) missing one or more channels.")
    if not complete:
        raise click.ClickException(
            f"No images in {indir} had all three of {red}, {grn}, {blu}"
        )

    merged = 0
    for key, paths in tqdm(sorted(complete.items()), desc="Merging"):
        target = os.path.join(outdir, f"{key}.tif")
        # The old condition was 'not exists and not replace', so passing
        # --replace wrote nothing at all.
        if os.path.exists(target) and not replace:
            continue

        planes = [tif.imread(path) for path in paths]
        shapes = {plane.shape for plane in planes}
        if len(shapes) != 1:
            print(f"Warning: {key} has mismatched channel shapes {shapes}; skipping.")
            continue

        # Interleaved RGB in the source dtype, so viewers and CellProfiler read
        # it as a colour image rather than a float64 3-plane stack.
        rgb = np.stack(planes, axis=-1).astype(planes[0].dtype)
        write_image(target, rgb, photometric="rgb")
        merged += 1

    print(f"Merged {merged} image(s) into {outdir}")
