#!/usr/bin/env python2.7

import os
import logging
import numpy as np

__all__ = ['save_bias_analysis']

logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt='%H:%M:%S',
        handlers=[ logging.StreamHandler() ]
)

def save_bias_analysis(al_stack, bias_data_path):
    """Saves bias analysis results to separate '.dat' files in the project directory.
    :param al_stack: The alignment data to be saved
    :type al_stack: dict
    :param bias_data_path: Path to where the bias data will be saved.
    :type bias_data_path: str"""
    logging.info('save_bias_analysis >>>>>>>>')
    logging.info('Saving Bias Data (.dat) at path %s' % bias_data_path)

    for i in range(len(al_stack)):

        if True or not al_stack[i]['skip']:

            atrm = al_stack[i]['align_to_ref_method']
            c_afm = np.array(atrm['method_results']['cumulative_afm'])
            rot = np.arctan(c_afm[1, 0] / c_afm[0, 0])
            afm = np.array(atrm['method_results']['affine_matrix'])
            snr = np.array(atrm['method_results']['snr'])
            scale_x = np.sqrt(c_afm[0, 0] ** 2 + c_afm[1, 0] ** 2)
            scale_y = (c_afm[1, 1] * np.cos(rot)) - (c_afm[0, 1] * np.sin(rot))
            skew_x = ((c_afm[0, 1] * np.cos(rot)) + (c_afm[1, 1] * np.sin(rot))) / scale_y
            det = (c_afm[0, 0] * c_afm[1, 1]) - (c_afm[0, 1] * c_afm[1, 0])

            with open(os.path.join(bias_data_path, 'snr_1.dat'), 'w') as f:
                f.write('%d %.6g\n' % (i, snr.mean()))
            with open(os.path.join(bias_data_path, 'bias_x_1.dat'), 'w') as f:
                f.write('%d %.6g\n' % (i, c_afm[0, 2]))
            with open(os.path.join(bias_data_path, 'bias_y_1.dat'), 'w') as f:
                f.write('%d %.6g\n' % (i, c_afm[1, 2]))
            with open(os.path.join(bias_data_path, 'bias_rot_1.dat'), 'w') as f:
                f.write('%d %.6g\n' % (i, rot))
            with open(os.path.join(bias_data_path, 'bias_scale_x_1.dat'), 'w') as f:
                f.write('%d %.6g\n' % (i, scale_x))
            with open(os.path.join(bias_data_path, 'bias_scale_y_1.dat'), 'w') as f:
                f.write('%d %.6g\n' % (i, scale_y))
            with open(os.path.join(bias_data_path, 'bias_skew_x_1.dat'), 'w') as f:
                f.write('%d %.6g\n' % (i, skew_x))
            with open(os.path.join(bias_data_path, 'bias_det_1.dat'), 'w') as f:
                f.write('%d %.6g\n' % (i, det))
            with open(os.path.join(bias_data_path, 'afm_1.dat'), 'w') as f:
                f.write('%d %.6g %.6g %.6g %.6g %.6g %.6g\n' % (
                        i, afm[0, 0], afm[0, 1], afm[0, 2], afm[1, 0], afm[1, 1], afm[1, 2]))
            with open(os.path.join(bias_data_path, 'c_afm_1.dat'), 'w') as f:
                f.write('%d %.6g %.6g %.6g %.6g %.6g %.6g\n' % (
                        i, c_afm[0, 0], c_afm[0, 1], c_afm[0, 2], c_afm[1, 0], c_afm[1, 1], c_afm[1, 2]))

            print('save_bias_analysis | AFM:  %d %.6g %.6g %.6g %.6g %.6g %.6g' % (
            i, afm[0, 0], afm[0, 1], afm[0, 2], afm[1, 0], afm[1, 1], afm[1, 2]))
            print('save_bias_analysis | CAFM: %d %.6g %.6g %.6g %.6g %.6g %.6g' % (
            i, c_afm[0, 0], c_afm[0, 1], c_afm[0, 2], c_afm[1, 0], c_afm[1, 1], c_afm[1, 2]))

    logging.info('<<<<<<<< save_bias_analysis')