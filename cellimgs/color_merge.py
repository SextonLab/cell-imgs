from email.policy import default
import os
import re
import glob

import click
import numpy as np

from progress.bar import Bar

import tifffile as tif

from .logger import logger

@click.command()
@click.argument('indir', help='Input Directory')
@click.argument('outdir', help='Output Directory')
@click.argument('red', help='Red Channel ID')
@click.argument('grn', help='Green Channel ID')
@click.argument('blu', help='Blue Channel ID')
@click.option('--replace', '-r', default=False, is_flag=True, help="Replace existing color channels")
def merge_channel(indir:str, outdir:str, red, grn, blu, repalce=False):
    """
    Merge Color 3 single channel tifs into a single rgb tif
    indir: directory where single channel tifs live
    outdir: directory where multichannel tifs will go
    red: red channel id e.g C1 C01
    grn: green channel id
    blu: blue channel id
    replace: flag to repalce existing files
    """
    logger(outdir, locals())
    assert os.path.exists(indir), "Input directory doesn't exist"
    if not os.path.exists(outdir):
        print(f"Output Directory doesn't exist, creating directory: ",{outdir})
        os.mkdir(outdir)
    
    names = glob.glob(os.path.join(indir, "*"+red+".tif")) # get all of the images needed
     
    img = tif.imread(names[0])
    x,y = img.shape
    img = np.zeros((3, x, y))
    remove = len(red)+4
    files = [f[:-remove] for f in names]
    bar = Bar('Merging...', max=len(files))
    for f in files:
        fname = os.path.join(outdir, f+".tif")
        if not os.path.exists(fname) and not repalce:
            img[0,:,:] = tif.imread(f+red+".tif")
            img[1,:,:] = tif.imread(f+grn+".tif")
            img[2,:,:] = tif.imread(f+blu+".tif")
            tif.imwrite(fname, img)
        bar.next()
    bar.finish()