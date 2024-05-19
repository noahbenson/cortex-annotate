# -*- coding: utf-8 -*-
################################################################################
# cortexannotate/__init__.py
#
# Initialization code for the annotate toolkit.
# The annotate toolkit primarily uses the neuropythy library
# (github.com/noahbenson/neuropythy) to facilitate the annotation of cortical
# surfaces by hand using a combination of Jupyter notebooks, Git/GitHub, and
# (optionally) Docker. 

'''
The cortexannotate package facilitates the manual annotation of the human cortex.

These tools are intended to be run using a Docker container; for information
on how to use these tools, see the README.md file in the github repository
noahbenson/cortex-annotate.
'''

# Imports ######################################################################

from ._util import (delay, ldict, watershed_contours)
from ._core import AnnotationTool
from .prfs  import annotate_prfs


# Meta-Data ####################################################################

__version__ = '0.1.3'
#__all__ = ("AnnotationTool",)


