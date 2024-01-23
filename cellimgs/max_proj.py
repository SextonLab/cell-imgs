from email.policy import default
import os
import re
import glob

import argparse
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

parser = argparse.ArgumentParser(description="Maximum projection for zstacked tifs")

parser.add_argument("indir", type=str, help="Input directory")
parser.add_argument("outdir", type=str, help="Output directory")
parser.add_argument("--channel","-c", default="*", required=False, help="Channel")
args = parser.parse_args()
def max_project():
    assert os.path.exists(args.indir), "Zstack directory does not exist"
    if not os.path.exists(args.outdir):
        print(f"Missing output directory... creating directory {args.outdir}")
        os.mkdir(args.outdir)
    logger(args.outdir, locals())
    files = glob.glob(os.path.join(args.indir, f"*{args.channel}.tif"))
    # print(files[:2])
    for f in files:
        fn = f.split(os.sep)[-1]
        print(fn)
        img = tif.imread(f)
        assert len(img.shape) == 3,f"Image {f} is not 3 dimensional"
        a, b,c = img.shape
        out = np.max(img, axis=_get_axis(a,b,c))
        fname = os.path.join(args.outdir, fn)
        tif.imsave(fname, data=out)