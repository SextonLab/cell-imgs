import os
import pandas as pd
from cellpose import utils
import glob
import tifffile as tif
import click
from tqdm import tqdm

MICROSCOPES = ['CQ1', 'CX5', 'CV8000']

@click.command()
@click.argument('path')
@click.option('--scope', '-s', default='CQ1', help='Microscope ')
def get_well_counts(path, scope):
    data = {
        'well_id':[],
        'count':[]
    }
    df = pd.read_csv(path)
    if scope == 'CQ1':
        df['well_id'] = df['image'].apply(lambda x: x.split('/')[-1].split('F')[0])
    elif scope == 'CX5' or scope=='CV800':
        df['well_id'] = df['image'].apply(lambda x: x.split('_')[-1].split('f')[0])
    else:
        assert scope in MICROSCOPES, "Scope not supported"
    wids = df['well_id'].unique().tolist()
    for w in wids:
        temp = df.loc[df['well_id']==w]
        data['well_id'].append(w)
        data['count'].append(temp['count'].sum())
    dt = pd.DataFrame(data=data)
    fname = os.path.join(os.path.dirname(path), 'well_count.csv')
    dt.to_csv(fname, index=False)