# -*- coding: utf-8 -*-
################################################################################
# cortexannotate/_util.py
#
# Utility types and functions used in the annotation toolkit.


# Dependencies #################################################################

import os
from functools import partial

import numpy as np
import scipy as sp
import matplotlib.pyplot as plt


# Lazy Dict Type ###############################################################
# The Lazy Dict type (ldict) is a mutable dictionary whose values may be delay
# objects (also defined here). Delay objects are automatically undelayed before
# they are revealed to the user.
# These ldict objects probably don't behave correctly with respect to dictionary
# equality, but that is a fairly small issue for a mutable dictionary.

class delay:
    """A delayed computation type.
    
    A `delay` object can be initialized exactly like a `partial` object (from
    the `functools` package) except that all of the arguments to the delayed
    function must be provided at initialization, unlike with a `partial`. The
    computation can be run and its result accessed by calling the `delay` object
    without arguments.
    
    Unlike a `partial` object, a `delay` object saves its result after it has
    been computed once and does not recall (or even keey a reference to) the
    original function after this point.
    """
    __slots__ = ('_partial', '_result')
    def __setattr__(self, k, v):
        raise TypeError(f"{type(self)} is immutable")
    def __call__(self):
        if self._partial is not None:
            object.__setattr__(self, '_result', self._partial())
            object.__setattr__(self, '_partial', None)
        return self._result
    def __init__(self, f, *args, **kw):
        object.__setattr__(self, '_partial', partial(f, *args, **kw))
        object.__setattr__(self, '_result', None)
    @property
    def is_cached(self):
        "Returns `True` if the delay object has been cached, otherwise `False`."
        return (self._partial is None)
def undelay(obj):
    """Returns the argument except for delays whose result values are returned.
    
    `undelay(d)` for a `delay` object `d` returns `d()`.
    
    `undelay(x)` for any object `x` that is not a `delay` object returns `x`.
    """
    return obj() if type(obj) is delay else obj
class ldict_setlike:
    __slots__ = ('_setlike',)
    @classmethod
    def _undelay(cls, ld):
        raise TypeError(f'{cls} has no _undelay method')
    @classmethod
    def _to_setlike(cls):
        raise TypeError(f'{cls} has no _to_setlike method')
    def __setattr__(self, k, v):
        raise TypeError(f"{type(self)} is immutable")
    def __getitem__(self, k):
        raise TypeError(f"{type(self)} is not subscriptable") 
    def __init__(self, ld):
        object.__setattr__(self, '_setlike', self._to_setlike(ld))
    def __iter__(self):
        return map(self._undelay, iter(self._setlike))
    def __reversed__(self, k):
        return map(self._undelay, reversed(self._setlike))
    def __len__(self):
        return len(self._setlike)
    def __contains__(self, k):
        return (k in self._setlike) or (k in iter(self))
    def __eq__(self, other):
        if type(self) is not type(other): return False
        if len(self) != len(other): return False
        return all(x in other for x in iter(self))
class ldict_items(ldict_setlike):
    @classmethod
    def _undelay(cls, el):
        return (el[0], undelay(el[1]))
    @classmethod
    def _to_setlike(cls, ld):
        return dict.items(ld)
    __slots__ = ()
class ldict_values(ldict_setlike):
    @classmethod
    def _undelay(cls, el):
        return undelay(el)
    @classmethod
    def _to_setlike(cls, ld):
        return dict.values(ld)
    __slots__ = ()
class ldict(dict):
    """A lazy dictionary type.
    
    `ldict` is identical to `dict` except that it calls `undelay` on all values
    before returning them, so it can be used to store lazy computations.
    """
    __slots__ = ()
    def __getitem__(self, k):
        v = dict.__getitem__(self, k)
        return undelay(v)
    def get(self, k, df=None):
        if k in self:
            return self[k]
        else:
            return df
    def items(self):
        return ldict_items(self)
    def values(self):
        return ldict_values(self)
    def __eq__(self, other):
        if not isinstance(other, dict): return False
        if len(self) != len(other): return False
        if self.keys() != other.keys(): return False
        other_items = other.items()
        self_items = ldict_items(self)
        return all(kv in other_items for kv in self_items)
    def is_lazy(self, k):
        """Returns `True` if the given key is an uncached lazy value."""
        v = dict.__getitem__(self, k)
        return (not v.is_cached) if type(v) is delay else False


# The Watershed Segmentation Approach ##########################################
# The segmentation algorithm used here was pointed out by Chris Luengo on the
# image processing Stack Exchange (https://dsp.stackexchange.com/users/33605),
# see here for the original implementation:
# https://dsp.stackexchange.com/a/89106/68937

def contours_image(contours, mesh=None, dpi=512, lw=0.1):
    """Given a mesh and a set of traces, return an image of the traces.
    
    The purpose of this function is to produce an image that can be mapped back
    to the original mesh but that contains the traces drawn in white on a black
    background for use with the watershed algorithm.
    """
    (fig,ax) = plt.subplots(1,1, figsize=(1,1), dpi=dpi)
    fig.subplots_adjust(0,0,1,1,0,0)
    canvas = fig.canvas
    for xy in contours:
        ax.plot(xy[:,0], xy[:,1], 'k-', lw=lw)
    if mesh is not None:
        (xmin,ymin) = np.min(mesh.coordinates, axis=1)
        (xmax,ymax) = np.max(mesh.coordinates, axis=1)
        ax.set_xlim((xmin,xmax))
        ax.set_ylim((ymin,ymax))
    ax.axis('off')
    canvas.draw()  # Draw the canvas, cache the renderer
    image_flat = np.frombuffer(canvas.tostring_rgb(), dtype='uint8')
    image = image_flat.reshape(*reversed(canvas.get_width_height()), 3)
    image = 255 - np.mean(image, -1)
    plt.close(fig)
    return image
def watershed_image(im, fill_contours=True, max_depth=2):
    """Applies the watershed algorithm to an image of contours.
    
    The contours image can be generated with the `contours_image` function. See
    the `watershed_contours` function for information on applying the watershed
    algorithm to the contours themselves.
    """
    import sys, contextlib
    if 'diplib' not in sys.modules:
        # Suppress stdout first time we import.
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                import diplib as dip
    else:
        import diplib as dip
    img = ~dip.Image(im)
    dt = dip.EuclideanDistanceTransform(img, border="object")
    # Ensure image border is a single local maximum
    dip.SetBorder(dt, value=dip.Maximum(dt)[0], sizes=2)
    # Watershed (inverted); the use of maxSize=0 is equivalent to applying
    # an H-Minima transform before applying the watershed. This is the default
    seg = dip.Watershed(
        dt,
        mask=img,
        connectivity=2,
        maxDepth=max_depth,
        flags={"high first", "correct"})
    lbls = np.array(dip.Label(~seg))
    # If requested, we fill in the contours somewhat arbitrarily with values
    # from the neighboring pixels.
    if fill_contours:
        lls = np.unique(lbls)
        bg = lbls[0,0]
        lls = [ll for ll in lls if ll != 0 and ll != bg]
        layers = [lbls == ll for ll in lls]
        # Fill in the 0 labels by dilating the inner regions.
        mask = (lbls == 0)
        while mask.any():
            layers = [sp.ndimage.binary_dilation(layer) for layer in layers]
            layernums = [layer[mask]*ll for (ll,layer) in zip(lls, layers)]
            lbls[mask] = np.max(layernums, axis=0)
            mask = (lbls == 0)
        # Extract the background and make it 0.
        if bg == 1:
            lbls -= 1
        elif bg == lls[-1]:
            lbls[lbls == bg] = 0
        else:
            ii = (lbls == bg)
            lbls[lbls > bg] -= 1
            lbls[ii] = 0
    return lbls
def watershed_contours(contours, mesh=None,
                       dpi=512, lw=0.1,
                       fill_contours=True, max_depth=2):
    """Apply the watershed algorithm to the contours and return mesh labels.
    
    This function uses the watershed algorithm, as implemented in the diplib
    package in order to segment a set of imprecisely-drawn contours. The
    return value is the labels of the mesh vertices. These labels are
    arbitrarily enumerated with the exception that the background is always 0.
    """
    im = contours_image(contours, mesh=mesh, dpi=dpi, lw=lw).astype(bool)
    lbls = watershed_image(im, fill_contours=fill_contours, max_depth=max_depth)
    # If there is no mesh, just return this labels image.
    if mesh is None:
        return lbls
    # Otherwise, invert these back to the mesh vertices.
    (xmin,ymin) = np.min(mesh.coordinates, axis=1)
    (xmax,ymax) = np.max(mesh.coordinates, axis=1)
    xpx = (mesh.coordinates[0] - xmin) / (xmax - xmin) * (dpi - 1)
    ypx = (ymax - mesh.coordinates[1]) / (ymax - ymin) * (dpi - 1)
    cs = np.round(xpx).astype(int)
    rs = np.round(ypx).astype(int)
    return lbls[rs, cs]


# Word Wrapping ################################################################
def wrap(message, wrap=60):
    """Word-wraps a string and returns the wrapped string.

    This function is a simple wrapper around the `textwrap.wrap` function. If
    the optional argument `wrap` is `None` or `False`, then no wrapping is
    performed and the message is returned as-is. Otherwise, the message is
    wrapped with the width given by `wrap`.
    """
    import textwrap
    if wrap:
        if wrap is True or wrap is Ellipsis:
            wrap = 60
        message = textwrap.wrap(message, width=wrap)
        message = "\n".join(message)
    return message
