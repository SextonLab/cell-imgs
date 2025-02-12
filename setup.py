from importlib.metadata import entry_points
from setuptools import setup

def readme():
    with open('README.md') as f:
        return f.read()

import os

if os.name =='nt':
    os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"

setup(
    name='cellimgs',
    version='0.2.1',
    description='Set of scripts to use on cell images',
    long_description=readme(),
    classifiers=[
        'Development Status :: Number - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.8'
    ],
    keywords='microscopy cellpose tif C01',
    url='https://github.com/SextonLab/cell-imgs',
    author='bhalliga',
    author_email='bhalliga@med.umich.edu',
    license='MIT',
    packages=['cellimgs'],
    entry_points = {
        'console_scripts' : [
            'gen-masks=cellimgs.gen_masks:generate_masks',
            'normal-params=cellimgs.gen_masks:normalize_params',
            'convert-c01=cellimgs.convert:convert',
            'max-proj=cellimgs.max_proj:max_project',
            'cmerge=cellimgs.color_merge:merge_channel',
            'smashtif=cellimgs.tifsmasher:smash_tif',
            'align_images=cellimgs.align_all:align_images',
            'get-wellcounts=cellimgs.counts:get_well_counts',
            'masker=gui.main:main',
            ]
    },
    # install_requries=[
    #     'cellpose', 'Click', 'javabridge',
    #     'progress','tifffile','python-bioformats'
    # ],
    dependency_links=[],
    include_package_data=True,
    zip_safe=False,
    test_suite='nose.collector',
)
