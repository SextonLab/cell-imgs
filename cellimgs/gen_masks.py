"""Cellpose segmentation, producing label masks for CellProfiler.

Targets Cellpose 4 (Cellpose-SAM). Three things changed in v4 that silently
broke the previous version of this module:

* ``model_type=`` is accepted but ignored, so ``--model cyto3`` produced CPSAM
  masks while the log file claimed otherwise.
* ``channels=`` is accepted but ignored, so the ``--color``/``CMAP`` path had
  no effect. Multi-channel input is now described with ``--channel-axis``.
* ``denoise.CellposeDenoiseModel`` no longer exists, so ``--denoise_model``
  raised ``AttributeError``.

The v3 model zoo (``cyto``, ``cyto2``, ``cyto3``, ``nuclei``, ...) is gone;
CPSAM replaces all of them. ``--model`` now names a *custom* trained model.
"""

import json
import os

import click
import numpy as np
import pandas as pd
import tifffile as tif
from tqdm import tqdm

from .imgio import count_labels, ensure_dir, find_images, write_image
from .logger import logger

#: Built-in model names from the Cellpose 3 zoo. These no longer exist in v4,
#: and passing one used to be silently ignored, so reject them loudly.
LEGACY_MODELS = {
    "cyto", "cyto2", "cyto3", "nuclei", "tissuenet", "livecell", "general",
    "cp", "cpx", "tn1", "tn2", "tn3", "lc1", "lc2", "lc3", "lc4",
    "bact_phase", "bact_fluor", "deepbacs", "yeast_phc", "yeast_bf",
}

MAX_LABELS = np.iinfo(np.uint16).max


def resolve_model(model):
    """Turn a ``--model`` value into a ``pretrained_model`` argument."""
    if not model:
        return None  # Cellpose default: cpsam_v2

    if os.path.exists(model):
        return model

    name = model.lower().removesuffix("_cp3")
    if name in LEGACY_MODELS:
        raise click.BadParameter(
            f"'{model}' is a Cellpose 3 model and does not exist in Cellpose 4. "
            "Cellpose-SAM replaces the entire v3 zoo -- omit --model to use it. "
            "Pass a path to a custom-trained model if you have one.",
            param_hint="--model",
        )
    return model


def load_normalize(normalize):
    """Resolve ``--normalize`` into the value Cellpose expects."""
    if normalize is None:
        return True
    if not os.path.exists(normalize):
        raise click.BadParameter(
            f"normalize parameter file not found: {normalize}. "
            "Run 'normal-params' to generate one.",
            param_hint="--normalize",
        )
    with open(normalize) as handle:
        return json.load(handle)


def build_model(pretrained_model, gpu):
    """Construct the Cellpose model, importing cellpose lazily."""
    from cellpose import models

    if gpu:
        import torch

        if not torch.cuda.is_available():
            print(
                "Warning: --gpu requested but torch reports no CUDA device. "
                "Falling back to CPU, which is dramatically slower."
            )
            gpu = False

    kwargs = {"gpu": gpu}
    if pretrained_model:
        kwargs["pretrained_model"] = pretrained_model
    return models.CellposeModel(**kwargs)


def get_masks(
    imgdir,
    outdir,
    diam=0.0,
    channel="*",
    model=None,
    no_edge=False,
    flow=0.4,
    prob=0.0,
    replace=False,
    count=False,
    normalize=None,
    batch=8,
    channel_axis=None,
    min_size=15,
    do_3d=False,
    anisotropy=None,
    gpu=True,
):
    """Segment every image in ``imgdir`` and write uint16 label masks.

    Returns the path of the counts CSV when ``count`` is set, else ``None``.
    """
    if os.name == "nt":
        os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    files = find_images(imgdir, channel=channel)
    if not files:
        raise click.ClickException(
            f"No .tif/.tiff images matching channel '{channel}' found in {imgdir}"
        )

    if flow < 0:
        raise click.BadParameter("flow threshold must not be negative", param_hint="--flow")
    if diam < 0:
        raise click.BadParameter("diameter must not be negative", param_hint="--diam")

    ensure_dir(outdir)
    pretrained_model = resolve_model(model)
    normalize_value = load_normalize(normalize)
    diameter = diam if diam > 0 else None

    logger(
        outdir,
        {
            "imgdir": imgdir,
            "outdir": outdir,
            "images": len(files),
            "model": pretrained_model or "cpsam_v2 (Cellpose-SAM default)",
            "diameter": diameter,
            "channel": channel,
            "channel_axis": channel_axis,
            "flow_threshold": flow,
            "cellprob_threshold": prob,
            "min_size": min_size,
            "no_edge": no_edge,
            "do_3D": do_3d,
            "anisotropy": anisotropy,
            "batch_size": batch,
            "normalize": normalize or True,
            "replace": replace,
        },
        command="gen-masks",
    )

    # Work out what actually needs segmenting before paying to load the model
    # onto the GPU.
    todo = [
        (path, os.path.join(outdir, os.path.basename(path)))
        for path in files
        if replace or not os.path.exists(os.path.join(outdir, os.path.basename(path)))
    ]
    skipped = len(files) - len(todo)
    if skipped:
        print(f"Skipping {skipped} image(s) with masks that already exist.")
    if not todo:
        print("Nothing to do.")
        return None

    from cellpose import utils

    model_obj = build_model(pretrained_model, gpu)

    cell_count = {"image": [], "count": []}
    for source, target in tqdm(todo, desc="Segmenting"):
        img = tif.imread(source)
        masks, _flows, _styles = model_obj.eval(
            img,
            batch_size=batch,
            diameter=diameter,
            channel_axis=channel_axis,
            normalize=normalize_value,
            flow_threshold=flow,
            cellprob_threshold=prob,
            min_size=min_size,
            do_3D=do_3d,
            anisotropy=anisotropy,
        )

        if no_edge:
            masks = utils.remove_edge_masks(masks)

        if masks.max() > MAX_LABELS:
            raise click.ClickException(
                f"{source}: {masks.max()} objects exceeds the uint16 label limit"
            )

        write_image(target, masks.astype(np.uint16))

        if count:
            cell_count["image"].append(source)
            cell_count["count"].append(count_labels(masks))
        del masks

    if count:
        csv_path = os.path.join(outdir, "counts.csv")
        pd.DataFrame(data=cell_count).to_csv(csv_path, index=False)
        print(f"Wrote {csv_path}")
        return csv_path
    return None


@click.command()
@click.argument("imgdir")
@click.argument("outdir")
@click.option("--diam", "-d", default=0.0, help="Cell diameter in pixels; 0 disables rescaling")
@click.option("--channel", "-c", default="*", help="Filename fragment selecting a channel, e.g. C01")
@click.option("--model", "-m", default=None, help="Path or name of a custom model; omit for Cellpose-SAM")
@click.option("--no_edge", "-n", is_flag=True, default=False, help="Remove objects touching the image edge")
@click.option("--flow", "-f", default=0.4, help="Flow threshold")
@click.option("--prob", "-p", default=0.0, help="Cell probability threshold")
@click.option("--replace", "-r", is_flag=True, default=False, help="Re-segment images that already have masks")
@click.option("--count", is_flag=True, default=False, help="Write counts.csv of per-image object counts")
@click.option("--normalize", default=None, help="Path to a normalize parameter JSON (see normal-params)")
@click.option("--batch", "-b", default=8, help="Cellpose batch size")
@click.option("--channel-axis", default=None, type=int, help="Axis holding channels for multi-channel input")
@click.option("--min-size", default=15, help="Discard objects smaller than this many pixels")
@click.option("--do-3d", is_flag=True, default=False, help="Segment 3D stacks volumetrically")
@click.option("--anisotropy", default=None, type=float, help="Z:XY sampling ratio for --do-3d")
@click.option("--gpu/--no-gpu", default=True, help="Use CUDA if available")
def generate_masks(**kwargs):
    """Generate Cellpose label masks for every image in IMGDIR into OUTDIR."""
    get_masks(**kwargs)


@click.command()
@click.option("--output", "-o", default="normalize_default.json", help="Where to write the JSON")
def normalize_params(output):
    """Write Cellpose's default normalization parameters to a JSON file."""
    from cellpose import models

    params = dict(models.normalize_default)
    params["percentile"] = [1.0, 99.0]
    with open(output, "w") as handle:
        json.dump(params, handle, indent=2)
    print(f"Wrote {output}")
