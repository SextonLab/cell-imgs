from email.policy import default
import os
import re
import glob
import argparse

import pandas as pd
import numpy as np

from progress.bar import Bar

import tifffile as tif

from cellpose import models, utils

from .logger import logger

CMAP = {'r':1,'g':2,'b':3}

def _get_channel(color):
    """
    get channel for doing color images (none=0, red=1, 2=green, 3=blue)
    grey [[0,0]]
    """
    if len(color)>2:
        channel = [[0,0]]
    else:
        channel =[[CMAP[color[0]], CMAP[color[1]]]]
    return channel

parser = argparse.ArgumentParser(description="Generate Masks from tifs")

# positional image and mask diretory
parser.add_argument("images", type=str, help="Source Tiffs")
parser.add_argument("masks", type=str, help="Mask Destination")

# Optional flagged arguments
parser.add_argument("-d", "--diam", type=float, default=0.0)
parser.add_argument('-c', '--channel', type=str, default='*')
parser.add_argument('-m', '--model', type=str, default='cyto') # possibly add all options as choices
parser.add_argument('-n','--no_edge', action='store_true', default=False) 
parser.add_argument('-f', '--flow', type=float, default=0.4)
parser.add_argument('-p', '--prob', type=float, default=0.0)
parser.add_argument('-r','--replace', action='store_true', default=False)
parser.add_argument('--count', action="store_true", default=False)
parser.add_argument('--color', type=str, default='grey', required=False, help='rgb value of cyto and nucleus ex. rg: red ctyo, green nuc')
args = parser.parse_args()

def generate_masks():
    if os.name =='nt':
        os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"
    assert os.path.exists(args.images), "Image Directory doesn't exist"
    if not os.path.exists(args.masks):
        print(f"Creating output directory: {args.masks}")
        os.mkdir(args.masks)
    assert args.diam >=0.0, "Diameter must not be zero"
    assert args.flow >= 0.0, "Flow threshold must not be zero"
    # assert prob >= 0.0, "Cell probability must not be zero"
    if not os.path.exists(os.path.join(args.masks, 'counts.csv')) & args.count:
        csv_path = os.path.join(args.masks, 'count.csv')
        cell_count = {"image":[], "count":[]}
    exten = os.path.join(args.images, f"*{args.channel}.tif")
    exten2 = os.path.join(args.images, f"*{args.channel}.tiff")
    files = glob.glob(exten) + glob.glob(exten2)
    model = models.CellposeModel(model_type=args.model, gpu=True)
    # imgs = [tif.imread(f) for f in files]
    nimg = len(files)
    assert nimg > 0, "no images found"
    
    channels = _get_channel(color=args.color) # black and white images
    if args.diam <= 0:
        args.diam = None
    
    logger(args.masks, locals())

    # split on '/' then take the last element as image name
    names = [f.split(os.sep)[-1] for f in files]
    for i, f in enumerate(files):
        fname = os.path.join(args.masks,names[i])
        if not os.path.exists(fname) or args.replace:
            img = tif.imread(f)
            print(f'Processing Image: {i+1} of {len(names)}')
            mask, _, _ = model.eval(img, diameter=args.diam, channels=channels, flow_threshold=args.flow, cellprob_threshold=args.prob) # , do_3d=do_3d
            if args.no_edge:
                mask = utils.remove_edge_masks(mask)
            tif.imsave(fname, mask.astype('uint16'))
            if args.count:
                cell_count['image'].append(f)
                cell_count['count'].append(len(utils.outlines_list(mask)))
            del mask
        else:
            print(f'Skipping Image: {i+1} of {len(names)} [Already exists]')
    
    if args.count:
        pd.DataFrame(data=cell_count).to_csv(csv_path, index=False)
