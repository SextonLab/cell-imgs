"""Tests for the Cellpose 4 migration that do not need a GPU or model weights."""

import click
import pytest

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
