# cellimgs
Group of python scripts and jupyter notebooks to convert C01 images to tifs, stack tifs, generate masks with cellpose and create max projections of tif stacks


## Installation

### Requirements

- Java 18 JDK https://www.oracle.com/java/technologies/downloads/
- Cuda and Cellpose [Follow the Cellpose install instructions](https://gitlab.umich.edu/sextonlab/documents/-/blob/master/environment/cellpose.md)
- C++ build tools, use relevant OS install instructions for more

### PIP install
```
git clone git@github.com:SextonLab/cell-imgs.git
cd cellimgs
pip install -r requirements.txt
pip install -e .
```

### Javabridge and Bioformats

Javabridge and Bioformats will need to be installed manually

- https://github.com/LeeKamentsky/python-javabridge
- https://github.com/CellProfiler/python-bioformats

Where bioformats will need to be installed without dependencies

```
pip install . --no-deps
```

### Windows

You'll need to download and install visual studio and the Microsoft C++ build tools
https://visualstudio.microsoft.com/visual-cpp-build-tools/

### MacOS

- WIP

## Included Scripts

### Generating Masks

`gen-masks imgdir/ maskdir/ --diam n --channel c1 --model cyto2`

By default diameters are generated per image and masks are generated on all images in the image directory

#### Options

- `--diam` or `-d` followed by a number to set to a fixed cell diameter
- `--channel` or `-c` followed by the channel idenifier, e.g. "d0", "C01"
- `--model` or `-m` followed by the model name from the model zoo default is "cyto"
- `--no_edge` or `-n` using this flag will add the step to remove masks around the edge of the image 
- `--flow` or `-f` followed by flow threshold, default 0.4
- `--prob` or `-p` followed by cell probablity threshold, default 0.0
- `--replace` or `-r` will replace all existing masks in the outdir instead of skipping them
- `--count` will create a `count.csv` in the outdir containing image name and the cell count of the image
- `--do_3d` will use 3D segmentation [DEPRECATED]

### Converting C01 images to TIFs

`convert-c01 imgdir/ outdir/`

Converts all C01 images in `imagedir` into tif files saved in `outdir`

#### Options

To convert a specific channel use option `--channel` or `-c` followed by a specify channel (i.e. C1, d2, etc.)

### Max Projection

`max-proj imagedir stackdir`

Generates max projections of tif stacks from `imagedir` and saves them to `stackdir`

#### Options

To convert a specific channel use option `--channel` or `-c` followed by channel (i.e. C1, d0, etc)

### Color Merging

`cmerge indir outdir red green blue`

Merges single channel tifs `indir` into multichannel RGB tifs `outdir` where `red`, `green` and `blue` correspond to image channel ID

## GUI Generate Masks

TODO: Add instructions and pictures for this bad boy

## Logging

A log file is created in the output directory whenever the a function is ran, it includes the current date and all used parameters

## Notebooks
In the notebook directory there are several similar workflows in jupyter notebooks including:

- ACAS Dose response scored data conversion
- Convert C01 files to TIF
- Generating Mask for 2D images
- Generating Masks for 3D images
