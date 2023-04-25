#!/usr/bin/env python3

import os
import logging
import numpy as np
from src.helpers import print_exception

__all__ = ['save_bias_analysis']

logger = logging.getLogger(__name__)

def save_bias_analysis(layers, bias_path):
    """
    Saves bias analysis results to separate '.dat' files in the datamodel directory. Called by 'compute_affines'.
    :param layers: Iterator over the alignment layer datamodel to be saved
    :cur_method layers: ScaleIterator
    :param bias_path: Path to where the bias datamodel will be saved.
    :cur_method bias_path: str
    """

    logger.info('Saving Bias Data (.dat) to Path %s' % bias_path)
    # for i in range(len(al_stack)):
    for i, layer in enumerate(layers):

        if True or not layer['skipped']:
            try:
                atrm = layer['alignment']
                c_afm = np.array(atrm['method_results']['cumulative_afm'])
                # snr = np.array(atrm['method_results']['snr_report']) #1205-
                try:
                    snr = np.array(atrm['method_results']['snr'])
                except:
                    snr = np.array([0])
                rot = np.arctan(c_afm[1, 0] / c_afm[0, 0])
                afm = np.array(atrm['method_results']['affine_matrix'])
                scale_x = np.sqrt(c_afm[0, 0] ** 2 + c_afm[1, 0] ** 2)
                scale_y = (c_afm[1, 1] * np.cos(rot)) - (c_afm[0, 1] * np.sin(rot))
                skew_x = ((c_afm[0, 1] * np.cos(rot)) + (c_afm[1, 1] * np.sin(rot))) / scale_y
                det = (c_afm[0, 0] * c_afm[1, 1]) - (c_afm[0, 1] * c_afm[1, 0])
                with open(os.path.join(bias_path, 'snr_1.dat'), 'a+') as f:
                    f.write('%d %.6g\n' % (i, float(snr.mean())))
                with open(os.path.join(bias_path, 'bias_x_1.dat'), 'a+') as f:
                    f.write('%d %.6g\n' % (i, c_afm[0, 2]))
                with open(os.path.join(bias_path, 'bias_y_1.dat'), 'a+') as f:
                    f.write('%d %.6g\n' % (i, c_afm[1, 2]))
                with open(os.path.join(bias_path, 'bias_rot_1.dat'), 'a+') as f:
                    f.write('%d %.6g\n' % (i, rot))
                with open(os.path.join(bias_path, 'bias_scale_x_1.dat'), 'a+') as f:
                    f.write('%d %.6g\n' % (i, scale_x))
                with open(os.path.join(bias_path, 'bias_scale_y_1.dat'), 'a+') as f:
                    f.write('%d %.6g\n' % (i, scale_y))
                with open(os.path.join(bias_path, 'bias_skew_x_1.dat'), 'a+') as f:
                    f.write('%d %.6g\n' % (i, skew_x))
                with open(os.path.join(bias_path, 'bias_det_1.dat'), 'a+') as f:
                    f.write('%d %.6g\n' % (i, det))
                with open(os.path.join(bias_path, 'afm_1.dat'), 'a+') as f:
                    f.write('%d %.6g %.6g %.6g %.6g %.6g %.6g\n' % (
                            i, afm[0, 0], afm[0, 1], afm[0, 2], afm[1, 0], afm[1, 1], afm[1, 2]))
                with open(os.path.join(bias_path, 'c_afm_1.dat'), 'a+') as f:
                    f.write('%d %.6g %.6g %.6g %.6g %.6g %.6g\n' % (
                            i, c_afm[0, 0], c_afm[0, 1], c_afm[0, 2], c_afm[1, 0], c_afm[1, 1], c_afm[1, 2]))

                logger.debug('AFM:  %d %.6g %.6g %.6g %.6g %.6g %.6g' % (
                i, afm[0, 0], afm[0, 1], afm[0, 2], afm[1, 0], afm[1, 1], afm[1, 2]))
                logger.debug('CAFM: %d %.6g %.6g %.6g %.6g %.6g %.6g' % (
                i, c_afm[0, 0], c_afm[0, 1], c_afm[0, 2], c_afm[1, 0], c_afm[1, 1], c_afm[1, 2]))
            except:
                print_exception()
                logger.warning('An Exception Occurred While Saving Bias Analysis')
