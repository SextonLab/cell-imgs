from email.policy import default
import os
import re # REEEEEEE
import glob

from .merger import make_table, sort_df, smash
from .logger import logger
import click
from progress.bar import ChargingBar

import pandas as pd

SCOPES = ['CV8000', 'CQ1']

@click.command()
@click.argument('indir')
@click.argument('outdir')
@click.option('--scope', default='CV8000', help='Which Scope')
@click.option('--on_loc', default=False, help='Used to for search and destroy data')
def smash_tif(indir, outdir, scope, on_loc=False):
    if os.name == 'nt':
        os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"
    assert os.path.exists(indir), "Image Directory doesn't exist"
    if not os.path.exists(outdir):
        print(f"Creating output directory: {outdir}")
        os.mkdir(outdir)
    assert scope in SCOPES, "Unknown Scope"
    if scope =='CQ1':
        on_loc=False
    files = glob.glob(os.path.join(indir, '*.tif')) + glob.glob(os.path.join(indir, '*.tiff'))
    df = make_table(files=files, scope=scope)
    wells = df['well_id'].unique().tolist()
    bar = ChargingBar('Smashing Tifs...', max=len(wells))
    for w in wells:
        if on_loc:
            fields = df.loc[df['well_id']==w, 'location'].unique().tolist()
        else:
            fields = df.loc[df['well_id']==w, 'field_id'].unique().tolist()
        channels = df.loc[df['well_id']==w, 'channel'].unique().tolist()
        for f in fields:
            for c in channels:
                fname = os.path.join(outdir, f"{w}_{f}_c{c}.tif")
                imgs = sort_df(df=df, well=w, channel=c, field=f, on_location=on_loc)
                imgs = sorted(imgs, key=lambda x: int("".join([i for i in x if i.isdigit()])))
                smash(files=imgs, filename=fname)
        bar.next()
    bar.finish()