# -*- coding: utf-8 -*-
################################################################################
# docker/ipython-startup.py
#
# IPython startup script. This code is run when the Jupyter kernel has started,
# so any basic initialization code should go here.


# Set up the save directory ####################################################

# This is a hack to pull the github username out of the git directory and put it
# where the AnnotationTool can find it.
def _init_save_path():
    import os
    git_username = os.popen("grep 'url = https://github.com/' /git/config")
    git_username = git_username.read()
    git_username = git_username.split('github.com/')[-1].split('/')[0]
    if git_username is None or git_username == '':
        git_username = os.popen("grep 'url = git@github.com:' /git/config")
        git_username = git_username.read()
        git_username = git_username.split('github.com:')[-1].split('/')[0]
    os.environ['GIT_USERNAME'] = git_username
    # Make sure there is a directory for this user to save into.
    save_path = f'/save/{git_username}'
    if not os.path.isdir(save_path):
        os.makedirs(f'/save/{git_username}', mode=0o775)
    os.environ['ANNOTATE_SAVE_PATH'] = save_path
    return save_path
_init_save_path()


# Set up the PYTHONPATH ########################################################

# This code ensures that /condig/src, if it exists, is on the python path.
def _init_pythonpath():
    import sys, os
    src_path = '/src'
    if src_path not in sys.path and os.path.isdir(src_path):
        sys.path.append(src_path)
    return None
_init_pythonpath()
