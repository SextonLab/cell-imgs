import pytest

from cellimgs import metadata


def test_cv8000_filename_parses():
    meta = metadata.parse_filename(
        "/data/plate1_A01_T0001F002L01A01Z03C02.tif", "CV8000"
    )
    assert meta["plate_id"] == "plate1"
    assert meta["well_id"] == "A01"
    assert meta["row_id"] == "A"
    assert meta["column_id"] == "1"
    assert meta["field_id"] == 2
    assert meta["zstack"] == 3
    assert meta["channel"] == 2
    assert meta["location"] == 1


def test_cq1_filename_parses_from_basename():
    """The old CQ1 regex required a path separator but was applied to the
    basename, so it never matched and every CQ1 run produced no output."""
    meta = metadata.parse_filename(
        "/data/PlateA/W0001F0002T0001Z003C1.tif", "CQ1"
    )
    assert meta is not None
    assert meta["well_id"] == "W0001"
    assert meta["field_id"] == 2
    assert meta["zstack"] == 3
    assert meta["channel"] == 1
    assert meta["plate_id"] == "PlateA"


def test_cx5_arrayscan_filename_parses():
    """Cellomics ArrayScan naming, as produced alongside .C01 files."""
    meta = metadata.parse_filename(
        "/data/MFGTMP_260306160001_A01f00d0.C01", "CX5"
    )
    assert meta["plate_id"] == "MFGTMP_260306160001"
    assert meta["well_id"] == "A01"
    assert meta["row_id"] == "A"
    assert meta["field_id"] == 0
    assert meta["channel"] == 0


def test_stich_filename_parses():
    meta = metadata.parse_filename("A01_F0001_T0001_Z0004_C02.tif", "STICH")
    assert meta["well_id"] == "A01"
    assert meta["zstack"] == 4
    assert meta["channel"] == 2


def test_stack_scope_reparses_this_packages_own_output():
    """stack-imgs and smashtif output must be feedable back into get-wellcounts."""
    name = metadata.stack_name("A01", 2, 3)
    meta = metadata.parse_filename(f"/masks/{name}", "STACK")
    assert meta["well_id"] == "A01"
    assert meta["field_id"] == 2
    assert meta["channel"] == 3


def test_unmatched_filename_returns_none():
    assert metadata.parse_filename("not_a_plate_image.tif", "CV8000") is None


def test_scope_normalisation_accepts_readme_typo():
    assert metadata.normalize_scope("cv800") == "CV8000"
    assert metadata.normalize_scope("cq1") == "CQ1"
    assert metadata.normalize_scope("cx5") == "CX5"
    with pytest.raises(ValueError):
        metadata.normalize_scope("NotAScope")


@pytest.mark.parametrize(
    "well,expected", [("A01", ("A", "1")), ("W0001", ("W", "1")), ("P24", ("P", "24"))]
)
def test_split_wellid(well, expected):
    assert metadata.split_wellid(well) == expected


def test_zstack_sorts_numerically_not_lexically(tmp_path):
    """Z10 must come after Z9, and digits in the directory name must not
    influence the order the way the old digit-concatenation sort did."""
    folder = tmp_path / "run2024"
    folder.mkdir()
    files = [
        str(folder / f"plate1_A01_T0001F001L01A01Z{z:02d}C01.tif")
        for z in (10, 2, 9, 1)
    ]
    df = metadata.build_table(files, "CV8000")
    ordered = metadata.stack_files(df, "A01", 1, 1)
    assert [int(p[-9:-7]) for p in ordered] == [1, 2, 9, 10]


def test_iter_groups_is_per_well(tmp_path):
    """Wells with different field lists must not produce empty groups."""
    files = [
        str(tmp_path / "plate1_A01_T0001F001L01A01Z01C01.tif"),
        str(tmp_path / "plate1_B02_T0001F007L01A01Z01C01.tif"),
    ]
    df = metadata.build_table(files, "CV8000")
    assert list(metadata.iter_groups(df)) == [("A01", 1, 1), ("B02", 7, 1)]


def test_stack_name_is_stable():
    assert metadata.stack_name("A01", 2, 3) == "A01_F002_C03.tif"
