# -*- coding: utf-8 -*-
################################################################################
# annotate/_util.py
#
# Utility types and functions used in the annotation toolkit.


# Dependencies #################################################################

import numpy as np
import yaml, os
from collections import namedtuple
from itertools import product

from ._util import (delay, ldict)


class ConfigError(Exception):
    """An exception raised due to errors in the config.yaml file.
    
    `ConfigError` is a subclass of `Exception` that is raised when an error is
    encountered while parsing the `config.yaml` file used to configure the
    `cortex-annotate` project.
    """
    __slots__ = ('section', 'yaml')
    def __init__(self, section, message, yaml=None):
        super().__init__(f"{section}: {message}")
        self.section = section
        self.yaml = yaml
class InitConfig:
    """An object that keeps track of the `init` section of `config.yaml`.

    The `InitConfig` type is used to keep track of the `init` section of the
    `config.yaml` file for the `cortex-annotate` project. The `init` section
    contains a code-block whose local values (after the code block is executed)
    are made available to all other code blocks in the config file. This allows
    one to, for example, import a library in the init block that is then
    available throughout the config file.
    """
    __slots__ = ('code', 'locals')
    def __init__(self, code, locals=None):
        if code is None:
            code = 'None'
        if not isinstance(code, str):
            raise ConfigError("init", "init section must be a string", code)
        self.code = code
        self.locals = {} if locals is None else locals
        exec(code, None, self.locals)
        # Merge in the current globals.
        self.locals = dict(globals(), **self.locals)
    def exec(self, code, copy=True):
        if copy:
            loc = self.locals.copy()
        else:
            loc = self.locals
        exec(code, loc)
        return loc
    def eval(self, code, copy=True):
        if copy:
            loc = self.locals.copy()
        else:
            loc = self.locals
        return eval(code, loc)
class DisplayConfig:
    """An object that tracks the configuration of the tool's image display.

    The `DisplayConfig` type keeps track of the `display` section of the
    `config.yaml` file for the `cortex-annotate` project.
    """
    __slots__ = ('figsize', 'dpi', 'imsize', 'plot_options', 'fg_options')
    def __init__(self, disp):
        from numbers import (Real, Integral)
        from ._core import AnnotationState
        if disp is None: disp = {}
        figsize0 = figsize = disp.get('figsize', [4,4])
        if not isinstance(figsize, (list,tuple)):
            figsize = [figsize, figsize]
        if not all(isinstance(u, Real) and u > 0 for u in figsize):
            raise ConfigError("display",
                              "invalid figsize in config.display: {figsize0}",
                              disp)
        figsize = tuple(figsize)
        dpi = disp.get('dpi', 128)
        if not isinstance(dpi, Integral) or dpi < 1:
            raise ConfigError("display",
                              "invalid dpi in config.display: {dpi}",
                              disp)
        # Compute the image size.
        imsize = (round(dpi*figsize[0]), round(dpi*figsize[0]))
        # Extract the plot options and foreground options.
        plot_opts = disp.get('plot_options', {})
        if not isinstance(plot_opts, dict):
            raise ConfigError("display", 
                              "plot_options in display must be a mapping",
                              disp)
        try: AnnotationState.fix_style(plot_opts)
        except Exception: plot_opts = None
        if plot_opts is None:
            raise ConfigError("display.plot_options", "invalid plot_options",
                              disp)
        fg_opts = disp.get('fg_options', {})
        if not isinstance(fg_opts, dict):
            raise ConfigError("display", 
                              "fg_options in display must be a mapping",
                              disp)
        try: AnnotationState.fix_style(fg_opts)
        except Exception: fg_opts = None
        if fg_opts is None:
            raise ConfigError("display.fg_options", "invalid fg_options",
                              disp)
        # Make sure the keys are valid
        style_keys = AnnotationState.style_keys
        for (opts, name) in zip([plot_opts, fg_opts], ["plot","fg"]):
            bad = [k for k in opts.keys() if k not in style_keys]
            if len(bad) > 0:
                raise ConfigError(
                    "display",
                    f"invalid keys in display.{name}_options: {bad}",
                    disp)
        # We need to merge the plot options and fg options together since the
        # plot options are the defaults for the fg options.
        fg_opts = dict(plot_opts, **fg_opts)
        # That's the whole section; we can set values and return now.
        self.figsize = figsize
        self.dpi = dpi
        self.imsize = imsize
        self.plot_options = plot_opts
        self.fg_options = fg_opts
class TargetsConfig(ldict):
    """A dict-like configuration item for the annotation tool's targets.

    The `TargetsConfig` type is a (lazy) dict-like object that stores, as dict
    entries, the targets of the annotation project (i.e., subjects, hemispheres)
    as well as meta-data about the targets.

    For a `TargetsConfig` object `targets`, `targets[(id1, id2...)]` evaluates
    to the `target` dictionary for the target that is identified by the values
    for the ordered concrete key `id1, id2...`.
    """
    __slots__ = ('items', 'concrete_keys')
    @staticmethod
    def _reify_target(items, concrete_keys, targ):
        """Builds up and returns an `ldict` of the all target data.

        `TargetsConfig._reify_target(items, concrete_keys, targ)` takes the
        target-id tuple `targ` and builds up the `ldict` representation of the
        target data, in which all keys in the `config.yaml` file have values
        (albeit lazy ones in the case of the keys that are not concrete). The
        parameters `items` and `concrete_keys` must be the configuration's
        target data and the list of concrete keys must be the concrete keys for
        the target, respectively.
        """
        d = ldict()
        targ_iter = iter(targ)
        for (k,v) in items.items():
            if k in concrete_keys:
                d[k] = next(targ_iter)
            else:
                d[k] = delay(v, ldict(d))
        return d
    def __init__(self, yaml, init):
        from itertools import product
        if yaml is None:
            raise ConfigError("targets", "targets section is required", yaml)
        if not isinstance(yaml, dict):
            raise ConfigError("targets",
                              "targets section must be a mapping",
                              yaml)
        # First we step through and compile the keys when necessary.
        concrete_keys = []
        items = {}
        for (k,v) in yaml.items():
            if isinstance(v, list):
                concrete_keys.append(k)
                items[k] = v
            elif isinstance(v, str):
                lines = [('    ' + ln) for ln in v.split('\n')]
                code = "\n".join(lines)
                fnname = f"__fn_{os.urandom(8).hex()}"
                loc = init.exec(f"def {fnname}(target):\n{code}")
                items[k] = loc[fnname]
            else:
                raise ConfigError(f"targets.{k}",
                                  "target elements must be strings or lists",
                                  yaml)
        # We then fill these out into a lazy dict that reifies each target
        # individually. We start with a dict but put the delays into this object
        # (which is a lazy dict itself).
        d = dict()
        for tup in product(*[items[k] for k in concrete_keys]):
            d[tup] = delay(TargetsConfig._reify_target,
                           items, concrete_keys, tup)
        self.concrete_keys = concrete_keys
        self.items = items
        self.update(d)
Annotation = namedtuple(
    'Annotation',
    ('grid', 'filter', 'type', 'plot_options'))
class AnnotationsConfig(dict):
    """An object that stores the configuration of the annotations to be drawn.

    The `AnnotationsConfig` type tracks the contours and boundaries that are to
    be drawn on the annotation targets for the `cortex-annotate` project.
    """
    __slots__ = ('all_figures')
    def __init__(self, yaml, init):
        from ._core import AnnotationState
        # The yaml should just contain entries for the annotations.
        if not isinstance(yaml, dict):
            raise ConfigError("annotations",
                              "annotations must contain a mapping",
                              yaml)
        # Go through and build up the lists of figures and the annotation data.
        annots = {}
        figs = set([])
        for (k,v) in yaml.items():
            if isinstance(v, list):
                # It is legal to just provide the grid.
                v = {'grid': v}
            if not isinstance(v, dict):
                raise ConfigError(f"annotations.{k}",
                                  f"annotation {k} must be a list or mapping",
                                  yaml)
            # Now just go through and parse the options.
            plot_opts = v.get('plot_options', {})
            if not isinstance(plot_opts, dict):
                raise ConfigError(f"annotations.{k}", 
                                  "annotation plot_options must be mappings",
                                  yaml)
            try: AnnotationState.fix_style(plot_opts)
            except Exception: plot_opts = None
            if plot_opts is None:
                raise ConfigError(f"annotations.{k}", "invalid plot_options",
                                  yaml)
            ctype = v.get('type', 'contour')
            if ctype not in ('contour', 'boundary', 'point'):
                raise ConfigError(
                    f"annotations.{k}", 
                    "type must be one of 'contour', 'boundary', or 'point'",
                    yaml)
            filter = v.get('filter', None)
            if filter is not None and not isinstance(filter, str):
                raise ConfigError(f"annotations.{k}",
                                  "filter must be null or a Python code string",
                                  yaml)
            grid = v.get('grid', None)
            if not isinstance(grid, list):
                raise ConfigError(f"annotations.{k}",
                                  "grid is required and must be a list/matrix",
                                  yaml)
            if all(el is None or isinstance(el, str) for el in grid):
                # Single row; this is fine.
                grid = [grid]
            cols = None
            for row in grid:
                if not isinstance(row, list):
                    raise ConfigError(f"annotations.{k}",
                                      "grid must be a list/matrix", yaml)
                if cols is None:
                    cols = len(row)
                elif cols != len(row):
                    raise ConfigError(f"annotations.{k}"
                                      "grid cannot be a ragged matrix", yaml)
                for el in row:
                    if el is None: continue
                    elif not isinstance(el, str):
                        raise ConfigError(f"annotations.{k}",
                                          "grid items must be null or strings",
                                          yaml)
                    figs.add(el)
            # We have extracted the data now; go ahead and compile the filter.
            if filter is not None:
                lines = [('    ' + ln) for ln in filter.split('\n')]
                code = "\n".join(lines)
                fnname = f"__fn_{os.urandom(8).hex()}"
                loc = init.exec(f"def {fnname}(target):\n{code}")
                filter = loc[fnname]
            # Everything for this annotation is now processed; just set up its
            # Annotation object.
            annots[k] = Annotation(grid, filter, ctype, plot_opts)
        # And now all the annotations are processed.
        self.update(annots)
        self.all_figures = figs
class FiguresConfig(dict):
    """An object that stores configuration information for making figures.

    The `FiguresConfig` type stores information from the `figures` section of
    the `config.yaml` file for the `cortex-annotate` project. It resembles a
    Python `dict` object whose keys are the figure names and whose values are
    Python functions (which require the arguments `target`, `key`, `figure`, and
    `axes`) that generate the appropriate figure.
    """
    __slots__ = ('yaml')
    @staticmethod
    def _compile_fn(code, initcode, termcode, initcfg):
        # The code is all going to go into a function, so start by indenting.
        lines = [('    ' + ln) for ln in code.split('\n')]
        code = "\n".join(lines)
        # We want to add in the init and term code if there is any provided.
        if initcode is not None:
            lines = [('    ' + ln) for ln in initcode.split('\n')]
            initcode = "\n".join(lines)
        else:
            initcode = ''
        if termcode is not None:
            lines = [('    ' + ln) for ln in termcode.split('\n')]
            termcode = "\n".join(lines)
        else:
            termcode = ''
        # Okay, now we can compile together the pieces into a function.
        fnname = f"__fn_{os.urandom(8).hex()}"
        fncode = (f"def {fnname}(target, key, figure, axes, figsize, dpi,\n"
                  f"             meta_data):\n"
                  f"{initcode}\n{code}\n{termcode}")
        loc = initcfg.exec(fncode)
        return loc[fnname]
    def __init__(self, yaml, init, all_figures):
        if not isinstance(yaml, dict):
            raise ConfigError("figures",
                              "figures section must contain a mapping", yaml)
        self.yaml = yaml
        yaml = yaml.copy() # Don't modify the original yaml dict.
        # Pull out the relevant special entries.
        initcode = yaml.pop('init', None)
        termcode = yaml.pop('term', None)
        wildcode = yaml.pop('_', None)
        if initcode is not None and not isinstance(initcode, str):
            raise ConfigError("figures.init",
                              "figure entries must contain (code) strings",
                              yaml)
        if termcode is not None and not isinstance(termcode, str):
            raise ConfigError("figures.term",
                              "figure entries must contain (code) strings",
                              yaml)
        if wildcode is not None:
            if not isinstance(wildcode, str):
                raise ConfigError("figures._",
                                  "figure entries must contain (code) strings",
                                  yaml)
            wildfn = FiguresConfig._compile_fn(wildcode, initcode, termcode,
                                               init)
        else:
            wildfn = None
        # The rest of the entries must be figure names.
        res = {}
        for k in all_figures:
            if k not in yaml:
                if wildfn is None:
                    raise ConfigError("figures", f"no figure entry for {k}",
                                      yaml)
                res[k] = wildfn
            else:
                code = yaml[k]
                if not isinstance(code, str):
                    raise ConfigError(
                        f"figures.{k}",
                        "figure entries must contain (code) strings",
                        yaml)
                res[k] = FiguresConfig._compile_fn(code, initcode, termcode,
                                                   init)
        # Same these into the dictionary.
        self.update(res)
class Config:
    """The configuration object for the `cortex-annotate` project.

    The `Config` class stores information about the configuration of the
    `cortex-annotate` project. The configuration is specified in the
    `config.yaml` file. Configuration objects store a single value per top-level
    config item in the `config.yaml` file. Additional top-level items that are
    not recognized by `Config` are not parsed, but they are available in the
    `Config.yaml` member variable.
    """
    __slots__ = ('config_path', 'yaml', 'display', 'init', 'targets',
                 'annotations', 'figures')
    def __init__(self, config_path='/config/config.yaml'):
        self.config_path = config_path
        with open(config_path, 'rt') as f:
            self.yaml = yaml.safe_load(f)
        # Parse the display section.
        self.display = DisplayConfig(self.yaml.get('display', None))
        # Parse the init section.
        self.init = InitConfig(self.yaml.get('init', None))
        # Parse the targets section.
        self.targets = TargetsConfig(self.yaml.get('targets', None), self.init)
        # Parse the annotations section.
        self.annotations = AnnotationsConfig(self.yaml.get('annotations', None),
                                             self.init)
        # Parse the figures section.
        self.figures = FiguresConfig(self.yaml.get('figures', None), self.init,
                                     self.annotations.all_figures)
