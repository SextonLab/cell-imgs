"""Maximum intensity projections of existing 3D TIF stacks."""

import os

import click
import tifffile as tif
from tqdm import tqdm

from .imgio import ensure_dir, find_images, write_image
from .imgio import max_project as project
from .logger import logger


def z_axis(shape, axis=None):
    """Pick the Z axis of a 3D stack.

    The old heuristic took the smallest of the three dimensions, which is
    wrong whenever a stack is deeper than the image is wide, and ties were
    resolved arbitrarily. Prefer an explicit ``axis``; otherwise assume the
    conventional ``(z, y, x)`` ordering that every stacking tool in this
    package writes.
    """
    if axis is not None:
        if not 0 <= axis < len(shape):
            raise click.BadParameter(
                f"axis {axis} is out of range for shape {shape}", param_hint="--axis"
            )
        return axis
    return 0


@click.command()
@click.argument("indir")
@click.argument("outdir")
@click.option("--channel", "-c", default="*", help="Filename fragment selecting a channel")
@click.option("--axis", "-a", default=None, type=int, help="Axis to project along; default 0 (z, y, x)")
@click.option("--replace", "-r", is_flag=True, default=False, help="Overwrite existing projections")
def max_project(indir, outdir, channel, axis, replace):
    """Write a max projection of every stack in INDIR to OUTDIR."""
    files = find_images(indir, channel=channel)
    if not files:
        raise click.ClickException(f"No stacks matching channel '{channel}' in {indir}")

    ensure_dir(outdir)
    logger(
        outdir,
        {"indir": indir, "outdir": outdir, "channel": channel,
         "axis": axis, "files": len(files)},
        command="max-proj",
    )

    projected, skipped = 0, []
    for path in tqdm(files, desc="Projecting"):
        target = os.path.join(outdir, os.path.basename(path))
        if os.path.exists(target) and not replace:
            continue

        img = tif.imread(path)
        # A 2D image in the input used to abort the whole run via assert.
        if img.ndim != 3:
            skipped.append((path, img.shape))
            continue

        write_image(target, project(img, axis=z_axis(img.shape, axis)))
        projected += 1

    print(f"Projected {projected} stack(s) into {outdir}")
    if skipped:
        print(f"Skipped {len(skipped)} file(s) that were not 3D:")
        for path, shape in skipped[:5]:
            print(f"  {os.path.basename(path)} has shape {shape}")
