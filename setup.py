from importlib_metadata import entry_points
from setuptools import setup

def readme():
    with open('README.md') as f:
        return f.read()

import os

if os.name =='nt':
    os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"

setup(
    name='cellimgs',
    version='0.60',
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
            'gen-masks=cellimgs.scripts:generate_masks',
            'convert-c01=cellimgs.scripts:convert',
            'max-proj=cellimgs.scripts:max_project',
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
