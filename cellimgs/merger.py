import enum
import random
import pandas as pd
import numpy as np
import re # REEEE
import glob
import tifffile


# CQ1 REGEX: (\w+)\/(W\d{4})(F\d{4})(T\d{4})(Z\d{3})(C\d)
# CV800 REGEX: .*\/(.*)_(.*)_(T[0-9]{4})(F.*)L01A[0-9]{2}(Z[0-9]{2})(C[0-9]{2})\.tif


def merge_images(channels, output, sub=1):
    """
    Merges zstacks of images
    params:
        channels - dict {str: [str]} final image name : [filenames]
    returns True
    """
    for key in channels.keys():
        name = os.path.join(output, key+'.tif')
        # name = f'{output}/{key}.tif'
        with tifffile.TiffWriter(name, bigtiff=True) as stack:
            for i, filename in enumerate(channels[key]):
                if i%sub==0:
                    stack.save(
                        tifffile.imread(filename),
                        photometric='minisblack', 
                        contiguous=True
                    )


def get_regex(scope):
    # well_reg = r'.*_([A-P][0-9]{2})_.*'
    if scope == 'CV8000':
        return r'.*_([A-P][0-9]{2})_.*'
    elif scope == 'CQ1':
        return r'(W\d{4})F\d{4}T\d{4}Z\d{3}C\d\.tif'
    else:
        return r'.*_([A-P][0-9]{2})_.*'

def make_wells(files, scope):
    """
    sorts images by well_id
    """
    
    well_reg = get_regex(scope=scope)

    # # well_reg = r'.*_([A-P][0-9]{2})_.*'
    # if scope == 'CV8000':
    #     well_reg = r'.*_([A-P][0-9]{2})_.*'
    # elif scope == 'CQ1':
    #     reg =  r'(W\d{4})F\d{4}T\d{4}Z\d{3}C\d\.tif'
    # else:
    #     well_reg = r'.*_([A-P][0-9]{2})_.*'
    
    wells = {}
    for f in files:
        entry = re.search(well_reg, f)
        if entry is None:
            print(f'BAD MATCH ON: {f}\nUsing REGEX: {well_reg}')
        key = entry.group(1)
        if key in wells.keys():
            wells[key].append(f)
        else:
            wells[key] = [f]
    return wells

def field_reg(field, scope):
    if scope == 'CV8000':
        if field:
            return r'.*_T[0-9]{4}(F[0-9]{3}).*'
        else:
            return r'.*_(T[0-9]{4})F[0-9]{3}.*'
    elif scope == 'CQ1':
        return r'W\d{4}(F\d{4})T\d{4}Z\d{3}C\d\.tif'
    else:
        print("you're not supposed to be here mortal")
        return r'.*_T[0-9]{4}(F[0-9]{3}).*'

def make_fields(wells, field, scope):
    """
    sorts images in wells to images in well_id_field_id
    """
    f_reg = field_reg(field=field, scope=scope)
    fields = {} # keys: well_id_field_id
    for w in wells.keys():
        for a in wells[w]:
            wl = re.search(f_reg, a)            
            fk = f'{w}_{wl.group(1)}' # well_id_field_id
            if fk in fields.keys():
                fields[fk].append(a)
            else:
                fields[fk] = [a]
    return fields

def make_channels(fields):
    """
    sorts well_id_field_id to  well_id_field_id_channelNum (1-3) typically
    """
    c_reg = r'.*(C[0-9]{2})\.tif'
    channels = {}
    for f in fields.keys():
        for i in fields[f]:
            c = re.search(c_reg, i)
            ck = f'{f}_{c.group(1)}'
            if ck in channels.keys():
                channels[ck].append(i)
            else:
                channels[ck] = [i]
    return channels

def sort_images(files, field, scope):
    """
    sorts images into final images in a dict
    params:
        files - list of filenames
    return:
        channels - dict of image names and list of filenames
    """
    w = make_wells(files,scope=scope)
    f = make_fields(w, field=field, scope=scope)
    c = make_channels(f)
    return c

def order_images(channels):
    """
    makes sure that all zstacks are in the correct order
    """
    for key in channels.keys():
        channels[key] = sorted(channels[key], key=lambda x: int("".join([i for i in x if i.isdigit()])))

# only works for cq1 as of 2021/05/03
# make_fields(wells, field, scope)
def merge_channels(files, on_field, scope, outdir=None):
    fields = make_fields(wells=make_wells(files=files, scope='CQ1'), field=True, scope='CQ1')

    for k in fields.keys():
        if outdir is not None:
            filename = f'{outdir}/{k}.tif'
        else:
            filename = f'{k}.tif'
        img = np.ones((len(fields[k]), 2160, 2560)) # assumes shape of (c, 2160, 2560)
        for i,j in enumerate(fields[k]):
            img[i] = tifffile.imread(j)
        tifffile.imwrite(filename, img)
    
def split_wellid(well):
    """
    splits wellid into row and column
    """
    row, column, _ = re.split(r'(\d+)', well)
    return row, column

def make_table(files, scope='CV8000'):
    """
    creates dataframe of data
    PARAMS:
        REG - regex fo CV8000 files
        files - list of files
    RETURNS:
        df - dataframe of file metadata
    """
    if scope =='CV8000':
        reg = r'.*[\/|\\]*(?P<plate_id>.*)_(?P<well_id>.*)_T(?P<timepoint>[0-9]{4})F(?P<field_id>[0-9]{3})L(?P<location>[0-9]+)A[0-9]{2}Z(?P<zstack>[0-9]+)C(?P<channel>[0-9]{2})\.tif'
    else:
        reg = r'[\/|\\]*(?P<plate_id>\w+)[\/|\\](?P<well_id>W\d{4})F(?P<field_id>\d{4})T(?P<timepoint>\d{4})Z(?P<zstack>\d{3})C(?P<channel>\d)'
    
    data = {
        'path':[],
        'plate_id':[],
        'well_id':[],
        'row_id':[],
        'column_id':[],
        'timepoint':[],
        'field_id':[],
        'location':[],
        'zstack':[],
        'channel':[]
    }
    for f in files:
        row = re.search(reg, f)
        if row is not None:
            meta = row.groupdict()
            data['path'].append(f)
            row, column = split_wellid(meta['well_id'])
            
            data['row_id'].append(row)
            data['column_id'].append(column)

            for k in meta.keys():
                data[k].append(meta[k])
    
    # if location is not used set all values to zero
    if len(data['location'])==0:
        data['location'] = [0 for x in range(len(data['path']))]
    
    return pd.DataFrame(data=data)


def sort_df(df, well, channel, field, on_location=False):
    """
    makes a list of files to smash into stack tif
    PARAMS:
        df - dataframe of image and metadata
        well - well to smash
        channel - channel to smash
        field - field to smash
        on_field - optional: bool for using field as stack identifier
    RETURN:
        files - list of tifs to become a TIF
    """
    if on_location:
        return df.loc[(df['well_id']==well)&(df['channel']==channel)&(df['location']==field), 'path'].to_list()
    else:
        return df.loc[(df['well_id']==well)&(df['channel']==channel)&(df['field_id']==field), 'path'].to_list()

def smash_tif(files, filename, bar):
    """
    TIF SMASH
    PARAMS TO SMASH:
        files - THINGS TO SMASH
        filename - NAME OF SMASHED THING
    RETURN:
        SMASHED TIF
    """
    a,b = tifffile.imread(files[0]).shape
    img = np.ones((len(files),a,b))
    for i,j in enumerate(files):
        img[i] = tifffile.imread(j)
        bar.value = float(i/len(files)*100)
    tifffile.imwrite(filename, img )

def smash(files, filename):
    """
    TIF SMASH - for use with CLI
    PRE-SMASH:
        files - files of stack
        filename - name of stack
    POST-SMASH:
        TIF STACK
    """
    a, b = tifffile.imread(files[0]).shape
    img = np.ones((len(files), a,b))
    for i, j in enumerate(files):
        img[i] =  tifffile.imread(j)
    tifffile.imwrite(filename, img)