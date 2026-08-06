import numpy as np
import pytest
import tifffile as tif


@pytest.fixture
def rng():
    return np.random.default_rng(1234)


def write_plane(path, value=0, shape=(16, 20), dtype=np.uint16):
    """Write a 2D TIF whose pixels are all ``value``, so stacks are checkable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tif.imwrite(path, np.full(shape, value, dtype=dtype))
    return path


@pytest.fixture
def plane_writer():
    return write_plane


@pytest.fixture
def cv8000_plate(tmp_path):
    """A CV8000 plate: 2 wells x 2 fields x 3 z-planes x 2 channels."""
    src = tmp_path / "cv8000"
    value = 0
    for well in ("A01", "B02"):
        for field in (1, 2):
            for zstack in (1, 2, 3):
                for channel in (1, 2):
                    name = (
                        f"plate1_{well}_T0001F{field:03d}L01A01"
                        f"Z{zstack:02d}C{channel:02d}.tif"
                    )
                    # Distinct values so the max projection is predictable.
                    write_plane(src / name, value=value)
                    value += 1
    return src


@pytest.fixture
def cq1_plate(tmp_path):
    """A CQ1 plate: 2 wells x 1 field x 3 z-planes x 1 channel."""
    src = tmp_path / "cq1" / "PlateA"
    for well in ("W0001", "W0002"):
        for zstack in (1, 2, 3):
            name = f"{well}F0001T0001Z{zstack:03d}C1.tif"
            write_plane(src / name, value=zstack * 10)
    return src
