from email.policy import default
import os
import re
import glob

import click
import pandas as pd
import numpy as np

from progress.bar import Bar

import tifffile as tif

from .logger import logger

def _get_axis(a,b,c):
    if a<b and a<c:
        return 0
    elif b<a and b<c:
        return 1
    else:
        return 2

@click.command()
@click.argument('indir')
@click.argument('outdir')
@click.option('--channel', "-c", default="*", required=False, help="Channel")
def max_project(indir, outdir, channel):
    assert os.path.exists(indir), "Zstack directory does not exist"
    if not os.path.exists(outdir):
        print(f"Missing output directory... creating directory {outdir}")
        os.mkdir(outdir)
    logger(outdir, locals())
    files = glob.glob(os.path.join(indir, f"{channel}.tif"))
    for f in files:
        fn = f.split(os.sep)[-1]
        print(fn)
        img = tif.imread(f)
        assert len(img.shape) == 3,f"Image {f} is not 3 dimensional"
        out = np.max(img, axis=_get_axis(img.shape))
        fname = os.path.join(outdir, fn)
        tif.imsave(fname, data=out)