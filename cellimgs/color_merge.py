from email.policy import default
import os
import re
import glob

import argparse
import numpy as np

from progress.bar import Bar

import tifffile as tif

from .logger import logger


parser = argparse.ArgumentParser(description="Merge Color channels from sinlge channel tiff to multichannel tifs")

parser.add_argument("indir", type=str, help="Input directory")
parser.add_argument("outdir", type=str, help="Output directory")
parser.add_argument("red", type=str, help='Red channel')
parser.add_argument("grn", type=str, help="Green channel")
parser.add_argument("blu", type=str, help="Blue channel")

parser.add_argument("--replace", "-r", default=False, action='store_true',help="Repalce existing images")

args = parser.parse_args()
def merge_channel():
    """
    Merge Color 3 single channel tifs into a single rgb tif
    indir: directory where single channel tifs live
    outdir: directory where multichannel tifs will go
    red: red channel id e.g C1 C01
    grn: green channel id
    blu: blue channel id
    replace: flag to repalce existing files
    """
    logger(args.outdir, locals())
    assert os.path.exists(args.indir), "Input directory doesn't exist"
    if not os.path.exists(args.outdir):
        print(f"Output Directory doesn't exist, creating directory: ",{args.outdir})
        os.mkdir(args.outdir)
    
    red_name = glob.glob(os.path.join(args.indir, "*"+args.red+".tif")) # get all of the images needed
    grn_name = glob.glob(os.path.join(args.indir, "*"+args.grn+".tif"))
    blu_name = glob.glob(os.path.join(args.indir, "*"+args.blu+".tif"))
     
    img = tif.imread(red_name[0])
    x,y = img.shape
    img = np.zeros((3, x, y))
    
    assert len(red_name) == len(grn_name) & len(red_name) == len(blu_name), f"Different number of images per color channel\nRED:{len(red_name)}\nGreen{len(grn_name)}\nBlue{len(blu_name)}"
    
    files = [f[:-7]+".tif" for f in red_name]
    
    bar = Bar('Merging...', max=len(files))
    for i,f in enumerate(files):
        fname = os.path.join(args.outdir, os.path.basename(f))
        if not os.path.exists(fname) and not args.replace:
            img[0,:,:] = tif.imread(red_name[i])
            img[1,:,:] = tif.imread(grn_name[i])
            img[2,:,:] = tif.imread(blu_name[i])
            tif.imwrite(fname, img)
        bar.next()
    bar.finish()
    