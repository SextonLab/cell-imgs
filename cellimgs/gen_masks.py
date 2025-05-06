from email.policy import default
import os
import re
import glob
import argparse
import json

import pandas as pd
import numpy as np

from progress.bar import Bar
from tqdm import tqdm
import tifffile as tif

from cellpose import models, utils, denoise

from .logger import logger

import click

CMAP = {'p':0,'r':1,'g':2,'b':3}

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

# @click.command()
def normalize_params():
    print("Pulling Standard Normalize Parameters...")
    params = models.normalize_default
    params['percentile'] = [1., 99.]
    print("Saving parameters to normalize_default.json")
    with open('normalize_default.json', "w") as file:
        json.dump(params, file)
    

@click.command()
@click.argument('imgdir')
@click.argument('outdir')
@click.option('--diam','-d', default=0.0, help='Cell diameter')
@click.option('--channel','-c', default='*', required=False, help='Channels to segement')
@click.option('--model', '-m',default='cyto3', required=False, help='Model')
@click.option('--no_edge', '-n', is_flag=True, default=False, required=False, help="Extra step to remove cells on the edge of masks")
@click.option('--flow', '-f', default=0.4, required=False, help='Flow threshold')
@click.option('--prob', '-p', default=0.0, required=False, help='Cell probability')
@click.option('--replace', '-r', is_flag=True, default=False, required=False, help='Replace existing masks')
@click.option('--count', is_flag=True, default=False, required=False, help='Create csv in mask folder of image cell counts')
@click.option('--color', default='grey', required=False, help='rgb value of cyto and nucleus ex. rg: red ctyo, green nuc')
@click.option("--normalize", default=True, required=False, help='Use custom Normalize Features')
@click.option('--denoise_model', is_flag=True, default=False, required=False, help="Change model to denoise model")
# @click.option('--do_3d', is_flag=True, default=False, required=False, help='Do 3d segmentation') # DO 3D not working
def generate_masks(imgdir, outdir, diam, channel, model, no_edge, flow, prob, replace, count, color, normalize, denoise_model):  # , do_3d
    get_masks(imgdir, outdir, diam, channel, model, no_edge, flow, prob, replace, count, color, normalize, denoise_model)
    
def get_masks(imgdir, outdir, diam, channel, model, no_edge, flow, prob, replace, count, color, normalize, denoise_model):  # , do_3d
    if os.name =='nt':
        os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"
    assert os.path.exists(imgdir), "Image Directory doesn't exist"
    if not os.path.exists(outdir):
        print(f"Creating output directory: {outdir}")
        os.mkdir(outdir)
    assert  diam >=0.0, "Diameter must not be zero"
    assert  flow >= 0.0, "Flow threshold must not be zero"
    # assert prob >= 0.0, "Cell probability must not be zero"
    if not os.path.exists(os.path.join(outdir, 'counts.csv')) &  count:
        csv_path = os.path.join( outdir, 'count.csv')
        cell_count = {"image":[], "count":[]}
    exten = os.path.join(imgdir, f"*{ channel}.tif")
    exten2 = os.path.join(imgdir, f"*{ channel}.tiff")
    files = glob.glob(exten) + glob.glob(exten2)
    if denoise_model:
        model = denoise.CellposeDenoiseModel(model_type=model, gpu=True)
    else:
        model = models.CellposeModel(model_type=model, gpu=True)
        
    if type(normalize) == str:
        with open(normalize) as f:
            normalize = json.load(f)
    else:
        normalize=True
    nimg = len(files)
    assert nimg > 0, "no images found"
    
    channels = _get_channel(color= color) # black and white images
    if  diam <= 0:
         diam = None
    
    logger(outdir, locals())

    names = [os.path.basename(f) for f in files] 
    for i, f in enumerate(tqdm(files)):
        fname = os.path.join( outdir,names[i])
        if not os.path.exists(fname) or  replace:
            img = tif.imread(f)
            if denoise_model:
                mask, _, _, _ = model.eval(img, diameter= diam, 
                                           channels=channels,  normalize=normalize,
                                           flow_threshold=flow, cellprob_threshold=prob)
            else:
                mask, _, _ = model.eval(img, diameter=diam,
                                        channels=channels, normalize=normalize,
                                        flow_threshold=flow, cellprob_threshold=prob)
            if  no_edge:
                mask = utils.remove_edge_masks(mask)
            tif.imwrite(fname, mask.astype('uint16'))
            if  count:
                cell_count['image'].append(f)
                cell_count['count'].append(len(utils.outlines_list(mask)))
            del mask
        else:
            print(f'Skipping Image: {i+1} of {len(names)} [Already exists]')
    
    if  count:
        pd.DataFrame(data=cell_count).to_csv(csv_path, index=False)
