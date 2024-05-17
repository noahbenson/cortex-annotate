# -*- coding: utf-8 -*-
################################################################################
# cortexannotate/_control_panel.py

"""Core implementation code for the annotation tool's control panel.

This file contains code for managing the panel's widget and window state. The
design intention is that the `AnnotationTool` (in `_core.py`) creates and
observes changes from the control panel (such as changes in the selection or
changes in the style parameters) and passes these on to the `FigurePanel` object
in `_figure.py` as appropriate.
"""


# Imports ######################################################################

from functools import partial

import ipywidgets as ipw


# The Control Panel Widgets ####################################################

# First, we have the sub-panels of the control panel: the selection and style
# panels.
class SelectionPanel(ipw.VBox):
    """The subpanel of the control panel for target selection."""
    __slots__ = ('state', 'dropdowns', 'annotations_dropdown', 
                 'target_observers', 'annotation_observers')
    def __init__(self, state):
        self.state = state
        self.dropdowns = {}
        ch = []
        dd_layout = dict(width="94%", margin="1% 3% 1% 3%")
        for k in state.config.targets.concrete_keys:
            els = state.config.targets.items[k]
            dd = ipw.Dropdown(options=els, value=els[0], layout=dd_layout,
                              description=(k + ":"))
            ch.append(dd)
            self.dropdowns[k] = dd
        # We need the annotation bit also.
        self.annotations_dropdown = ipw.Dropdown(options=[], layout=dd_layout,
                                                 description="Annotation:")
        ch.append(self.annotations_dropdown)
        super().__init__(ch)
        # Because we want to control the order of a few things, we actually
        # listen to our selection items ourselves, then update them and pass
        # them along to our listeners. This is important so that, for example,
        # the Figure panel's listener doesn't get updated before the annotation
        # selection dropbox is changed when the user changes the target
        #  selection.
        for k in state.config.targets.concrete_keys:
            self.dropdowns[k].observe(
                partial(self.on_target_change, k), 
                names='value')
        self.annotations_dropdown.observe(
            self.on_annotation_change,
            names='value')
        self.target_observers = []
        self.annotation_observers = []
        # Initialize the annotations menu.
        self.refresh_annotations()
    @property
    def target(self):
        """Compute the current target selection."""
        return tuple(dd.value for dd in self.dropdowns.values())
    @property
    def annotation(self):
        """Compute the current annotation selection."""
        return self.annotations_dropdown.value
    @property
    def selection(self):
        """Compute the current selection."""
        return self.target + (self.selection,)
    def refresh_annotations(self):
        # Get the new target selection entire.
        sel = self.target
        # Look up the target for this selection.
        target = self.state.config.targets[sel]
        # Recalculate the annotations for this target and update the menu.
        anns = [k for (k,ann) in self.state.config.annotations.items()
                if ann.filter is None or ann.filter(target)]
        self.annotations_dropdown.options = anns
        self.annotations_dropdown.value = anns[0]
    def on_target_change(self, key, change):
        # Refresh the annotations menu.
        self.refresh_annotations()
        # Alert our other observers, now that our updates are finished.
        for fn in self.target_observers:
            fn(key, change)
    def on_annotation_change(self, change):
        # Alert our observers.
        for fn in self.annotation_observers:
            fn(change)
    def observe_target(self, fn):
        """Registers the given function to be called when the taget changes.

        The selection target refers to the selection of all the concrete keys in
        the `config.yaml` file's `targets` section. In other words, the
        selection target changes when any of the selection dropdowns are changed
        except for the annotation dropdown.

        When the selection target changes, the given function is called with two
        arguments: `fn(concrete_key, change)` where `concrete_key` is the
        (string) name of one of the concrete keys and `change` is the change
        object typically used in the `ipywidget` `observe` pattern.
        """
        self.target_observers.append(fn)
    def observe_annotation(self, fn):
        """Registers the argument to be called when the annotation changes.

        The annotation selection is the currently selected annotation in the
        annotations dropdown menu of the `SelectionPanel` component of the
        `ControlPanel`.

        When the annotation selection changes, the given function is called with
        the argument `change` where `change` is the `change` object typically
        used in the `ipywidget` `observe` pattern.
        """
        self.annotation_observers.append(fn)
    def observe_selection(self, fn):
        """Registers the given function to be called when the selection changes.

        The selection refers to the combination of target and annotation
        selection; see the `observe_target` and `observe_annotation` methods for
        more information.

        When the selection changes, the given function is called with two
        arguments: `fn(concrete_key, change)` where `concrete_key` is the
        (string) concrete key that has changed and `change` is the change object
        typically used in the `ipywidget` `observe` pattern. If the annotation
        has changed, then the `key` will be `None`.
        """
        self.observe_target(fn)
        self.observe_annotation(partial(fn, None))
class StylePanel(ipw.VBox):
    """The subpanel of the control panel containing the style controls."""
    @classmethod
    def _make_hline(cls, width=85):
        return ipw.HTML(f"""
            <style> .cortex-annotate-StylePanel-hline {{
                border-color: lightgray;
                border-style: dotted;
                border-width: 1px;
                height: 0px;
                width: {width}%;
                margin: 0% {(100-width)//2}% 0% {100 - width - (100-width)//2}%;
            }} </style>
            <div class="cortex-annotate-StylePanel-hline"></div>
        """)
    def __init__(self, state):
        self.state = state
        # We use the config to populate the collection of style preferences, but
        # we keep track of these separately so that we can remember them.
        self.user_preferences = {}
        entries = ['Selected Annotation']
        entries += list(state.config.annotations.keys())
        entries += list(state.config.builtin_annotations.keys())
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
        # Set up our observer pattern. We track these manually so that we can
        # call the functions using a parameter order that makes sense.
        self.style_observers = []
        self.style_names = {"visible": self.visible_checkbox,
                            "color": self.color_picker,
                            "markersize": self.pointsize_slider,
                            "linewidth": self.linewidth_slider,
                            "linestyle": self.linestyle_dropdown}
        for (k,v) in self.style_names.items():
            v.observe(partial(self.on_style_change, k), names="value")
        # We need to make sure that we update things when the style dropdown
        # changes also.
        self.style_dropdown.observe(self.refresh_style, names="index")
        self.refresh_style()
    @property
    def annotation(self):
        dd = self.style_dropdown
        return dd.value if dd.index > 0 else None
    @property
    def preferences(self):
        return {k:v.value for (k,v) in self.style_names.items()}
    @property
    def style(self):
        prefs = self.user_preferences
        prefs['annotation'] = self.annotation
        return prefs
    def refresh_style(self, change=None):
        ann = self.style_dropdown.index if change is None else change.new
        ann = self.style_dropdown.options[ann] if ann > 0 else None
        prefs = self.state.style(ann)
        for (k,v) in self.style_names.items():
            v.value = prefs[k]
    def on_style_change(self, key, change):
        ann = self.annotation
        # Alert our observers.
        for fn in self.style_observers:
            fn(ann, key, change)
    def observe_style(self, fn):
        """Registers the given function to be called when the a style changes.

        Style elements refer to the settings managed by the `StylePanel` of the
        `ControlPanel` object. A style element is considered to have changed
        when any of these controls are changed except for the style annotation
        selection dropdown, which controls which of the annotations the other
        style controls affect.

        When a style element changes, the given function is called with three
        arguments: `fn(annotation, element, change)` where `annotation` is the
        name of the annotation that is currently selected (i.e., the annotation
        that is changing), `element` is the name of the element that is
        changing, and `change` is the typical `ipywidget` change object used
        with the `observe` pattern. If the annotation representing the currently
        selected contour is edited, then the `annotation` value will be `None`.

        The possible values for `element` are as follows:
         * `"visible"`: the visibility has changed.
         * `"color"`: the draw color has changed.
         * `"linewidth"`: the line width has changed.
         * `"linestyle"`: the line style has changed.
         * `"markersize"`: the marker size has changed.
        """
        self.style_observers.append(fn)
class ControlPanel(ipw.VBox):
    """The panel that contains the controls for the Annotation Tool.
    """
    @classmethod
    def _make_imagesize_slider(cls, initial_value=256):
        return ipw.IntSlider(value=initial_value, min=250, max=1280, step=1,
                             description="Image Size: ",
                             readout=False,
                             continuous_update=False,
                             layout=dict(width='90%', padding="0px"))
    @classmethod
    def _make_html_header(cls,
                          background_color="#f0f0f0",
                          save_button_color="#e0e0e0"):
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
            .widget-button {{
                background-color: {save_button_color};
            }}
            </style>
        """)
    @classmethod
    def _make_hline(cls):
        return ipw.HTML("""
            <style> .cortex-annotate-ControlPanel-hline {
                border-color: lightgray;
                border-style: solid;
                border-width: 1px;
                height: 0px;
                width: 94%;
                margin: 3%;
            } </style>
            <div class="cortex-annotate-ControlPanel-hline">
            </div>
        """)
    @classmethod
    def _make_infomsg(cls):
        return ipw.VBox(
            [ipw.HTML("""
                <div style="line-height:1.2; margin: 2%;">
                <center><b>CLICK</b> to add a point to the circled end of the
                current annotation.</center></div>
                """),
             ipw.HTML("""
                <div style="line-height:1.2; margin: 2%;">
                <center><b>BACKSPACE</b> to delete the circled point.
                </center></div>
                """),
             ipw.HTML("""
                <div style="line-height:1.2; margin: 2%;">
                <center><b>TAB</b> to toggle the circled end.</center></div>
                """)],
            layout={'margin': '3%', 'width': '88%'})
    def __init__(self, state,
                 background_color="#f0f0f0", imagesize=256,
                 save_button_color="#e0e0e0"):
        self.html_header = self._make_html_header(background_color,
                                                  save_button_color)
        self.imagesize_slider = self._make_imagesize_slider(imagesize)
        self.selection_panel = SelectionPanel(state)
        self.style_panel = StylePanel(state)
        self.review_button = ipw.Button(
            description='Review',
            button_style='',
            tooltip='Review the annotations.')
        self.save_button = ipw.Button(
            description='Save',
            button_style='',
            tooltip='Save all annotations and preferences.')
        self.edit_button = ipw.Button(
            description='Edit',
            button_style='',
            tooltip='Continue editing annotation.')
        if state.config.review.function is not None:
            buttons = [self.review_button, self.save_button, self.edit_button]
            self.review_button.disabled = False
            self.save_button.disabled = True
            self.edit_button.disabled = True
            layout = {'margin':"3% 3% 3% 3%", "width": "94%"}
        else:
            buttons = [self.save_button]
            self.review_button.disabled = True
            self.save_button.disabled = False
            self.edit_button.disabled = True
            layout = {'margin':"3% 33% 3% 33%", "width": "34%"}
        self.button_box = ipw.HBox(buttons, layout=layout)
        self.info_message = self._make_infomsg()
        hline = self._make_hline()
        self.vbox_children = [
            ipw.HTML("<b style=\"margin: 0% 3% 0% 3%;\">Selection:</b>"),
            self.selection_panel,
            hline,
            self.imagesize_slider,
            hline,
            self.style_panel,
            hline,
            self.button_box,
            hline,
            self.info_message]
        vbox_layout = {'width': '250px'}
        vbox = ipw.VBox(self.vbox_children, layout=vbox_layout)
        children = [self.html_header,
                    ipw.Accordion((vbox,), selected_index=0),
                    self.html_header]
        layout = {'border-width':'0px', 'height':'100%'}
        super().__init__(children, layout=layout)
    def observe_target(self, fn):
        """Registers the given function to be called when the taget changes.

        The selection target refers to the selection of all the concrete keys in
        the `config.yaml` file's `targets` section. In other words, the
        selection target changes when any of the selection dropdowns are changed
        except for the annotation dropdown.

        When the selection target changes, the given function is called with two
        arguments: `fn(concrete_key, change)` where `concrete_key` is the
        (string) name of one of the concrete keys and `change` is the change
        object typically used in the `ipywidget` `observe` pattern.
        """
        self.selection_panel.observe_target(fn)
    def observe_annotation(self, fn):
        """Registers the argument to be called when the annotation changes.

        The annotation selection is the currently selected annotation in the
        annotations dropdown menu of the `SelectionPanel` component of the
        `ControlPanel`.

        When the annotation selection changes, the given function is called with
        the argument `change` where `change` is the `change` object typically
        used in the `ipywidget` `observe` pattern.
        """
        self.selection_panel.observe_annotation(fn)
    def observe_selection(self, fn):
        """Registers the given function to be called when the selection changes.

        The selection refers to the combination of target and annotation
        selection; see the `observe_target` and `observe_annotation` methods for
        more information.

        When the selection changes, the given function is called with two
        arguments: `fn(concrete_key, change)` where `concrete_key` is the
        (string) concrete key that has changed and `change` is the change object
        typically used in the `ipywidget` `observe` pattern. If the annotation
        has changed, then the `key` will be `None`.
        """
        self.selection_panel.observe_selection(fn)
    def observe_style(self, fn):
        """Registers the given function to be called when the a style changes.

        Style elements refer to the settings managed by the `StylePanel` of the
        `ControlPanel` object. A style element is considered to have changed
        when any of these controls are changed except for the style annotation
        selection dropdown, which controls which of the annotations the other
        style controls affect.

        When a style element changes, the given function is called with three
        arguments: `fn(annotation, element, change)` where `annotation` is the
        name of the annotation that is currently selected (i.e., the annotation
        that is changing), `element` is the name of the element that is
        changing, and `change` is the typical `ipywidget` change object used
        with the `observe` pattern. If the annotation representing the currently
        selected contour is edited, then the `annotation` value will be `None`.

        The possible values for `element` are as follows:
         * `"visible"`: the visibility has changed.
         * `"color"`: the draw color has changed.
         * `"linewidth"`: the line width has changed.
         * `"linestyle"`: the line style has changed.
         * `"markersize"`: the marker size has changed.
        """
        self.style_panel.observe_style(fn)
    def observe_imagesize(self, fn):
        """Registers the argument to be called when the image size changes.

        `control_panel.observe_imagesize(fn)` is equivalent to
        `control_panel.imagesize_slider.observe(fn, names="value")`.
        """
        self.imagesize_slider.observe(fn, names="value")
    def observe_save(self, fn):
        """Registers the argument to be called when the save button is clicked.
        
        The function is called with a single argument, which is the save button
        instance.
        """
        self.save_button.on_click(fn)
    def observe_review(self, fn):
        """Registers the argument to be called when the save button is clicked.
        
        The function is called with a single argument, which is the review
        button instance.
        """
        self.review_button.on_click(fn)
    def observe_edit(self, fn):
        """Registers the argument to be called when the edit button is clicked.
        
        The function is called with a single argument, which is the edit button
        instance.
        """
        self.edit_button.on_click(fn)
    @property
    def target(self):
        """Compute the current target selection."""
        return self.selection_panel.target
    @property
    def annotation(self):
        """Compute the current annotation selection."""
        return self.selection_panel.annotation
    @property
    def selection(self):
        """Compute the current selection."""
        return self.selection_panel.selection
