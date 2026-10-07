"""Tests for the Cellpose 4 migration that do not need a GPU or model weights."""

import click
import numpy as np
import pytest
import tifffile as tif

from cellimgs import gen_masks


@pytest.mark.parametrize("name", ["cyto", "cyto2", "cyto3", "nuclei", "CPx", "cyto2_cp3"])
def test_cellpose3_zoo_names_are_rejected(name):
    """v4 accepts model_type= and silently ignores it, so --model cyto3 used
    to produce CPSAM masks while the log claimed otherwise."""
    with pytest.raises(click.BadParameter, match="Cellpose 3 model"):
        gen_masks.resolve_model(name)


def test_no_model_uses_the_cellpose_default():
    assert gen_masks.resolve_model(None) is None
    assert gen_masks.resolve_model("") is None


def test_custom_model_path_passes_through(tmp_path):
    model = tmp_path / "my_model"
    model.write_bytes(b"weights")
    assert gen_masks.resolve_model(str(model)) == str(model)


def test_unknown_model_name_passes_through():
    """Names that are not from the v3 zoo may be user models in ~/.cellpose."""
    assert gen_masks.resolve_model("my_finetuned_sam") == "my_finetuned_sam"


def test_normalize_defaults_to_true():
    assert gen_masks.load_normalize(None) is True


def test_missing_normalize_file_is_reported():
    with pytest.raises(click.BadParameter, match="normal-params"):
        gen_masks.load_normalize("/nonexistent/normalize.json")


def test_normalize_file_is_loaded(tmp_path):
    path = tmp_path / "norm.json"
    path.write_text('{"percentile": [1.0, 99.0], "normalize": true}')
    assert gen_masks.load_normalize(str(path))["percentile"] == [1.0, 99.0]


def test_missing_images_raises_before_loading_the_model(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(click.ClickException, match="No .tif/.tiff images"):
        gen_masks.get_masks(str(empty), str(tmp_path / "masks"))


class FakeModel:
    """Stands in for CellposeModel: records each eval call, returns one object."""

    def __init__(self):
        self.calls = []

    def eval(self, img, **kwargs):
        self.calls.append((img, kwargs))
        masks = np.zeros(img.shape[:2], dtype=np.int32)
        masks[2:5, 2:5] = 1
        return masks, None, None


@pytest.fixture
def fake_model(monkeypatch):
    model = FakeModel()
    monkeypatch.setattr(gen_masks, "build_model", lambda *args: model)
    return model


@pytest.fixture
def cell_nuc_plate(tmp_path, plane_writer):
    """CV8000 cell (C04, action 01) and nuclear (C01, action 04) planes.
    Field 2 has no nuclear image."""
    src = tmp_path / "plate"
    plane_writer(src / "plate1_A01_T0001F001L01A01Z01C04.tif", value=4)
    plane_writer(src / "plate1_A01_T0001F001L01A04Z01C01.tif", value=1)
    plane_writer(src / "plate1_A01_T0001F002L01A01Z01C04.tif", value=4)
    return src


def test_nuc_channel_segments_cell_and_nucleus_together(tmp_path, cell_nuc_plate, fake_model):
    out = tmp_path / "masks"
    gen_masks.get_masks(str(cell_nuc_plate), str(out), channel="C04", nuc_channel="C01")

    assert len(fake_model.calls) == 1, "field 2 has no nuclear image and must be skipped"
    img, kwargs = fake_model.calls[0]
    assert img.shape == (16, 20, 2)
    assert (img[..., 0] == 4).all() and (img[..., 1] == 1).all(), "cell channel first, nucleus second"
    assert kwargs["channel_axis"] == -1
    assert sorted(p.name for p in out.glob("*.tif")) == ["plate1_A01_T0001F001L01A01Z01C04.tif"]
    assert tif.imread(out / "plate1_A01_T0001F001L01A01Z01C04.tif").dtype == np.uint16


def test_nuc_channel_requires_a_cell_channel(tmp_path, cell_nuc_plate):
    with pytest.raises(click.BadParameter, match="--channel"):
        gen_masks.get_masks(str(cell_nuc_plate), str(tmp_path / "masks"), nuc_channel="C01")


@pytest.mark.parametrize("extra", [{"channel_axis": 0}, {"do_3d": True}])
def test_nuc_channel_rejects_conflicting_options(tmp_path, cell_nuc_plate, extra):
    with pytest.raises(click.BadParameter):
        gen_masks.get_masks(
            str(cell_nuc_plate), str(tmp_path / "masks"), channel="C04", nuc_channel="C01", **extra
        )


def test_nuc_channel_without_any_partner_raises_before_loading_the_model(tmp_path, cell_nuc_plate):
    with pytest.raises(click.ClickException, match="matching C02"):
        gen_masks.get_masks(str(cell_nuc_plate), str(tmp_path / "masks"), channel="C04", nuc_channel="C02")
    assert not (tmp_path / "masks").exists()
