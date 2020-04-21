import sys, traceback
import os
import argparse
import cv2
import copy

import json

import shutil

import alignem
from alignem import IntField, BoolField, FloatField, CallbackButton, ComboBoxControl, MainWindow

from PySide2.QtWidgets import QInputDialog, QDialog, QPushButton, QProgressBar
from PySide2.QtCore import QThread, Signal, QObject

import pyswift_tui
import align_swiftir
import task_queue
# import task_wrapper

import time


main_win = None

## project_data = None  # Use from alignem

swift_roles = ['ref','base','aligned']

def print_exception():
    exi = sys.exc_info()
    alignem.print_debug ( 1, "  Exception type = " + str(exi[0]) )
    alignem.print_debug ( 1, "  Exception value = " + str(exi[1]) )
    alignem.print_debug ( 1, "  Exception trace = " + str(exi[2]) )
    alignem.print_debug ( 1, "  Exception traceback:" )
    traceback.print_tb(exi[2])

def get_best_path ( file_path ):
    return os.path.abspath(os.path.normpath(file_path))

def link_stack_orig():
    alignem.print_debug ( 10, "Linking stack" )

    ref_image_stack = []
    for layer_index in range(len(alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'])):
      if layer_index == 0:
        main_win.add_empty_to_role ( 'ref' )
      else:
        # layer = alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'][layer_index]
        prev_layer = alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'][layer_index-1]
        fn = ""
        if 'base' in prev_layer['images'].keys():
          fn = prev_layer['images']['base']['filename']
        main_win.add_image_to_role ( fn, 'ref' )

    alignem.print_debug ( 10, "Loading images: " + str(ref_image_stack) )
    #main_win.load_images_in_role ( 'ref', ref_image_stack )

    main_win.update_panels()

    #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


def link_stack():
    alignem.print_debug ( 10, "Linking stack" )

    skip_list = []
    for layer_index in range(len(alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'])):
      if alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'][layer_index]['skip']==True:
        skip_list.append(layer_index)

    alignem.print_debug ( 10, '\nSkip List = \n' + str(skip_list) + '\n')

    for layer_index in range(len(alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'])):
      base_layer = alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'][layer_index]

      if layer_index == 0:
        # No ref for layer 0
        if 'ref' not in base_layer['images'].keys():
          base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
        base_layer['images']['ref']['filename'] = ''
      elif layer_index in skip_list:
        # No ref for skipped layer
        if 'ref' not in base_layer['images'].keys():
          base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
        base_layer['images']['ref']['filename'] = ''
      else:
        # Find nearest previous non-skipped layer
        j = layer_index-1
        while (j in skip_list) and (j>=0):
          j -= 1

        # Use the nearest previous non-skipped layer as ref for this layer
        if (j not in skip_list) and (j>=0):
          ref_layer = alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'][j]
          ref_fn = ''
          if 'base' in ref_layer['images'].keys():
            ref_fn = ref_layer['images']['base']['filename']
          if 'ref' not in base_layer['images'].keys():
            base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
          base_layer['images']['ref']['filename'] = ref_fn

    main_win.update_panels()

    #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


def make_bool(thing):
  if thing:
    return True
  else:
    return False

def ensure_proper_data_structure ():
    ''' Try to ensure that the data model is usable. '''
    scales_dict = alignem.project_data['data']['scales']
    for scale_key in scales_dict.keys():
      scale = scales_dict[scale_key]

      if not 'null_cafm_trends' in scale:
        scale ['null_cafm_trends'] = null_cafm_trends.get_value()
      if not 'use_bounding_rect' in scale:
        scale ['use_bounding_rect'] = make_bool ( use_bounding_rect.get_value() )
      if not 'poly_order' in scale:
        scale ['poly_order'] = poly_order.get_value()

      for layer_index in range(len(scale['alignment_stack'])):
        layer = scale['alignment_stack'][layer_index]
        if not 'align_to_ref_method' in layer:
          layer['align_to_ref_method'] = {}
        atrm = layer['align_to_ref_method']
        if not 'method_data' in atrm:
          atrm['method_data'] = {}
        mdata = atrm['method_data']
        if not 'win_scale_factor' in mdata:
          mdata['win_scale_factor'] = win_scale_factor.get_value()
        if not 'whitening_factor' in mdata:
          mdata['whitening_factor'] = whitening_factor.get_value()



def link_all_stacks():
    alignem.print_debug ( 10, "Linking all stacks" )
    ensure_proper_data_structure()

    for scale_key in alignem.project_data['data']['scales'].keys():
        skip_list = []
        for layer_index in range(len(alignem.project_data['data']['scales'][scale_key]['alignment_stack'])):
          if alignem.project_data['data']['scales'][scale_key]['alignment_stack'][layer_index]['skip']==True:
            skip_list.append(layer_index)

        alignem.print_debug ( 10, '\nSkip List = \n' + str(skip_list) + '\n')

        for layer_index in range(len(alignem.project_data['data']['scales'][scale_key]['alignment_stack'])):
          base_layer = alignem.project_data['data']['scales'][scale_key]['alignment_stack'][layer_index]

          if layer_index == 0:
            # No ref for layer 0
            if 'ref' not in base_layer['images'].keys():
              base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
            base_layer['images']['ref']['filename'] = ''
          elif layer_index in skip_list:
            # No ref for skipped layer
            if 'ref' not in base_layer['images'].keys():
              base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
            base_layer['images']['ref']['filename'] = ''
          else:
            # Find nearest previous non-skipped layer
            j = layer_index-1
            while (j in skip_list) and (j>=0):
              j -= 1

            # Use the nearest previous non-skipped layer as ref for this layer
            if (j not in skip_list) and (j>=0):
              ref_layer = alignem.project_data['data']['scales'][scale_key]['alignment_stack'][j]
              ref_fn = ''
              if 'base' in ref_layer['images'].keys():
                ref_fn = ref_layer['images']['base']['filename']
              if 'ref' not in base_layer['images'].keys():
                base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
              base_layer['images']['ref']['filename'] = ref_fn

    main_win.update_panels()

    #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})




class RunProgressDialog(QDialog):
    """
    Simple dialog that consists of a Progress Bar and a Button.
    Clicking on the button results in the start of a timer and
    updates the progress bar.
    """
    def __init__(self):
        super().__init__()
        alignem.print_debug ( 10, "RunProgressDialog constructor called" )
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Progress Bar')
        self.progress = QProgressBar(self)
        self.progress.setGeometry(0, 0, 300, 25)
        self.progress.setMaximum(100)
        #self.button = QPushButton('Start', self)
        #self.button.move(0, 30)
        self.setModal(True)
        self.show()
        self.onButtonClick()

        #self.button.clicked.connect(self.onButtonClick)

    def onButtonClick(self):
        self.calc = RunnableThread()
        self.calc.countChanged.connect(self.onCountChanged)
        self.calc.start()

    def onCountChanged(self, value):
        self.progress.setValue(value)

COUNT_LIMIT = 100
class RunnableThread(QThread):
    """
    Runs a counter thread.
    """
    countChanged = Signal(int)

    def run(self):
        count = 0
        while count < COUNT_LIMIT:
            count +=1
            time.sleep(0.02)
            self.countChanged.emit(count)

window = None
def run_progress():
    global window
    alignem.print_debug ( 10, "Run started" )
    window = RunProgressDialog()




class GenScalesDialog(QDialog):
    """
    Simple dialog that consists of a Progress Bar.
    """
    def __init__(self):
        super().__init__()
        alignem.print_debug ( 10, "GenScalesDialog constructor called" )
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Generating Scales')
        self.progress = QProgressBar(self)
        self.progress.setGeometry(0, 0, 300, 25)

        total_images_to_scale = 0
        image_scales_to_run = [ alignem.get_scale_val(s) for s in sorted(alignem.project_data['data']['scales'].keys()) ]
        for scale in image_scales_to_run:
            scale_key = str(scale)
            if not 'scale_' in scale_key:
                scale_key = 'scale_' + scale_key
            total_images_to_scale += len(alignem.project_data['data']['scales'][scale_key]['alignment_stack'])
        if total_images_to_scale <= 1:
            total_images_to_scale = 1
        alignem.print_debug ( 10, "Total images to scale = " + str(total_images_to_scale) )

        self.progress.setMaximum(total_images_to_scale)

        #self.button = QPushButton('Start', self)
        #self.button.move(0, 30)

        self.setModal(True)
        self.show()
        self.calc = GenScalesThread()
        self.calc.countChanged.connect(self.onCountChanged)
        self.calc.start()

    def onCountChanged(self, value):
        self.progress.setValue(value)

def create_project_structure_directories ( subdir_path ):
  alignem.print_debug (70, "Creating a subdirectory named " + subdir_path)
  try:
    os.mkdir (subdir_path)
  except:
    # This catches directories that already exist
    alignem.print_debug (40, 'Warning: Exception creating scale path (may already exist).')
    pass
  src_path = os.path.join (subdir_path, 'img_src')
  alignem.print_debug (70, "Creating source subsubdirectory named " + src_path)
  try:
    os.mkdir (src_path)
  except:
    # This catches directories that already exist
    alignem.print_debug (40, 'Warning: Exception creating "img_src" path (may already exist).')
    pass
  aligned_path = os.path.join (subdir_path, 'img_aligned')
  alignem.print_debug (70, "Creating aligned subsubdirectory named " + aligned_path)
  try:
    os.mkdir (aligned_path)
  except:
    # This catches directories that already exist
    alignem.print_debug (40, 'Warning: Exception creating "img_aligned" path (may already exist).')
    pass
  bias_data_path = os.path.join (subdir_path, 'bias_data')
  alignem.print_debug (70, "Creating bias subsubdirectory named " + bias_data_path)
  try:
    os.mkdir (bias_data_path)
  except:
    # This catches directories that already exist
    alignem.print_debug (40, 'Warning: Exception creating "bias_data" path (may already exist).')
    pass


class GenScalesThread ( QThread ):

  countChanged = Signal(int)

  def run(self):
    # Note: all printed output has been suppressed for testing
    #alignem.print_debug ( 10, "GenScalesThread.run inside alignem_swift called" )
    #main_win.status.showMessage("Generating Scales ...")

    count = 0

    image_scales_to_run = [ alignem.get_scale_val(s) for s in sorted(alignem.project_data['data']['scales'].keys()) ]

    #alignem.print_debug ( 40, "Create images at all scales: " + str ( image_scales_to_run ) )

    for scale in sorted(image_scales_to_run):

      #alignem.print_debug ( 70, "Creating images for scale " + str(scale) )
      #main_win.status.showMessage("Generating Scale " + str(scale) + " ...")

      scale_key = str(scale)
      if not 'scale_' in scale_key:
        scale_key = 'scale_' + scale_key

      subdir_path = os.path.join(alignem.project_data['data']['destination_path'],scale_key)
      scale_1_path = os.path.join(alignem.project_data['data']['destination_path'],'scale_1')

      create_project_structure_directories(subdir_path)

      for layer in alignem.project_data['data']['scales'][scale_key]['alignment_stack']:
        # Remove previously aligned images from panel ??

        # Copy (or link) the source images to the expected scale_key"/img_src" directory
        for role in layer['images'].keys():

          # Update the counter for the progress bar and emit the signal to update
          count += 1
          self.countChanged.emit(count)

          # Only copy files for roles "ref" and "base"
          # if role in ['ref', 'base']:
          if role in ['base']:

            base_file_name = layer['images'][role]['filename']
            if base_file_name != None:
              if len(base_file_name) > 0:
                abs_file_name = os.path.abspath(base_file_name)
                bare_file_name = os.path.split(abs_file_name)[1]
                destination_path = os.path.abspath ( alignem.project_data['data']['destination_path'] )
                outfile_name = os.path.join(destination_path, scale_key, 'img_src', bare_file_name)
                if scale == 1:
                  if get_best_path(abs_file_name) != get_best_path(outfile_name):
                    # The paths are different so make the link
                    try:
                      #alignem.print_debug ( 70, "UnLinking " + outfile_name )
                      os.unlink ( outfile_name )
                    except:
                      #alignem.print_debug ( 70, "Error UnLinking " + outfile_name )
                      pass
                    try:
                      #alignem.print_debug ( 70, "Linking from " + abs_file_name + " to " + outfile_name )
                      os.symlink ( abs_file_name, outfile_name )
                    except:
                      #alignem.print_debug ( 5, "Unable to link from " + abs_file_name + " to " + outfile_name )
                      #alignem.print_debug ( 5, "Copying file instead" )
                      # Not all operating systems allow linking for all users (Windows 10, for example, requires admin rights)
                      try:
                        shutil.copy ( abs_file_name, outfile_name )
                      except:
                        #alignem.print_debug ( 1, "Unable to link or copy from " + abs_file_name + " to " + outfile_name )
                        print_exception()
                else:
                  try:
                    # Do the scaling
                    #alignem.print_debug ( 70, "Copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(scale) )

                    if os.path.split ( os.path.split ( os.path.split ( abs_file_name )[0] )[0] )[1].startswith('scale_'):
                      # Convert the source from whatever scale is currently processed to scale_1
                      p,f = os.path.split(abs_file_name)
                      p,r = os.path.split(p)
                      p,s = os.path.split(p)
                      abs_file_name = os.path.join ( p, 'scale_1', r, f )

                    img = align_swiftir.swiftir.scaleImage ( align_swiftir.swiftir.loadImage(abs_file_name), fac=scale )
                    align_swiftir.swiftir.saveImage ( img, outfile_name )
                    # Change the base image for this scale to the new file
                    layer['images'][role]['filename'] = outfile_name
                  except:
                    #alignem.print_debug ( 1, "Error copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(scale) )
                    #print_exception()
                    pass

                # Update the Data Model with the new absolute file name. This replaces the originally opened file names
                #alignem.print_debug ( 40, "Original File Name: " + str(layer['images'][role]['filename']) )
                layer['images'][role]['filename'] = outfile_name
                #alignem.print_debug ( 40, "Updated  File Name: " + str(layer['images'][role]['filename']) )
    #main_win.status.showMessage("Done Generating Scales")


gen_scales_dialog = None
def gen_scales_with_thread():
    global gen_scales_dialog
    if (alignem.project_data['data']['destination_path'] == None) or (len(alignem.project_data['data']['destination_path']) <= 0):
      alignem.show_warning ( "Note", "Scales can not be generated without a destination (use File/Set Destination)" )
    else:
      alignem.print_debug ( 10, "Generating Scales with Progress Bar ..." )
      gen_scales_dialog = GenScalesDialog()
      #main_win.status.showMessage("Done Generating Scales ...")


def generate_scales ():
    alignem.print_debug ( 10, "generate_scales inside alignem_swift called" )
    #main_win.status.showMessage("Generating Scales ...")

    image_scales_to_run = [ alignem.get_scale_val(s) for s in sorted(alignem.project_data['data']['scales'].keys()) ]

    alignem.print_debug ( 40, "Create images at all scales: " + str ( image_scales_to_run ) )

    if (alignem.project_data['data']['destination_path'] == None) or (len(alignem.project_data['data']['destination_path']) <= 0):

      alignem.show_warning ( "Note", "Scales can not be generated without a destination (use File/Set Destination)" )

    else:

      for scale in sorted(image_scales_to_run):

        alignem.print_debug ( 70, "Creating images for scale " + str(scale) )
        #main_win.status.showMessage("Generating Scale " + str(scale) + " ...")

        scale_key = str(scale)
        if not 'scale_' in scale_key:
          scale_key = 'scale_' + scale_key

        subdir_path = os.path.join(alignem.project_data['data']['destination_path'],scale_key)
        scale_1_path = os.path.join(alignem.project_data['data']['destination_path'],'scale_1')

        create_project_structure_directories (subdir_path)

        alignem.print_debug ( 70, "Begin creating images at each layer for key: " + str(scale_key))

        for layer in alignem.project_data['data']['scales'][scale_key]['alignment_stack']:
          alignem.print_debug (40, "Generating images for layer: \"" + str(alignem.project_data['data']['scales'][scale_key]['alignment_stack'].index(layer)) + "\"")
          # Remove previously aligned images from panel ??

          # Copy (or link) the source images to the expected scale_key"/img_src" directory
          for role in layer['images'].keys():

            # Only copy files for roles "ref" and "base"

            if role in ['ref', 'base']:
              alignem.print_debug (40, "Generating images for role: \"" + role + "\"")
              base_file_name = layer['images'][role]['filename']
              if base_file_name != None:
                if len(base_file_name) > 0:
                  abs_file_name = os.path.abspath(base_file_name)
                  bare_file_name = os.path.split(abs_file_name)[1]
                  destination_path = os.path.abspath ( alignem.project_data['data']['destination_path'] )
                  outfile_name = os.path.join(destination_path, scale_key, 'img_src', bare_file_name)
                  if scale == 1:
                    if get_best_path(abs_file_name) != get_best_path(outfile_name):
                      # The paths are different so make the link
                      try:
                        alignem.print_debug ( 70, "UnLinking " + outfile_name )
                        os.unlink ( outfile_name )
                      except:
                        alignem.print_debug ( 70, "Error UnLinking " + outfile_name )
                      try:
                        alignem.print_debug ( 70, "Linking from " + abs_file_name + " to " + outfile_name )
                        os.symlink ( abs_file_name, outfile_name )
                      except:
                        alignem.print_debug ( 5, "Unable to link from " + abs_file_name + " to " + outfile_name )
                        alignem.print_debug ( 5, "Copying file instead" )
                        # Not all operating systems allow linking for all users (Windows 10, for example, requires admin rights)
                        try:
                          shutil.copy ( abs_file_name, outfile_name )
                        except:
                          alignem.print_debug ( 1, "Unable to link or copy from " + abs_file_name + " to " + outfile_name )
                          print_exception()
                  else:
                    try:
                      # Do the scaling
                      alignem.print_debug ( 70, "Copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(scale) )

                      if os.path.split ( os.path.split ( os.path.split ( abs_file_name )[0] )[0] )[1].startswith('scale_'):
                        # Convert the source from whatever scale is currently processed to scale_1
                        p,f = os.path.split(abs_file_name)
                        p,r = os.path.split(p)
                        p,s = os.path.split(p)
                        abs_file_name = os.path.join ( p, 'scale_1', r, f )

                      img = align_swiftir.swiftir.scaleImage ( align_swiftir.swiftir.loadImage(abs_file_name), fac=scale )
                      align_swiftir.swiftir.saveImage ( img, outfile_name )
                      # Change the base image for this scale to the new file
                      layer['images'][role]['filename'] = outfile_name
                    except:
                      alignem.print_debug ( 1, "Error copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(scale) )
                      print_exception()

                  # Update the Data Model with the new absolute file name. This replaces the originally opened file names
                  alignem.print_debug ( 40, "Original File Name: " + str(layer['images'][role]['filename']) )
                  layer['images'][role]['filename'] = outfile_name
                  alignem.print_debug ( 40, "Updated  File Name: " + str(layer['images'][role]['filename']) )
    #main_win.status.showMessage("Done Generating Scales ...")


def generate_scales_queue ():
    alignem.print_debug ( 1, "generate_scales_queue inside alignem_swift called" )

    image_scales_to_run = [ alignem.get_scale_val(s) for s in sorted(alignem.project_data['data']['scales'].keys()) ]

    alignem.print_debug ( 2, "Create images at all scales: " + str ( image_scales_to_run ) )

    if (alignem.project_data['data']['destination_path'] == None) or (len(alignem.project_data['data']['destination_path']) <= 0):

      alignem.show_warning ( "Note", "Scales can not be generated without a destination (use File/Set Destination)" )

    else:

      ### Create the queue here

      for scale in sorted(image_scales_to_run):

        alignem.print_debug ( 70, "Creating images for scale " + str(scale) )
        #main_win.status.showMessage("Generating Scale " + str(scale) + " ...")

        scale_key = str(scale)
        if not 'scale_' in scale_key:
          scale_key = 'scale_' + scale_key

        subdir_path = os.path.join(alignem.project_data['data']['destination_path'],scale_key)
        scale_1_path = os.path.join(alignem.project_data['data']['destination_path'],'scale_1')

        create_project_structure_directories (subdir_path)

        alignem.print_debug ( 70, "Begin creating images at each layer for key: " + str(scale_key))

        for layer in alignem.project_data['data']['scales'][scale_key]['alignment_stack']:
          alignem.print_debug (40, "Generating images for layer: \"" + str(alignem.project_data['data']['scales'][scale_key]['alignment_stack'].index(layer)) + "\"")
          # Remove previously aligned images from panel ??

          # Copy (or link) the source images to the expected scale_key"/img_src" directory
          for role in layer['images'].keys():

            # Only copy files for roles "ref" and "base"

            if role in ['ref', 'base']:
              alignem.print_debug (40, "Generating images for role: \"" + role + "\"")
              base_file_name = layer['images'][role]['filename']
              if base_file_name != None:
                if len(base_file_name) > 0:
                  abs_file_name = os.path.abspath(base_file_name)
                  bare_file_name = os.path.split(abs_file_name)[1]
                  destination_path = os.path.abspath ( alignem.project_data['data']['destination_path'] )
                  outfile_name = os.path.join(destination_path, scale_key, 'img_src', bare_file_name)
                  if scale == 1:
                    if get_best_path(abs_file_name) != get_best_path(outfile_name):
                      # The paths are different so make the link
                      try:
                        alignem.print_debug ( 70, "UnLinking " + outfile_name )
                        os.unlink ( outfile_name )
                      except:
                        alignem.print_debug ( 70, "Error UnLinking " + outfile_name )
                      try:
                        alignem.print_debug ( 70, "Linking from " + abs_file_name + " to " + outfile_name )
                        os.symlink ( abs_file_name, outfile_name )
                      except:
                        alignem.print_debug ( 5, "Unable to link from " + abs_file_name + " to " + outfile_name )
                        alignem.print_debug ( 5, "Copying file instead" )
                        # Not all operating systems allow linking for all users (Windows 10, for example, requires admin rights)
                        try:
                          shutil.copy ( abs_file_name, outfile_name )
                        except:
                          alignem.print_debug ( 1, "Unable to link or copy from " + abs_file_name + " to " + outfile_name )
                          print_exception()
                  else:
                    try:
                      # Do the scaling
                      alignem.print_debug ( 70, "Copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(scale) )

                      if os.path.split ( os.path.split ( os.path.split ( abs_file_name )[0] )[0] )[1].startswith('scale_'):
                        # Convert the source from whatever scale is currently processed to scale_1
                        p,f = os.path.split(abs_file_name)
                        p,r = os.path.split(p)
                        p,s = os.path.split(p)
                        abs_file_name = os.path.join ( p, 'scale_1', r, f )

                      ### Add this job to the task queue

                      img = align_swiftir.swiftir.scaleImage ( align_swiftir.swiftir.loadImage(abs_file_name), fac=scale )
                      align_swiftir.swiftir.saveImage ( img, outfile_name )
                      # Change the base image for this scale to the new file
                      layer['images'][role]['filename'] = outfile_name
                    except:
                      alignem.print_debug ( 1, "Error copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(scale) )
                      print_exception()

                  # Update the Data Model with the new absolute file name. This replaces the originally opened file names
                  alignem.print_debug ( 40, "Original File Name: " + str(layer['images'][role]['filename']) )
                  layer['images'][role]['filename'] = outfile_name
                  alignem.print_debug ( 40, "Updated  File Name: " + str(layer['images'][role]['filename']) )

      ### Join the queue here to ensure that all have been generated before returning

    #main_win.status.showMessage("Done Generating Scales ...")


def get_code_mode():
    ### All of this code is just trying to find the right menu item for the Use C Version check box:
    code_mode = 'python'
    menubar = alignem.main_window.menu
    menubar_items = [ menubar.children()[x].title() for x in range(len(menubar.children())) if 'title' in dir(menubar.children()[x]) ]
    submenus = [ menubar.children()[x] for x in range(len(menubar.children())) if 'title' in dir(menubar.children()[x]) ]
    alignem.print_debug ( 40, "Menubar contains: " + str(menubar_items) )
    setmenu_index = -1
    for m in menubar_items:
      if "Set" in m:
        setmenu_index = menubar_items.index(m)
    alignem.print_debug ( 40, "Set menu is item " + str(setmenu_index) )
    if setmenu_index >= 0:
      set_menu = submenus[setmenu_index]
      set_menu_actions = set_menu.actions()
      use_c_version = None
      for action in set_menu_actions:
        if "Use C Version" in action.text():
          use_c_version = action
          break
      if use_c_version != None:
        if use_c_version.isChecked():
          code_mode = "c"
    return ( code_mode )


def align_layers ( first_layer=0, num_layers=-1 ):
    alignem.print_debug ( 30, 100*'=' )
    if num_layers < 0:
      alignem.print_debug ( 30, "Aligning all layers starting with " + str(first_layer) + " using SWiFT-IR ..." )
    else:
      alignem.print_debug (30, "Aligning layers " + str (first_layer) + " through " + str (first_layer + num_layers - 1) + " using SWiFT-IR ...")
    alignem.print_debug ( 30, 100*'=' )

    remove_aligned(starting_layer=first_layer, prompt=False)

    ensure_proper_data_structure()

    code_mode = get_code_mode()

    # Check that there is a place to put the aligned images
    if (alignem.project_data['data']['destination_path'] == None) or (len(alignem.project_data['data']['destination_path']) <= 0):

      alignem.print_debug ( 1, "Error: Cannot align without destination set (use File/Set Destination)" )
      alignem.show_warning ( "Note", "Projects can not be aligned without a destination (use File/Set Destination)" )

    else:

      alignem.print_debug ( 10, "Aligning with output in " + alignem.project_data['data']['destination_path'] )
      scale_to_run_text = alignem.project_data['data']['current_scale']
      alignem.print_debug ( 10, "Aligning scale " + str(scale_to_run_text) )

      # Create the expected directory structure for pyswift_tui.py
      source_dir = os.path.join ( alignem.project_data['data']['destination_path'], scale_to_run_text, "img_src" )
      alignem.makedirs_exist_ok ( source_dir, exist_ok=True )
      target_dir = os.path.join ( alignem.project_data['data']['destination_path'], scale_to_run_text, "img_aligned" )
      alignem.makedirs_exist_ok ( target_dir, exist_ok=True )

      # Create links or copy files in the expected directory structure
      # os.symlink(src, dst, target_is_directory=False, *, dir_fd=None)
      this_scale = alignem.project_data['data']['scales'][scale_to_run_text]
      stack_at_this_scale = alignem.project_data['data']['scales'][scale_to_run_text]['alignment_stack']
      for layer in stack_at_this_scale:
        image_name = None
        if 'base' in layer['images'].keys():
          image = layer['images']['base']
          try:
            image_name = os.path.basename(image['filename'])
            destination_image_name = os.path.join(source_dir,image_name)
            shutil.copyfile(image.image_file_name, destination_image_name)
          except:
            pass

      # Copy the data model for this project to add local fields
      dm = copy.deepcopy ( alignem.project_data )
      # Add fields needed for SWiFT:
      stack_at_this_scale = dm['data']['scales'][scale_to_run_text]['alignment_stack']
      for layer in stack_at_this_scale:
        layer['align_to_ref_method']['method_data']['bias_x_per_image'] = 0.0
        layer['align_to_ref_method']['method_data']['bias_y_per_image'] = 0.0
        layer['align_to_ref_method']['selected_method'] = 'Auto Swim Align'

      # Run the project via pyswift_tui
      pyswift_tui.debug_level = alignem.debug_level
      updated_model, need_to_write_json = pyswift_tui.run_json_project ( project = dm,
                                                                         alignment_option = this_scale['method_data']['alignment_option'],
                                                                         use_scale = alignem.get_scale_val(scale_to_run_text),
                                                                         swiftir_code_mode = code_mode,
                                                                         start_layer = first_layer,
                                                                         num_layers = num_layers )

      if need_to_write_json:
          alignem.project_data = updated_model
      else:
          alignem.print_debug ( 1, 100*"+" )
          alignem.print_debug ( 1, "run_json_project returned with need_to_write_json=false" )
          alignem.print_debug ( 1, 100*"+" )
          # Load the alignment stack after the alignment has completed
          aln_image_stack = []
          stack_at_this_scale = alignem.project_data['data']['scales'][scale_to_run_text]['alignment_stack']

          for layer in stack_at_this_scale:

            image_name = None
            if 'base' in layer['images'].keys():
              image_name = layer['images']['base']['filename']

            # Convert from the base name to the standard aligned name:
            aligned_name = None
            if image_name != None:
              # The first scale is handled differently now, but it might be better to unify if possible
              if scale_to_run_text == "scale_1":
                aligned_name = os.path.join ( os.path.abspath(alignem.project_data['data']['destination_path']), scale_to_run_text, 'img_aligned', os.path.split(image_name)[-1] )
              else:
                name_parts = os.path.split(image_name)
                if len(name_parts) >= 2:
                  aligned_name = os.path.join ( os.path.split(name_parts[0])[0], os.path.join('img_aligned', name_parts[1]) )
            aln_image_stack.append ( aligned_name )
            alignem.print_debug ( 30, "Adding aligned image " + aligned_name )
            layer['images']['aligned'] = {}
            layer['images']['aligned']['filename'] = aligned_name
          try:
            main_win.load_images_in_role ( 'aligned', aln_image_stack )
          except:
            alignem.print_debug ( 1, "Error from main_win.load_images_in_role." )
            print_exception()
            pass
      refresh_all()

combo_name_to_dm_name = {'Init Affine':'init_affine', 'Refine Affine':'refine_affine', 'Apply Affine':'apply_affine'}
dm_name_to_combo_name = {'init_affine':'Init Affine', 'refine_affine':'Refine Affine', 'apply_affine':'Apply Affine'}

def align_all_or_some (first_layer=0, num_layers=-1, prompt=True):
    actually_remove = True
    if prompt:
        actually_remove = alignem.request_confirmation ("Note", "Do you want to delete aligned images from " + str(first_layer) + "?")

    if actually_remove:
        alignem.print_debug ( 5, "Removing aligned from scale " + str (alignem.get_cur_scale()) + " forward from layer " + str (first_layer) + "  (align_all_or_some)" )

        remove_aligned (starting_layer=first_layer,prompt=False)
        alignem.print_debug ( 30, "Aligning Forward with SWiFT-IR from layer " + str(first_layer) + " ..." )
        alignem.print_debug ( 70, "Control Model = " + str(control_model) )

        thing_to_do = init_ref_app.get_value ()
        scale_to_run_text = alignem.project_data['data']['current_scale']
        this_scale = alignem.project_data['data']['scales'][scale_to_run_text]
        this_scale['method_data']['alignment_option'] = str(combo_name_to_dm_name[thing_to_do])
        alignem.print_debug ( 5, '')
        alignem.print_debug ( 5, 40 * '@=' + '@')
        alignem.print_debug ( 5, 40 * '=@' + '=')
        alignem.print_debug ( 5, 40 * '@=' + '@')
        alignem.print_debug ( 5, '')
        alignem.print_debug ( 5, "Doing " + thing_to_do + " which is: " + str(combo_name_to_dm_name[thing_to_do]))
        alignem.print_debug ( 5, '')
        alignem.print_debug ( 5, 40 * '@=' + '@')
        alignem.print_debug ( 5, 40 * '=@' + '=')
        alignem.print_debug ( 5, 40 * '@=' + '@')
        alignem.print_debug ( 5, '')
        align_layers(first_layer, num_layers)
        refresh_all()

def align_forward():
    num_layers = num_fwd.get_value ()
    first_layer = alignem.project_data['data']['current_layer']
    alignem.print_debug ( 5, "Inside 'align_forward' with first_layer=" + str(first_layer))
    align_all_or_some (first_layer,num_layers,prompt=True)
    refresh_all()

def regenerate_aligned():
    print ( "Regenerate Aligned ... not working yet.")

def jump_to_layer():
    requested_layer = jump_to_val.get_value()
    alignem.print_debug ( 3, "Jump to layer " + str(requested_layer) )
    num_layers = len(alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'])
    if requested_layer >= num_layers: # Limit to largest
        requested_layer = num_layers - 1
    if requested_layer < 0: # Consider negative values as indexes from the end
        requested_layer = num_layers + requested_layer
    if requested_layer < 0: # If the end index was greater than the length, just show 0
        requested_layer = 0
    alignem.project_data['data']['current_layer'] = requested_layer
    main_win.image_panel.update_multi_self()

def center_all():
    main_win.center_all_images()


def refresh_all ():
    main_win.refresh_all_images ()


def remove_aligned(starting_layer=0, prompt=True):
    alignem.print_debug ( 5, "Removing aligned from scale " + str(alignem.get_cur_scale()) + " forward from layer " + str(starting_layer) + "  (remove_aligned)" )
    actually_remove = True
    if prompt:
        actually_remove = alignem.request_confirmation ("Note", "Do you want to delete aligned images?")
    if actually_remove:
        alignem.print_debug ( 5, "Removing aligned images ..." )

        delete_list = []

        layer_index = 0
        for layer in alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack']:
          if layer_index >= starting_layer:
            alignem.print_debug ( 5, "Removing Aligned from Layer " + str(layer_index) )
            if 'aligned' in layer['images'].keys():
              delete_list.append ( layer['images']['aligned']['filename'] )
              alignem.print_debug (5, "  Removing " + str (layer['images']['aligned']['filename']))
              layer['images'].pop('aligned')
              # Remove the method results since they are no longer applicable
              if 'align_to_ref_method' in layer.keys():
                if 'method_results' in layer['align_to_ref_method']:
                  # Set the "method_results" to an empty dictionary to signify no results:
                  layer['align_to_ref_method']['method_results'] = {}
          layer_index += 1

        #alignem.image_library.remove_all_images()

        for fname in delete_list:
          if fname != None:
            if os.path.exists(fname):
              os.remove(fname)
              alignem.image_library.remove_image_reference ( fname )

        main_win.update_panels()
        refresh_all ()


def method_debug():
    alignem.print_debug ( 1, "In Method debug for " + str(__name__) )
    __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

def notyet():
    alignem.print_debug ( 0, "Function not implemented yet. Skip = " + str(skip.value) )


def view_change_callback ( prev_scale_key, next_scale_key, prev_layer_num, next_layer_num, new_data_model=False ):
    alignem.print_debug ( 3, "\nView changed from scale,layer " + str((prev_scale_key,prev_layer_num)) + " to " + str((next_scale_key,next_layer_num)) )

    if alignem.project_data != None:

      copy_from_widgets_to_data_model = True
      copy_from_data_model_to_widgets = True

      if new_data_model:
          # Copy all data from the data model into the widgets, ignoring what's in the widgets
          # But don't copy from the widgets to the data model
          copy_from_widgets_to_data_model = False
      elif (prev_scale_key == None) or (next_scale_key == None):
          # None signals a button change and not an actual layer or scale change
          # Copy all of the data from the widgets into the data model
          # But don't copy from the data model to the widgets
          copy_from_data_model_to_widgets = False

      # Set up convenient prev and next layer references
      prev_layer = None
      next_layer = None
      if prev_scale_key in alignem.project_data['data']['scales']:
          if prev_layer_num in range(len(alignem.project_data['data']['scales'][prev_scale_key]['alignment_stack'])):
              prev_layer = alignem.project_data['data']['scales'][prev_scale_key]['alignment_stack'][prev_layer_num]
      if next_scale_key in alignem.project_data['data']['scales']:
          if next_layer_num in range(len(alignem.project_data['data']['scales'][next_scale_key]['alignment_stack'])):
              next_layer = alignem.project_data['data']['scales'][next_scale_key]['alignment_stack'][next_layer_num]

      # Begin the copying

      # First copy from the widgets to the previous data model if desired
      if copy_from_widgets_to_data_model:

          # Start with the scale-level items

          # Build any scale-level structures that might be needed
          if not 'method_data' in alignem.project_data['data']['scales'][prev_scale_key]:
              alignem.project_data['data']['scales'][prev_scale_key]['method_data'] = {}

          # Copy the scale-level data
          alignem.project_data['data']['scales'][prev_scale_key]['null_cafm_trends'] = make_bool(null_cafm_trends.get_value())
          alignem.project_data['data']['scales'][prev_scale_key]['use_bounding_rect'] = make_bool(use_bounding_rect.get_value())
          alignem.project_data['data']['scales'][prev_scale_key]['poly_order'] = poly_order.get_value()
          alignem.project_data['data']['scales'][prev_scale_key]['method_data']['alignment_option'] = str(combo_name_to_dm_name[init_ref_app.get_value()])

          alignem.print_debug ( 5, "In DM: Null Bias = " + str (alignem.project_data['data']['scales'][prev_scale_key]['null_cafm_trends']) )
          alignem.print_debug ( 5, "In DM: Use Bound = " + str (alignem.project_data['data']['scales'][prev_scale_key]['use_bounding_rect']) )

          # Next copy the layer-level items
          if prev_layer != None:

              # Build any layer-level structures that might be needed in the data model
              if not 'align_to_ref_method' in prev_layer:
                  prev_layer['align_to_ref_method'] = {}
              if not 'method_data' in prev_layer['align_to_ref_method']:
                  prev_layer ['align_to_ref_method']['method_data'] = {}

              # Copy the layer-level data
              prev_layer ['skip'] = make_bool(skip.get_value())
              prev_layer ['align_to_ref_method']['method_data']['whitening_factor'] = whitening_factor.get_value()
              prev_layer ['align_to_ref_method']['method_data']['win_scale_factor'] = win_scale_factor.get_value()

      # Second copy from the data model to the widgets if desired (check each along the way)
      if copy_from_data_model_to_widgets:

          alignem.ignore_changes = True

          # Start with the scale-level items

          if 'null_cafm_trends' in alignem.project_data['data']['scales'][next_scale_key]:
              null_cafm_trends.set_value (alignem.project_data['data']['scales'][next_scale_key]['null_cafm_trends'])
          if 'use_bounding_rect' in alignem.project_data['data']['scales'][next_scale_key]:
              use_bounding_rect.set_value (alignem.project_data['data']['scales'][next_scale_key]['use_bounding_rect'])
          if 'poly_order' in alignem.project_data['data']['scales'][next_scale_key]:
              poly_order.set_value (alignem.project_data['data']['scales'][next_scale_key]['poly_order'])
          if 'method_data' in alignem.project_data['data']['scales'][next_scale_key]:
              if 'alignment_option' in alignem.project_data['data']['scales'][next_scale_key]['method_data']:
                  new_option = alignem.project_data['data']['scales'][next_scale_key]['method_data']['alignment_option']
                  init_ref_app.set_value (dm_name_to_combo_name[new_option])

          # Next copy the layer-level items

          if next_layer != None:
              # Copy the layer-level data
              if 'skip' in next_layer:
                  skip.set_value ( next_layer ['skip'] )
              if 'align_to_ref_method' in next_layer:
                  if 'method_data' in next_layer['align_to_ref_method']:
                      if 'whitening_factor' in next_layer['align_to_ref_method']['method_data']:
                          whitening_factor.set_value ( next_layer['align_to_ref_method']['method_data']['whitening_factor'] )
                      if 'win_scale_factor' in next_layer['align_to_ref_method']['method_data']:
                          win_scale_factor.set_value (next_layer['align_to_ref_method']['method_data']['win_scale_factor'])

          alignem.ignore_changes = False


def mouse_down_callback ( role, screen_coords, image_coords, button ):
    global match_pt_mode
    if match_pt_mode.get_value():
        alignem.print_debug ( 20, "Adding a match point for role \"" + str(role) + "\" at " + str(screen_coords) + " == " + str(image_coords) )
        scale_key = alignem.project_data['data']['current_scale']
        layer_num = alignem.project_data['data']['current_layer']
        stack = alignem.project_data['data']['scales'][scale_key]['alignment_stack']
        layer = stack[layer_num]

        if not 'metadata' in layer['images'][role]:
            layer['images'][role]['match_points'] = {}

        metadata = layer['images'][role]['metadata']

        if not 'match_points' in metadata:
            metadata['match_points'] = []
        match_point_data = [ c for c in image_coords ]
        metadata['match_points'].append ( match_point_data )

        if not 'annotations' in metadata:
            metadata['annotations'] = []
        '''
        # Use default colors when commented, so there are no colors in the JSON
        if not 'colors' in metadata:
            metadata['colors'] = [ [ 255, 0, 0 ], [ 0, 255, 0 ], [ 0, 0, 255 ], [ 255, 255, 0 ], [ 255, 0, 255 ], [ 0, 255, 255 ] ]
        '''

        match_point_data = [ m for m in match_point_data ]

        color_index = len(metadata['annotations'])
        match_point_data.append ( color_index )

        metadata['annotations'].append ( "circle(%f,%f,10,%d)" % tuple(match_point_data) )
        for ann in metadata['annotations']:
          alignem.print_debug ( 20, "   Annotation: " + str(ann) )
        return ( True )  # Lets the framework know that the click has been handled
    else:
        # print_debug ( 10, "Do Normal Processing" )
        return ( False ) # Lets the framework know that the click has not been handled

def mouse_move_callback ( role, screen_coords, image_coords, button ):
    global match_pt_mode
    if match_pt_mode.get_value():
        return ( True )  # Lets the framework know that the move has been handled
    else:
        return ( False ) # Lets the framework know that the move has not been handled

def clear_match_points():
    global match_pt_mode
    if not match_pt_mode.get_value():
        alignem.print_debug ( 1, "\nMust be in \"Match\" mode to delete all match points." )
    else:
        alignem.print_debug ( 20, "Deleting all match points for this layer" )
        scale_key = alignem.project_data['data']['current_scale']
        layer_num = alignem.project_data['data']['current_layer']
        stack = alignem.project_data['data']['scales'][scale_key]['alignment_stack']
        layer = stack[layer_num]

        for role in layer['images'].keys():
            if 'metadata' in layer['images'][role]:
                layer['images'][role]['metadata']['match_points'] = []
                layer['images'][role]['metadata']['annotations'] = []
        main_win.update_panels()
        main_win.refresh_all_images ()

def clear_all_skips():
    image_scale_keys = [ s for s in sorted(alignem.project_data['data']['scales'].keys()) ]
    for scale in image_scale_keys:
        scale_key = str(scale)
        for layer in alignem.project_data['data']['scales'][scale_key]['alignment_stack']:
            layer['skip'] = False
    skip.set_value(False)

def copy_skips_to_all_scales():
    source_scale_key = alignem.project_data['data']['current_scale']
    if not 'scale_' in str(source_scale_key):
        source_scale_key = 'scale_' + str(source_scale_key)
    scales = alignem.project_data['data']['scales']
    image_scale_keys = [ s for s in sorted(scales.keys()) ]
    for scale in image_scale_keys:
        scale_key = str(scale)
        if not 'scale_' in str(scale_key):
            scale_key = 'scale_' + str(scale_key)
        if scale_key != source_scale_key:
            for l in range(len(scales[source_scale_key]['alignment_stack'])):
                if l < len(scales[scale_key]['alignment_stack']):
                    scales[scale_key]['alignment_stack'][l]['skip'] = scales[source_scale_key]['alignment_stack'][l]['skip']
    # Not needed: skip.set_value(scales[source_scale_key]['alignment_stack'][alignem.project_data['data']['current_layer']]['skip']


link_stack_cb = CallbackButton('Link Stack', link_stack)
gen_scales_cb = CallbackButton('Gen Scales', generate_scales)
gen_scalesq_cb = CallbackButton('Gen Scales Q', generate_scales_queue)
align_all_cb  = CallbackButton('Align All', align_all_or_some)
center_cb     = CallbackButton('Center', center_all)
align_fwd_cb  = CallbackButton('Align Forward', align_forward)
init_ref_app  = ComboBoxControl(['Init Affine', 'Refine Affine', 'Apply Affine'])

poly_order   = IntField("Poly Order:",4,1)

regen_aligned_cb = CallbackButton('Regenerate Aligned', regenerate_aligned)
num_fwd       = IntField("#",1,1)
jump_to_cb    = CallbackButton('Jump To:', jump_to_layer)
jump_to_val   = IntField("#",1,1)
rem_algn_cb   = CallbackButton('Remove Aligned', remove_aligned)
skip          = BoolField("Skip",False)
match_pt_mode = BoolField("Match",False)
clear_match   = CallbackButton("Clear Match", clear_match_points)
progress_cb   = CallbackButton('Prog Bar', run_progress)
gen_scales_thread_cb = CallbackButton('Gen Scales (thread)', gen_scales_with_thread)
link_stacks_cb = CallbackButton("Link All Stacks", link_all_stacks )
debug_cb       = CallbackButton('Debug', method_debug)

clear_skips_cb = CallbackButton("Clear all Skips", clear_all_skips)
skips_to_all_cb = CallbackButton('Skips -> All Scales', copy_skips_to_all_scales)

refine_aff_cb  = CallbackButton('Refine Affine', notyet)
apply_aff_cb  = CallbackButton('Apply Affine', notyet)
whitening_factor  = FloatField('Whitening', -0.68)
win_scale_factor  = FloatField('Window Scale Factor', 0.8125)

null_cafm_trends  = BoolField("Null Bias",False)
use_bounding_rect = BoolField("Bounding Rect",False)

control_model = [
  # Panes
  [ # Begin first pane of rows
    [
      gen_scales_cb,
      " ", gen_scalesq_cb,
      " ", link_stacks_cb,
      " ", poly_order,
      " ", null_cafm_trends,
      " ", use_bounding_rect,
      " ", align_all_cb,
      " ", align_fwd_cb, num_fwd,
      " ", jump_to_cb, jump_to_val,
      " ", center_cb,
      "  ", rem_algn_cb,
      "    ", skip,
      "  ", match_pt_mode,
      " ", clear_match,
      "    "
    ],
    [
      # "Test: ",
      # gen_scales_thread_cb,
      " ", link_stack_cb,
      " ", init_ref_app,
      #" ", do_thing_cb,
      #" ", refine_aff_cb,
      #" ", apply_aff_cb,
      " ", regen_aligned_cb,
      " ", clear_skips_cb,
      " ", skips_to_all_cb,
      " ", whitening_factor,
      " ", win_scale_factor,
      # " ", progress_cb,
      " ", debug_cb
    ]
  ] # End first pane
]

from source_tracker import get_hash_and_rev

global_source_rev = ""
global_source_hash = ""

if __name__ == "__main__":

    alignem.debug_level = 10

    options = argparse.ArgumentParser()
    options.add_argument("-d", "--debug", type=int, required=False, help="Print more information with larger DEBUG (0 to 100)")
    args = options.parse_args()

    if args.debug != None:
      alignem.debug_level = args.debug
    try:
      if args.debug != None:
        alignem.debug_level = int(args.debug)
        align_swiftir.debug_level = int(args.debug)
    except:
        pass

    source_list = [
      "alignem_swift.py",
      "alignem_data_model.py",
      "alignem.py",
      "swift_project.py",
      "pyswift_tui.py",
      "swiftir.py",
      "align_swiftir.py",
      "source_tracker.py",
      "task_queue.py",
      "task_wrapper.py"
    ]
    global_source_hash, global_source_rev = get_hash_and_rev (source_list, "source_info.json")
    control_model[0].append ( [ "Source Tag: " + str(global_source_rev), " ", "Source Hash: " + str(global_source_hash) ] )

    print ("\n\nRunning with source hash: " + str (global_source_hash) + ", tagged as revision: " + str (global_source_rev)+"\n\n")

    main_win = alignem.MainWindow ( control_model=control_model, title="Align SWiFT-IR" )
    main_win.register_view_change_callback ( view_change_callback )
    main_win.register_mouse_move_callback ( mouse_move_callback )
    main_win.register_mouse_down_callback ( mouse_down_callback )

    main_win.resize(1400,640)  # This value is typically chosen to show all widget text

    #main_win.register_project_open ( open_json_project )
    #main_win.register_project_save ( save_json_project )
    #main_win.register_gen_scales ( generate_scales )

    alignem.print_debug ( 30, "================= Defining Roles =================" )

    main_win.define_roles ( swift_roles )

    alignem.run_app(main_win)

