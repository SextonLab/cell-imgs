"""Group single-plane TIFs into 3D stacks for volumetric analysis."""

import os

import click
from tqdm import tqdm

from .imgio import ensure_dir, find_images, read_stack, write_stack
from .logger import logger
from .metadata import SCOPES, build_table, iter_groups, normalize_scope, stack_files, stack_name

ON_CHOICES = {"z": "zstack", "t": "timepoint", "l": "location"}


def stack_directory(src, dest, scope="CV8000", on="z", channel="*", bulk=False, replace=False):
    """Build one 3D TIF per (well, field, channel) group found in ``src``."""
    if os.name == "nt":
        os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    scope = normalize_scope(scope)
    if on not in ON_CHOICES:
        raise click.BadParameter(
            f"--on must be one of {list(ON_CHOICES)}", param_hint="--on"
        )

    # The non-bulk glob used to be hardcoded to 'PECCU*.tif', a plate prefix
    # from one experiment, so every other plate silently matched nothing.
    files = find_images(src, channel=channel, bulk=bulk)
    if not files:
        raise click.ClickException(f"No .tif/.tiff images found in {src}")

    ensure_dir(dest)
    df = build_table(files, scope)
    if df.empty:
        raise click.ClickException(
            f"None of the {len(files)} file(s) in {src} matched the {scope} naming pattern"
        )

    logger(
        dest,
        {"src": src, "dest": dest, "scope": scope, "on": on, "channel": channel,
         "bulk": bulk, "files": len(files), "parsed": len(df)},
        command="stack-imgs",
    )

    groups = list(iter_groups(df))
    written = 0
    for well, field, chan in tqdm(groups, desc="Stacking"):
        target = os.path.join(dest, stack_name(well, field, chan))
        if os.path.exists(target) and not replace:
            continue

        paths = stack_files(df, well, field, chan, on=on)
        if not paths:
            continue
        write_stack(target, read_stack(paths))
        written += 1

    print(f"Wrote {written} stack(s) from {len(groups)} group(s) into {dest}")
    return written


@click.command()
@click.argument("src")
@click.argument("dest")
@click.option("--scope", "-s", default="CV8000", help=f"Microscope naming convention {list(SCOPES)}")
@click.option("--on", "-o", default="z", help=f"Axis to stack along {list(ON_CHOICES)}")
@click.option("--channel", "-c", default="*", help="Filename fragment selecting a channel")
@click.option("--bulk", "-b", is_flag=True, default=False, help="Look one directory deeper for images")
@click.option("--replace", "-r", is_flag=True, default=False, help="Overwrite existing stacks")
def stack_tif(src, dest, scope, on, channel, bulk, replace):
    """Group the single-plane TIFs in SRC into 3D stacks in DEST."""
    stack_directory(src, dest, scope=scope, on=on, channel=channel, bulk=bulk, replace=replace)
