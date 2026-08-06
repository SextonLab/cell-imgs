"""CLI-level tests for every command that does not need a GPU."""

import numpy as np
import pandas as pd
import pytest
import tifffile as tif
from click.testing import CliRunner

from cellimgs import c01
from cellimgs.color_merge import merge_channel
from cellimgs.convert import convert
from cellimgs.counts import get_image_counts, get_well_counts
from cellimgs.full_smash import s_n_s
from cellimgs.max_proj import max_project
from cellimgs.stacker import stack_tif


@pytest.fixture
def runner():
    return CliRunner()


def invoke(runner, command, args):
    result = runner.invoke(command, args)
    assert result.exit_code == 0, result.output + str(result.exception)
    return result


# --------------------------------------------------------------------------
# stack-imgs


def test_stack_imgs_cv8000(runner, cv8000_plate, tmp_path):
    dest = tmp_path / "stacks"
    invoke(runner, stack_tif, [str(cv8000_plate), str(dest)])

    # 2 wells x 2 fields x 2 channels
    stacks = sorted(p.name for p in dest.glob("*.tif"))
    assert stacks == [
        "A01_F001_C01.tif", "A01_F001_C02.tif",
        "A01_F002_C01.tif", "A01_F002_C02.tif",
        "B02_F001_C01.tif", "B02_F001_C02.tif",
        "B02_F002_C01.tif", "B02_F002_C02.tif",
    ]
    stack = tif.imread(dest / "A01_F001_C01.tif")
    assert stack.shape == (3, 16, 20)
    assert stack.dtype == np.uint16


def test_stack_imgs_cq1_produces_output(runner, cq1_plate, tmp_path):
    """The CQ1 path used to parse zero files and silently write nothing."""
    dest = tmp_path / "cq1_stacks"
    invoke(runner, stack_tif, [str(cq1_plate), str(dest), "-s", "CQ1"])

    assert sorted(p.name for p in dest.glob("*.tif")) == [
        "W0001_F001_C01.tif", "W0002_F001_C01.tif"
    ]
    assert tif.imread(dest / "W0001_F001_C01.tif").shape == (3, 16, 20)


def test_stack_imgs_no_longer_requires_the_peccu_prefix(runner, cv8000_plate, tmp_path):
    """The non-bulk glob was hardcoded to 'PECCU*.tif'."""
    assert not any(p.name.startswith("PECCU") for p in cv8000_plate.glob("*.tif"))
    dest = tmp_path / "out"
    invoke(runner, stack_tif, [str(cv8000_plate), str(dest)])
    assert list(dest.glob("*.tif"))


def test_stack_imgs_rejects_unmatched_names(runner, tmp_path, plane_writer):
    src = tmp_path / "src"
    plane_writer(src / "random_name.tif")
    result = runner.invoke(stack_tif, [str(src), str(tmp_path / "dest")])
    assert result.exit_code != 0
    assert "did not match" in result.output or "matched" in result.output


# --------------------------------------------------------------------------
# smashtif


def test_smashtif_writes_max_projections(runner, cv8000_plate, tmp_path):
    dest = tmp_path / "mips"
    invoke(runner, s_n_s, [str(cv8000_plate), str(dest)])

    mip = tif.imread(dest / "A01_F001_C01.tif")
    assert mip.ndim == 2
    assert mip.dtype == np.uint16
    # Z-planes for A01/F001/C01 carry values 0, 2 and 4.
    assert int(mip[0, 0]) == 4


def test_smashtif_skips_existing_without_replace(runner, cv8000_plate, tmp_path):
    dest = tmp_path / "mips"
    invoke(runner, s_n_s, [str(cv8000_plate), str(dest)])

    result = invoke(runner, s_n_s, [str(cv8000_plate), str(dest)])
    assert "Wrote 0 projection" in result.output

    result = invoke(runner, s_n_s, [str(cv8000_plate), str(dest), "--replace"])
    assert "Wrote 8 projection" in result.output


# --------------------------------------------------------------------------
# max-proj


def test_max_proj_projects_axis_zero(runner, tmp_path):
    src, dest = tmp_path / "stacks", tmp_path / "mips"
    src.mkdir()
    # 40 z-planes of a 16x20 image: the old "smallest axis" heuristic picked
    # the 16-row axis instead of z.
    stack = np.zeros((40, 16, 20), dtype=np.uint16)
    stack[7] = 99
    tif.imwrite(src / "stack.tif", stack)

    invoke(runner, max_project, [str(src), str(dest)])
    out = tif.imread(dest / "stack.tif")
    assert out.shape == (16, 20)
    assert out.max() == 99


def test_max_proj_skips_2d_images_without_aborting(runner, tmp_path, plane_writer):
    src, dest = tmp_path / "stacks", tmp_path / "mips"
    src.mkdir()
    plane_writer(src / "flat.tif", value=5)
    tif.imwrite(src / "real.tif", np.zeros((3, 8, 8), dtype=np.uint16),
                photometric="minisblack")

    result = invoke(runner, max_project, [str(src), str(dest)])
    assert (dest / "real.tif").exists()
    assert not (dest / "flat.tif").exists()
    assert "not 3D" in result.output


# --------------------------------------------------------------------------
# cmerge


def test_cmerge_pairs_channels_by_name(runner, tmp_path, plane_writer):
    src, dest = tmp_path / "src", tmp_path / "rgb"
    for index, name in enumerate(["imgA", "imgB"]):
        plane_writer(src / f"{name}_C01.tif", value=index + 1)
        plane_writer(src / f"{name}_C02.tif", value=index + 10)
        plane_writer(src / f"{name}_C03.tif", value=index + 100)

    invoke(runner, merge_channel, [str(src), str(dest), "C01", "C02", "C03"])
    rgb = tif.imread(dest / "imgA.tif")
    assert rgb.shape == (16, 20, 3)
    assert list(rgb[0, 0]) == [1, 10, 100]


def test_cmerge_replace_actually_writes(runner, tmp_path, plane_writer):
    """--replace used to invert the guard so that nothing was written."""
    src, dest = tmp_path / "src", tmp_path / "rgb"
    plane_writer(src / "img_C01.tif", value=1)
    plane_writer(src / "img_C02.tif", value=2)
    plane_writer(src / "img_C03.tif", value=3)

    invoke(runner, merge_channel, [str(src), str(dest), "C01", "C02", "C03"])
    (dest / "img.tif").unlink()
    invoke(runner, merge_channel, [str(src), str(dest), "C01", "C02", "C03", "--replace"])
    assert (dest / "img.tif").exists()


def test_cmerge_skips_images_missing_a_channel(runner, tmp_path, plane_writer):
    src, dest = tmp_path / "src", tmp_path / "rgb"
    plane_writer(src / "full_C01.tif")
    plane_writer(src / "full_C02.tif")
    plane_writer(src / "full_C03.tif")
    plane_writer(src / "partial_C01.tif")

    result = invoke(runner, merge_channel, [str(src), str(dest), "C01", "C02", "C03"])
    assert "missing one or more channels" in result.output
    assert sorted(p.name for p in dest.glob("*.tif")) == ["full.tif"]


def test_cmerge_creates_output_dir_before_logging(runner, tmp_path, plane_writer):
    """logger() used to run before os.mkdir, so a new outdir raised."""
    src = tmp_path / "src"
    plane_writer(src / "img_C01.tif")
    plane_writer(src / "img_C02.tif")
    plane_writer(src / "img_C03.tif")
    invoke(runner, merge_channel, [str(src), str(tmp_path / "new" / "nested"),
                                   "C01", "C02", "C03"])


# --------------------------------------------------------------------------
# counts


def test_get_imgcounts_is_invokable(runner, tmp_path):
    """The option was spelled --chanel while the parameter was channel, so
    this command raised TypeError however it was called."""
    masks = tmp_path / "masks"
    masks.mkdir()
    mask = np.zeros((10, 10), dtype=np.uint16)
    mask[0:2, 0:2] = 1
    mask[5:7, 5:7] = 2
    tif.imwrite(masks / "plate1_A01_T0001F001L01A01Z01C01.tif", mask)

    invoke(runner, get_image_counts, [str(masks)])
    df = pd.read_csv(masks / "counts.csv")
    assert df["count"].tolist() == [2]


def test_get_wellcounts_aggregates(runner, tmp_path):
    rows = []
    for well in ("A01", "A02"):
        for field in (1, 2):
            rows.append({
                "image": f"/x/plate1_{well}_T0001F{field:03d}L01A01Z01C01.tif",
                "count": 10,
            })
    csv = tmp_path / "counts.csv"
    pd.DataFrame(rows).to_csv(csv, index=False)

    invoke(runner, get_well_counts, [str(csv), "-s", "CV8000"])
    totals = pd.read_csv(tmp_path / "well_count.csv")
    assert totals.set_index("well_id")["count"].to_dict() == {"A01": 20, "A02": 20}


def test_get_wellcounts_reads_stacked_output_names(runner, tmp_path):
    """Counts taken from smashtif/stack-imgs output use the STACK scope."""
    csv = tmp_path / "counts.csv"
    pd.DataFrame([
        {"image": "/masks/A01_F001_C01.tif", "count": 3},
        {"image": "/masks/A01_F002_C01.tif", "count": 4},
    ]).to_csv(csv, index=False)

    invoke(runner, get_well_counts, [str(csv), "-s", "STACK"])
    totals = pd.read_csv(tmp_path / "well_count.csv")
    assert totals.set_index("well_id")["count"].to_dict() == {"A01": 7}


def test_get_wellcounts_handles_windows_paths(runner, tmp_path):
    """The old implementation split on '/' only."""
    csv = tmp_path / "counts.csv"
    pd.DataFrame([
        {"image": r"C:\data\plate1_A01_T0001F001L01A01Z01C01.tif", "count": 4}
    ]).to_csv(csv, index=False)

    invoke(runner, get_well_counts, [str(csv), "-s", "CV8000"])
    totals = pd.read_csv(tmp_path / "well_count.csv")
    assert totals["well_id"].tolist() == ["A01"]


# --------------------------------------------------------------------------
# convert-c01


def test_convert_c01_without_java(runner, tmp_path, rng):
    src, dest = tmp_path / "c01", tmp_path / "tif"
    src.mkdir()
    original = rng.integers(0, 4096, size=(12, 18)).astype(np.uint16)
    (src / "plate1_A01_T0001F001L01A01Z01C01.C01").write_bytes(c01.encode(original))

    invoke(runner, convert, [str(src), str(dest)])
    converted = tif.imread(dest / "plate1_A01_T0001F001L01A01Z01C01.tif")
    np.testing.assert_array_equal(converted, original)
