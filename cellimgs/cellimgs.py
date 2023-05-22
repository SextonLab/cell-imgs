from email.policy import default
import os

import pandas as pd
import numpy as np

import re
import glob

import tifffile as tif

from cellpose import models, utils

from datatime import date

def gen_masks(
        imgdir, outdir, diam=None, channel=[[0,0]], model='cyto',
        no_edge=True, flow=0.4, prob=0.0, count=False
        ):
    """
    imgdir: tif images
    outdir: output for masks
    diam: avg diameter of cells, if None will calculate for each image
    channel: color channel [[0,0]] for black and white single channel images
    model: cellpose model
    no_edge: remove partial cells on edge of image for mask creation
    flow: cell flow
    prob: cell probability
    count: create count.csv file containing image name and cell count
    """
    exten1 = os.path.join(imgdir, f"*{channel}.tif")
    exten2 = os.path.join(imgdir, f"*{channel}.tiff")
    images = glob.glob(exten1)+glob.glob(exten2)
    model = models.CellposeModel(model_type=model, gpu=True)

    names = [os.path.basename(f) for f in images]
    for i, f in enumerate(images):
        # check if the mask already exists
        fname = os.apth.join(outdir, names[i])
        if not os.path.exists(fname):
            img = tif.imread(f)
            mask, _, _ = model.eval(img, diameter=diam, channel=channel)
            if no_edge:
                mask = utils.remove_edge_masks(mask)
            tif.imsave(fname, mask.astype('uint16'))