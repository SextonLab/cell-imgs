from email.policy import default
import os

import click
import pandas as pd
import numpy as np

import re # REEEE
import glob

from progress.bar import Bar

import tifffile as tif
import matplotlib.pyplot as plt

from cellpose import models, utils

import javabridge
import bioformats

from datetime import date


def logger(path, args):
    print("Logfile saved to :",os.path.join(path,"log.txt"))
    with open(os.path.join(path,"log.txt"), "w") as f:
        today = str(date.today())+"\n"
        f.write(today)
        for k in args.keys():
            line = f"{k}:{args[k]}\n"
            f.write(line)

@click.command()
@click.argument('imgdir')
@click.argument('outdir')
@click.option('--diam','-d', default=0, help='Cell diameter')
@click.option('--channel','-c', default='*', required=False, help='Channels to segement')
@click.option('--model', '-m',default='cyto', required=False, help='Model')
@click.option('--no_edge', '-n', is_flag=True, default=False, required=False, help="Extra step to remove cells on the edge of masks")
@click.option('--flow', '-f', default=0.4, required=False, help='Flow threshold')
@click.option('--prob', '-p', default=0.0, required=False, help='Cell probability')
@click.option('--replace', '-r', is_flag=True, default=False, required=False, help='Replace existing masks')
@click.option('--count', is_flag=True, default=False, required=False, help='Create csv in mask folder of image cell counts')
# @click.option('--do_3d', is_flag=True, default=False, required=False, help='Do 3d segmentation') # DO 3D not working
def generate_masks(imgdir, outdir, diam, channel, model, no_edge, flow, prob, replace, count):  # , do_3d
    if os.name =='nt':
        os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"
    assert os.path.exists(imgdir), "Image Directory doesn't exist"
    # assert os.path.exists(outdir), "Mask directory doens't exist"
    if not os.path.exists(outdir):
        print(f"Creating output directory: {outdir}")
        os.mkdir(outdir)
    assert diam >= 0.0, "Diameter must be greater than zero"
    assert flow > 0.0, "Flow threshold must be greater than zero"
    if not os.path.exists(os.path.join(outdir, 'counts.csv')) & count:
        csv_path = os.path.join(outdir, 'count.csv')
        cell_count = {"image":[], "count":[]}
    # assert prob >= 0.0, "Cell probability must be greater or equal to zero"
    exten = os.path.join(imgdir, f"*{channel}.tif")
    exten2 = os.path.join(imgdir, f"*{channel}.tiff")
    files = glob.glob(exten) + glob.glob(exten2)
    model = models.CellposeModel(model_type=model, gpu=True)
    # imgs = [tif.imread(f) for f in files]
    nimg = len(files)
    assert nimg > 0, "no images found"
    
    channels = [[0,0]] # black and white images
    if diam <= 0:
        diam = None
    
    logger(outdir, locals())

    # split on '/' then take the last element as image name
    names = [f.split(os.sep)[-1] for f in files]
    for i, f in enumerate(files):
        fname = os.path.join(outdir,names[i])
        if not os.path.exists(fname) or replace:
            img = tif.imread(f)
            print(f'Processing Image: {i+1} of {len(names)}')
            mask, _, _ = model.eval(img, diameter=diam, channels=channels, flow_threshold=flow, cellprob_threshold=prob) # , do_3d=do_3d
            if no_edge:
                mask = utils.remove_edge_masks(mask)
            tif.imsave(fname, mask.astype('uint16'))
            if count:
                cell_count['image'].append(f)
                cell_count['count'].append(len(utils.outlines_list(mask)))
            del mask
        else:
            print(f'Skipping Image: {i+1} of {len(names)} [Already exists]')
    
    if count:
        pd.DataFrame(data=cell_count).to_csv(csv_path, index=False)


@click.command()
@click.argument('indir')
@click.argument('outdir')
@click.option('--channel','-c', default='*', help='Specific Channel')
def convert(indir, outdir, channel):
    if os.name =='nt':
        os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"
    assert os.path.exists(indir), "C01 Directory doesn't exist"
    assert os.path.exists(outdir), "TIF directory doens't exist"

    logger(outdir, locals())

    javabridge.start_vm(class_path=bioformats.JARS)
    path = os.path.join(indir, f'*{channel}.C01')
    files = glob.glob(path)
    bar = Bar('converting',max=len(files))
    for f in files:
        filename = os.path.join(outdir,re.search(r'(MFGTMP_\d+_\w+)', f, re.IGNORECASE).group(1)+'.tif')
        data = bioformats.ImageReader(f).read()
        # data = data.astype('float16')
        tif.imsave(filename, data=data)
        bar.next()
    bar.finish()
    javabridge.kill_vm()


def _get_axis(a,b,c):
    if a<b and a<c:
        return 0
    elif b<a and b<c:
        return 1
    else:
        return 2

@click.command()
@click.argument('indir')
@click.argument('outdir')
@click.option('--channel', "-c", default="*", required=False, help="Channel")
def max_project(indir, outdir, channel):
    assert os.path.exists(indir), "Zstack directory does not exist"
    if not os.path.exists(outdir):
        print(f"Missing output directory... creating directory {outdir}")
        os.mkdir(outdir)
    logger(outdir, locals())
    files = glob.glob(os.path.join(indir, f"{channel}.tif"))
    for f in files:
        fn = f.split(os.sep)[-1]
        print(fn)
        img = tif.imread(f)
        assert len(img.shape) == 3,f"Image {f} is not 3 dimensional"
        out = np.max(img, axis=_get_axis(img.shape))
        fname = os.path.join(outdir, fn)
        tif.imsave(fname, data=out)
        