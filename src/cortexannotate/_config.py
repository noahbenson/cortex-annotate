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


def _compile_fn(argstr, codestr, init):
    name = f"__fn_{os.urandom(8).hex()}"
    lines = [('    ' + ln) for ln in codestr.split('\n')]
    code = "\n".join(lines)
    loc = init.exec(f"def {name}({argstr}):\n{code}")
    return loc[name]

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
    __slots__ = ('code', 'locals', 'globals')
    def __init__(self, code, globals=None, locals=None):
        if code is None:
            code = 'None'
        if not isinstance(code, str):
            raise ConfigError("init", "init section must be a string", code)
        self.code = code
        # Hack to get the globals function back:
        globs = globals
        globals = eval('globals', {}, None)
        # Save the passed values.
        self.locals = {} if locals is None else locals
        self.globals = globals().copy() if globs is None else globs
        exec(code, self.globals, self.locals)
        self.globals = dict(self.globals, **self.locals)
        self.locals = {}
    def exec(self, code, copy=True):
        if copy:
            loc = self.locals.copy()
            glo = self.globals.copy()
        else:
            loc = self.locals
            glo = self.globals
        exec(code, glo, loc)
        return loc
    def eval(self, code, copy=True):
        if copy:
            loc = self.locals.copy()
            glo = self.globals.copy()
        else:
            loc = self.locals
            glo = self.globals
        exec(code, glo, loc)
        return eval(code, glo, loc)
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
                items[k] = _compile_fn('target', v, init)
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
    ('grid', 'filter', 'type', 'plot_options', 'fixed_head', 'fixed_tail'),
    defaults=(None,None))
class AnnotationsConfig(dict):
    """An object that stores the configuration of the annotations to be drawn.

    The `AnnotationsConfig` type tracks the contours and boundaries that are to
    be drawn on the annotation targets for the `cortex-annotate` project.
    """
    __slots__ = ('all_figures', 'types')
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
            fixed = [v.get('fixed_head'), v.get('fixed_tail')]
            for (ii,f) in enumerate(fixed):
                if f is None: continue
                if isinstance(f, str):
                    f = dict(calculate=f'return annotations["{f}"][-1,:]',
                             requires=f)
                if not isinstance(f, dict):
                    raise ConfigError(
                        f"annotations.{k}",
                        f"fixed_{['head','tail'][ii]} must be a str or mapping",
                        yaml)
                reqs = f.get('requires', [])
                reqs = reqs if isinstance(reqs, list) else [reqs]
                calc = f.get('calculate')
                if calc is None:
                    raise ConfigError(
                        f"annotations.{k}",
                        f"fixed_{['head','tail'][ii]} must contain 'calculate'",
                        yaml)
                calc = _compile_fn('target, annotations', calc, init)
                f = dict(calculate=calc, requires=reqs)
                fixed[ii] = f
            (fh,ft) = fixed
            # We have extracted the data now; go ahead and compile the filter.
            if filter is not None:
                filter = _compile_fn("target", filter, init)
            # Everything for this annotation is now processed; just set up its
            # Annotation object.
            annots[k] = Annotation(grid, filter, ctype, plot_opts, fh, ft)
        # And now all the annotations are processed.
        self.update(annots)
        self.all_figures = figs
        # Last thing to do is to make the annotation types dictionary.
        self.types = {k:v.type for (k,v) in self.items()}
_BuiltinAnnotationBase = namedtuple(
    '_BuiltinAnnotationBase',
    ('type', 'filter', 'data', 'plot_options', 'target', 'cache'),
    defaults=(None, []))
class BuiltinAnnotation(_BuiltinAnnotationBase):
    __slots__ = ()
    def __new__(cls, *args, **kw):
        return _BuiltinAnnotationBase.__new__(cls, *args, **kw)
    def __init__(self, *args, **kw):
        if self.cache is None:
            pass
        elif not isinstance(self.cache, list):
            raise ValueError("cache must be a list")
        elif len(self.cache) > 1:
            raise ValueError("cache must be an empty or 1-element list")
    def get_data(self, target=None):
        if target is None:
            target = self.target
            if target is None:
                raise ValueError("no target given to get_data")
        elif target != self.target:
            raise ValueError(f"builtin annotation target mismatch:"
                             f" {target} / {self.target}")
        if self.cache is not None:
            if len(self.cache) == 0:
                dat = self.data(target)
                self.cache.append(dat)
            else:
                dat = self.cache[0]
        else:
            dat = self.data(target)
        tmp = np.asarray(dat)
        if np.issubdtype(tmp.dtype, np.number):
            if len(tmp.shape) == 2:
                if tmp.shape[1] == 2:
                    return [tmp]
                else:
                    raise ValueError(
                        f"bad shape for builtin annotation: {tmp.shape}")
            elif len(tmp.shape) == 3:
                if tmp.shape[2] == 2:
                    return tmp
                else:
                    raise ValueError(
                        f"bad shape for builtin annotation: {tmp.shape}")
            else:
                raise ValueError(
                    f"bad shape for builtin annotation: {tmp.shape}")
        tmp = []
        for el in dat:
            el = np.asarray(el)
            if not np.issubdtype(el.dtype, np.number):
                raise ValueError("bad dtype for builtin annotation: {el.dtype}")
            elif len(el.shape) != 2 or el.shape[1] != 2:
                raise ValueError("bad shape for builtin annotation: {el.shape}")
            else:
                tmp.append(el)
        return tmp
    def with_target(self, targ):
        cache = self.cache if self.cache is None else []
        return BuiltinAnnotation(self.type, self.filter, self.data,
                                 self.plot_options, targ, cache)
class BuiltinAnnotationsConfig(dict):
    """An object that stores the configuration of the builtin annotations.

    The `BuiltinAnnotationsConfig` type tracks the contours and boundaries that
    are optionally drawn on the annotation targets for the `cortex-annotate`
    project.
    """
    __slots__ = ('types')
    def __init__(self, yaml, init):
        from ._core import AnnotationState
        # The yaml should just contain entries for the annotations.
        if yaml is None:
            yaml = {}
        if not isinstance(yaml, dict):
            raise ConfigError("builtin_annotations",
                              "builtin_annotations must contain a mapping",
                              yaml)
        # Go through and build up the lists of builtin annotation data.
        annots = {}
        for (k,v) in yaml.items():
            if not isinstance(v, dict):
                raise ConfigError(f"builtin_annotations.{k}",
                                  f"builtin annotation {k} must be a mapping",
                                  yaml)
            # Now just go through and parse the options.
            plot_opts = v.get('plot_options', {})
            if not isinstance(plot_opts, dict):
                raise ConfigError(
                    f"builtin_annotations.{k}", 
                    "builtin annotation plot_options must be mappings",
                    yaml)
            try: AnnotationState.fix_style(plot_opts)
            except Exception: raise#plot_opts = None
            if plot_opts is None:
                raise ConfigError(f"builtin_annotations.{k}",
                                  "invalid plot_options",
                                  yaml)
            ctype = v.get('type', 'points')
            if ctype not in ('lines', 'points'):
                raise ConfigError(
                    f"builtin_annotations.{k}", 
                    "type must be one of 'lines' or 'points'",
                    yaml)
            filter = v.get('filter', None)
            if filter is not None:
                if not isinstance(filter, str):
                    raise ConfigError(
                        f"builtin_annotations.{k}",
                        "filter must be null or a Python code string",
                        yaml)
                lines = [('    ' + ln) for ln in filter.split('\n')]
                code = "\n".join(lines)
                fnname = f"__fn_{os.urandom(8).hex()}"
                loc = init.exec(f"def {fnname}(target):\n{code}")
                filter = loc[fnname]
            data = v.get('data', None)
            if isinstance(data, str):
                # A code-block.
                data = _compile_fn("target", data, init)
            else:
                raise ConfigError(
                    f"builtin_annotations.{k}",
                    "data is required and must be a code-block string",
                    yaml)
            # Everything for this annotation is now processed; just set up its
            # Annotation object.
            annots[k] = BuiltinAnnotation(ctype, filter, data, plot_opts)
        # And now all the annotations are processed.
        self.update(annots)
        # Finally make the types dictionary.
        self.types = {k: v.type for (k,v) in self.items()}
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
    def _compile_figfn(code, initcode, termcode, initcfg):
        return _compile_fn(
            "target, key, figure, axes, figsize, dpi, meta_data",
            f"{initcode}\n{code}\n{termcode}",
            initcfg)
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
            wildfn = FiguresConfig._compile_figfn(wildcode, initcode, termcode,
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
                res[k] = FiguresConfig._compile_figfn(code, initcode, termcode,
                                                      init)
        # Same these into the dictionary.
        self.update(res)
class ReviewConfig:
    """An object that stores the configuration of the review panel.

    The `ReviewConfig` type stores information from the `review` section of the
    `config.yaml` file for the `cortex-annotate` project. This section stores
    only a function that generates the figure to plot in the `Review` tab of the
    display panel. The review function requires the arguments `target`,
    `annotations`, `figure`, and `axes`, and it must draw the desired graphics
    on the given matplotlib axes. The `annotations` argument is a dictionary
    whose keys are the annotation names and whose values are the drawn
    annotation. Annotations may be missing if the user opens the review tab
    before completing the annotations. If an error is raised from this function,
    then the error message is printed to the display.
    """
    __slots__ = ('code', 'function', 'figsize', 'dpi')
    @staticmethod
    def _compile(code, initcfg):
        return _compile_fn(
            "target, annotations, figure, axes, save_hooks",
            f"{code}\n",
            initcfg)
    def __init__(self, yaml, init):
        if yaml is None:
            self.code = None
            self.function = None
            self.figsize = None
            self.dpi = None
            return
        elif isinstance(yaml, str):
            yaml = {'function': yaml}
        elif not isinstance(yaml, dict):
            raise ConfigError(
                "review",
                "review section must contain a Python code string or a dict",
                yaml)
        self.code = yaml.get('function')
        if self.code is None:
            raise ConfigError(
                "review",
                "review section must contain the key function",
                yaml)
        self.figsize = yaml.get('figsize', (3,3))
        self.dpi = yaml.get('dpi', 256)
        self.function = ReviewConfig._compile(self.code, init)
class Config:
    """The configuration object for the `cortex-annotate` project.

    The `Config` class stores information about the configuration of the
    `cortex-annotate` project. The configuration is specified in the
    `config.yaml` file. Configuration objects store a single value per top-level
    config item in the `config.yaml` file. Additional top-level items that are
    not recognized by `Config` are not parsed, but they are available in the
    `Config.yaml` member variable.
    """
    __slots__ = (
        'config_path', 'yaml', 'display', 'init', 'targets', 'figures',
        'annotations', 'builtin_annotations', 'review', 'annotation_types')
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
        self.annotations = AnnotationsConfig(
            self.yaml.get('annotations', None),
            self.init)
        # Parse the builtin_annotations section.
        self.builtin_annotations = BuiltinAnnotationsConfig(
            self.yaml.get('builtin_annotations', None),
            self.init)
        # Parse the figures section.
        self.figures = FiguresConfig(
            self.yaml.get('figures', None),
            self.init,
            self.annotations.all_figures)
        # Parse the review section.
        self.review = ReviewConfig(self.yaml.get('review', None), self.init)
        # Make the annotation types dictionary.
        d = self.annotations.types.copy()
        d.update(self.builtin_annotations.types)
        self.annotation_types = d
