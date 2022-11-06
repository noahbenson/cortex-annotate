# -*- coding: utf-8 -*-
################################################################################
# annotate/_figure.py

"""Core implementation code for the cortex-annotate tool's figure panel.

"""


# Imports ######################################################################

from functools import partial

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import ipycanvas as ipc
import ipywidgets as ipw

from ._util import (delay, ldict)
from ._config import Config


# The Figure Panel #############################################################

class FigurePanel(ipw.HBox):
    """The canvas that manages the display of figures and annotations.

    The `FigurePanel` is an subclass of `ipycanvas.MultiCanvas` that is designed
    to manage the display of images and annotations for the `AnnotationTool` in
    `_core.py`.
    """
    def __init__(self, state, imagesize=256):
        self.state = state
        self.imagesize = imagesize
        # Make a multicanvas for the image [0] and the drawings [1].
        imsz = imagesize
        # Make a multicanvas.
        self.multicanvas = ipc.MultiCanvas(2, width=imsz, height=imsz)
        html = ipw.HTML(f"""
            <style> canvas {{
                border-color: #f0f0f0;
                border-style: solid;
                border-width: 1px;
                cursor: crosshair !important;
            }} </style>
            <div class="cortex-annotate-StylePanel-hline"></div>
        """)
        # We always seem to need to explicitly set the layout size in pixels.
        imsz = f"{imsz}px"
        self.multicanvas.layout.width = imsz
        self.multicanvas.layout.height = imsz
        # Separate out the two canvases.
        self.image_canvas = self.multicanvas[0]
        self.draw_canvas = self.multicanvas[1]
        # We start out with nothing drawn initially.
        self.image = None
        self.grid_shape = (1,1)
        self.foreground = None
        self.xlim = None
        self.ylim = None
        self.annotations = {}
        # Initialize our parent class.
        super().__init__([html, self.multicanvas])
        # Temporary hack.
        with open("/cache/test512.png", "rb") as f:
            self.image = ipw.Image(value=f.read(), format="png")
    def resize_canvas(self, new_size):
        """Resizes the figure canvas so that images appear at the given size.

        `figure_panel.resize_canvas(new_size)` results in the canvas being
        resized to match the new image-size. Note that this does not resize the
        canvas to have a width of `new_size` but rather resizes it so that each
        image in the grid has a width of `new_size`.

        The `reside_canvas` method triggers a redraw because the resizing of the
        canvas clears it.
        """
        # The canvas size is a product of the image size and the grid shape.
        canvas_width = new_size * self.grid_shape[1]
        canvas_height = new_size * self.grid_shape[0]
        # First resize the canvas (this clears it).
        self.multicanvas.width = canvas_width
        self.multicanvas.height = canvas_height
        # Then we also resize the layout component.
        self.multicanvas.layout.width = f"{canvas_width}px"
        self.multicanvas.layout.height = f"{canvas_height}px"
        # Note the new image size.
        self.imagesize = new_size
        # Finally, because the canvas was cleared upon resize, we redraw it.
        self.redraw_canvas()
    def cellshape(self):
        "Returns the `(width, height)` in pixels of one cell of the image grid."
        imwidth = self.imagesize
        (figw, figh) = self.state.config.display.figsize
        imheight = imwidth * figh / figw
        return (imwidth, imheight)
    def figure_to_image(self, points):
        "Converts the `N x 2` matrix of figure points into image coordinates."
        points = np.asarray(points)
        if len(points.shape) == 1:
            return self.figure_to_image([points])[0]
        (imwidth, imheight) = self.cellshape()
        xlim = (0, imwidth) if self.xlim is None else self.xlim
        ylim = (0, imheight) if self.ylim is None else self.ylim
        # First, make the basic conversion.
        points = points - [xlim[0], ylim[0]]
        points *= [imwidth / (xlim[1] - xlim[0]),
                   imheight / (ylim[1] - ylim[0])]
        # Then invert the y-axis
        points[:,1] = imheight - points[:,1]
        # And build up the point matrices for each grid element.
        (rows,cols) = self.grid_shape
        return [points + [ii*imwidth, jj*imheight]
                for ii in range(cols)
                for jj in range(rows)]
    def image_to_figure(self, points):
        "Converts the `N x 2` matrix of image points into figure coordinates."
        points = np.asarray(points)
        if len(points.shape) == 1:
            return self.figure_to_image([points])[0]
        # First off, we want to apply the grid mod to make sure that any
        (imwidth, imheight) = self.cellshape()
        points = points % [imwidth, imheight]
        # Get the figure limits.
        xlim = (0, imwidth) if self.xlim is None else self.xlim
        ylim = (0, imheight) if self.ylim is None else self.ylim
        # We need to invert the y axis.
        points[:,1] = imheight - points[:,1]
        # Now, make the conversion.
        points *= [(xlim[1] - xlim[0]) / imwidth,
                   (ylim[1] - ylim[0]) / imheight]
        points += [xlim[0], ylim[0]]
        return points
    def redraw_canvas(self,
                      image=Ellipsis, grid_shape=None, xlim=None, ylim=None,
                      redraw_image=True, redraw_annotations=True):
        """Redraws the entire canvas.

        `figure_panel.redraw_canvas()` redraws the canvas as-is.

        `figure_panel.redraw_canvas(new_image)` redraws the canvas with the new
        image; this requires that the grid has not changed.

        `figre_panel.redraw_canvas(new_image, new_grid_shape)` redraws the
        canvas with the given new image and new grid shape.

        The optional arguments `redraw_image` and `redraw_annotations` both
        default to `True`. They can be set to `False` to skip the redrawing of
        one or the other layer of the canvas.
        """
        # If no new image was passed, we redraw the one currently here.
        if image is Ellipsis:
            image = self.image
        elif image is None:
            pass
        else:
            self.image = image
        if xlim is not None:
            self.xlim = xlim
        if ylim is not None:
            self.ylim = ylim
        # Handle potential changes to the grid.
        if grid_shape is None:
            grid_shape = self.grid_shape
        elif grid_shape != self.grid_shape:
            self.grid_shape = grid_shape
            # We need to resize the image, which will itself trigger a redraw
            # request, for everything, so we want to end here by resizing.
            self.resize_canvas(self.imagesize)
            return
        # Redraw the image (assuming one was given).
        w = self.multicanvas.width
        h = self.multicanvas.height
        if redraw_image:
            self.image_canvas.clear()
            if image is not None:
                self.image_canvas.draw_image(image, 0, 0, w, h)
        if redraw_annotations:
            self.draw_canvas.clear()
            # We step through all (visible) annotations and draw them.
            for (ann_name, points) in self.annotations.items():
                # Skip the foreground for now.
                if ann_name == self.foreground: continue
                if len(points) == 0: continue
                # If this annotation isn't visible, we can skip it also.
                style = self.state.style(ann_name)
                if not style['visible']: continue
                # Okay, it needs to be drawn, so convert the figure points into
                # image coordinates.
                grid_points = self.figure_to_image(points)
                # For all the point-matrices here, we need to draw them.
                for pts in grid_points:
                    self.state.draw_path(ann_name, pts, self.draw_canvas)
        # That's all that's required for now.
    def change_foreground(self, annot):
        """Changes the foreground annotation (the annotation being edited).

        `figure_panel.change_foreground(annot)` changes the current foreground
        annotation to the annotation with the name `annot`. The foreground
        annotation is the annotation that is currently being edited by the user.
        """
        self.foreground = annot
        self.redraw_canvas(redraw_image=False)
