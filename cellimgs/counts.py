import os
import pandas as pd
from cellpose import utils
import glob
import tifffile as tif
import click
from tqdm import tqdm

@click.command()
@click.argument('path')
def get_well_counts(path):
    data = {
        'well_id':[],
        'count':[]
    }
    df = pd.read_csv(path)
    df['well_id'] = df['image'].apply(lambda x: x.split('_')[-1].split('f')[0])
    wids = df['well_id'].unique().tolist()
    for w in wids:
        temp = df.loc[df['well_id']==w]
        data['well_id'].append(w)
        data['count'].append(temp['count'].sum())
    dt = pd.DataFrame(data=data)
    fname = os.path.join(os.path.dirname(path), 'well_count.csv')
    dt.to_csv(fname, index=False)