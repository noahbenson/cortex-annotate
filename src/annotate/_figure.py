# -*- coding: utf-8 -*-
################################################################################
# annotate/_figure.py

"""Core implementation code for the cortex-annotate tool's figure panel.

"""


# Imports ######################################################################

from functools import partial
from collections import defaultdict

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
    class LoadingContext:
        __slots__ = ('canvas',)
        _count = defaultdict(lambda:0)
        def __init__(self, canvas):
            self.canvas = canvas
        def __enter__(self):
            c = FigurePanel.LoadingContext._count
            idc = id(self.canvas)
            count = c[idc]
            if count == 0:
                FigurePanel.draw_loading(self.canvas)
            c[idc] = count + 1 
        def __exit__(self, type, value, traceback):
            c = FigurePanel.LoadingContext._count
            idc = id(self.canvas)
            count = c[idc]
            count -= 1
            c[idc] = count
            if count == 0:
                self.canvas.clear()
                del c[idc]
    def __init__(self, state, imagesize=256):
        self.state = state
        self.imagesize = imagesize
        # Make a multicanvas for the image [0] and the drawings [1].
        imsz = imagesize
        # Make a multicanvas.
        self.multicanvas = ipc.MultiCanvas(4, width=imsz, height=imsz)
        html = ipw.HTML(f"""
            <style> canvas {{
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
        self.fg_canvas = self.multicanvas[2]
        self.loading_canvas = self.multicanvas[3]
        # Draw the loading screen on the loading canvas and save it.
        self.draw_loading(self.loading_canvas)
        self.loading_canvas.save()
        self.loading_context = FigurePanel.LoadingContext(self.loading_canvas)
        # Set up our event observers for clicks/tabs/backspaces.
        self.multicanvas.on_key_down(self.on_key_press)
        self.multicanvas.on_mouse_down(self.on_mouse_click)
        # We start out with nothing drawn initially.
        self.image = None
        self.grid_shape = (1,1)
        self.foreground = None
        self.xlim = None
        self.ylim = None
        self.annotations = {}
        self.cursor_position = 'head'
        self.fixed_heads = None
        self.fixed_tails = None
        # Initialize our parent class.
        super().__init__([html, self.multicanvas])
    @classmethod
    def draw_loading(cls, dc):
        """Clears the draw canvas and draws the loading screen."""
        with ipc.hold_canvas():
            dc.clear()
            dc.fill_style = 'white'
            dc.global_alpha = 0.85
            dc.fill_rect(0, 0, dc.width, dc.height)
            dc.global_alpha = 1
            dc.font = "32px HelveticaNeue"
            dc.fill_style = 'black'
            dc.text_align = 'center'
            dc.fill_text("Loading...", 120, 120)
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
        elif image is not None:
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
        if redraw_image or redraw_annotations:
            self.loading_canvas.restore()
        with ipc.hold_canvas():
            if redraw_image:
                self.redraw_image()
            if redraw_annotations:
                self.redraw_annotations()
        # That's all that's required for now.
    def redraw_image(self):
        "Clears the image canvas and redraws the image."
        self.image_canvas.clear()
        if self.image is not None:
            w = self.image_canvas.width
            h = self.image_canvas.height
            self.image_canvas.draw_image(self.image, 0, 0, w, h)
    def redraw_annotations(self, foreground=True, background=True):
        "Clears the draw canvas and redraws all annotations."
        if background: self.draw_canvas.clear()
        if foreground: self.fg_canvas.clear()
        # We step through all (visible) annotations and draw them.
        for (ann_name, points) in self.annotations.items():
            # If ann_name is the foreground, we use None as the style tag.
            # We also draw on the foreground canvas instead of the background.
            if ann_name == self.foreground:
                if not foreground: continue
                styletag = None
                canvas = self.fg_canvas
                cursor = self.cursor_position
            else:
                if not background: continue
                styletag = ann_name
                canvas = self.draw_canvas
                cursor = None
            # If there are no points, we can skip.
            if points is None or len(points) == 0: continue
            # If this annotation isn't visible, we can skip it also.
            style = self.state.style(styletag)
            if not style['visible']: continue
            # Grab the fixed head and tail statuses.
            fh = self.fixed_head(ann_name) is not None
            ft = self.fixed_tail(ann_name) is not None
            # Okay, it needs to be drawn, so convert the figure points
            # into image coordinates.
            grid_points = self.figure_to_image(points)
            # For all the point-matrices here, we need to draw them.
            for pts in grid_points:
                self.state.draw_path(
                    styletag, pts, canvas,
                    fixed_head=fh, fixed_tail=ft, cursor=cursor)
    def change_annotations(self, annots,
                           fixed_heads=None, fixed_tails=None, redraw=True):
        """Changes the set of currently visible annotations.

        The argument `annots` must be a dictionary whose keys are the annotation
        names and whose values are the `N x 2` matrices of annotation points, in
        figure coordinates. The optional argument `fixed_heads` may be a
        `dict`-like object whose keys are annotation names and whose values are
        the `(x,y)` coordinates of the fixed head position for that particular
        annotation.
        """
        self.annotations = annots
        self.fixed_heads = fixed_heads
        self.fixed_tails = fixed_tails
        if redraw:
            self.redraw_annotations()
    def change_foreground(self, annot, redraw=True):
        """Changes the foreground annotation (the annotation being edited).

        `figure_panel.change_foreground(annot)` changes the current foreground
        annotation to the annotation with the name `annot`. The foreground
        annotation is the annotation that is currently being edited by the user.
        """
        self.foreground = annot
        if redraw:
            self.redraw_annotations()
    def toggle_cursor(self):
        """Toggles the cursor position between head/tail."""
        orig = self.cursor_position
        if orig == 'tail':
            self.cursor_position = 'head'
        else:
            self.cursor_position = 'tail'
        self.redraw_annotations(background=False)
        return self.cursor_position
    def fixed_head(self, annot):
        "Returns the 2D fixed-head point for the given annotation or `None`."
        if self.fixed_heads is None: return None
        pt = self.fixed_heads.get(self.foreground)
        if pt is None: return None
        if np.shape(pt) != 1: return None
        if len(pt) != 2: return None
        if np.isfinite(pt).sum() != 2: return None
        return pt
    def fixed_tail(self, annot):
        "Returns the 2D fixed-tail point for the given annotation or `None`."
        if self.fixed_tails is None: return None
        pt = self.fixed_tails.get(self.foreground)
        if pt is None: return None
        if np.shape(pt) != 1: return None
        if len(pt) != 2: return None
        if np.isfinite(pt).sum() != 2: return None
        return pt
    @staticmethod
    def _to_point_matrix(x, y=None):
        x = np.asarray(x) if y is None else np.array([[x,y]])
        if x.shape == (2,):
            x = x[None,:]
        elif x.shape != (1,2):
            raise ValueError(f"bad point shape: {x.shape}")
        return x
    def push_point(self, x, y=None, redraw=True):
        """Push the given image point onto the path at the cursor end.

        The point may be given as `x, y` or as a vector or 1 x 2 matrix. The
        point is added to the head or the tail depending on the cursor.
        """
        if self.foreground is None:
            # We got a click while not accepting clicks. Just ignore it.
            return None
        x = FigurePanel._to_point_matrix(x, y)
        # Add it on!
        points = self.annotations.get(self.foreground)
        if points is None:
            points = np.zeros((0,2), dtype=float)
        # We'll need to know the fixed head and tail conditions.
        fh = self.fixed_head(self.foreground)
        ft = self.fixed_tail(self.foreground)
        # How/where we add the point depends partly on whether there are points
        # and what the fixed head/tail state is.
        if len(points) == 0:
            # If this is the first point, we add the fixed points as well.
            fh = np.zeros((0,2),dtype=float) if fh is None else fh[None,:]
            ft = np.zeros((0,2),dtype=float) if ft is None else ft[None,:]
            points = np.vstack([fh, x, ft])
        else:
            if fh is None:
                fh = np.zeros((0,2), dtype=float)
            else:
                fh = points[[0]]
                points = points[1:]
            if ft is None:
                ft = np.zeros((0,2), dtype=float)
            else:
                ft = points[[-1]]
                points = points[:-1]
            # Where we add depends on the cursor position.
            if self.cursor_position == 'head':
                points = np.vstack([fh, x, points, ft])
            else:
                points = np.vstack([fh, points, x, ft])
        self.annotations[self.foreground] = points
        # Redraw the annotations.
        if redraw:
            self.redraw_annotations(background=False)
    def push_impoint(self, x, y=None, redraw=True):
        """Push the given image point onto the selected annotation.

        The point may be given as `x, y` or as a vector or 1 x 2 matrix. Image
        points are always converted into figure points before being appended to
        the annotation. The point is added to the head or the tail depending on
        the cursor.
        """
        x = FigurePanel._to_point_matrix(x, y)
        # Convert to a figure point.
        x = self.image_to_figure(x)
        return self.push_point(x, redraw=redraw)
    def pop_point(self, redraw=True):
        if self.foreground is None:
            # We got a backspace while not accepting edits; ignore it.
            return None
        # Get the current points.
        points = self.annotations.get(self.foreground)
        if points is None or len(points) == 0:
            # No points to pop!
            return None
        fh = self.fixed_head(self.foreground)
        ft = self.fixed_tail(self.foreground)
        if fh is None:
            fh = np.zeros((0,2), dtype=float)
        else:
            fh = points[[0]]
            points = points[1:]
        if ft is None:
            ft = np.zeros((0,2), dtype=float)
        else:
            ft = points[[-1]]
            points = points[:-1]
        if len(points) < 2:
            if len(points) == 0:
                import warnings
                warnings.warn(
                    "Current annotation contains only fixed points. This could"
                    " indicate a corrupted save file. Discarding this"
                    " annotation.")
            self.annotations[self.foreground] = None
        else:
            if self.cursor_position == 'head':
                points = points[1:]
            else:
                points = points[:-1]
            points = np.vstack([fh, points, ft])
            self.annotations[self.foreground] = points
        # Redraw the annotations.
        if redraw:
            self.redraw_annotations(background=False)
    def on_mouse_click(self, x, y):
        """This method is called when the mouse is clicked on the canvas."""
        # Add to the current contour.
        self.push_impoint(x, y)
    def on_key_press(self, key, shift_down, ctrl_down, meta_down):
        """This method a key is pressed."""
        key = key.lower()
        if key == 'tab':
            self.toggle_cursor()
        elif key == 'backspace':
            # Delete from head/tail, wherever the cursor is.
            self.pop_point()
        else:
            pass
