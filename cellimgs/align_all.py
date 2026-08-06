"""Align a second imaging pass to a first pass using their Cellpose masks.

Both passes are segmented, the masks are binarised, and the second pass is
translated a few pixels at a time until its overlap with the first pass stops
improving. The resulting per-image offsets are then applied to the raw
second-pass images.
"""

import os

import click
import numpy as np
import pandas as pd
import tifffile as tif
from tqdm import tqdm

from .gen_masks import get_masks
from .imgio import ensure_dir, find_images, write_image
from .logger import logger

ROUTE = ("left", "up", "right", "down")
BINARY_MASK_FIRST = "first_pass_binary"
BINARY_MASK_SECOND = "second_pass_binary"

#: Overlap fraction at which an image is considered aligned.
TARGET_OVERLAP = 0.988

#: Hard cap on hill-climbing rounds per image.
MAX_ITERATIONS = 200


def get_pad_val(current):
    """Step size in pixels; coarse when far from aligned, fine when close."""
    if 0.0 < current <= 0.15:
        return 20
    if 0.15 < current <= 0.50:
        return 10
    if 0.50 < current <= 0.70:
        return 4
    return 2


def pad_image(img, how, pad_value):
    """Translate ``img`` by ``pad_value`` pixels, keeping the original shape."""
    height, width = img.shape
    if how == "left":
        return np.pad(img, [(0, 0), (pad_value, 0)])[:, :width]
    if how == "right":
        return np.pad(img, [(0, 0), (0, pad_value)])[:, pad_value:]
    if how == "up":
        return np.pad(img, [(pad_value, 0), (0, 0)])[:height, :]
    if how == "down":
        return np.pad(img, [(0, pad_value), (0, 0)])[pad_value:, :]
    raise ValueError(f"unknown direction {how!r}")


def apply_pad(images, outdir, right, left, top, bot):
    """Apply a net (left-right, top-bottom) translation to each image."""
    for path in images:
        img = tif.imread(path)
        height, width = img.shape[:2]
        padded = np.pad(img, [(top, bot), (left, right)])
        # Height and width were previously both taken from shape[0], which
        # corrupted every non-square image.
        write_image(
            os.path.join(outdir, os.path.basename(path)),
            padded[bot:height + bot, right:width + right],
        )


def align_pair(first_path, second_path):
    """Align one mask pair. Returns a record dict, or None if shapes differ."""
    first = tif.imread(first_path)
    second = tif.imread(second_path)
    if first.shape != second.shape:
        return None

    first = (first > 0).astype(np.uint8)
    second = (second > 0).astype(np.uint8)

    ideal = int(first.sum())
    if ideal == 0:
        return None

    current = int((first * second).sum())
    overlap = current / ideal
    start_overlap = overlap

    offsets = {"left": 0, "right": 0, "up": 0, "down": 0}
    iterations = 0
    step = get_pad_val(overlap)

    # Coarse-to-fine hill climb. The old loop recomputed the step purely from
    # the current overlap and gave up after five rounds without improvement,
    # so a coarse step that overshot the true offset could never be refined --
    # a 6 pixel shift would stall at 10 pixel steps and never converge.
    while overlap < TARGET_OVERLAP and step >= 1 and iterations < MAX_ITERATIONS:
        improved = False
        for how in ROUTE:
            candidate = pad_image(second, how, step)
            score = int((first * candidate).sum())
            if score > current:
                second = candidate
                current = score
                overlap = score / ideal
                offsets[how] += step
                improved = True
        iterations += 1

        if improved:
            # Never coarsen again, only refine.
            step = min(step, get_pad_val(overlap))
        else:
            step //= 2

    return {
        "first": first,
        # The old code wrote `temp`, the last direction tried rather than the
        # accepted result -- and it was unbound entirely when an image was
        # already aligned and the loop never ran.
        "second": second,
        "record": {
            "right_correction": offsets["right"],
            "left_correction": offsets["left"],
            "top_correction": offsets["up"],
            "bottom_correction": offsets["down"],
            "starting_alignment": start_overlap,
            "ending_alignment": overlap,
            "iterations": iterations,
        },
    }


def align_images(first_pass_images, second_pass_images, output_1, output_2, channel):
    """Align matched mask pairs and return a DataFrame of corrections."""
    first_binary = ensure_dir(os.path.join(output_1, BINARY_MASK_FIRST))
    second_binary = ensure_dir(os.path.join(output_2, BINARY_MASK_SECOND))

    if len(first_pass_images) != len(second_pass_images):
        raise ValueError(
            f"pass image lists differ in length: {len(first_pass_images)} vs "
            f"{len(second_pass_images)}"
        )

    corrections = []
    failures = []
    pairs = list(zip(first_pass_images, second_pass_images, strict=True))
    for first_path, second_path in tqdm(pairs, desc="Aligning"):
        name = os.path.basename(first_path)
        result = align_pair(first_path, second_path)
        if result is None:
            failures.append({
                "fname": name,
                "first_shape": str(tif.imread(first_path).shape),
                "second_shape": str(tif.imread(second_path).shape),
            })
            continue

        write_image(os.path.join(first_binary, name), result["first"])
        write_image(os.path.join(second_binary, name), result["second"])

        record = {"fname": name, "image_set": name.split(channel)[0]}
        record.update(result["record"])
        corrections.append(record)

    pd.DataFrame(failures).to_csv(
        os.path.join(output_2, "failed_images.csv"), index=False
    )
    if failures:
        print(f"{len(failures)} image pair(s) could not be aligned; see failed_images.csv")

    return pd.DataFrame(corrections)


@click.command()
@click.argument("first_pass")
@click.argument("second_pass")
@click.option("--diam", "-d", default=0.0, help="Cell diameter in pixels; 0 disables rescaling")
@click.option("--channel", "-c", default="*", help="Filename fragment selecting a channel")
@click.option("--model", "-m", default=None, help="Path or name of a custom model; omit for Cellpose-SAM")
@click.option("--no_edge", "-n", is_flag=True, default=False, help="Remove objects touching the image edge")
@click.option("--flow", "-f", default=0.4, help="Flow threshold")
@click.option("--prob", "-p", default=0.0, help="Cell probability threshold")
@click.option("--normalize", default=None, help="Path to a normalize parameter JSON")
@click.option("--batch", "-b", default=8, help="Cellpose batch size")
@click.option("--gpu/--no-gpu", default=True, help="Use CUDA if available")
def run(first_pass, second_pass, diam, channel, model, no_edge, flow, prob,
        normalize, batch, gpu):
    """Segment FIRST_PASS and SECOND_PASS, then align the second to the first."""
    if os.name == "nt":
        os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    for path in (first_pass, second_pass):
        if not os.path.isdir(path):
            raise click.ClickException(f"Image directory does not exist: {path}")

    first_output = ensure_dir(os.path.join(first_pass, "outputs"))
    second_output = ensure_dir(os.path.join(second_pass, "outputs"))
    first_masks = os.path.join(first_pass, "masks")
    second_masks = os.path.join(second_pass, "masks")

    logger(
        second_output,
        {"first_pass": first_pass, "second_pass": second_pass, "channel": channel,
         "model": model, "diam": diam, "flow": flow, "prob": prob},
        command="align_images",
    )

    mask_kwargs = dict(
        diam=diam, channel=channel, model=model, no_edge=no_edge, flow=flow,
        prob=prob, replace=False, count=False, normalize=normalize,
        batch=batch, gpu=gpu,
    )
    print("Generating first pass masks...")
    get_masks(first_pass, first_masks, **mask_kwargs)
    print("Generating second pass masks...")
    get_masks(second_pass, second_masks, **mask_kwargs)

    print("Finding alignment...")
    shared = sorted(
        {os.path.basename(f) for f in find_images(first_masks, channel=channel)}
        & {os.path.basename(f) for f in find_images(second_masks, channel=channel)}
    )
    if not shared:
        raise click.ClickException("No masks with matching filenames between the two passes")

    corrections = align_images(
        [os.path.join(first_masks, name) for name in shared],
        [os.path.join(second_masks, name) for name in shared],
        output_1=first_output,
        output_2=second_output,
        channel=channel,
    )
    corrections.to_csv(os.path.join(second_output, "correction_results.csv"), index=False)
    if corrections.empty:
        raise click.ClickException("No image pairs were aligned; nothing to apply")

    print("Applying alignment...")
    dest_dir = ensure_dir(os.path.join(second_output, "aligned_images"))
    for _, row in tqdm(corrections.iterrows(), total=len(corrections), desc="Applying"):
        images = find_images(second_pass, channel="*")
        images = [f for f in images if os.path.basename(f).startswith(row["image_set"])]
        apply_pad(
            images,
            outdir=dest_dir,
            right=int(row["right_correction"]),
            left=int(row["left_correction"]),
            top=int(row["top_correction"]),
            bot=int(row["bottom_correction"]),
        )
    print(f"Wrote aligned images to {dest_dir}")
