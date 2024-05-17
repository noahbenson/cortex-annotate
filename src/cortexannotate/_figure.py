# -*- coding: utf-8 -*-
################################################################################
# cortexannotate/_figure.py

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
        __slots__ = ('canvas', 'message')
        _count = defaultdict(lambda:0)
        def __init__(self, canvas, msg="Loading..."):
            self.canvas = canvas
            self.message = msg
        def __enter__(self):
            c = FigurePanel.LoadingContext._count
            idc = id(self.canvas)
            count = c[idc]
            if count == 0:
                FigurePanel.draw_loading(self.canvas, self.message)
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
    def write_message(self, message, wrap=True, fontsize=32, canvas=None):
        """Sets a message in the message canvas."""
        from ._util import wrap as wordwrap
        if canvas is None:
            dc = self.message_canvas
        else:
            dc = canvas
        with ipc.hold_canvas():
            dc.clear()
            dc.fill_style = 'white'
            dc.global_alpha = 0.85
            dc.fill_rect(0, 0, dc.width, dc.height)
            dc.global_alpha = 1
            dc.font = f"{fontsize}px HelveticaNeue"
            dc.fill_style = 'black'
            dc.text_align = 'left'
            dc.text_baseline = 'top'
            # Word wrap the message before printing.
            if wrap is True or wrap is Ellipsis:
                wrap = int(dc.width*13/15 / fontsize*2)
            message = wordwrap(message, wrap=wrap)
            for (ii,ln) in enumerate(message.split("\n")):
                dc.fill_text(ln, dc.width//15, dc.height//15 + fontsize*ii,
                             max_width=(dc.width - dc.width//15*2))
    def clear_message(self):
        """Clears the current message canvas."""
        self.message_canvas.clear()
    def __init__(self, state, imagesize=256):
        self.state = state
        self.imagesize = imagesize
        # Make a multicanvas for the image [0] and the drawings [1].
        imsz = imagesize
        # Make a multicanvas.
        self.multicanvas = ipc.MultiCanvas(6, width=imsz, height=imsz)
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
        self.reviewing_canvas = self.multicanvas[4]
        self.message_canvas = self.multicanvas[5]
        # Draw the loading screen on the loading canvas and save it.
        self.draw_loading(self.loading_canvas)
        self.loading_canvas.save()
        self.loading_context = FigurePanel.LoadingContext(self.loading_canvas)
        # Same for the reviewing canvas.
        review_msg = "Preparing review..."
        self.draw_loading(self.reviewing_canvas, review_msg)
        self.reviewing_canvas.save()
        self.reviewing_context = FigurePanel.LoadingContext(
            self.reviewing_canvas,
            review_msg)
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
        self.builtin_annotations = {}
        self.cursor_position = 'tail'
        self.fixed_heads = None
        self.fixed_tails = None
        self.annotation_types = {}
        self.ignore_input = False
        self.reviewing = False
        # Initialize our parent class.
        super().__init__([html, self.multicanvas])
    @classmethod
    def draw_loading(cls, dc, message='Loading...', wrap=True, fontsize=32):
        """Clears the draw canvas and draws the loading screen."""
        from ._util import wrap as wordwrap
        with ipc.hold_canvas():
            dc.clear()
            dc.fill_style = 'white'
            dc.global_alpha = 0.85
            dc.fill_rect(0, 0, dc.width, dc.height)
            dc.global_alpha = 1
            dc.font = f"{fontsize}px HelveticaNeue"
            dc.fill_style = 'black'
            dc.text_align = 'left'
            # Word wrap the message before printing.
            if wrap is True or wrap is Ellipsis:
                wrap = int(dc.width*13/15 / fontsize*2)
            message = wordwrap(message, wrap=wrap)
            for (ii,ln) in enumerate(message.split("\n")):
                dc.fill_text(ln, dc.width//15, dc.height//15 + fontsize*ii,
                             max_width=(dc.width - dc.width//15*2))
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
    def review_start(self, msg, wrap=True):
        from ._util import wrap as wordwrap
        self.review_msg = msg
        self.redraw_canvas(redraw_review=True)
    def review_end(self):
        self.review_msg = None
        self.redraw_canvas()
    def redraw_canvas(self,
                      image=Ellipsis, grid_shape=None, xlim=None, ylim=None,
                      redraw_image=True, redraw_annotations=True,
                      redraw_review=False):
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
        if redraw_image or redraw_annotations or redraw_review:
            self.loading_canvas.restore()
        with ipc.hold_canvas():
            if redraw_image:
                self.redraw_image()
            if redraw_annotations:
                self.redraw_annotations()
            if redraw_review:
                self.redraw_review()
        # That's all that's required for now.
    def redraw_image(self):
        "Clears the image canvas and redraws the image."
        self.image_canvas.clear()
        if self.image is not None:
            w = self.image_canvas.width
            h = self.image_canvas.height
            self.image_canvas.draw_image(self.image, 0, 0, w, h)
    def redraw_review(self, wrap=True, fontsize=32):
        "Clears the draw and image canvases and draws the review canvas."
        if self.review_msg is None:
            # If there's nothing to review, we do nothing.
            return
        self.image_canvas.clear()
        self.draw_canvas.clear()
        self.fg_canvas.clear()
        dc = self.image_canvas
        if isinstance(self.review_msg, str):
            with ipc.hold_canvas():
                dc.fill_style = 'white'
                dc.fill_rect(0, 0, dc.width, dc.height)
                self.write_message(
                    self.review_msg,
                    wrap=wrap,
                    fontsize=fontsize,
                    canvas=dc)
        else:
            dc.draw_image(self.review_msg, 0, 0, dc.width, dc.height)
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
            # See if the boundary is closed and connected.
            atype = self.annotation_type(ann_name)
            if atype in ('point', 'points'):
                (closed, joined) = (False, False)
            elif atype in ('path', 'contour', 'paths', 'contours'):
                (closed, joined) = (False, True)
            elif atype in ('boundary', 'boundaries', 'loop', 'loops'):
                (closed, joined) = (True, True)
            else:
                raise ValueError(f"invalid annotation type: {atype}")
            # Okay, it needs to be drawn, so convert the figure points
            # into image coordinates.
            grid_points = self.figure_to_image(points)
            # For all the point-matrices here, we need to draw them.
            for pts in grid_points:
                self.state.draw_path(
                    styletag, pts, canvas,
                    fixed_head=fh, fixed_tail=ft, cursor=cursor,
                    closed=closed, path=joined)
        # Next, we step through all the (visible) builtin annotations.
        if background:
            for (ann_name, dat) in self.builtin_annotations.items():
                if dat is None: continue
                style = self.state.style(ann_name)
                if not style['visible']: continue
                points_list = dat.get_data()
                for points in points_list:
                    grid_points = self.figure_to_image(points)
                    for pts in grid_points:
                        self.state.draw_path(ann_name, pts, self.draw_canvas,
                                             path=False)
        # That's it.
    def change_annotations(self, annots, builtin_annots,
                           redraw=True, allow=True,
                           fixed_heads=None, fixed_tails=None,
                           annotation_types=None):
        """Changes the set of currently visible annotations.

        The argument `annots` must be a dictionary whose keys are the annotation
        names and whose values are the `N x 2` matrices of annotation points, in
        figure coordinates. The optional argument `fixed_heads` may be a
        `dict`-like object whose keys are annotation names and whose values are
        the `(x,y)` coordinates of the fixed head position for that particular
        annotation.
        """
        self.annotations = annots
        self.builtin_annotations = builtin_annots
        self.fixed_heads = fixed_heads
        self.fixed_tails = fixed_tails
        self.annotation_types = annotation_types
        if redraw:
            self.redraw_annotations()
        self.ignore_input = not allow
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
    def fixed_head(self, annot=None):
        "Returns the 2D fixed-head point for the given annotation or `None`."
        if self.fixed_heads is None: return None
        if annot is None: annot = self.foreground
        pt = self.fixed_heads.get(annot)
        if pt is None: return None
        if len(np.shape(pt)) != 1: return None
        if len(pt) != 2: return None
        if np.isfinite(pt).sum() != 2: return None
        return pt
    def fixed_tail(self, annot=None):
        "Returns the 2D fixed-tail point for the given annotation or `None`."
        if self.fixed_tails is None: return None
        if annot is None: annot = self.foreground
        pt = self.fixed_tails.get(annot)
        if pt is None: return None
        if len(np.shape(pt)) != 1: return None
        if len(pt) != 2: return None
        if np.isfinite(pt).sum() != 2: return None
        return pt
    def annotation_type(self, annot=None):
        "Returns the annotation type of the given annotation."
        if self.annotation_types is None: return 'points'
        if annot is None: annot = self.foreground
        at = self.annotation_types.get(annot)
        return 'points' if at is None else at
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
        at = self.annotation_type(self.foreground)
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
            if at in ('point','points'):
                points = np.reshape(x, (1,2))
            elif self.cursor_position == 'head':
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
            fhq = False
        else:
            fh = points[[0]]
            points = points[1:]
            fhq = True
        if ft is None:
            ft = np.zeros((0,2), dtype=float)
            ftq = False
        else:
            ft = points[[-1]]
            points = points[:-1]
            ftq = True
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
        if self.ignore_input:
            return
        # Add to the current contour.
        self.push_impoint(x, y)
    def on_key_press(self, key, shift_down, ctrl_down, meta_down):
        """This method a key is pressed."""
        if self.ignore_input:
            return
        key = key.lower()
        if key == 'tab':
            self.toggle_cursor()
        elif key == 'backspace':
            # Delete from head/tail, wherever the cursor is.
            self.pop_point()
        else:
            pass
