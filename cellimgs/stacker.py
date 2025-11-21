from email.policy import default
import os
import re # REEEEEE
from glob import glob

from .merger import make_table, sort_df, smash
from .logger import logger
import click
from tqdm import tqdm
import tifffile as tif
import numpy as np
import pandas as pd

SCOPES = ['CV8000', 'CQ1']
ON = ['z', 't', 'l']
REG = {
    'CV8000':r".*_([A-Z]\d{2})_(T[0-9]{4})(F\d{3})(L\d{2})(A\d{2})(Z\d{2})(C\d{2})",
    'CQ1':r"(W\d{4})(F\d{4})(T\d{4})(Z\d{3})(C\d)"
}
TARGET = {
    'z':'zstack',
    't':'timepoint',
    'l':'loc'
}

def sort(df, well, channel, field, on='z'):
    if on == 't': # timepoint
        return df.loc[(df['well_id']==well) & (df['channel']==channel) & (df['field_id']==field), 'path'].tolist()
        

def make_df(files, scope):
    reg = REG[scope]
    if scope == 'CV8000':
        data = {
            'wellID':[],
            'timepoint':[],
            'fieldID':[],
            'loc':[],
            'acq':[],
            'zstack':[],
            'channel':[],
            'fname':[]
        }
        for f in files:
            _, well, timepoint, field, loc, acq, zstack, chan, _ = re.split(reg, os.path.basename(f))
            data['wellID'].append(well)
            data['timepoint'].append(timepoint)
            data['fieldID'].append(field)
            data['loc'].append(loc)
            data['acq'].append(acq)
            data['zstack'].append(zstack)
            data['channel'].append(chan)
            data['fname'].append(f)

    elif scope == 'CQ1':
        data = {
            'wellID':[],
            'timepoint':[],
            'fieldID':[],
            # 'loc':[],
            # 'acq':[],
            'zstack':[],
            'channel':[],
            'fname':[]
        } 
        for f in files:
            _, well, field, timepoint, zstack, chan, _ = re.split(reg, os.path.basename(f))
            data['wellID'].append(well)
            data['timepoint'].append(timepoint)
            data['fieldID'].append(field)
            # data['loc'].append(loc)
            # data['acq'].append(acq)
            data['zstack'].append(zstack)
            data['channel'].append(chan)
            data['fname'].append(f)

    else:
        print("You broke something")
        data = {}

    return pd.DataFrame(data=data)

def order_files(df, wid, fid, chan, on='z'):
    return df.loc[(df['wellID']==wid)&(df['fieldID']==fid)&(df['channel']==chan)].sort_values(TARGET[on])['fname'].tolist()

def stack_imgs(files, wid, fid, chan, dest):
    a, b = tif.imread(files[0]).shape
    img = np.zeros((len(files), a,b))
    for i, f in enumerate(files):
        img[i, :, :] += tif.imread(f)
    fname = os.path.join(dest, f"{wid}_{fid}_{chan}.tif")
    tif.imwrite(fname, img)
    
@click.command()
@click.argument('src')
@click.argument('dest')
@click.option('--scope', '-s', required=False, default='CV8000', help=f'Which scope options:{SCOPES}')
@click.option('--on', '-o', required=False, default='z', help=f"Which part of the image name to stack on: {ON}")
@click.option('--bulk', '-b',  default=False, help='Find sub directories')
def stack_tif(src, dest, scope, on, bulk):
    if os.name == 'nt':
        os.environ['KMP_DUPLICATE_LIB_OK']="TRUE"
    assert os.path.exists(src), "Source Directory doesn't exist"
    if not os.path.exists(dest):
        print(f"Creating destination directory: {dest}")
        os.mkdir(dest)
    assert scope in SCOPES, "Unknown Scope"

    if bulk:
        files = glob(os.path.join(src, '*', '*.tif')) + glob(os.path.join(src, '*', '*.tiff'))
    else:
        files = glob(os.path.join(src,  'PECCU*.tif')) + glob(os.path.join(src, '*.tiff'))     
    
    logger(dest, locals())
    
    df = make_df(files=files, scope=scope)
    for wid in tqdm(df['wellID'].unique()):
        for fid in df['fieldID'].unique():
            for chan in df['channel'].unique():
                too_stack = order_files(df, wid, fid, chan, on=on)
                stack_imgs(too_stack, wid, fid, chan, dest)
                

# if __name__ == '__main__':
#     stack_tif()