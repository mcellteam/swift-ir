#!/usr/bin/env python2.7

import os
import numpy as np

def save_bias_analysis(al_stack, bias_data_path):
    '''Save bias analysis results to named .dat files.'''
    print('save_bias_analysis >>>>>>>>')
    print('Saving Bias Data (.dat)...')

    snr_file = open(os.path.join(bias_data_path, 'snr_1.dat'), 'w')
    bias_x_file = open(os.path.join(bias_data_path, 'bias_x_1.dat'), 'w')
    bias_y_file = open(os.path.join(bias_data_path, 'bias_y_1.dat'), 'w')
    bias_rot_file = open(os.path.join(bias_data_path, 'bias_rot_1.dat'), 'w')
    bias_scale_x_file = open(os.path.join(bias_data_path, 'bias_scale_x_1.dat'), 'w')
    bias_scale_y_file = open(os.path.join(bias_data_path, 'bias_scale_y_1.dat'), 'w')
    bias_skew_x_file = open(os.path.join(bias_data_path, 'bias_skew_x_1.dat'), 'w')
    bias_det_file = open(os.path.join(bias_data_path, 'bias_det_1.dat'), 'w')
    afm_file = open(os.path.join(bias_data_path, 'afm_1.dat'), 'w')
    c_afm_file = open(os.path.join(bias_data_path, 'c_afm_1.dat'), 'w')

    print('save_bias_analysis | len(al_stack) = ', len(al_stack))
    for i in range(len(al_stack)):

        if True or not al_stack[i]['skip']:
            # try:
            atrm = al_stack[i]['align_to_ref_method']
            afm = np.array(atrm['method_results']['affine_matrix'])
            c_afm = np.array(atrm['method_results']['cumulative_afm'])
            snr = np.array(atrm['method_results']['snr'])
            # except:
            #     print('save_bias_analysis | EXCEPTION | There was a problem reading the project file')

            # Compute and save final biases in analysis data files
            rot = np.arctan(c_afm[1, 0] / c_afm[0, 0])
            scale_x = np.sqrt(c_afm[0, 0] ** 2 + c_afm[1, 0] ** 2)
            scale_y = (c_afm[1, 1] * np.cos(rot)) - (c_afm[0, 1] * np.sin(rot))
            skew_x = ((c_afm[0, 1] * np.cos(rot)) + (c_afm[1, 1] * np.sin(rot))) / scale_y
            det = (c_afm[0, 0] * c_afm[1, 1]) - (c_afm[0, 1] * c_afm[1, 0])

            snr_file.write('%d %.6g\n' % (i, snr.mean()))
            bias_x_file.write('%d %.6g\n' % (i, c_afm[0, 2]))
            bias_y_file.write('%d %.6g\n' % (i, c_afm[1, 2]))
            bias_rot_file.write('%d %.6g\n' % (i, rot))
            bias_scale_x_file.write('%d %.6g\n' % (i, scale_x))
            bias_scale_y_file.write('%d %.6g\n' % (i, scale_y))
            bias_skew_x_file.write('%d %.6g\n' % (i, skew_x))
            bias_det_file.write('%d %.6g\n' % (i, det))

            afm_file.write('%d %.6g %.6g %.6g %.6g %.6g %.6g\n' % (
            i, afm[0, 0], afm[0, 1], afm[0, 2], afm[1, 0], afm[1, 1], afm[1, 2]))
            c_afm_file.write('%d %.6g %.6g %.6g %.6g %.6g %.6g\n' % (
            i, c_afm[0, 0], c_afm[0, 1], c_afm[0, 2], c_afm[1, 0], c_afm[1, 1], c_afm[1, 2]))

            # print_debug(50, 'AFM:  %d %.6g %.6g %.6g %.6g %.6g %.6g' % (
            # i, afm[0, 0], afm[0, 1], afm[0, 2], afm[1, 0], afm[1, 1], afm[1, 2]))
            # print_debug(50, 'CAFM: %d %.6g %.6g %.6g %.6g %.6g %.6g' % (
            # i, c_afm[0, 0], c_afm[0, 1], c_afm[0, 2], c_afm[1, 0], c_afm[1, 1], c_afm[1, 2]))

    snr_file.close()
    bias_x_file.close()
    bias_y_file.close()
    bias_rot_file.close()
    bias_scale_x_file.close()
    bias_scale_y_file.close()
    bias_skew_x_file.close()
    bias_det_file.close()
    afm_file.close()
    c_afm_file.close()

    print('<<<<<<<< save_bias_analysis')