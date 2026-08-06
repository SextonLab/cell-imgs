"""Group single-plane TIFs into stacks and collapse them to max projections.

This is ``stack-imgs`` followed by ``max-proj`` without writing the
intermediate stack to disk.
"""

import os

import click
from tqdm import tqdm

from .imgio import ensure_dir, find_images, max_project, read_stack, write_image
from .logger import logger
from .metadata import SCOPES, build_table, iter_groups, normalize_scope, stack_files, stack_name


def stack_n_smash(indir, outdir, scope="CV8000", channel="*", on_loc=False,
                  bulk=False, replace=False):
    """Write one max projection per (well, field, channel) group in ``indir``."""
    if os.name == "nt":
        os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    scope = normalize_scope(scope)
    # CQ1 filenames carry no location field.
    if scope == "CQ1":
        on_loc = False

    files = find_images(indir, channel=channel, bulk=bulk)
    if not files:
        raise click.ClickException(f"No .tif/.tiff images found in {indir}")

    ensure_dir(outdir)
    df = build_table(files, scope)
    if df.empty:
        raise click.ClickException(
            f"None of the {len(files)} file(s) in {indir} matched the {scope} naming pattern"
        )

    logger(
        outdir,
        {"indir": indir, "outdir": outdir, "scope": scope, "channel": channel,
         "on_loc": on_loc, "bulk": bulk, "files": len(files), "parsed": len(df)},
        command="smashtif",
    )

    field_column = "location" if on_loc else "field_id"
    groups = list(iter_groups(df, field_column=field_column))
    written = 0
    for well, field, chan in tqdm(groups, desc="Arranging Z-stacks"):
        target = os.path.join(outdir, stack_name(well, field, chan))
        if os.path.exists(target) and not replace:
            continue

        paths = stack_files(df, well, field, chan, field_column=field_column)
        if not paths:
            continue
        write_image(target, max_project(read_stack(paths)))
        written += 1

    print(f"Wrote {written} projection(s) from {len(groups)} group(s) into {outdir}")
    return written


@click.command()
@click.argument("indir")
@click.argument("outdir")
@click.option("--scope", "-s", default="CV8000", help=f"Microscope naming convention {list(SCOPES)}")
@click.option("--channel", "-c", default="*", help="Filename fragment selecting a channel")
@click.option("--on_loc", "-l", is_flag=True, default=False, help="Group by stage location instead of field")
@click.option("--bulk", "-b", is_flag=True, default=False, help="Look one directory deeper for images")
@click.option("--replace", "-r", is_flag=True, default=False, help="Overwrite existing projections")
def s_n_s(indir, outdir, scope, channel, on_loc, bulk, replace):
    """Stack the TIFs in INDIR by Z and write max projections to OUTDIR."""
    stack_n_smash(indir, outdir, scope=scope, channel=channel,
                  on_loc=on_loc, bulk=bulk, replace=replace)
