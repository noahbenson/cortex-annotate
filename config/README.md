# Configuration Directory for the Docker Container

This directory is a placeholder for configuration information for the
cortex-annotate project. When running the cortex-annotate docker container, this
directory is automatically mapped to the directory `/config` inside of the
running docker container. In order to create an annotation project, you should
put a file `<PROJECT>.json` where `<PROJECT>` should be the name of the
annotation project; additional files required for the project can be placed in a
directory named `<PROJECT>`. For example, to make a project for annotating the
[NSD dataset](http://naturalscenesdataset.org/), you might want to make a file
`NSD.json` along with the subdirectory `NSD/` containing python scripts for
generating the images on which raters can annotate contours and boundaries.

