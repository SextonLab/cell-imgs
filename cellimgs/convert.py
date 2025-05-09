from email.policy import default
import os
import re
import glob

import click
import pandas as pd
import numpy as np

from progress.bar import Bar

import tifffile as tif

import javabridge
import bioformats

from .logger import logger

@click.command()
@click.argument('indir')
@click.argument('outdir')
@click.option('--channel','-c', default='*', help='Specific Channel')
def convert(indir, outdir, channel):
    if os.name =='nt':
        os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"
    assert os.path.exists(indir), "C01 Directory doesn't exist"
    # assert os.path.exists(outdir), "TIF directory doens't exist"
    if not os.path.exists(outdir):
        print("Creating Directory: ", outdir)
        os.mkdir(outdir)
    logger(outdir, locals())

    javabridge.start_vm(class_path=bioformats.JARS)
    path = os.path.join(indir, f'*{channel}.C01')
    files = glob.glob(path)
    bar = Bar('converting',max=len(files))
    for f in files:
        fname = os.path.splitext(os.path.basename(f))[0]+'.tif'
        filename = os.path.join(outdir, fname)
        data = bioformats.ImageReader(f).read()
        # data = data.astype('float16')
        tif.imwrite(filename, data=data)
        bar.next()
    bar.finish()
    javabridge.kill_vm()