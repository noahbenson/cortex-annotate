# -*- coding: utf-8 -*-
################################################################################
# annotate/_core.py
#
# Core implementation code for the annotation tool.


# Imports ######################################################################

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import ipycanvas as ipc
import ipywidgets as ipw

from ._util import (delay, ldict)
from ._config import Config


# The Tool #####################################################################

class SelectionPanel(ipw.VBox):
    """The subpanel of the control panel for target selection.
    """
    def _refresh_annotations(self, chname=None, change=None):
        sel = self.selection()
        target = self.targets[sel]
        anns = [k for (k,ann) in self.config.annotations.items()
                if ann.filter is None or ann.filter(target)]
        self.annotations_dropdown.options = anns
        self.annotations_dropdown.value = anns[0]
    def __init__(self, config):
        self.config = config
        self.targets = config.targets
        self.dropdowns = {}
        ch = []
        dd_layout = dict(width="94%", margin="1% 3% 1% 3%")
        for k in self.targets.concrete_keys:
            els = self.targets.items[k]
            dd = ipw.Dropdown(options=els, value=els[0], layout=dd_layout,
                              description=(k + ":"))
            #ch.append(ipw.Label(k + ":"))
            ch.append(dd)
            self.dropdowns[k] = dd
        # We need the annotation bit also.
        self.annotations_dropdown = ipw.Dropdown(options=[], layout=dd_layout,
                                                 description="Annotation:")
        self._refresh_annotations()
        #ch.append(ipw.Label('Annotation:'))
        ch.append(self.annotations_dropdown)
        super().__init__(ch)
        # We want to have our own refresh annotations function be run whenever
        # the selection changes.
        self.observe_selection(self._refresh_annotations)
    def selection(self):
        return tuple(dd.value for dd in self.dropdowns.values())
    def observe_selection(self, fn):
        for k in self.targets.concrete_keys:
            self.dropdowns[k].observe(partial(fn, k), names='value')
class StylePanel(ipw.VBox):
    """The subpanel of the control panel containing the style controls.
    """
    @classmethod
    def _make_hline(cls, width=85):
        return ipw.HTML(f"""
            <style>
                .cortex-annotate-StylePanel-hline {{
                    border-color: lightgray;
                    border-style: dotted;
                    border-width: 1px;
                    height: 0px;
                    width: {width}%;
                    margin: 0% {(100-width)//2}% 0% {100 - width - (100-width)//2}%;
                }}
            </style>
            <div class="cortex-annotate-StylePanel-hline">
            </div>
        """)
    def __init__(self, config):
        self.config = config
        # We use the config to populate the collection of style preferences, but
        # we keep track of these separately so that we can remember them.
        self.preferences = {}
        entries = ['Selected Annotation'] + list(config.annotations.keys())
        layout = dict(width="94%", margin="0% 3% 0% 3%")
        self.style_dropdown = ipw.Dropdown(
            options=entries, value=entries[0], description="Annotation:",
            layout=dict(layout, margin="3% 3% 3% 3%"))
        self.visible_checkbox = ipw.Checkbox(
            description="Visible",
            value=True,
            layout=layout)
        self.color_picker = ipw.ColorPicker(
            concise=False,
            description='Color:',
            value='blue',
            layout=layout)
        self.pointsize_slider = ipw.IntSlider(
            value=1, min=0, max=12, step=1,
            description="Point Size:",
            readout=True,
            continuous_update=False,
            layout=layout)
        self.linewidth_slider = ipw.IntSlider(
            value=1, min=1, max=8, step=1,
            description="Line Width:",
            readout=True,
            continuous_update=False,
            layout=layout)
        self.linestyle_dropdown = ipw.Dropdown(
            options=['solid', 'dashed', 'dot-dashed', 'dotted'],
            description="Line Style:",
            layout=layout)
        ch = [
            ipw.HTML("<b style=\"margin: 0% 3% 0% 3%;\">Style Options:</b>"),
            self.style_dropdown,
            self._make_hline(),
            self.visible_checkbox,
            self.color_picker,
            self.pointsize_slider,
            self.linewidth_slider,
            self.linestyle_dropdown]
        super().__init__(ch, layout=dict(margin="0% 0% 3% 0%"))
class ControlPanel(ipw.VBox):
    """The panel that contains selection widgets and options.
    """
    @classmethod
    def _make_imagesize_slider(cls, initial_value=500):
        return ipw.IntSlider(value=initial_value, min=250, max=2750, step=1,
                             description="Image Size: ",
                             readout=False,
                             continuous_update=False,
                             layout=dict(width='90%', padding="0px"))
    @classmethod
    def _make_html_header(cls, background_color="#f0f0f0"):
        return ipw.HTML(f"""
            <style>
            .jupyter-widget-Collapse-contents {{
                background-color: {background_color};
                padding: 2px;
                border-width: 1px;
                border-style: solid;
                border-color: lightgray;
            }}
            .jupyter-widget-Collapse-header {{
                background-color: white;
                border-width: 0px;
                padding: 0px;
            }}
            .jupyter-widget-Collapse-open {{
                background-color: white;
            }}
            </style>
        """)
    @classmethod
    def _make_hline(cls):
        return ipw.HTML("""
            <style>
                .cortex-annotate-ControlPanel-hline {
                    border-color: lightgray;
                    border-style: solid;
                    border-width: 1px;
                    height: 0px;
                    width: 94%;
                    margin: 3%;
                }
            </style>
            <div class="cortex-annotate-ControlPanel-hline">
            </div>
        """)
    def __init__(self, config, background_color="#f0f0f0", image_size=500):
        self.html_header = self._make_html_header(background_color)
        self.imagesize_slider = self._make_imagesize_slider(image_size)
        self.selection_panel = SelectionPanel(config)
        self.style_panel = StylePanel(config)
        hline = self._make_hline()
        self.vbox_children = [
            ipw.HTML("<b style=\"margin: 0% 3% 0% 3%;\">Selection:</b>"),
            self.selection_panel,
            hline,
            self.imagesize_slider,
            hline,
            self.style_panel]
        vbox_layout = {'width': '250px'}
        vbox = ipw.VBox(self.vbox_children, layout=vbox_layout)
        children = [self.html_header,
                    ipw.Accordion((vbox,), selected_index=0),
                    self.html_header]
        layout = {'border-width':'0px',
                  'height': '100%'}
        super().__init__(children, layout=layout)
    def observe_selection(self, fn):
        self.selection_panel.observe(fn)
class AnnotationTool(ipw.HBox):
    """The core annotation tool for the `cortex-annotate` project.

    The `AnnotationTool` type handles the annotation of the cortical surface
    images for the `cortex-annotate` project.
    """
    def on_image_size_change(self, change):
        "This method runs when the control panel's image size slider changes."
        self.multicanvas.width = change.new
        self.multicanvas.height = change.new
        self.multicanvas.layout.width = f"{change.new}px"
        self.multicanvas.layout.height = f"{change.new}px"
        self.layout.width = f"{change.new + 262}px";
        # Redraw the image.
        self.redraw_canvas()
    def on_selection_change(self, key, change):
        pass
    def redraw_canvas(self):
        self.image_canvas.draw_image(image,
                                     0, 0,
                                     self.multicanvas.width,
                                     self.multicanvas.height)
    def __init__(self,
                 config_path='/config/config.yaml',
                 cache_path='/cache',
                 control_panel_background_color="#f0f0f0",
                 draw_panel_width=500):
        self.config = Config(config_path)
        self.cache_path = cache_path
        # Make the control panel.
        self.control_panel = ControlPanel(
            self.config,
            background_color=control_panel_background_color,
            image_size=draw_panel_width)
        # Make a multicanvas for the image [0] and the drawings [1].
        dpw = draw_panel_width
        self.multicanvas = ipc.MultiCanvas(2, width=dpw, height=dpw)
        self.multicanvas.layout.width = f"{dpw}px"
        self.multicanvas.layout.height = f"{dpw}px"
        self.image_canvas = self.multicanvas[0]
        self.draw_canvas = self.multicanvas[1]
        # Add a listener for the image size change.
        self.control_panel.imagesize_slider.observe(
            self.on_image_size_change,
            names='value')
        # And a listener for the selection change.
        self.control_panel.observe_selection(self.on_selection_change)
        super().__init__((self.control_panel, self.multicanvas),
                         layout={'width': f'{262 + dpw}px'})
