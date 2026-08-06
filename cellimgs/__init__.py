"""Command line tools for high-content microscopy image processing.

Nothing heavy is imported here on purpose. The previous version eagerly
imported every submodule, so a single missing optional dependency (cellpose,
or the long-gone ``progress`` package) broke all eleven console scripts at
once. Import the submodule you need, or use the installed commands.
"""

__version__ = "1.0.0"

__all__ = [
    "c01",
    "imgio",
    "logger",
    "metadata",
]
