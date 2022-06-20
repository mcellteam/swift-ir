#!/usr/bin/env python3
# print(f'glanceem_utils.py | Loading {__name__}')

import webbrowser
import operator
import logging
import traceback
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
# from source_tracker import get_hash_and_rev # what was this being used for?

# from package.globals import cfg.project_data
import package.globals as cfg
from package.globals import QT_API, USES_PYSIDE, USES_PYQT, USES_QT5, USES_QT6
from package.get_image_size import get_image_size

center_switch = 0

combo_name_to_dm_name = {'Init Affine': 'init_affine', 'Refine Affine': 'refine_affine', 'Apply Affine': 'apply_affine'}
dm_name_to_combo_name = {'init_affine': 'Init Affine', 'refine_affine': 'Refine Affine', 'apply_affine': 'Apply Affine'}

def get_trace() -> str:
    trace = traceback.format_exc()
    return trace

def getProjectFileLength(path: str) -> int:
    f = open(path, 'r')
    text = f.read()
    f.close()
    for count, line in enumerate(text):
        pass
    return count+1


def printProjectDetails(project_data: dict) -> None:
    print('\nIn Memory:')
    print("  project_data['data']['destination_path']         :", project_data['data']['destination_path'])
    print("  project_data['data']['source_path']              :", project_data['data']['source_path'])
    print("  project_data['data']['current_scale']            :", project_data['data']['current_scale'])
    print("  project_data['data']['current_layer']            :", project_data['data']['current_layer'])
    print("  project_data['method']                           :", project_data['method'])
    print("  Destination Set Status (isDestinationSet)        :", isDestinationSet())
    print("  Images Imported Status (areImagesImported)       :", areImagesImported())
    print("  Project Scaled Status (isProjectScaled)          :", isProjectScaled())
    print("  Any Scale Aligned Status (isAnyScaleAligned)     :", isAnyScaleAligned())
    print("  Cur Scale Aligned (areAlignedImagesGenerated)    :", areAlignedImagesGenerated())
    print("  Any Exported Status (isAnyAlignmentExported)     :", isAnyAlignmentExported())
    print("  # Imported Images (getNumImportedImages)         :", getNumImportedImages())
    print("  Current Layer SNR (getCurSNR)                    :", getCurSNR())

    return None


def debug_project():
    print('\n-------------- DEBUG PROJECT --------------')
    path = cfg.project_data['data']['destination_path']
    cat_str = 'cat %s.json' % path
    n_init_affine = os.system(cat_str + ' |grep init_affine')
    n_refine_affine = os.system(cat_str + ' |grep refine_affine')
    n_apply_affine = os.system(cat_str + ' |grep apply_affine')
    n_alignment_option = os.system(cat_str + ' |grep alignment_option')
    n_method_options = os.system(cat_str + ' |grep method_options')
    print('Project File:')
    print('  init_affine (project FILE)              :', n_init_affine)
    print('  refine_affine (project FILE)            :', n_refine_affine)
    print('  apply_affine (project FILE)             :', n_apply_affine)
    print('  alignment_option (project_FILE)         :')
    print('\ncfg.project_data:')
    print('  init_affine (cfg.project_data)    :', str(cfg.project_data).count('init_affine'))
    print('  refine_affine (cfg.project_data)  :', str(cfg.project_data).count('refine_affine'))
    print('  apply_affine (cfg.project_data)   :', str(cfg.project_data).count('apply_affine'))



    print('-------------------------------------------\n')

#debug #debuglayer
def debug_layer():
    print("\n___________________DEBUG LAYER_____________________")
    print("\nProject____________________________________________")
    if cfg.project_data['data']['source_path']:
        print("  Source path                                      :", cfg.project_data['data']['source_path'])
    else:
        print("  Source path                                      : n/a")
    if cfg.project_data['data']['destination_path']:
        print("  Destination path                                 :", cfg.project_data['data']['destination_path'])
    else:
        print("  Destination path                                 : n/a")
    print("  Current scale                                    :", cfg.project_data['data']['current_scale'])
    print("  Current layer                                    :", cfg.project_data['data']['current_layer'])
    print("  Method                                           :", cfg.project_data['method'])

    print("\nData Selection & Scaling___________________________")
    print("  Are images imported?                             :", areImagesImported())
    print("  How many images?                                 :", getNumImportedImages())
    if getSkipsList():
        print("  Skip list                                        :", getSkipsList())
    else:
        print("  Skip list                                        : n/a")
    print("  Is scaled?                                       :", isProjectScaled())
    if isProjectScaled():
        print("  How many scales?                                 :", getNumScales())
    else:
        print("  How many scales?                                 : n/a")
    print("  Which scales?                                    :", str(getScaleKeys()))

    print("\nAlignment__________________________________________")
    print("  Is any scale aligned?                            :", isAnyScaleAligned())
    print("  Is this scale aligned?                           :", isCurScaleAligned())
    try:
        print("  How many aligned?                                :", getNumAligned())
    except:
        print("  How many aligned?                                : n/a")
    scale = cfg.project_data['data']['current_scale']
    try: print("  alignment_option                                 :", cfg.project_data['data']['scales'][getCurScale()]['method_data']['alignment_option'])
    except: print_exception()
    try: scale = cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]  # print(scale) # returns massive wall of text
    except: print_exception()
    try:
        print("  whitening factor                                 :",scale['alignment_stack'][cfg.project_data['data']['current_layer']]['align_to_ref_method']['method_data']['whitening_factor'])
    except:
        print("  whitening factor                                 : n/a")
    try:
        print("  SWIM window                                      :", scale['alignment_stack'][cfg.project_data['data']['current_layer']]['align_to_ref_method']['method_data']['win_scale_factor'])
    except:
        print("  SWIM window                                      : n/a")
    print("  Layer SNR                                        :", getCurSNR())

    print("\nPost-alignment_____________________________________")
    # try:
    #     null_cafm_trends = cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['null_cafm_trends']
    #     print("  null_cafm_trends                                 :", null_cafm_trends)
    # except:
    #     print("  null_cafm_trends                                 : n/a")
    try:
        poly_order = cfg.project_data['data']['scales'][getCurScale()]['poly_order']
        print("  poly_order                                       :", poly_order)
    except:
        print("  poly_order                                       : n/a")
        pass
    try:
        use_bounding_rect = cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['use_bounding_rect']
        print("  use_bounding_rect                                :", use_bounding_rect)
    except:
        print("  use_bounding_rect                                : n/a")

    print("\nExport & View______________________________________")
    print("  Is any alignment exported?                       :", isAnyAlignmentExported())
    print("  Is current scale exported?                       :", isCurScaleExported())


def areImagesImported() -> bool:
    '''Checks if any images have been imported.'''
    # print('areImagesImported:')
    # print("areImagesImported | len(cfg.project_data['data']['scales']['scale_1']['alignment_stack']) = ", len(cfg.project_data['data']['scales']['scale_1']['alignment_stack']))

    n_imgs = len(cfg.project_data['data']['scales']['scale_1']['alignment_stack'])
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
        n_imgs = len(cfg.project_data['data']['scales']['scale_1']['alignment_stack'])
        # print('getNumImportedImages | Returning %d as int' % n_imgs)
        return n_imgs
    except:
        print('getNumImportedImages | WARNING | No image layers were found')
        return


def getCurScale() -> str:
    '''Returns the current scale, according to cfg.project_data (project dictionary).'''
    # print('getCurScale:')

    cur_scale = cfg.project_data['data']['current_scale']
    # print('  getCurScale | Returning %s' % cur_scale)
    return cur_scale

def isDestinationSet() -> bool:
    '''Checks if there is a project open'''

    if cfg.project_data['data']['destination_path']:
        check = True
    else:
        check = False
    # print('  isDestinationSet() | Returning %s' % check)
    return check

def isProjectScaled() -> bool:
    '''Checks if there exists any stacks of scaled images

    #fix Note: This will return False if no scales have been generated, but code should be dynamic enough to run alignment
    functions even for a project that does not need scales.'''
    if len(cfg.project_data['data']['scales']) < 2:
        isScaled = False
    else:
        isScaled = True

    # print('isProjectScaled | checking if %s is less than 2 (proxy for not scaled)' % str(len(cfg.project_data['data']['scales'])))
    # print('isProjectScaled | Returning %s' % isScaled)
    return isScaled

def isCurScaleAligned() -> bool:
    '''Checks if there exists an alignment stack for the current scale

    #0615 Bug fixed - look for populated bias_data folder, not presence of aligned images

    #fix Note: This will return False if no scales have been generated, but code should be dynamic enough to run alignment
    functions even for a project that does not need scales.'''
    try:
        project_dir = cfg.project_data['data']['destination_path']
        bias_dir = os.path.join(project_dir, getCurScale(), 'bias_data')
        afm_1_file = os.path.join(bias_dir,'afm_1.dat')
        # print('afm_1_file = ', afm_1_file)
        # print('os.path.exists(afm_1_file) = ', os.path.exists(afm_1_file))
        if os.path.exists(afm_1_file):
            # print('isCurScaleAligned | Returning True')
            return True
        else:
            # print('isCurScaleAligned | Returning False')
            return False
    except:
        print('isCurScaleAligned | EXCEPTION | Unexpected function behavior - Returning False')
        return False

def getNumAligned() -> int:
    '''Returns the count aligned images for the current scale'''

    path = os.path.join(cfg.project_data['data']['destination_path'], getCurScale(), 'img_aligned')
    # print('getNumAligned | path=', path)
    try:
        n_aligned = len([name for name in os.listdir(path) if os.path.isfile(os.path.join(path, name))])
    except:
        return 0
    # print('getNumAligned() | returning:', n_aligned)
    return n_aligned

def getSkipsList() -> list[int]:
    '''Returns the list of skipped images at the current scale'''
    # print('getSkipsList | called by ',inspect.stack()[1].function)
    skip_list = []
    try:
        for layer_index in range(len(cfg.project_data['data']['scales'][getCurScale()]['alignment_stack'])):
            if cfg.project_data['data']['scales'][getCurScale()]['alignment_stack'][layer_index]['skip'] == True:
                skip_list.append(layer_index)
            # print('getSkipsList() | ', str(skip_list))
    except:
        print('getSkipsList | EXCEPTION | failed to get skips list')
        return

    return skip_list

def getNumScales() -> int:
    '''Returns the number of scales in scale pyramid'''
    try:
        n_scales = len(cfg.project_data['data']['scales'].keys())
        return n_scales
    except:
        print('getNumScales | EXCEPTION | Unable to return the number of scales')


def getScaleKeys() -> list[str]:
    '''Returns the sorted dictionary keys for the scales in the current project'''
    try:
        scale_keys = sorted(cfg.project_data['data']['scales'].keys())
        return scale_keys
    except:
        print('getScaleKeys | EXCEPTION | Unable to return dictionary keys for scales')


def isAnyScaleAligned() -> bool:
    '''Checks if there exists a set of aligned images at the current scale'''

    try:
        files = glob(cfg.project_data['data']['destination_path'] + '/scale_*/img_aligned/*.tif')
    except:
        files = '' #0520
        print('isAnyScaleAligned | EXCEPTION | Looking for *.tif in project dir but didnt find any - Returning empty string')

    if len(files) > 0:
        # print('isAnyScaleAligned | Returning True')
        return True
    else:
        # print('isAnyScaleAligned | Returning False')
        return False


def isScaleAligned(scale: str) -> bool:
    '''Returns boolean based on whether arg scale is aligned '''
    try:
        project_dir = cfg.project_data['data']['destination_path']
        bias_dir = os.path.join(project_dir, scale, 'bias_data')
        afm_1_file = os.path.join(bias_dir,'afm_1.dat')
        if os.path.exists(afm_1_file):
            print('isScaleAligned | Returning True')
            return True
        else:
            print('isScaleAligned | Returning False')
            return False
    except:
        print('isScaleAligned | EXCEPTION | Unexpected function behavior - Returning False')
        return False



# def isAlignmentOfCurrentScale() -> bool:
#     '''Checks if there exists a set of aligned images at the current scale
# 
#     DOES *NOT* FUNCTION PROPERLY
# 
#     NEEDS TO PROBE 'bias_data' DIRECTORIES
# 
#     ISSUES THAT REGENERATING SCALES MEANS PREVIOUS AALIGNMENTS STILL EXIST AND THUS THIS CAN INCORRECTLY RETURN TRUE
#     MIGHT WANT TO HAVE SCALE RE-GENERATION CAUSE PREVIOUSLY ALIGNED IMAGES TO BE REMOVED'''
# 
#     try:
#         destination_path = os.path.join(cfg.project_data['data']['destination_path'])
#     except:
#         print('isAlignmentOfCurrentScale | WARNING | There is no project open - Returning False')
#         return False
# 
#     try:
#         isProjectScaled()
#     except:
#         print('isAlignmentOfCurrentScale | WARNING | This project has not been scaled yet - returning False')
#         return False
# 
#     try:
#         bias_path = destination_path + '/' + getCurScale() + '/bias_data'
#         print('isAlignmentOfCurrentScale | bias path =', bias_path)
#         bias_dir_byte_size=0
#         for path, dirs, files in os.walk(bias_path):
#             for f in files:
#                 fp = os.path.join(path, f)
#                 bias_dir_byte_size += os.path.getsize(fp)
#     except:
#         print('isAlignmentOfCurrentScale | WARNING | Unable to get size of the bias directory - Returning False')
# 
# 
#     print('isAlignmentOfCurrentScale | size of bias dir=', bias_dir_byte_size)
# 
#     if bias_dir_byte_size < 20:
#         print('isAlignmentOfCurrentScale | Returning False')
#         return False
#     else:
#         print('isAlignmentOfCurrentScale | Returning True')
#         return True

def areAlignedImagesGenerated():
    '''Returns True or False dependent on whether aligned images have been generated for the current scale.'''
    path = os.path.join(cfg.project_data['data']['destination_path'], getCurScale(), 'img_aligned')
    # print("cfg.project_data['data']['destination_path'] = ", cfg.project_data['data']['destination_path'])
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
        files = glob(cfg.project_data['data']['destination_path'] + '/scale_*/img_aligned/*.tif')
    except:
        print('returnAlignedImg | WARNING | Something went wrong. Check project dictionary - Returning None')
        return None


    # print('returnAlignedImg | # aligned images found: ', len(files))
    # print('returnAlignedImg | List of aligned imgs: ', files)
    return files

def isAnyAlignmentExported() -> bool:
    '''Checks if there exists an exported alignment'''

    return os.path.isdir(os.path.join(cfg.project_data['data']['destination_path'], 'project.zarr'))

def isCurScaleExported() -> bool:
    '''Checks if there exists an exported alignment'''
    path = os.path.join(cfg.project_data['data']['destination_path'], 'project.zarr', 'aligned_' + getCurScale())
    answer = os.path.isdir(path)
    # print("isCurScaleExported | path = " + path)
    # print("isCurScaleExported | answer = " + str(answer))
    return answer

def getCurSNR() -> str:
    if not  cfg.project_data['data']['current_scale']:
        print("Aborting getCurSNR() because no current scale is even set...")
        return

    s = cfg.project_data['data']['current_scale']
    l = cfg.project_data['data']['current_layer']

    # print("  len(cfg.project_data['data']['scales']) = ", len(cfg.project_data['data']['scales']))

    if len(cfg.project_data['data']['scales']) > 0:
        # print("len(cfg.project_data['data']['scales']) =", len(cfg.project_data['data']['scales'][s]))
        scale = cfg.project_data['data']['scales'][s]
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

    try: n_scales = len(cfg.project_data['data']['scales'])
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





def clear_all_skips():
    print('Clearing all skips | clear_all_skips...')
    image_scale_keys = [s for s in sorted(cfg.project_data['data']['scales'].keys())]
    for scale in image_scale_keys:
        scale_key = str(scale)
        for layer in cfg.project_data['data']['scales'][scale_key]['alignment_stack']:
            layer['skip'] = False

    # main_win.status_skips_label.setText(str(skip_list))  # settext #status
    # skip.set_value(False) #skip


def copy_skips_to_all_scales():
    print('Copying skips to all scales | copy_skips_to_all_scales...')
    source_scale_key = cfg.project_data['data']['current_scale']
    if not 'scale_' in str(source_scale_key):
        source_scale_key = 'scale_' + str(source_scale_key)
    scales = cfg.project_data['data']['scales']
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
    # Not needed: skip.set_value(scales[source_scale_key]['alignment_stack'][cfg.project_data['data']['current_layer']]['skip']


# skip
def update_skip_annotations():
    print('\nupdate_skip_annotations:\n')
    # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
    remove_list = []
    add_list = []
    for sk, scale in cfg.project_data['data']['scales'].items():
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
#     # interface.print_debug(0, "Function not implemented yet. Skip = " + main_window.toggle_skip.isChecked())

# def crop_mode_callback():
#     return
#     # return view_match_crop.get_value()



