# -*- coding: utf-8 -*-
################################################################################
# cortexannotate/prfs.py

"""Tools and utilities for annotating population receptive field data.

Currently this namespace contains only tools specifically for annnotating
datasets that are in BIDS format and that have been processed with the PRFModel
module prfanalyze-vista (see https://github.com/vistalab/PRFmodel). If you have
a BIDS dataset processed by this tool, you can use the `annotate_prfs` function
with the `prf_format` option set to `'prfanalyze-vista'`.
"""


# Dependencies #################################################################

import os
from pathlib import Path

import numpy as np
import nibabel as nib


# Global Values ################################################################

occpole_mask = ('parcellation', 43)
annotate_prfs_visual_areas_default = dict(
    V1=1,
    V2=2,
    V3=3,
    hV4=4,
    VO1=5,
    VO2=6,
    V3A=7,
    V3B=8,
    LO1=9,
    IPS0=10)


# prfanalyze-vista Functions ###################################################

def _find_bids_surfpath(bids_path, surface_format, surface_path):
    if surface_path is not None:
        if surface_format is None:
            raise ValueError(
                "surface_format must be supplied if surface_path is supplied")
    der_path = bids_path / 'derivatives'
    src_path = bids_path / 'sourcedata'
    surf_path = None
    if isinstance(surface_format, str):
        fmt = surface_format.lower()
        fmt = {'freesurfer':'fs', 'hcppipelines':'hcp'}.get(fmt, fmt)
    elif surface_format is None:
        fmt = None
    else:
        raise ValueError("surface_format must be None, 'freesurfer', or 'hcp'")
    if surface_path is None:
        if fmt == 'fs' or fmt is None:
            if (der_path / 'freesurfer').is_dir():
                surface_path = der_path / 'freesurfer'
            elif (src_path / 'freesurfer').is_dir():
                surface_path = src_path / 'freesurfer'
            if surface_path is not None:
                fmt = 'fs'
        if surface_path is None and (fmt == 'hcp' or fmt is None):
            if (der_path / 'HCPpipelines').is_dir():
                surface_path = der_path / 'HCPpipelines'
            elif (src_path / 'HCPpipelines').is_dir():
                surface_path = src_path / 'HCPpipelines'
            if surface_path is not None:
                fmt = 'hcp'
        if surface_path is None:
            raise ValueError("could not deduce surface data type")
    else:
        surface_path = Path(surface_path)
        if not surface_path.is_dir():
            raise ValueError("given surface_path is not a directory")
    return (fmt, surface_path)
def _find_subject_list(data_path,
                       prf_format='prfanalyze-vista',
                       subjects=None):
    data_path = Path(data_path)
    if subjects is None:
        subjects = []
        for path in data_path.iterdir():
            if not path.name.startswith('sub-') or not path.is_dir():
                continue
            subjects.append(sub.name)
    subjects = list(subjects)
    for (ii,sid) in enumerate(subjects):
        if not sid.startswith('sub-'):
            sid = 'sub-' + sid
            subjects[ii] = sid
        if not (data_path / sid).is_dir():
            raise RuntimeError(f"no subject directory found: {data_path / sid}")
    return subjects
def _find_prfanalyze_vista_path(bids_path, prf_format):
    from collections import defaultdict
    data_path = Path(bids_path) / 'derivatives' / 'prfanalyze-vista'
    if not data_path.is_dir():
        raise RuntimeError("prfanalyze-vista derivatives directory not found")
    prf_format = prf_format.lower()
    if prf_format == 'prfanalyze-vista':
        anals = [p for p in data_path.iterdir() if p.name.startswith('analysis-')]
        if len(anals) == 0:
            raise ValueError("could not deduce prfanalyze-vista analysis id")
        elif len(anals) > 1:
            raise ValueError("found multiple prfanalyze-vista analyses")
        data_path = anals[0]
        analysis = data_path.name
    elif prf_format.startswith('prfanalyze-vista/'):
        data_path = data_path / prf_format[17:]
        if not data_path.is_dir():
            raise ValueError(f"data path not found: {data_path}")
        if data_path.name.startswith('analysis-'):
            analysis = data_path.name
        else:
            analysis = None
    else:
        raise ValueError(f"invalid prfanalyze-vista prf_format: {prf_format}")
    return (data_path, analysis)
def _find_prfanalyze_vista_targets(prf_path, result={}):
    prf_path = Path(prf_path)
    for p in prf_path.iterdir():
        if p.name.startswith('.'):
            pass
        elif p.is_dir():
            _find_prfanalyze_vista_targets(p, result=result)
        elif p.name.endswith('_r2.nii.gz'):
            tags = p.name[:-10]
            x0 = prf_path / (tags + '_centerx0.nii.gz')
            y0 = prf_path / (tags + '_centery0.nii.gz')
            if x0.is_file() and y0.is_file():
                result[tags] = prf_path
    return result
def _load_prfanalyze_vista_prfs(prf_path, tag, invert_y=True):
    path = Path(prf_path)
    x0 = path / (tag + '_centerx0.nii.gz')
    y0 = path / (tag + '_centery0.nii.gz')
    r2 = path / (tag + '_r2.nii.gz')
    files = dict(
        x=np.squeeze(nib.load(os.fspath(x0)).dataobj),
        y=np.squeeze(nib.load(os.fspath(y0)).dataobj),
        r2=np.squeeze(nib.load(os.fspath(r2)).dataobj))
    if invert_y:
        files['y'] = - files['y']
    return files
def _make_prfanalyze_vista_config(file, targets,
                                  surf_path, surf_format, prf_path,
                                  invert_y, visual_areas):
    from os import fspath
    surffn = 'freesurfer_subject' if surf_format == 'fs' else 'hcp_subject'
    display_block = f'''
    display:
      figsize: [4, 4]
      dpi: 128
      plot_options:
        color: [0.25, 0.25, 0.75]
        linewidth: 1
        markersize: 1
        linestyle: "solid"
      fg_options:
        color: [0.55, 0.55, 0.9]
        markersize: 2'''
    init_block = f'''
    init: |
      # Several code-blocks in this config.yaml file use the numpy and neuropythy
      # libraries, so we load them here.
      import os
      import numpy as np
      import neuropythy as ny
      from pathlib import Path
      from cortexannotate.prfs import (occpole_mask, _load_prfanalyze_vista_prfs)
      # The (FreeSurfer or HCP) path we get surface-based data from.
      surfdata_path = Path("{fspath(surf_path)}")
      prfdata_path = Path("{prf_path}")
      target_paths = { {k: str(v) for (k,v) in targets.items()} }
      # The visual areas we are labeling.
      visual_areas = {visual_areas}'''
    targets_block = f'''
    targets:
      Target:
        - {(chr(10) + "        - ").join(targets.keys())}
      dict: |
        return {{
            k: v
            for s in target['Target'].split('_')
            for (k,v) in [s.split('-')]}}
      subject: |
        sid = target['dict']['sub']
        sid_path = surfdata_path / ('sub-' + sid)
        return ny.{surffn}(os.fspath(sid_path))
      prfs: |
        H = target['dict']['hemi']
        sid = target['dict']['sub']
        tag = target['Target']
        dat = _load_prfanalyze_vista_prfs(
            target_paths[tag], tag, invert_y={invert_y})
        ang = np.arctan2(dat['y'], dat['x'])
        dat['polar_angle'] = np.mod(90 - 180/np.pi*ang + 180, 360) - 180
        dat['eccentricity'] = np.sqrt(dat['x']**2, dat['y']**2)
        dat['variance_explained'] = dat['r2']
        return dat
      hem: |
        h = target['dict']['hemi'].lower() + 'h'
        sub = target['subject']
        return sub.hemis[h].with_prop(target['prfs'])
      flatmap:
        return target['hem'].mask_flatmap(
            occpole_mask,
            map_right='right',
            radius=np.pi/2)'''
    annots = []
    for (k,lbl) in visual_areas.items():
        annots.append(f'{k}: [["polar_angle", "eccentricity"], ["r2", "curvature"]]')
    annots = '\n      '.join(annots)
    annot_block = f'''
    annotations:
      {annots}'''
    figures_block = f'''
    figures:
      r2: |
        ny.cortex_plot(
            target['flatmap'], color='variance_explained', axes=axes,
            cmap='hot', vmin=0, vmax=1)
      curvature: |
        ny.cortex_plot(target['flatmap'])
      _: |
        ny.cortex_plot(target['flatmap'], color=key, axes=axes)'''
    review_block = f'''
    review: |
      from cortexannotate.prfs import _review_prfanalyze_vista_rois
      _review_prfanalyze_vista_rois(target, annotations, figure, axes,
                                    save_hooks, visual_areas)
    '''
    s = (f"{init_block}\n"
         f"{display_block}\n"
         f"{targets_block}\n"
         f"{annot_block}\n"
         f"{figures_block}\n"
         f"{review_block}\n")
    s = '\n'.join([ln[4:] for ln in s.split('\n')])
    file.write(s)
def _review_prfanalyze_vista_rois(target, annotations,
                                  fig, axes, save_hooks,
                                  visual_areas):
    # We want to step through the annotations in the order given in the
    # visual_areas option.
    import matplotlib.pyplot as plt
    import neuropythy as ny
    (lblfig, lblax) = plt.subplots(1,1, figsize=(4,4), dpi=256, facecolor='k')
    from matplotlib.pyplot import Polygon
    n = np.max(list(visual_areas.values()))
    for (k,v) in visual_areas.items():
        ann = annotations.get(k)
        if ann is None or len(ann) == 0:
            continue
        if len(ann) < 3:
            raise ValueError(f"Boundary for {k} has fewer than 3 points!")
        gl = v / n
        poly = Polygon(
            ann,
            closed=True,
            fill=True,
            edgecolor=None,
            facecolor=(gl, gl, gl),
            zorder=(n - v))
        lblax.add_patch(poly)
    # Make the plot and convert to a nifti2 file.
    lblax.axis('off')
    lblax.set_facecolor('k')
    (xmin,ymin) = np.min(target['flatmap'].coordinates, axis=1)
    (xmax,ymax) = np.max(target['flatmap'].coordinates, axis=1)
    lblax.set_xlim([xmin,xmax])
    lblax.set_ylim([ymin,ymax])
    lblfig.canvas.draw()
    image_flat = np.frombuffer(lblfig.canvas.tostring_rgb(), dtype='uint8')
    (w,h) = lblfig.canvas.get_width_height()
    image = image_flat.reshape(h, w, 3)
    image = np.round(n * np.mean(image, axis=-1)/255).astype(int)
    image = np.flipud(image)
    imcoords = (target['flatmap'].coordinates.T - [xmin, ymin])
    imcoords *= ([(w-1) / (xmax - xmin), (h-1) / (ymax - ymin)])
    (cols, rows) = np.round(imcoords.T).astype(int)
    labels = image[rows, cols]
    plt.close(lblfig)
    def _savenii2(filename):
        import nibabel as nib
        lbls = np.zeros(target['hem'].vertex_count, dtype=np.int32)
        lbls[target['flatmap'].labels] = labels
        nii = nib.Nifti2Image(lbls, np.eye(4))
        nii.header.set_xyzt_units('mm', 'sec')
        ny.save(filename, nii)
    save_hooks["labels.nii.gz"] = _savenii2
    # Now we can make a plot on the axes for the review.
    ny.cortex_plot(
        target['flatmap'],
        color=labels, cmap='rainbow',
        mask=(labels > 0),
        axes=axes)


# annotate_prfs ################################################################

def annotate_prfs(bids_path,
                  prf_format='prfanalyze-vista',
                  derivative='cortexannotate',
                  save_path=None,
                  cache_path=None,
                  surface_format=None,
                  surface_path=None,
                  subjects=None,
                  visual_areas=None,
                  overwrite=False,
                  invert_y=None,
                  mkdir_mode=0o775):
    """Runs the cortical annotation tool on the given BIDS path.
    
    This function is meant to be used interactively in a Jupyter notebook. It
    creates an `ipycanvas` interface for the annotation of cortical images of
    retinotopic maps. Outputs are written to the derivatives directory.
    """
    from os import PathLike
    # We can parse a few of the arguments and check things before we begin.
    if visual_areas is None:
        visual_areas = annotate_prfs_visual_areas_default
    elif not isinstance(visual_areas, dict):
        visual_areas = {k:(ii+1) for (ii,k) in enumerate(visual_areas)}
    if any(not isinstance(v, int) or v < 1 for v in visual_areas.values()):
        raise ValueError(
            "visual_areas must contain strings mapped to positive integers")
    if not isinstance(bids_path, (str, os.PathLike)):
        raise ValueError(
            f"annotate_prfs expected str or PathLike for argument bids_path,"
            f" not type {type(bids_path)}")
    try:
        import neuropythy as ny
    except Exception:
        ny = None
    ny = True
    if ny is None:
        raise RuntimeError(
            "The library neuropythy could not be imported; neuropythy is"
            " required for using annotate_prfs")
    # The bids_path must be a local path.
    bids_path = Path(bids_path)
    der_path = bids_path / 'derivatives'
    src_path = bids_path / 'sourcedata'
    # If we're not overwriting the data, we need to make sure the directory
    # doesn't already exist.
    out_path = der_path / derivative
    if not overwrite and out_path.is_dir():
        raise RuntimeError(
            f"overwrite set to false but path already exists: {out_path}")
    # First step: find the FreeSurfer or HCPpipelines path.
    (surffmt, surfpath) = _find_bids_surfpath(
        bids_path, surface_format, surface_path)
    # Next, parse the prf_format and get a nested dictionary of the PRF files.
    if prf_format.startswith('prfanalyze-vista'):
        (prf_path,analysis) = _find_prfanalyze_vista_path(bids_path, prf_format)
        # Now figure out the targets we're going to use:
        targets = _find_prfanalyze_vista_targets(prf_path)
        if len(targets) < 1:
            raise ValueError(f"no targets found in path: {prf_path}")
        # Next we need to make a configuration file and put it in the derivatives
        # directory.
        if analysis is not None:
            out_path = out_path / analysis
        out_path.mkdir(exist_ok=True, parents=True, mode=mkdir_mode)
        config_path = out_path / 'config.yaml'
        with open(config_path, 'wt') as cfg:
            _make_prfanalyze_vista_config(
                cfg, targets,
                surfpath, surffmt, prf_path,
                invert_y, visual_areas)
    else:
        raise ValueError(f"prf_format not currently supported: {prf_format}")
    # Now run the annotation tool...
    from cortexannotate import AnnotationTool
    return AnnotationTool(
        config_path=config_path,
        cache_path=cache_path,
        save_path=out_path,
        git_path=None)
