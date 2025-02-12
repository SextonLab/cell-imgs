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

from .gen_masks import get_masks

from .logger import logger
import click

ROUTE = ['left', 'up', 'right', 'down']
BINARY_MASK_FIRST = 'first_pass_binary'
BINARY_MASK_SECOND = 'second_pass_binary'

def get_pad_val(current):
    pv = 2
    if current>0 and current<=0.15:
        pv = 10
    elif current>15 and current<=0.50:
        pv = 5
    return pv

def apply_pad(images, outdir,right, left, top, bot):
    for f in images:
        img = tif.imread(f)
        dim, _ = img.shape
        outname = os.path.join(outdir, os.path.basename(f))
        img_out = np.pad(img, [(top,bot), (left,right)])
        img_out = img_out[bot:dim+bot,right:dim+right]
        tif.imwrite(outname, img_out)

def pad_image(img, how, ideal, pad_value=2):
    """
    adds empty pixels of pad_value to the side of how
    """
    dim, _ = img.shape
    if how=='left':
        temp = np.pad(img, [(0,0),(pad_value, 0)])
        temp = temp[:, :dim]
    elif how=='right':
        temp = np.pad(img, [(0,0),(0, pad_value)])
        temp = temp[:, pad_value:]
    elif how=='up':
        temp = np.pad(img, [(pad_value,0),(0, 0)])
        temp = temp[:dim, :]
    elif how=='down':
        temp = np.pad(img, [(0,pad_value),(0, 0)])
        temp = temp[pad_value:, :]
    return temp

def align_images(first_pass_images, second_pass_images, output_1, output_2, channel):
    """Aligns image in second pass to first pass

    Args:
        first_pass_images (str): path to first pass images
        second_pass_images (str): path to second pass images
        output_dir (str): path to save first pass binary masks (for comparison)
        output_dir (str): path to save second pass binary masks (for comparison)

    Returns:
        pd.DataFrame: DataFrame of images and corrections
    """
    # assert len(first_pass_images)==len(second_pass_images), "Different Number of Images between First and Second Pass..."
    if len(first_pass_images)==len(second_pass_images):
        a= len(first_pass_images)
        b = len(second_pass_images)
        if a < b:
            first_pass_images = first_pass_images[:a]
            second_pass_images = second_pass_images[:a]
        else:
            first_pass_images = first_pass_images[:b]
            second_pass_images = second_pass_images[:b]

    frist_pass_binary = os.path.join(output_1, BINARY_MASK_FIRST)
    second_pass_binary = os.path.join(output_2, BINARY_MASK_SECOND)
    
    # dataframe output corrections
    corrections = {
            "fname":[],
            "image_set":[],
            "right_correction":[],
            "left_correction":[],
            "top_correction":[],
            "bottom_correction":[],
            "starting_alignment":[],
            "ending alignment":[],
            "iterations":[],
        }
    failed_images = {
        "fname":[],
        'first_shape':[],
        'second_shape':[]
    }
    for fm, sm in zip(first_pass_images, second_pass_images):
        print(fm, sm)
        # Read images in and convert to binary mask
        first = tif.imread(fm)
        first[first>0]=1 
        second = tif.imread(sm)
        second[second>0]=1

        # get output filename 
        fname = os.path.basename(fm)
        if first.shape == second.shape:
            # get the alignment metric
            ideal = first.sum()
            currrent = (first*second).sum()
            past = currrent
            percent_diff = currrent/ideal

            corrections["fname"].append(fname)
            corrections['image_set'].append(fname.split(channel)[0])
            corrections['starting_alignment'].append(percent_diff)
            
            iters = 0
            right_cor = 0
            left_cor = 0
            top_cor = 0
            bot_cor = 0
            past_count = 0
            while(percent_diff<0.988 and past_count<=5):
                print("Currrent Iteration:", iters, f"Current %:{(percent_diff*100):.3f}% padding {get_pad_val(current=percent_diff)}")
                
                # if iters > 30:
                #     print("DID NOT CONVERGE AFTER: ", iters, " ITERATIONS STOPPING EARLY")
                    
                #     break

                # iterate over the routes thru the image
                for how in ROUTE:
                    pv = get_pad_val(current=currrent)
                    if how == 'left':
                        temp = pad_image(second, how, first, pad_value=pv)
                        new_percent = (first*temp).sum()
                        if new_percent>currrent:
                            second = temp # change the shape
                            percent_diff = new_percent/ideal
                            left_cor+=2
                            currrent = new_percent
                    elif how == 'right':
                        temp = pad_image(second, how, first, pad_value=pv)
                        new_percent = (first*temp).sum()
                        if new_percent>currrent:
                            second = temp # change the shape
                            percent_diff = new_percent/ideal
                            right_cor+=2
                            currrent = new_percent
                    elif how == 'up':
                        temp = pad_image(second, how, first, pad_value=pv)
                        new_percent = (first*temp).sum()
                        if new_percent>currrent:
                            second = temp # change the shape
                            percent_diff = new_percent/ideal
                            top_cor+=2
                            currrent = new_percent
                    elif how == 'down':
                        temp = pad_image(second, how, first, pad_value=pv)
                        new_percent = (first*temp).sum()
                        if new_percent>currrent:
                            second = temp # change the shape
                            percent_diff = new_percent/ideal
                            bot_cor+=2
                            currrent = new_percent
                if past == currrent:
                    past_count+=1
                else:
                    past = currrent
                iters+=1
            print("Completed with ", iters, f" with {(percent_diff*100):.3f}%")
            corrections['ending alignment'].append(percent_diff)
            corrections["right_correction"].append(right_cor)
            corrections['left_correction'].append(left_cor)
            corrections['top_correction'].append(top_cor)
            corrections['bottom_correction'].append(bot_cor)
            corrections['iterations'].append(iters)
            tif.imwrite(os.path.join(frist_pass_binary, fname), first)
            tif.imwrite(os.path.join(second_pass_binary,fname), temp)
        else:
            failed_images['fname'].append(fname)
            failed_images['first_shape'].append(first.shape)
            failed_images['second_shape'].append(second.shape)
    failures = pd.DataFrame(data=failed_images)
    failures.to_csv(os.path.join(output_2, 'failed_images.csv'), index=False)
    return pd.DataFrame(data=corrections)
    # return corrections

@click.command()
@click.argument('first_pass')
@click.argument('second_pass')
@click.option('--diam','-d', default=0.0, help='Cell diameter')
@click.option('--channel','-c', default='*', required=False, help='Channels to segement')
@click.option('--model', '-m',default='cyto3', required=False, help='Model')
@click.option('--no_edge', '-n', is_flag=True, default=False, required=False, help="Extra step to remove cells on the edge of masks")
@click.option('--flow', '-f', default=0.4, required=False, help='Flow threshold')
@click.option('--prob', '-p', default=0.0, required=False, help='Cell probability')
@click.option('--color', default='grey', required=False, help='rgb value of cyto and nucleus ex. rg: red ctyo, green nuc')
@click.option("--normalize", default=True, required=False, help='Use custom Normalize Features')
@click.option('--denoise_model', is_flag=True, default=False, required=False, help="Change model to denoise model")
def align_images(first_pass, second_pass, diam, channel, model, no_edge, flow, prob, color, normalize, denoise_model):
    """
    psudo code time
    take the image folder for both passes
    find masks
    align
    """
    if os.name =='nt':
        os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"
    assert os.path.exists(first_pass), "First Pass Image Directory Not Found"
    assert os.path.exists(second_pass), 'Second Pass Image Directory Not Found'
    
    assert  diam >=0.0, "Diameter must not be zero"
    assert  flow >= 0.0, "Flow threshold must not be zero"
    
    first_output = os.path.join(first_pass, 'outputs')
    second_output = os.path.join(second_pass, 'outputs')
    if not os.path.exists(first_output):
        os.mkdir(first_output)
    if not os.path.exists(second_output):
        os.mkdir(second_output)
    
    first_masks = os.path.join(first_pass, 'masks')
    second_masks = os.path.join(second_pass, 'masks')
    
    # first_stitched = os.path.join(first_pass, "Stitched",)
    # second_stitched = os.path.join(second_pass, "Stitched",)
    
    print('Created Directories')
    
    print(first_output)
    print(first_masks)
    # print(first_stitched)
    
    print(second_output)
    print(second_masks)
    # print(second_stitched)
    
    print("Generating First Pass Masks...\n")
    get_masks(first_pass, first_masks, diam=diam, channel=channel, 
                   model=model, no_edge=no_edge, flow=flow, prob=prob,
                   replace=False, count=False,
                   color=color, normalize=normalize, denoise_model=denoise_model)
    print("Generating Second Pass Masks...\n")
    get_masks(second_pass, second_masks, diam=diam, channel=channel, 
                   model=model, no_edge=no_edge, flow=flow, prob=prob,
                   replace=False, count=False,
                   color=color, normalize=normalize, denoise_model=denoise_model)
    
    print("Finding Alignment...")
    first_binary = os.path.join(first_output, BINARY_MASK_FIRST)
    second_binary = os.path.join(second_output, BINARY_MASK_SECOND)
    if not os.path.exists(first_binary):
        os.mkdir(first_binary)
    if not os.path.exists(second_binary):
        os.mkdir(second_binary)
    
    first_images = glob.glob(os.path.join(first_masks, f"*{channel}.tif")) # +glob.glob(os.path.join(first_masks, f"*{channel}.tiff"))
    second_images = glob.glob(os.path.join(second_masks, f"*{channel}.tif"))  # +glob.glob(os.path.join(second_masks, f"*{channel}.tiff"))
    correction_results = align_images(first_pass_images=first_images, second_pass_images=second_images, output_1=first_output, output_2=second_output, channel=channel)
    correction_results.to_csv(os.path.join(second_output, "corrrections_results.csv"), index=False)
    
    print("Applying Alignment...")
    dest_dir = os.path.join(second_output, "aligned_images")
    if  not os.path.exists(dest_dir):
        os.mkdir(dest_dir)
    rows = len(correction_results)
    for index, row in correction_results.iterrows():
        print(f"{index+1} of {rows}...")
        img_set = row['image_set']
        right = row['right_correction']
        left = row['left_correction']
        top = row['top_correction']
        bot = row['bottom_correction']
        images = glob.glob(os.path.join(second_pass, img_set+"*"))
        apply_pad(
            images, outdir=dest_dir, 
            right=right,
            left=left,
            top=top,
            bot=bot
            )
