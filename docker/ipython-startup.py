# -*- coding: utf-8 -*-
################################################################################
# docker/ipython-startup.py
#
# IPython startup script. This code is run when the Jupyter kernel has started,
# so any basic initialization code should go here.


# Set up the PYTHONPATH ########################################################

# This code ensures that /condig/src, if it exists, is on the python path.
def _init_pythonpath():
    import sys, os
    src_path = '/src'
    if src_path not in sys.path and os.path.isdir(src_path):
        sys.path.append(src_path)
    return None
try:
    _init_pythonpath()
except Exception as e:
    from warnings import warn
    warn(f"error initializing PYTHONPATH: {e}")
