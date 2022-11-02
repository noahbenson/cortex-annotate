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
pairs, and the snippet evaluates to its final expression.

Example:

```yaml
targets:
    subject:
        - sub001
        - sub002
        - sub003
    hemisphere:
        - LH
        - RH
    flatmap: |
        # Python code snippet to post-process a target; we use it to make a 
        # flatmap of the hemisphere.
        # Start by importing neuropythy.
        import neuropythy as ny
        # Get the freesurfer-subject object.
        sub = ny.freesurfer_subject(f'/subjects/{target['subject']}')
        # Extract the hemisphere.
        h = target['hemisphere'].lower()
        hem = sub.hemis[h]
        # Make a flatmap projection of the occipital cortex.
        ny.to_flatmap('occipital_pole', hem)
```


#### `images` (required)

TBD


#### `annotations` (optional)

TBD


#### `` (optional)
