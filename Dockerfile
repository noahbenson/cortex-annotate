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
 && mkdir /config \
 && mkdir /data \
 && mkdir -p /data/freesurfer/subjects \
 && mkdir -p /data/required_subjects \
 && mkdir -p /data/hcp/subjects \
 && mkdir -p /data/hcp/lines \
 && mkdir -p /data/hcp/meta \
 && chown -R $NB_USER /cache /save /annotate /git /config /data \
 && chmod -R 755 /cache /save /annotate /git /config /data
# Make sure we have a place to put the annotate library where it will be found.
RUN LPP="`python -c 'import site; print(site.getusersitepackages())'`" \
 && mkdir -p "$LPP" \
 && cd "$LPP" \
 && ln -s /annotate ./annotate
# Fix the ownership of the .ipython and .local directory if needed.
RUN [ -d /home/$NB_USER/.ipython/jupyter ] \
 || mkdir -p /home/$NB_USER/.ipython/jupyter
RUN [ -d /home/$NB_USER/.ipython/profile_default ] \
 || mkdir -p /home/$NB_USER/.ipython/profile_default
RUN chown -R $NB_USER /home/$NB_USER/.ipython \
 && chmod 700 /home/$NB_USER/.ipython
RUN [ -d /home/$NB_USER/.local ] \
 || mkdir /home/$NB_USER/.local
RUN chown -R $NB_USER /home/$NB_USER/.local 

# Next, we want to make sure that we have an fsaverage and an fsaverage_sym
# subject for neuropythy to use if needed.
# Download the required FreeSurfer subjects.
RUN apt-get update \
 && apt-get install --yes --no-install-recommends curl
RUN curl -L -o /data/required_subjects/fsaverage.tar.gz \
      https://github.com/noahbenson/neuropythy/wiki/files/fsaverage.tar.gz \
 && cd /data/required_subjects \
 && tar zxf fsaverage.tar.gz \
 && rm fsaverage.tar.gz
RUN curl -L -o /data/required_subjects/fsaverage_sym.tar.gz \
      https://github.com/noahbenson/neuropythy/wiki/files/fsaverage_sym.tar.gz \
 && cd /data/required_subjects \
 && tar zxf fsaverage_sym.tar.gz \
 && rm ./fsaverage_sym.tar.gz


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


# Copy User Files ##############################################################

user $NB_USER
# Now, do things that depend on the local files. COPY statements should go in
# this section rather than earlier when possible.
COPY docker/jupyter_notebook_config.py /home/$NB_USER/.jupyter/
COPY docker/custom.css                 /home/$NB_USER/.jupyter/custom/
COPY docker/custom.js                  /home/$NB_USER/.jupyter/custom/
COPY docker/ipython_kernel_config.py   /home/$NB_USER/.ipython/profile_default/
COPY docker/ipython-startup.py         /home/$NB_USER/.ipython/profile_default/startup/
COPY docker/npythy.json                /home/$NB_USER/.npythy.json
COPY notebooks/annotate.ipynb          /home/$NB_USER/work/open_me.ipynb
# We want to trust the notebook (this also fixed id-less cells).
RUN jupyter trust /home/$NB_USER/work/open_me.ipynb
# Finaly, copy over the annotate library.
COPY annotate/ /annotate/


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


# Permission Cleanup ###########################################################

# We need to fix the permissions for anything created in the meantime.
USER root
RUN fix-permissions /home/$NB_USER/.ipython


# Entrypoint ###################################################################

USER $NB_USER
ENTRYPOINT ["tini", "-g", "--", "/usr/local/bin/start-notebook.sh"]
