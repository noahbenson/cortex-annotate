# Configuration Directory for the Docker Container

This directory is a placeholder for configuration information for the
cortex-annotate project. When running the cortex-annotate docker container, this
directory is automatically mapped to the directory `/config` inside of the
running docker container. In order to create an annotation project, you should
only need to edit files in this directory, primarily the `config.yaml`
file. (Additionally, you may need to put additional Python code in the `/src`
directory; see the `/src/README.md` file.)


## Directory Contents ##########################################################

* **`build_root.sh`**: This file is a BASH script for any commands that should
  be run when the docker image for the annotate tool is built. The commands in
  this file are run by the root user inside the docker-image after all other
  parts of the build process except for the `build_user.sh` script, also in this
  directory. When possible, it is recommended that one use the user version of
  this script instead of the root version.
* **`build_user.sh`**: This file is a BASH script that is run when the docker
  image for the annotate tool is built. The commands in this file are run by the
  `$NB_USER` user inside the docker-image after all other parts of the build
  process including the `build_root.sh` script, also in this directory. The
  `$NB_USER` user is the default user inside the docker-image and isn't
  generally important.
* **`config.yaml`**: This is the primary configuration file for the annotation
  tool. This is the primary file that must be edited in order to have a viable
  `cortex-annotate` project. The format specification of this file is below.
* **`requirements.txt`**: This file is a simple PyPI-style requirements file
  with one Python library requirement listed per line. These requirements are
  automatically installed when the docker image is built.

Note that if you need to include custom Python code in the docker container for
use in the `config.yaml` Python snippets, you should include it in the `/src`
directory (where the `annotate` library lives); any library in this directory is
put on the `PYTHONPATH` while running the annotation tool so is available for
import.


## The `config.yaml` File ######################################################

The `config.yaml` file is a basic configuration file for the `cortex-annotate`
tool. It must parse into a mapping (`dict`) at the top level. This section
describes the format of the configuration file and provides examples.


### Top Level Configuration Keys

The contents of the `config.yaml` file must parse into a Python `dict` object
whose allowed keys are documented in this section.


#### `targets` (required)

The `targets` key must contain instructions for what objects can be selected for
annotation. In this context, "objects" are typically individual hemispheres from
a dataset, as identified by subject ID and hemisphere name (`"lh"` or
`"rh"`). The annotations that are to be placed on an object and the images that
are rendered for annotation are defined in the `annotations` and `images`
section; the targets of annotation are usually the hemispheres.

The contents of the `targets` section should be a mapping itself; each key of
the mapping will become a single drop-down menu in the annotation tool for
selectign the annotation target and thus must usually be a list of concrete
string or number values. In Python code snippets that are provided elsewhere in
this file, the target data is provided as a local variable `target` containing a
mapping object (a `dict`-like object) of the target keys mapped to their
selected values. If a key is mapped to a list with only one element, then that
element is not included in the selection panel of the annotation tool, but it is
included in the `target` dict of code snippets.

Additionally, a key in the `targets` section whose value is a string is treated
as a Python code snippet that is run to produce the actual value for the given
key. Such keys are called *lazy* keys (as opposed to *concrete* keys whose
values must be lists), and they do not appear in the selection panel of the
annotation tool. However, they are available in other code snippets throughout
the configuration file. When a lazy ekey's code snippet is run, it has access to
a local variable `target`, which is a `dict` object of the concrete key-value
pairs, and the snippet evaluates to its return value (i.e., you must include a
`return` statement or the block evaluates to `None`).

Example:

```yaml
# We assume in this example that the libraries neuropythy and numpy have been
# imported (as ny and np respectively) in the init section (see below).
targets:
    # The subject ID is selectable because there are 3 of them.
    subject:
        - sub001
        - sub002
        - sub003
    # The nysubject item is a code snippet that loads a neuropythy Subject
    # object, which we will need for generating images.
    # This code block assumes that the `init` section defined the
    # `subject_path` variable.
    nysubject: |
        subj = target['subject']
        return ny.freesurfer_subject(f'{subject_path}/{subj}')
    # The hemisphere is another selectable item because there are 2 of them.
    hemisphere:
        - LH
        - RH
    # Cortex, which has a string, is again a lazy value defined by a code
    # snippet. This snippet extracts the Cortex object for the selected
    # hemisphere.
    cortex: |
        h = target['hemisphere'].
        return target['nysubject'].hemis[h]
    # Additionally, we create a flatmap projection for the hemisphere. Here we
    # make a projection of the occipital cortex.
    flatmap: |
        # Start by importing neuropythy.
        # Make a flatmap projection of the occipital cortex.
        return ny.to_flatmap('occipital_pole', target['cortex'])
    # Finally, it's useful to have information about the image coordinates in
    # the target data, so we add these.
    xlim: |
        x = target['flatmap'].coordinates[0]
        return (np.min(x), np.max(x))
    ylim: |
        y = target['flatmap'].coordinates[1]
        return (np.min(y), np.max(y))
```


#### `annotations` (required)

The `annotations` section details the individual contours and boundaries that
are to be annotated on the cortical surfaces. Both the `contours` and
`boundaries` section have the same format, but `contours` are intended to be
lines and curves while `boundaries` are intended to be closed loops. Both kinds
of annotations are treated identically except that boundaries are always
automatically closed (the first point is always appended to the boundary
points).

Both of the `contours` or `boundaries` subsections must contain mappings, and
the keys are the names of the contours or boundaries that are to be drawn on
each target (i.e., the names of the annotations). Each of these annotations'
sections must either be a list or a mapping as well. If the section is a list,
then it is equivalent to a mapping whose only key is `grid` and whose other keys
take the default value. Otherwise, a given annotation section must be a mapping
whose keys may include `grid`, `filter`, `plot_options`, and `fg_options`:
* **`grid`** is the grid of figures that is to be displayed while annotating. If
  a single list (as opposed to a matrix) is provided, then it is assumed to be a
  row. Elements of the `grid` must either be figure names or `null`.
* **`filter`** is a code-snippet that must return either `True` or `False`
  depending on whether the annotation is enabled for the given `target`. By
  default, this is equivalent to `return True`.
* **`plot_options`** is a mapping of display options for the annotation when it
  is not the selected annotation. The keys in this section may be any viable
  optional argument for the `matplotlib.pyplot.plot` function. See also the
  root-scope `plot_options` section, below.
* **`fg_options`** is a mapping of display options, like `plot_options` that
  specifies the display options for the annotation when it is the selected
  annotation. Any key that does not appear here defaults to its value in either
  the local-scope or the global-scope `plot_options` key, if provided. In other
  words, if the global `plot_options` specifies a `linewidth` of 2, the
  annotation's `options` specify a `markersize` of 3 and a color of `[1,0,0]`,
  and the annotation's `fg_options` specifies a color of `[1, 0.5, 0.5]`, then
  the `fg_options` is equivalent to having a `linewidth` of 2, a `markersize` of
  3, and a color of `[1, 0.5, 0.5]`.

Example:

```yaml
# When annotating V1-V3 using retinotopic maps; we need contours for the
# periphery and for V1, V2, and V3 boundaries. When drawn like this, they are
# all simple contours (not boundaries).
annotations:
    # The grids of images we want to show when annotating each contour 
    # (see images section below).
    contours:
        periphery:
            - ["polar_angle", "eccentricity"]
            - ["curvature", "highlight_periphery"]
        V1 boundary:
            - ["polar_angle", "eccentricity"]
            - ["curvature", "highlight_vm"]
        V2 boundary:
            - ["polar_angle", "eccentricity"]
            - ["curvature", "highlight_hm"]
        V3 boundary:
            - ["polar_angle", "eccentricity"]
            - ["curvature", "highlight_vm"]
    # Additionally, sub001 has a lesion that we want to draw a boundary around.
    boundaries:
        lesion:
            # We only want this boundary to appear for sub001, right hemisphere.
            filter: |
                if   target['subject'] != 'sub001': return False
                elif target['hemisphere'] != 'RH': return False
                else: return True
            # We want this boundary to appear dark red when not selected.
            plot_options:
                color: [0.6, 0, 0]
            # And we want it to be thick and bright red when selected.
            fg_options:
                color: [1, 0.2, 0.2]
                linewidth: 2
            grid: [["cod", "curvature"]]
```


#### `figures` (required)

The `figures` section provides code for drawing the images that are to be used
in annotation. The `figures` section must contain one entry for each of the grid
image names that appear in the `annotation` sections; for example, in order to
be valid for the example `annotations` section given above, the `figures`
section would have to include entries for `polar_angle`, `eccentricity`,
`curvature`, `highlight_periphery`, `highlight_vm`, `highlight_hm`, and
`cod`. Each entry of these entries must be a Python code snippet that draws the
matplotlib figure on which annotations are to be drawn. Note that annotation
coordinates are converted into the coordinates of this figure (not the pixel
coordinates of the cached/displayed image). Within each of these code snippets,
the local variables `figure` (a matplotlib figure object), `axes` (an axes
object), `figsize` (the figure size in inches, see `images` section), `dpi` (the
number of pixels per inch), `key` (the name of the annotation), and
`target`. The code snippet must draw the image on the given axes (it is not
important what the code snippet returns so long as the figure has been correctly
drawn).

Alternately, the `figures` section may be a single Python code snippet, in which
case, it is called given all of the local variables listed in the above
paragraph. The variable `key`, specifically, is useful in this case as it gives
the name of the figure that is to be generated (e.g., `"polar_angle"`).

Similarly, the two use-cases described in the two paragraphs above can be
combined; if the `figures` section is not a single code snippet, then it may
optionally include the special key `_`, which is treated as a fallback code
snippet for any annotation name not explicitly included. In fact, a `figures`
section that contains a code snippet is equivalent to a `figures` section that
contains only the entry `_` mapped to the same code snippet.

Finally, there are two special keys in the `figures` section: `init` and
`term`. The `init` block is prepended to all the other blocks (including the `_`
block but not the `term` block), and the `term` block is similarly appended to
all other blocks.

Example:

```yaml
figures:
    # We don't really need an init block, but to demonstrate it, we use it to
    # set a local value for the maximum stimulus eccentricity. 
    init: |
        max_eccen = 10
    # We want to make sure the images all have the xlim and ylim set correctly.
    term: |
        axes.set_xlim(target['xlim'])
        axes.set_ylim(target['ylim'])
    # The highlight images need some specific code to plot correctly.
    highlight_vm: |
        prf_x = target['flatmap'].prop('prf_x')
        ny.cortex_plot(target['flatmap'], color=np.abs(prf_x), axes=axes,
                       cmap='hot', vmax=0, vmin=2)
    highlight_hm: |
        prf_y = target['flatmap'].prop('prf_y')
        ny.cortex_plot(target['flatmap'], color=np.abs(prf_y), axes=axes,
                       cmap='hot', vmax=0, vmin=2)
    highlight_periphery: |
        prf_ecc = target['flatmap'].prop('prf_eccentricity')
        highlight = np.abs(max_eccen - prf_ecc) # max_eccen was set in init.
        ny.cortex_plot(target['flatmap'], color=highlight, axes=axes,
                       cmap='hot', vmax=0, vmin=2)
    # The curvature is very straightforward.
    curvature: |
        ny.cortex_plot(target['flatmap'])
    # The rest are PRF properties.
    _: |
        prop = 'prf_' + key
        ny.cortex_plot(target['flatmap'], color=prop, axes=axes)
```


#### `display` (optional)

The `display` section contains simple configuration information about the images
that are to be produced and the plotting style for annotations. The keys that
may appear in this section are `plot_options` (see below), `fg_options` (see
below), `figsize` (default: `[8,8]`), which should be the size of the image in
inches, and `dpi` (default: `128`), which should be the number of dots per
inch. The size of the image in pixels is the `figsize` times the `dpi`.

The `plot_options` and `fg_options` keys must map to additional mappings that
specify the options for the `matplotlib.pyplot.plot` function when drawing
annotations that are either currently unselected (`plot_options`) or that are
currently selected (`fg_options`). See the `annotations` section for more
information on the contents of these sections. The `fg_options` inherits values
from the `plot_options` mapping.

Example:

```yaml
display:
  # We want images to be 512 x 512 pixels.
  figsize: [4, 4]
  dpi: 128
  # By default, we want annotations to appear dark bluish with fairly thin lines
  # when not selected. We don't want unselected annotations to have points.
  plot_options:
    color: [0.25, 0.25, 0.65]
    linewidth: 1
    markersize: 0
    linestyle: "-"
  # We want selected annotations to be brighter and with markers/points plotted.
  # We can keep the same linewidth and linestyle as in plot_options.
  fg_options:
    color: [0.5, 0.5, 1]
    markersize: 2
```


#### `init` (optional)

The `init` section may optionally contain a Python code snippet that is run
prior to any other code snippet from the `config.yaml` file. All local and
global variables that result from this code snippet are made available to other
code snippets as local and/or global variables. This snippet should not return a
value.

Example:

```yaml
init: |
    import neuropythy as ny, numpy as np
    subject_path = "/cache/subjects"
```
