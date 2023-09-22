from email.policy import default
import os

import numpy as np
import pandas as pd

import tifffile as tif

from cellpose import models, utils

from datetime import date

def logger(path, args):
    print("Logfile saved to :",os.path.join(path,"log.txt"))

    with open(os.path.join(path,"log.txt"), "w") as f:
        today = str(date.today())+"\n"
        f.write(today)
        for k in args.keys():
            line = f"{k}:{args[k]}\n"
            f.write(line)