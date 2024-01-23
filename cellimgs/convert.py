from email.policy import default
import os
import re
import glob

import argparse

import pandas as pd
import numpy as np

from progress.bar import Bar

import tifffile as tif

import javabridge
import bioformats

from .logger import logger

parser = argparse.ArgumentParser(description="Convert CO1 images to tifs")

# required arguments, input dir and dest dir
parser.add_argument("indir", type=str, help='CO1 folder')
parser.add_argument("outidr", type=str, help="Tif folder")

# Optional argumnets
parser.add_argument("--channel", "-c", default="*", type=str, help="Specific channel")
args = parser.parse_args()

def convert():
    if os.name =='nt':
        os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"
    assert os.path.exists(args.indir), "C01 Directory doesn't exist"
    assert os.path.exists(args.outdir), "TIF directory doens't exist"

    logger(args.outdir, locals())

    javabridge.start_vm(class_path=bioformats.JARS)
    path = os.path.join(args.indir, f'*{args.channel}.C01')
    files = glob.glob(path)
    bar = Bar('converting',max=len(files))
    for f in files:
        filename = os.path.join(args.outdir,re.search(r'(MFGTMP_\d+_\w+)', f, re.IGNORECASE).group(1)+'.tif')
        data = bioformats.ImageReader(f).read()
        # data = data.astype('float16')
        tif.imsave(filename, data=data)
        bar.next()
    bar.finish()
    javabridge.kill_vm()