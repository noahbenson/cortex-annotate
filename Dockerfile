# This Dockerfile constructs a docker image that contains an installation
# of the cortex-annotate project for annotating cortical surfaces.
#
# Example build:
#   docker build --no-cache --tag cortex-annotate `pwd`
#
#   (but really, use `docker-compose up` instead).
#

# Configuration ################################################################

# Start with the python 3.10 Jupyter scipy-notebook docker-image.
FROM jupyter/scipy-notebook:python-3.10
# Note the Maintainer.
MAINTAINER Noah C. Benson <nben@uw.edu>


# The Root Operations ##########################################################

# The initial root operations are fast (making directories mostly), so we run
# them first; they are unlikely to fail or take any real time. Any COPY
# operations should come later on in the dockerfile after long-running layers
# have had an opportunity to fail (so that updates to the files don't force
# unrelated libraries to be reinstalled when building).
USER root
# Make some directories
RUN mkdir /cache \
 && mkdir /save \
 && mkdir /annotate \
 && mkdir /git \
 && mkdir /build \
 && chown $NB_USER /cache /save /annotate /git \
 && chmod 755 /cache /save /annotate /git
# Make sure we have a place to put the annotate library where it will be found.
RUN LPP="`python -c 'import site; print(site.getusersitepackages())'`" \
 && mkdir -p "$LPP" \
 && cd "$LPP" \
 && ln -s /annotate ./annotate
# Fix the ownership of the ipython directory.
RUN chown -R $NB_USER /home/$NB_USER/.ipython \
 && chmod 700 /home/$NB_USER/.ipython


# The User Operations ##########################################################

# First, do the stuff that takes a long time but doesn't depend on anything from
# the filesystem outside this Dockerfile. That way if we tweak the files, we
# won't usually have to rebuild these dependencies.
USER $NB_USER
# Install some stuff we are likely to need, including neuropythy.
RUN conda update -y -n base conda \
 && conda install -y nibabel s3fs \
 && conda install -y -cconda-forge ipywidgets pip jupyter_contrib_nbextensions \
 && pip install --upgrade setuptools \
 && pip install 'neuropythy >= 0.12.5' matplotlib
# Install collapsible cell extensions...
RUN jupyter contrib nbextension install --user \
 && jupyter nbextension enable collapsible_headings/main \
 && jupyter nbextension enable select_keymap/main
RUN mkdir -p /home/$NB_USER/.jupyter/custom
# Remove the work directory (we don't need it).
RUN rmdir /home/$NB_USER/work

# Now, do things that depend on the local files. COPY statements should go in
# this section rather than earlier when possible.
COPY docker/jupyter_notebook_config.py /home/$NB_USER/.jupyter/
COPY docker/custom.css                 /home/$NB_USER/.jupyter/custom/
COPY docker/custom.js                  /home/$NB_USER/.jupyter/custom/
COPY docker/ipython_kernel_config.py   /home/$NB_USER/.ipython/profile_default/
COPY docker/ipython-startup.py         /home/$NB_USER/.ipython/profile_default/startup/
COPY notebooks/annotate.ipynb          /home/$NB_USER/open_me.ipynb


# Custom Build Scripts #########################################################

# The last thing we do is run any custom build scripts. The root scripts get run
# first, then the user script.
USER root
COPY docker/build_root.sh /build/
RUN chmod 755 /build/build_root.sh
# Run the root script.
RUN /bin/bash /build/build_root.sh
# Then the user script.
COPY docker/build_user.sh /build/
RUN chmod 755 /build/build_user.sh
USER $NB_USER
RUN /bin/bash /build/build_user.sh


# Entrypoint ###################################################################

ENTRYPOINT ["tini", "-g", "--", "/usr/local/bin/start-notebook.sh"]
