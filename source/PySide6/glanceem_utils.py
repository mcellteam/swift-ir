#!/usr/bin/env python3
# print(f'glanceem_utils.py | Loading {__name__}')
import interface
import webbrowser
import operator
import logging
import json
import numpy as np
import zarr
import skimage.measure
import dask.array as da
import struct
import multiprocessing
import inspect
import os
import sys
import time
import traceback
import copy
from glob import glob
from PIL import Image
# from source_tracker import get_hash_and_rev # what was Bob using this for?

from PySide6.QtWidgets import QInputDialog, QDialog, QProgressBar, QMessageBox
from PySide6.QtCore import QThread, QThreadPool
try:
    from PySide6.QtCore import Signal, Slot
except ImportError:
    from PyQt6.QtCore import pyqtSignal as Signal
    from PyQt6.QtCore import pyqtSlot as Slot

from get_image_size import get_image_size

center_switch = 0


# IMPORTS FROM alignem_swift.py
# from source_tracker import get_hash_and_rev
# import sys, traceback, os, time, shutil, psutil, copy, argparse, cv2, json, platform, inspect, logging, glob

# from PySide6.QtWidgets import QInputDialog, QDialog, QPushButton, QProgressBar, QMessageBox, QApplication, \
#     QVBoxLayout, QTextEdit, QPlainTextEdit, QWidget
# from PySide6.QtCore import Signal, QObject, QUrl, QThread, QThreadPool
# from PySide6.QtGui import QImageReader
# import pyswift_tui
# import align_swiftir
# import task_queue_mp as task_queue
# import task_wrapper
# import project_runner

def getProjectFileLength(path: str) -> int:
    f = open(path, 'r')
    text = f.read()
    f.close()
    for count, line in enumerate(text):
        pass
    return count+1


def printProjectDetails(project_data: dict) -> None:
    print('\nIn Memory:')
    print("  project_data['data']['destination_path']         :", interface.project_data['data']['destination_path'])
    print("  project_data['data']['source_path']              :", interface.project_data['data']['source_path'])
    print("  project_data['data']['current_scale']            :", interface.project_data['data']['current_scale'])
    print("  project_data['data']['current_layer']            :", interface.project_data['data']['current_layer'])
    print("  project_data['method']                           :", interface.project_data['method'])
    print("  Destination Set Status (isDestinationSet)        :", isDestinationSet())
    print("  Images Imported Status (areImagesImported)       :", areImagesImported())
    print("  Project Scaled Status (isProjectScaled)          :", isProjectScaled())
    print("  Any Scale Aligned Status (isAnyScaleAligned)     :", isAnyScaleAligned())
    print("  Cur Scale Aligned (isAlignmentOfCurrentScale)    :", isAlignmentOfCurrentScale())
    print("  Any Exported Status (isAnyAlignmentExported)     :", isAnyAlignmentExported())
    print("  # Imported Images (getNumImportedImages)         :", getNumImportedImages())
    print("  Current Layer SNR (getCurSNR)                    :", getCurSNR())

    return None

def debug_project():
    print('\n-------------- DEBUG PROJECT --------------')
    path = interface.project_data['data']['destination_path']
    cat_str = 'cat %s.json' % path
    n_init_affine = os.system(cat_str + ' |grep init_affine')
    n_refine_affine = os.system(cat_str + ' |grep refine_affine')
    n_apply_affine = os.system(cat_str + ' |grep apply_affine')
    n_alignment_option = os.system(cat_str + ' |grep alignment_option')
    print('# init_affine (project FILE)              :', n_init_affine)
    print('# refine_affine (project FILE)            :', n_refine_affine)
    print('# apply_affine (project FILE)             :', n_apply_affine)
    print('# alignment_option (project_FILE)         :')
    print('')
    print('# init_affine (interface.project_data)    :', str(interface.project_data).count('init_affine'))
    print('# refine_affine (interface.project_data)  :', str(interface.project_data).count('refine_affine'))
    print('# apply_affine (interface.project_data)   :', str(interface.project_data).count('apply_affine'))
    print('-------------------------------------------\n')

#debug #debuglayer
def debug_layer():
    scale = interface.project_data['data']['current_scale']
    print('\n\n----------- DEBUG LAYER -----------')
    print("project_data['data']['source_path']              :", interface.project_data['data']['source_path'])
    print("project_data['data']['destination_path']         :", interface.project_data['data']['destination_path'])
    print("project_data['data']['current_scale']            :", interface.project_data['data']['current_scale'])
    print("project_data['data']['current_layer']            :", interface.project_data['data']['current_layer'])
    print("project_data['method']                           :", interface.project_data['method'])

    # scale = project_data['data']['scales'][project_data['data']['current_scale']]  # print(scale) # returns massive wall of text

    # base_file_name = layer['images']['base']['filename']
    print("Destination Set Status (isDestinationSet)        :", isDestinationSet())
    print("Images Imported Status (areImagesImported)       :", areImagesImported())
    print("# Imported Images (getNumImportedImages)         :", getNumImportedImages())
    print("Project Scaled Status (isProjectScaled)          :", isProjectScaled())
    print("Any Scale Aligned Status (isAnyScaleAligned)     :", isAnyScaleAligned())
    print("Cur Scale Aligned (isAlignmentOfCurrentScale)    :", isAlignmentOfCurrentScale())
    print("Current Layer SNR (getCurSNR)                    :", getCurSNR())
    print("Any Exported Status (isAnyAlignmentExported)     :", isAnyAlignmentExported())
    try:
        print("alignment_option                                 :", interface.project_data['data']['scales'][getCurScale()]['method_data']['alignment_option'])
    except:
        print("alignment_option not found")
    try:
        print("project_data.keys()                              :", interface.project_data.keys())
    except:
        print("project_data.keys() not found")

    null_cafm_trends = interface.project_data['data']['scales'][interface.project_data['data']['current_scale']]['null_cafm_trends']
    use_bounding_rect = interface.project_data['data']['scales'][interface.project_data['data']['current_scale']]['use_bounding_rect']
    poly_order = interface.project_data['data']['scales'][getCurScale()]['poly_order']
    try:
        scale = interface.project_data['data']['scales'][interface.project_data['data']['current_scale']]  # print(scale) # returns massive wall of text
    except:
        print("unable to set scale = project_data['data']['scales'][project_data['data']['current_scale']]")
    try:
        layer = scale['alignment_stack'][interface.project_data['data']['current_layer']]
    except:
        print("unable to set layer = scale['alignment_stack'][project_data['data']['current_layer']]")
    try:
        print("whitening factor                                 :",scale['alignment_stack'][interface.project_data['data']['current_layer']]['align_to_ref_method']['method_data']['whitening_factor'])
    except:
        print("whitening factor not found")
    try:
        print("SWIM window                                      :", scale['alignment_stack'][interface.project_data['data']['current_layer']]['align_to_ref_method']['method_data']['win_scale_factor'])
    except:
        print("SWIM window not found")


    # print("layer = \n", pretty(layer)) # dict_keys(['align_to_ref_method', 'images', 'skip']
    try:
        print("layer['skip']                                    :", layer['skip'])
    except:
        print("layer['skip'] not found")
    try:
        print("scale['alignment_stack'][project_data['data']['current_layer']]['skip'] = ", scale['alignment_stack'][interface.project_data['data']['current_layer']]['skip'])
    except:
        print("scale['alignment_stack'][project_data['data']['current_layer']]['skip'] not found")

    # skip_list = []
    # for layer_index in range(len(project_data['data']['scales'][getCurScale()]['alignment_stack'])):
    #     if project_data['data']['scales'][getCurScale()]['alignment_stack'][layer_index]['skip'] == True:
    #         skip_list.append(layer_index)
    # print("skip_list                                        :", skip_list)
    # print("scale['alignment_stack'][project_data['data']['current_layer']] = \n",scale['alignment_stack'][project_data['data']['current_layer']])


    print("null_cafm_trends                                 :", null_cafm_trends)
    print("use_bounding_rect                                :", use_bounding_rect)
    print("poly_order                                       :", poly_order)
    print("skips list                                       :", getSkipsList())

    try:
        print("scale.keys()                                     :", scale.keys())
    except:
        print("scale.keys() not found")

    try:
        print("layer.keys()                                     :", layer.keys())
    except:
        print("layer.keys() not found")


def areImagesImported() -> bool:
    '''Checks if any images have been imported.'''
    # print('areImagesImported:')
    # print("areImagesImported | len(interface.project_data['data']['scales']['scale_1']['alignment_stack']) = ", len(interface.project_data['data']['scales']['scale_1']['alignment_stack']))

    n_imgs = len(interface.project_data['data']['scales']['scale_1']['alignment_stack'])
    if n_imgs > 0:
        check = True
    else:
        check = False

    # print('areImagesImported | Returning ', str(check))

    return check


def getNumImportedImages() -> int:
    '''Returns # of imported images.

    CHECK THIS FOR OFF-BY-ONE BUG'''

    try:
        n_imgs = len(interface.project_data['data']['scales']['scale_1']['alignment_stack'])
        # print('getNumImportedImages | Returning %d as int' % n_imgs)
        return n_imgs
    except:
        print('getNumImportedImages | WARNING | No image layers were found')
        return


def getCurScale() -> str:
    '''Returns the current scale, according to interface.project_data (project dictionary).'''
    # print('getCurScale:')

    cur_scale = interface.project_data['data']['current_scale']
    # print('  getCurScale | Returning %s' % cur_scale)
    return cur_scale

def isDestinationSet() -> bool:
    '''Checks if there is a project open'''

    if interface.project_data['data']['destination_path']:
        check = True
    else:
        check = False
    # print('  isDestinationSet() | Returning %s' % check)
    return check

def isProjectScaled() -> bool:
    '''Checks if there exists any stacks of scaled images

    #fix Note: This will return False if no scales have been generated, but code should be dynamic enough to run alignment
    functions even for a project that does not need scales.'''

    if len(interface.project_data['data']['scales']) < 2:
        isScaled = False
    else:
        isScaled = True

    # print('isProjectScaled | checking if %s is less than 2 (proxy for not scaled)' % str(len(interface.project_data['data']['scales'])))
    # print('isProjectScaled | Returning %s' % isScaled)
    return isScaled

def isScaleAligned() -> bool:
    '''Checks if there exists an alignment stack for the current scale

    #fix Note: This will return False if no scales have been generated, but code should be dynamic enough to run alignment
    functions even for a project that does not need scales.'''
    print('isScaleAligned (caller=%s):' % str(inspect.stack()[1].function))
    try:
        alignment = len(interface.project_data["data"]["scales"][interface.getCurScale()]["alignment_stack"])
        if alignment > 1:
            print('isScaleAligned | Returning True')
            return True
        else:
            print('isScaleAligned | Returning False')
            return False
    except:
        print('isScaleAligned | EXCEPTION | Unexpected function behavior - Returning False')
        return False

def getNumAligned() -> int:
    '''Returns the count aligned images for the current scale'''

    path = os.path.join(interface.project_data['data']['destination_path'], interface.getCurScale(), 'img_aligned')
    # print('getNumAligned | path=', path)
    try:
        n_aligned = len([name for name in os.listdir(path) if os.path.isfile(os.path.join(path, name))])
    except:
        print('getNumAligned() | EXCEPTION | Unable to get number of aligned - returning 0')
        return 0
    # print('getNumAligned() | returning:', n_aligned)
    return n_aligned

def getSkipsList() -> list[int]:
    '''Returns the list of skipped images at the current scale'''
    print('getSkipsList | called by ',inspect.stack()[1].function)
    skip_list = []
    try:
        for layer_index in range(len(interface.project_data['data']['scales'][getCurScale()]['alignment_stack'])):
            if interface.project_data['data']['scales'][getCurScale()]['alignment_stack'][layer_index]['skip'] == True:
                skip_list.append(layer_index)
            # print('getSkipsList() | ', str(skip_list))
    except:
        print('getSkipsList | EXCEPTION | failed to get skips list')
        return

    return skip_list

def isAnyScaleAligned() -> bool:
    '''Checks if there exists a set of aligned images at the current scale'''

    try:
        files = glob(interface.project_data['data']['destination_path'] + '/scale_*/img_aligned/*.tif')
    except:
        files = '' #0520
        print('isAnyScaleAligned | WARNING | Looking for *.tif in project dir but didnt find any - Returning empty string')

    if len(files) > 0:
        # print('isAnyScaleAligned | Returning True')
        return True
    else:
        # print('isAnyScaleAligned | Returning False')
        return False

def isAlignmentOfCurrentScale() -> bool:
    '''Checks if there exists a set of aligned images at the current scale

    DOES *NOT* FUNCTION PROPERLY

    NEEDS TO PROBE 'bias_data' DIRECTORIES

    ISSUES THAT REGENERATING SCALES MEANS PREVIOUS AALIGNMENTS STILL EXIST AND THUS THIS CAN INCORRECTLY RETURN TRUE
    MIGHT WANT TO HAVE SCALE RE-GENERATION CAUSE PREVIOUSLY ALIGNED IMAGES TO BE REMOVED'''

    try:
        destination_path = os.path.join(interface.project_data['data']['destination_path'])
    except:
        print('isAlignmentOfCurrentScale | WARNING | There is no project open - Returning False')
        return False

    try:
        isProjectScaled()
    except:
        print('isAlignmentOfCurrentScale | WARNING | This project has not been scaled yet - returning False')
        return False

    try:
        bias_path = destination_path + '/' + getCurScale() + '/bias_data'
        print('isAlignmentOfCurrentScale | bias path =', bias_path)
        bias_dir_byte_size=0
        for path, dirs, files in os.walk(bias_path):
            for f in files:
                fp = os.path.join(path, f)
                bias_dir_byte_size += os.path.getsize(fp)
    except:
        print('isAlignmentOfCurrentScale | WARNING | Unable to get size of the bias directory - Returning False')


    print('isAlignmentOfCurrentScale | size of bias dir=', bias_dir_byte_size)

    if bias_dir_byte_size < 20:
        print('isAlignmentOfCurrentScale | Returning False')
        return False
    else:
        print('isAlignmentOfCurrentScale | Returning True')
        return True

def areAlignedImagesGenerated():
    '''Returns True or False dependent on whether aligned images have been generated for the current scale.'''
    path = os.path.join(interface.project_data['data']['destination_path'], getCurScale(), 'img_aligned')
    # print("interface.project_data['data']['destination_path'] = ", interface.project_data['data']['destination_path'])
    files = glob(path + '/*.tif')
    if len(files) < 1:
        print('areAlignedImagesGenerated | Zero aligned TIFs were found at this scale - Returning False')
        return False
    else:
        print('areAlignedImagesGenerated | One or more aligned TIFs were found at this scale - Returning True')
        return True


def returnAlignedImgs() -> list:
    '''Checks if there exists a set of aligned images at the current scale'''

    try:
        files = glob(interface.project_data['data']['destination_path'] + '/scale_*/img_aligned/*.tif')
    except:
        print('returnAlignedImg | WARNING | Something went wrong. Check project dictionary - Returning None')
        return None


    # print('returnAlignedImg | # aligned images found: ', len(files))
    # print('returnAlignedImg | List of aligned imgs: ', files)
    return files

def isAnyAlignmentExported() -> bool:
    '''Checks if there exists an exported alignment'''

    return os.path.isdir(os.path.join(interface.project_data['data']['destination_path'], 'project.zarr'))

def isCurScaleExported() -> bool:
    '''Checks if there exists an exported alignment'''

    return os.path.isdir(os.path.join(interface.project_data['data']['destination_path'], 'project.zarr', 'aligned_' + getCurScale()))

def getCurSNR() -> str:
    if not  interface.project_data['data']['current_scale']:
        print("Aborting getCurSNR() because no current scale is even set...")
        return

    s = interface.project_data['data']['current_scale']
    l = interface.project_data['data']['current_layer']

    # print("  len(project_data['data']['scales']) = ", len(project_data['data']['scales']))

    if len(interface.project_data['data']['scales']) > 0:
        # print("len(project_data['data']['scales']) =", len(project_data['data']['scales'][s]))
        scale = interface.project_data['data']['scales'][s]
        if len(scale['alignment_stack']) > 0:
            layer = scale['alignment_stack'][l]
            if 'align_to_ref_method' in layer:
                if 'method_results' in layer['align_to_ref_method']:
                    method_results = layer['align_to_ref_method']['method_results']
                    if 'snr_report' in method_results:
                        if method_results['snr_report'] != None:
                            curr_snr = method_results['snr_report']
                            # print("  returning the current snr:", str(curr_snr))
                            return str(curr_snr)



def getNumScales() -> int:
    '''Returns the number of scales for the open project'''

    try: n_scales = len(interface.project_data['data']['scales'])
    except: print('getNumScales | WARNING | Something went wrong getting the # of scales. Check project dictionary.')
    # print('getNumScales() | Returning %d' % n_scales)
    return n_scales

def printCurrentDirectory():
    '''Checks if there exists a set of aligned images at the current scale'''

    print('Current directory is : %s' % os.getcwd())

def requestConfirmation(title, text):
    '''Simple request confirmation dialog.'''

    button = QMessageBox.question(None, title, text)
    print('requestConfirmation | button=',str(button))
    print('requestConfirmation | type(button)=', type(button))
    print("requestConfirmation | Returning " + str(button == QMessageBox.StandardButton.Yes))
    return (button == QMessageBox.StandardButton.Yes)

def print_exception():
    exi = sys.exc_info()
    print("  Exception type = " + str(exi[0]))
    print("  Exception value = " + str(exi[1]))
    print("  Exception trace = " + str(exi[2]))
    print("  Exception traceback:")
    traceback.print_tb(exi[2])

def print_project_data_stats():
    pass




class SwiftirException:
    def __init__(self, project_file, message):
        self.project_file = project_file
        self.message = message
    def __str__(self):
        return self.message


'''
# to override or pass additional arguments...

class ValidationError(Exception):
    def __init__(self, message, errors):            
        # Call the base class constructor with the parameters it needs
        super().__init__(message)

        # Now for your custom code...
        self.errors = errors
        
        
        
Rules of global Keyword

The basic rules for global keyword in Python are:

    When we create a variable inside a function, it is local by default.
    When we define a variable outside of a function, it is global by default. You don't have to use global keyword.
    We use global keyword to read and write a global variable inside a function.
    Use of global keyword outside a function has no effect.

        
        
'''


########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################


def link_stack():
    print('Linking stack | link_stack...')

    skip_list = []
    for layer_index in range(len(interface.project_data['data']['scales'][getCurScale()]['alignment_stack'])):
        if interface.project_data['data']['scales'][getCurScale()]['alignment_stack'][layer_index][
            'skip'] == True:
            skip_list.append(layer_index)

    print('\nlink_stack(): Skip List = \n' + str(skip_list) + '\n')

    for layer_index in range(len(interface.project_data['data']['scales'][getCurScale()]['alignment_stack'])):
        base_layer = interface.project_data['data']['scales'][getCurScale()]['alignment_stack'][layer_index]

        if layer_index == 0:
            # No ref for layer 0
            if 'ref' not in base_layer['images'].keys():
                base_layer['images']['ref'] = copy.deepcopy(interface.new_image_template)
            base_layer['images']['ref']['filename'] = ''
        elif layer_index in skip_list:
            # No ref for skipped layer
            if 'ref' not in base_layer['images'].keys():
                base_layer['images']['ref'] = copy.deepcopy(interface.new_image_template)
            base_layer['images']['ref']['filename'] = ''
        else:
            # Find nearest previous non-skipped layer
            j = layer_index - 1
            while (j in skip_list) and (j >= 0):
                j -= 1

            # Use the nearest previous non-skipped layer as ref for this layer
            if (j not in skip_list) and (j >= 0):
                ref_layer = interface.project_data['data']['scales'][getCurScale()]['alignment_stack'][j]
                ref_fn = ''
                if 'base' in ref_layer['images'].keys():
                    ref_fn = ref_layer['images']['base']['filename']
                if 'ref' not in base_layer['images'].keys():
                    base_layer['images']['ref'] = copy.deepcopy(interface.new_image_template)
                base_layer['images']['ref']['filename'] = ref_fn

    # main_win.update_panels() #0526
    interface.main_window.update_win_self()
    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
    print('\nskip_list =\n', str(skip_list))
    print('Exiting link_stack')


'''
# ONLY CALLED WHEN LINKING LAYERS (i.e. when importing images)

DEPRECATE THIS
'''
def ensure_proper_data_structure():
    print('\nensure_proper_data_structure:')
    ''' Try to ensure that the data model is usable. '''
    scales_dict = interface.project_data['data']['scales']
    for scale_key in scales_dict.keys():
        scale = scales_dict[scale_key]
        '''
        if not 'null_cafm_trends' in scale:
          scale ['null_cafm_trends'] = null_cafm_trends.get_value()
        if not 'use_bounding_rect' in scale:
          scale ['use_bounding_rect'] = make_bool ( use_bounding_rect.get_value() )
        if not 'poly_order' in scale:
          scale ['poly_order'] = poly_order.get_value()
        '''
        # 0405 #hardcode whatever values
        if not 'null_cafm_trends' in scale:
            scale['null_cafm_trends'] = False  # 0523 need to hardcode this since cannot any longer read the value from toggle
        if not 'use_bounding_rect' in scale:
            scale['use_bounding_rect'] = True  # 0523 need to hardcode this as well for similar reason
        if not 'poly_order' in scale:
            scale['poly_order'] = int(0)  # 0523 need to hardcode this as well for similar reason

        for layer_index in range(len(scale['alignment_stack'])):
            layer = scale['alignment_stack'][layer_index]
            if not 'align_to_ref_method' in layer:
                layer['align_to_ref_method'] = {}
            atrm = layer['align_to_ref_method']
            if not 'method_data' in atrm:
                atrm['method_data'] = {}
            mdata = atrm['method_data']
            if not 'win_scale_factor' in mdata:
                # NOTE: THIS IS IMPORTANT, BUT NEEDS REFACTORING
                # print("  Warning: if NOT 'win_scale_factor' in mdata was run")
                mdata['win_scale_factor'] = float(interface.main_window.get_swim_input())

            # print("Evaluating: if not 'whitening_factor' in mdata")
            if not 'whitening_factor' in mdata:
                # NOTE: THIS IS IMPORTANT, BUT NEEDS REFACTORING
                # print("  Warning: if NOT 'whitening_factor' in mdata was run")
                mdata['whitening_factor'] = float(interface.main_window.get_whitening_input())

    print("Exiting ensure_proper_data_structure")


# NOTE: this is called right after importing base images (through update_linking_callback)
def link_all_stacks():
    print('\nlink_all_stacks:')
    ensure_proper_data_structure()

    for scale_key in interface.project_data['data']['scales'].keys():
        skip_list = []
        for layer_index in range(len(interface.project_data['data']['scales'][scale_key]['alignment_stack'])):
            if interface.project_data['data']['scales'][scale_key]['alignment_stack'][layer_index]['skip'] == True:
                print('  appending layer ' + str(layer_index) + ' to skip_list')
                skip_list.append(layer_index)  # skip


        for layer_index in range(len(interface.project_data['data']['scales'][scale_key]['alignment_stack'])):
            base_layer = interface.project_data['data']['scales'][scale_key]['alignment_stack'][layer_index]

            if layer_index == 0:
                # No ref for layer 0 # <-- ******
                if 'ref' not in base_layer['images'].keys():
                    base_layer['images']['ref'] = copy.deepcopy(interface.new_image_template)
                base_layer['images']['ref']['filename'] = ''
            elif layer_index in skip_list:
                # No ref for skipped layer
                if 'ref' not in base_layer['images'].keys():
                    base_layer['images']['ref'] = copy.deepcopy(interface.new_image_template)
                base_layer['images']['ref']['filename'] = ''
            else:
                # Find nearest previous non-skipped layer
                j = layer_index - 1
                while (j in skip_list) and (j >= 0):
                    j -= 1

                # Use the nearest previous non-skipped layer as ref for this layer
                if (j not in skip_list) and (j >= 0):
                    ref_layer = interface.project_data['data']['scales'][scale_key]['alignment_stack'][j]
                    ref_fn = ''
                    if 'base' in ref_layer['images'].keys():
                        ref_fn = ref_layer['images']['base']['filename']
                    if 'ref' not in base_layer['images'].keys():
                        base_layer['images']['ref'] = copy.deepcopy(interface.new_image_template)
                    base_layer['images']['ref']['filename'] = ref_fn

    # main_win.update_panels() #0526
    interface.main_window.update_win_self()

    if center_switch:
        interface.main_window.center_all_images()


    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
    print("Exiting link_all_stacks")


# class RunProgressDialog(QDialog):
#     """
#     Simple dialog that consists of a Progress Bar and a Button.
#     Clicking on the button results in the start of a timer and
#     updates the progress bar.
#     """
#
#     def __init__(self):
#         super().__init__()
#         print("RunProgressDialog constructor called")
#         self.initUI()
#
#     def initUI(self):
#         self.setWindowTitle('Progress Bar')
#         self.progress = QProgressBar(self)
#         self.progress.setGeometry(0, 0, 300, 25)
#         self.progress.setMaximum(100)
#         # self.button = QPushButton('Start', self)
#         # self.button.move(0, 30)
#         self.setModal(True)
#         self.show()
#         self.onButtonClick()
#
#         # self.button.clicked.connect(self.onButtonClick)
#
#     def onButtonClick(self):
#         self.calc = RunnableThread()
#         self.calc.countChanged.connect(self.onCountChanged)
#         self.calc.start()
#
#     def onCountChanged(self, value):
#         self.progress.setValue(value)
#
#
# class RunnableThread(QThread):
#     """
#     Runs a counter thread.
#     """
#     countChanged = Signal(int)
#
#     def run(self):
#         count = 0
#         while count < COUNT_LIMIT:
#             count += 1
#             time.sleep(0.02)
#             self.countChanged.emit(count)
#
#
# def run_progress():
#     print('run_progress: Initializing a RunProgressDialog()')
#     global window
#     window = RunProgressDialog()


# Call this function when run_json_project returns with need_to_write_json=false
def update_datamodel(updated_model):
    print('\nUpdating data model | update_datamodel...\n')
    # interface.print_debug(1, 100 * "+")
    # interface.print_debug(1, "run_json_project returned with need_to_write_json=false")
    # interface.print_debug(1, 100 * "+")
    # Load the alignment stack after the alignment has completed
    aln_image_stack = []
    scale_to_run_text = interface.project_data['data']['current_scale']
    stack_at_this_scale = interface.project_data['data']['scales'][scale_to_run_text]['alignment_stack']

    for layer in stack_at_this_scale:

        image_name = None
        if 'base' in layer['images'].keys():
            image_name = layer['images']['base']['filename']

        # Convert from the base name to the standard aligned name:
        aligned_name = None
        if image_name != None:
            # The first scale is handled differently now, but it might be better to unify if possible
            if scale_to_run_text == "scale_1":
                aligned_name = os.path.join(os.path.abspath(interface.project_data['data']['destination_path']),
                                            scale_to_run_text, 'img_aligned', os.path.split(image_name)[-1])
            else:
                name_parts = os.path.split(image_name)
                if len(name_parts) >= 2:
                    aligned_name = os.path.join(os.path.split(name_parts[0])[0],
                                                os.path.join('img_aligned', name_parts[1]))
        aln_image_stack.append(aligned_name)
        # interface.print_debug(30, "Adding aligned image " + aligned_name)
        layer['images']['aligned'] = {}
        layer['images']['aligned']['filename'] = aligned_name
    try:
        print('update_datamodel | trying to load_images_into_role')
        interface.main_window.load_images_in_role('aligned', aln_image_stack)
    except:
        print('Error from main_win.load_images_in_role.')
        print_exception()
        pass
    interface.main_window.refresh_all_images()

    # center
    # main_win.center_all_images()
    # main_win.update_win_self()
    if center_switch:
        interface.main_window.center_all_images()
    interface.main_window.update_win_self()


combo_name_to_dm_name = {'Init Affine': 'init_affine', 'Refine Affine': 'refine_affine', 'Apply Affine': 'apply_affine'}
dm_name_to_combo_name = {'init_affine': 'Init Affine', 'refine_affine': 'Refine Affine', 'apply_affine': 'Apply Affine'}

# def clear_match_points():
#     print('\nCalling clear_match_points() in alignem_swift.py:\n')
#
#     # global match_pt_mode
#     # if not match_pt_mode.get_value():
#     if view_match_crop.get_value() != 'Match':
#         print('"\nMust be in \"Match\" mode to delete all match points."')
#     else:
#         print('Deleting all match points for this layer')
#         scale_key = interface.project_data['data']['current_scale']
#         layer_num = interface.project_data['data']['current_layer']
#         stack = interface.project_data['data']['scales'][scale_key]['alignment_stack']
#         layer = stack[layer_num]
#
#         for role in layer['images'].keys():
#             if 'metadata' in layer['images'][role]:
#                 layer['images'][role]['metadata']['match_points'] = []
#                 layer['images'][role]['metadata']['annotations'] = []
#         interface.main_window.update_win_self()
#         interface.main_window.refresh_all_images()


def clear_all_skips():
    print('Clearing all skips | clear_all_skips...')
    image_scale_keys = [s for s in sorted(interface.project_data['data']['scales'].keys())]
    for scale in image_scale_keys:
        scale_key = str(scale)
        for layer in interface.project_data['data']['scales'][scale_key]['alignment_stack']:
            layer['skip'] = False

    # main_win.status_skips_label.setText(str(skip_list))  # settext #status
    # skip.set_value(False) #skip


def copy_skips_to_all_scales():
    print('Copying skips to all scales | copy_skips_to_all_scales...')
    source_scale_key = interface.project_data['data']['current_scale']
    if not 'scale_' in str(source_scale_key):
        source_scale_key = 'scale_' + str(source_scale_key)
    scales = interface.project_data['data']['scales']
    image_scale_keys = [s for s in sorted(scales.keys())]
    for scale in image_scale_keys:
        scale_key = str(scale)
        if not 'scale_' in str(scale_key):
            scale_key = 'scale_' + str(scale_key)
        if scale_key != source_scale_key:
            for l in range(len(scales[source_scale_key]['alignment_stack'])):
                if l < len(scales[scale_key]['alignment_stack']):
                    scales[scale_key]['alignment_stack'][l]['skip'] = scales[source_scale_key]['alignment_stack'][l][
                        'skip']  # <----
    # Not needed: skip.set_value(scales[source_scale_key]['alignment_stack'][interface.project_data['data']['current_layer']]['skip']


# skip
def update_skip_annotations():
    print('\nupdate_skip_annotations:\n')
    # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
    remove_list = []
    add_list = []
    for sk, scale in interface.project_data['data']['scales'].items():
        for layer in scale['alignment_stack']:
            layer_num = scale['alignment_stack'].index(layer)
            for ik, im in layer['images'].items():
                if not 'metadata' in im:
                    im['metadata'] = {}
                if not 'annotations' in im['metadata']:
                    im['metadata']['annotations'] = []
                ann = im['metadata']['annotations']
                if layer['skip']:
                    # Check and set as needed
                    already_skipped = False
                    for a in ann:
                        if a.startswith('skipped'):
                            already_skipped = True
                            break
                    if not already_skipped:
                        add_list.append((sk, layer_num, ik))
                        ann.append('skipped(1)')
                else:
                    # Remove all "skipped"
                    for a in ann:
                        if a.startswith('skipped'):
                            remove_list.append((sk, layer_num, ik))
                            ann.remove(a)
    # for item in remove_list:
    #     interface.print_debug(80, "Removed skip from " + str(item))
    # for item in add_list:
    #     interface.print_debug(80, "Added skip to " + str(item))


# NOTE: this is called right after importing base images
# def update_linking_callback():
#     print('Updating linking callback | update_linking_callback...')
#     link_all_stacks()
#     print('Exiting update_linking_callback()')
#
#
# def update_skips_callback(new_state):
#     print('Updating skips callback | update_skips_callback...')
#
#     # Update all of the annotations based on the skip values
#     copy_skips_to_all_scales()
#     # update_skip_annotations()  # This could be done via annotations, but it's easier for now to hard-code into interface.py
#     print("Exiting update_skips_callback(new_state)")


# def mouse_down_callback(role, screen_coords, image_coords, button):
#     # global match_pt_mode
#     # if match_pt_mode.get_value():
#     # print("mouse_down_callback was called but there is nothing to do.")
#     return  # monkeypatch
#
#
# def mouse_move_callback(role, screen_coords, image_coords, button):
#     # global match_pt_mode
#     # if match_pt_mode.get_value():
#     return #monkeypatch #jy
#
#     # # print("view_match_crop.get_value() = ", view_match_crop.get_value())
#     # if view_match_crop.get_value() == 'Match':
#     #     return (True)  # Lets the framework know that the move has been handled
#     # else:
#     #     return (False)  # Lets the framework know that the move has not been handled

# def notyet():
#     print('notyet() was called')
#     # interface.print_debug(0, "Function not implemented yet. Skip = " + str(skip.value)) #skip
#     # interface.print_debug(0, "Function not implemented yet. Skip = " + interface.main_window.toggle_skip.isChecked())

# def crop_mode_callback():
#     return
#     # return view_match_crop.get_value()



