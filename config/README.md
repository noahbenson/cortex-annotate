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
  be run when the docker image when the annotate tool is built. The commands in
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
  `cortex-annotate` project. The format specification of this file is detailed
  below.
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


### General Principles

#### Python Code Snippets

The `config.yaml` file frequently expects that entries in the file will contain
strings that are interpreted as Python code snippets. These code snippets are
generally compiled as the bodies of Python functions with specificly named
parameters. For example, the parameter name `target` is used by most such code
snippets to represent the data for the annotation target currently selected by
the annotation tool's user. The return values of these code snippets are used by
the `cortex-annotate` tool in various ways depending on the specific code
snippet.

#### Paths and Runtime

It is important to remember that these code snippets will generally be run
inside of the docker container that is used to run the Jupyter notebook that
runs the annotation tool. Accordingly, paths should generally be absolute within
the docker image. The following directories are provided automatically:
 * `/cache` is a cache directory that maps to the `cache` directory of the
   `cortex-annotate` repository. It can be used for storing temporary files (but
   note that the user may clean these out between runs of the docker).
 * `/config` is mapped to the `config` directory of the repository.
 * `/save` is mapped to the `save` directory of the repository (note that save
   files are usually managed by `cortex-annotate` so it should not generally be
   necessary to interact with this directory directly).
 * `/src` is mapped to the `src` directory of the repository. In particular,
   this can be used to hold Python library code that one wants to run but does
   not want to store in the `config.yaml` file.

#### Including External Python Code

It is often the case that one prefers to write Python code in Python code files
and libraries rather than in the `config.yaml` file. This can be accomplished by
putting code in the repository's `src` directory. This directory is always
mounted inside of the running docker container that serves the Jupyter notebook
as `/src` and is always put on the `PYTHONPATH` environment
variable. Accordingly, any library directory in the `src` directory can be
imported and run by code in the `config.yaml` file.


### Top Level Configuration Keys

The contents of the `config.yaml` file must parse into a Python `dict` object
whose allowed keys are documented in this section.

#### `init` (optional)
The `init` key is optional; if it is provided, then it must be mapped to a
string, which is intrpreted as a Python code snippet. Unlike other code snippets
in the `config.yaml` file, this code snippet is not compiled into a function and
thus should not have a return value. Instead, this code snippet is run in the
global namespace, and variables declared here are made available to all other
code snippets in the file. In general, this section is used to initialize code
or data that is used throughout the config file.

**Example**. The following `yaml` block contains example initialization code for
the Natural Scene Dataset (NSD). The entire `config.yaml` file for the NSD can
be found in the `NSD` branch of the `cortex-annotate` repository.

```yaml
init: |
  # Several code-blocks in this config.yaml file use the numpy and neuropythy
  # libraries, so we load them here.
  import numpy as np
  import neuropythy as ny
  # We also want to create an object that tracks the S3 path/data for the NSD.
  # We use the cache path '/cache/nsd' because the /cache directory is always
  # abailable for use with cache files inside of the docker container that runs
  # the annotation tool.
  nsd_path = ny.util.pseudo_path(
      's3://natural-scenes-dataset/nsddata/',
      cache_path='/cache/nsd')
  # We will specifically load these population receptive fields (pRF) files in
  # order to draw visual area annotations on the retinotopic maps for each
  # subject.
  nsd_prf_files = {
      "polar_angle": "prfangle.mgz",
      "eccentricity": "prfeccentricity.mgz",
      "cod": "prfR2.mgz"}
  # This occipital pole mask is used with neuropythy's flatmap code; the tuple
  # indicates that the FreeSurfer parcellation property uses the value 43 to
  # indicate the occipital pole of the brain.
  occpole_mask = ('parcellation', 43)
```

#### `targets` (required)
The `targets` key must contain instructions for what objects can be selected for
annotation. In this context, "objects" are typically individual hemispheres from
a dataset, as identified by subject ID and hemisphere name (`"lh"` or `"rh"`),
but this is not enforced. A dataset could, for example, define individual
targets to be different ROIs or different views of a hemisphere. The annotations
(contours or boundaries) that are to be placed on a target are defined in the
`annotations` section while the images that are displayed when a target is
selected, onto which the annotations are drawn, are defined in the `images`
section.

The contents of the `targets` section should be a mapping itself. Each key of
this mapping will become either a single drop-down menu in the annotation tool,
used for selecting the annotation target, or will become a piece of meta-data
associated with the chosen target. For any target key that is to become a
dropdown menu, the key must be mapped to a list of concrete string or number
values. If this list of concrete values contains only one element, then the key
is not shown in the annotation tool (but the single value is included in the
target selection nonetheless).  Alternatively, if a a target key is mapped to a
single string (which may be a multi-line string but not a list of strings), then
it is treated as a Python code snipped. Such a snippet is compiled into a
function with a single parameter `target` which is always a Python `dict`
containing all the target data above it in the `targets` section. For example,
the following `targets` section first defines a `Subject ID`, which becomes a
dropdown menu in the annotation tool from which the user selects a subject; the
target key after the `Subject Name` is the `subject_id` key, and because it maps
to a multi-line string instead of a list, it is treated as a code-snippet that
extracts the integer identifier for the chosen subject. The return value of this
code-snippet/function becomes part of the `target` data (`target['subject_id']`)
that is used throughout the tool.

```yaml
targets:
  Subject Name:
    - Subject 1
    - Subject 2
    - Subject 3
  subject_id: |
    # Get the selected Subject Name
    sid = target['Subject Name']
    # Transform this id into an integer identifier.
    sid_int = int(sid.split()[1])
    # This integer is the subject_id:
    return sid_int
```

Any code snippet in the `targets` section is passed a single parameter:
`target`, which is a dictionary containing all of the target keys that precede
the code snippet. These keys are mapped to either the entry that was chosen by
the user (for keys that map to lists, such as `Subject Name` in the example
above) or to the return value of the key's code snippet (for keys that map to
strings, such as `subject_id` in the example above). In Python code snippets
that appear in other sections in this file, the target data is also provided as
a local variable `target` containing `dict`-like object of all the target keys
mapped to their selected or calculated values. If a key in the `targets` section
is mapped to a list with only one element, then that element is not included in
the selection panel of the annotation tool, but it is included in the `target`
dict of code snippets.


**Example**: the following `yaml` block demonstrates how target data can be
prepared for the Natural Scene Dataset (NSD). The entire `config.yaml` file for
the NSD can be found in the `NSD` branch of the `cortex-annotate` repository.

```yaml
# We assume in this example that the libraries neuropythy and numpy have been
# imported (as ny and np respectively) in the init section (see below).
targets:
  # The NSD contains 8 subjects, listed below. The 'Subject ID' entry will be
  # a dropdown menu in the annotation tool because it is a list of multiple
  # choices rather than a code-block or a list with a single entry.
  Subject ID:
    - subj01
    - subj02
    - subj03
    - subj04
    - subj05
    - subj06
    - subj07
    - subj08
  # The 'subject' entry is a multi-line string, so it is interpreted as a Python
  # code snippet. This snippet is compiled into a function whose parameter list
  # contains only the variable `target`. The `target` will be a dictionary with
  # the target data above the subject, so in this case only the 'Subject ID'.
  subject: |
    # Get the subject ID that the user chose from the above selection list.
    sid = target['Subject ID']
    # Find a sub-path for the subject's FreeSurfer directory; we get the
    # nsd_path variable from the `init` section of the config.yaml file; see
    # above.
    fs_path = nsd_path.subpath('freesurfer', sid)
    # Load and return a FreeSurfer subject object for this path.
    return ny.freesurfer_subject(fs_path)
  # The 'Hemisphere' is a choice for the user; as a list of two options, it will
  # appear as a dropdown meny with these two options in the annotation tool.
  Hemisphere:
    - LH
    - RH
  # We will want to include the Wang et al. (2015) probabilistic visual area
  # atlas as an optional annotation that users can turn on and off (see the
  # `builtin_annotations` section, below). This element of the target section
  # loads the Wang atlas and applies it to the subject we are workign with.
  wang15: |
    import neuropythy.commands as nycmd, os
    # Grab the subject object that was loaded in the 'subject' section.
    sub = target['subject']
    # We also need to know the hemisphere name.
    h = target['Hemisphere'].lower()
    # Get the subject's cache-path; this is tracked by neuropythy.
    subpath = sub.pseudo_path.cache_path
    # Possibly, this atlas has already been applied to this subject; if so, we
    # don't need to (re-)run neuropythy's atlas command (which applies the atlas
    # to the subject and saves it as a file).
    wangpath = os.path.join(subpath, 'surf', f'{h}.wang15_mplbl.mgz')
    if not os.path.isfile(wangpath):
        # Make sure the fsaverage-alignment has already been loaded into cache;
        # because the atlas command operates on the filesystem while the subject
        # and cache path load things lazily, we need to make sure these have
        # already been downloaded before we run the command.
        sub.hemis['lh'].surface('fsaverage')
        sub.hemis['rh'].surface('fsaverage')
        # Now run the atlas command.
        nycmd.atlas.main(["-awang15", "-fmgz", subpath])
    # Load and return the file.
    return ny.load(wangpath)
  # The 'cortex' key in the target data is for the cortical surface object,
  # which is managed and loaded by neuropythy from the subject's FreeSurfer
  # object. Note that the 'cortex' entry is like the 'subject' entry in that it
  # is compiled into a function whose only parameter is a dict object called
  # `target`, but because it is farther down in the target section, the `target`
  # parameter will contain entries for 'Subject ID', 'subject', and 'Hemisphere'
  # from the sections above.
  cortex: |
    # Extract the subject object and the hsmisphere name.
    sub = target['subject']
    h = target['Hemisphere'].lower()
    # Load retinotopic mapping data from the label directory, where these data
    # are stored on the NSD repository.
    label_path = nsd_path.subpath('freesurfer', sid, 'label')
    props = {
        k: ny.load(label_path.subpath(f'{h}.{filename}'))
        for (k,filename) in nsd_prf_files.items()}
    # Convert the polar angle into Neuropythy's "visual" format (i.e., 0 degrees
    # is the upper vertical meridian, 90 degrees is the right horizontal
    # meridian, and -90 degrees is the left horizontal meridian.
    ang = props['polar_angle']
    props['polar_angle'] = np.mod(90 - ang + 180, 360) - 180
    # Add the Wang et al. (2015) atlas, loaded in the above 'wang15' section.
    props['wang15'] = target['wang15']
    # Grab the appropriate coretx/hemisphere object.
    cortex = sub.hemis[h]
    # Finally, return that hemisphere object with the properties associated with
    # it (this is Neuropythy's typical modus operandi for adding properties to
    # existing objects: make a copy with the properties attached).
    return cortex.with_prop(props)
  # Finally, we include a 'flatmap' entry of the `targets` section in order to
  # create a flattened projection of the hemisphere for annotation. We use the
  # `mask_flatmap` method of the cortex/hemisphere object in order to create a
  # projection of the inflated native surface that is centered on the occipital
  # pole. This uses the `occpole_mask` defined in the `init` section above.
  flatmap: |
    cortex = target['cortex']
    return cortex.mask_flatmap(occpole_mask, map_right='right', radius=np.pi/2)
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
