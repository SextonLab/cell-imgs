"""Object counts from label masks, per image and aggregated per well."""

import os

import click
import pandas as pd
import tifffile as tif
from tqdm import tqdm

from .imgio import count_labels, find_images
from .metadata import SCOPES, normalize_scope, parse_filename


@click.command()
@click.argument("path")
@click.option("--channel", "-c", default="*", help="Filename fragment selecting the mask channel")
@click.option("--output", "-o", default=None, help="CSV to write; defaults to PATH/counts.csv")
def get_image_counts(path, channel, output):
    """Count objects in every mask under PATH."""
    # The option used to be spelled --chanel while the parameter was channel,
    # so this command raised TypeError on every invocation.
    files = find_images(path, channel=channel)
    if not files:
        raise click.ClickException(f"No masks matching channel '{channel}' in {path}")

    data = {"image": [], "count": []}
    for mask_path in tqdm(files, desc="Counting"):
        data["image"].append(mask_path)
        data["count"].append(count_labels(tif.imread(mask_path)))

    target = output or os.path.join(path, "counts.csv")
    pd.DataFrame(data=data).to_csv(target, index=False)
    print(f"Wrote {target}")


@click.command()
@click.argument("path")
@click.option("--scope", "-s", default="CQ1", help=f"Microscope naming convention {list(SCOPES)}")
@click.option("--output", "-o", default=None, help="CSV to write; defaults to well_count.csv beside PATH")
def get_well_counts(path, scope, output):
    """Aggregate an image-level counts CSV to per-well totals."""
    scope = normalize_scope(scope)
    df = pd.read_csv(path)
    if "image" not in df.columns or "count" not in df.columns:
        raise click.ClickException(
            f"{path} must have 'image' and 'count' columns; found {list(df.columns)}"
        )

    # Parse the well out of the filename with the shared metadata patterns
    # rather than splitting on '/' and '_', which broke on Windows-produced
    # CSVs and on any plate name containing the delimiter.
    wells = []
    for image in df["image"]:
        meta = parse_filename(image, scope)
        wells.append(meta["well_id"] if meta else None)
    df["well_id"] = wells

    unmatched = int(df["well_id"].isna().sum())
    if unmatched:
        print(f"Warning: {unmatched} row(s) did not match the {scope} pattern and were dropped.")
    df = df.dropna(subset=["well_id"])
    if df.empty:
        raise click.ClickException(f"No rows in {path} matched the {scope} naming pattern")

    totals = (
        df.groupby("well_id", as_index=False)["count"]
        .sum()
        .sort_values("well_id")
    )
    target = output or os.path.join(os.path.dirname(os.path.abspath(path)), "well_count.csv")
    totals.to_csv(target, index=False)
    print(f"Wrote {target}")
