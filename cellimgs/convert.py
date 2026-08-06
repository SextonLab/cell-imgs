"""Convert vendor image files to TIF.

Previously this started a JVM via ``python-javabridge`` and read through
``python-bioformats``. Both are gone: ``.C01`` is decoded by :mod:`cellimgs.c01`
in pure Python, and any other format is delegated to ``bioio`` if it is
installed.
"""

import os
from glob import glob

import click
import tifffile as tif
from tqdm import tqdm

from . import c01
from .imgio import ensure_dir, write_image
from .logger import logger


def read_any(path):
    """Read ``path`` into a numpy array, choosing a decoder by extension."""
    extension = os.path.splitext(path)[1].lower()

    if extension == ".c01":
        return c01.read(path)
    if extension in (".tif", ".tiff"):
        return tif.imread(path)

    try:
        from bioio import BioImage
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise click.ClickException(
            f"Cannot read {extension} files. Install the bioio reader for this "
            f"format, e.g. 'pip install cellimgs[formats]'."
        ) from exc
    return BioImage(path).get_image_data("YX")


@click.command()
@click.argument("indir")
@click.argument("outdir")
@click.option("--channel", "-c", default="*", help="Filename fragment selecting a channel")
@click.option("--pattern", "-p", default="*.C01", help="Glob for input files, e.g. '*.C01'")
@click.option("--replace", "-r", is_flag=True, default=False, help="Overwrite existing TIFs")
def convert(indir, outdir, channel, pattern, replace):
    """Convert every matching image in INDIR to a TIF in OUTDIR."""
    if os.name == "nt":
        os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    if not os.path.isdir(indir):
        raise click.ClickException(f"Input directory does not exist: {indir}")

    ensure_dir(outdir)

    stem, extension = os.path.splitext(pattern)
    files = sorted(glob(os.path.join(indir, f"{stem}{channel}{extension}")))
    if not files:
        raise click.ClickException(
            f"No files matching '{stem}{channel}{extension}' found in {indir}"
        )

    logger(
        outdir,
        {"indir": indir, "outdir": outdir, "channel": channel,
         "pattern": pattern, "files": len(files), "replace": replace},
        command="convert-c01",
    )

    converted = 0
    for path in tqdm(files, desc="Converting"):
        target = os.path.join(
            outdir, os.path.splitext(os.path.basename(path))[0] + ".tif"
        )
        if os.path.exists(target) and not replace:
            continue
        write_image(target, read_any(path))
        converted += 1

    print(f"Converted {converted} of {len(files)} file(s) into {outdir}")
