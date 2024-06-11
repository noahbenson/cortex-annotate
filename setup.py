#! /usr/bin/env python

import os
from setuptools import (setup, Extension)

setup(
    name='cortexannotate',
    version='0.1.4',
    description='Toolbox for flexible annotation of the cortical surface by many raters',
    keywords='neuroscience cortex annotation',
    author='Noah C. Benson',
    author_email='nben@uw.edu',
    maintainer_email='nben@uw.edu',
    long_description='''
        See the README.md file at the github repository for this package:
        https://github.com/noahbenson/cortex-annotate
    ''',
    package_dir={'': 'src'},
    url='https://github.com/noahbenson/cortex-annotate',
    download_url='https://github.com/noahbenson/cortex-annotate',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: Information Analysis',
        'Topic :: Scientific/Engineering :: Medical Science Apps.',
        'Operating System :: POSIX',
        'Operating System :: Unix',
        'Operating System :: MacOS'],
    install_requires=[
        'neuropythy >= 0.12.13',
        'pandas >= 2.2.2',
        'pyyaml >= 6.0.1',
        'ipywidgets >= 8.1.2',
        'ipycanvas >= 0.13.2',
        'imageio >= 2.26.0',
        'pandas >= 1.4.1'],
    packages=['cortexannotate'])
