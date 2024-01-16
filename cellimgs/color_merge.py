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
@click.argument('indir')
@click.argument('outdir')
@click.argument('red')
@click.argument('grn')
@click.argument('blu')
@click.option('--replace', '-r', default=False, is_flag=True, help="Replace existing color channels")
def merge_channel(indir:str, outdir:str, red, grn, blu, replace):
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
    
    red_name = glob.glob(os.path.join(indir, "*"+red+".tif")) # get all of the images needed
    grn_name = glob.glob(os.path.join(indir, "*"+grn+".tif"))
    blu_name = glob.glob(os.path.join(indir, "*"+blu+".tif"))
     
    img = tif.imread(red_name[0])
    x,y = img.shape
    img = np.zeros((3, x, y))
    
    assert len(red_name) == len(grn_name) & len(red_name) == len(blu_name), f"Different number of images per color channel\nRED:{len(red_name)}\nGreen{len(grn_name)}\nBlue{len(blu_name)}"
    
    files = [f[:-7]+".tif" for f in red_name]
    print(files[:4])
    
    bar = Bar('Merging...', max=len(files))
    for i,f in enumerate(files):
        fname = os.path.join(outdir, os.path.basename(f))
        if not os.path.exists(fname) and not replace:
            img[0,:,:] = tif.imread(red_name[i])
            img[1,:,:] = tif.imread(grn_name[i])
            img[2,:,:] = tif.imread(blu_name[i])
            tif.imwrite(fname, img)
        bar.next()
    bar.finish()
    