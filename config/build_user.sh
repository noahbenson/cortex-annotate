#! /bin/bash
################################################################################
# build_user.sh
# This file is a placeholder for any commands that should be run when the docker
# image for the annotate tool is built. The commands in this file are run by the
# $NB_USER user inside the docker-image after all other parts of the build
# process including the build_root.sh script, also in this directory. The
# $NB_USER user is the default user inside the docker-image and isn't generally
# important.
# You do not need to do anything to this script, but if you need to install
# something or configure something during the docker build process, you can put
# the required commands in this file instead of editing the Dockerfile directly.

