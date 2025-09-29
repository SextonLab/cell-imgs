import os
import re

from email.policy import default
from glob import glob

# from .logger import logger
from .merger import make_table, sort_df, smash
from .max_proj import _get_axis

import click
from tqdm import tqdm

import numpy as np
import pandas as pd
import tifffile as tif

SCOPES = ['CV8000', 'CQ1', "STICH"]

def stack_n_smash(indir, outdir, scope, channel="*", on_loc=False, bulk=False):
    if os.name == 'nt':
        os.environ['KMP_DUPLICATE_LIB_OK'] = "TRUE"
    assert os.path.exists(indir), f"Image Directory {indir} does not exist"
    if not os.path.exists(outdir):
        print(f'Creating output directoy {outdir}')
        os.mkdir(outdir)
    scope = str(scope).upper()
    assert scope in SCOPES, f"Unknown scope: {scope}"
    if scope == 'CQ1':
        on_loc = False
    if bulk:
        files = glob(os.path.join(indir, '*', f"*{channel}.tif")) + glob(os.path.join(indir, '*', f"*{channel}.tiff"))
    else:
        files = glob(os.path.join(indir, f"*{channel}.tif")) + glob(os.path.join(indir, f"*{channel}.tiff"))
    df = make_table(files=files, scope=scope)
    wells = df['well_id'].unique().tolist()
    for w in tqdm(wells, desc='Arranging Z-Stacks'):
        # temp = df.loc[df['well_id']==w]

        if on_loc:
            fields = df.loc[df['well_id']==w, 'location'].unique().tolist()
        else:
            fields = df.loc[df['well_id']==w, 'field_id'].unique().tolist()
        channels = df.loc[df['well_id']==w, 'channel'].unique().tolist()
        for f in fields:
            for c in channels:
                imgs = sort_df(df=df, well=w, channel=c, field=f, on_location=on_loc)
                images = [tif.imread(x) for x in imgs]
                a,b = images[0].shape
                out_img = np.zeros((len(images), a, b))
                for i, img in enumerate(images):
                    out_img[i, :, :] += img
                out = np.max(out_img, axis=0)
                outname = os.path.join(outdir, f"{w}_{f}_{c}.tif")
                tif.imwrite(outname, out)

@click.command()
@click.argument('indir')
@click.argument('outdir')
@click.option('--scope', '-s', default='CV8000', required=False, help='Microscope')
@click.option("--channel", "-c", default='*', required=False, help='Selected Channel, defaults to all channels')
@click.option('--on_loc', "-l", is_flag=True, default=False, required=False, help='Change from zstack to location')
@click.option('--bulk', '-b', is_flag=True, default=False, required=False, help='Set for sub directories')
def s_n_s(indir, outdir, scope, channel, on_loc, bulk):
    stack_n_smash(indir=indir, outdir=outdir, scope=scope,
                  channel=channel, on_loc=on_loc, bulk=bulk)

                  
if __name__ == "__main__":
    s_n_s()
    