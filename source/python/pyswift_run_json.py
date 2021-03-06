#!/usr/bin/env python

#__import__('code').interact(local = locals())

#import numpy as np
#import cv2

import time
import os
import sys
import json
import math
import random
import shutil

import align_swiftir

global debug_level
debug_level = 50

def print_debug ( level, str ):
  global debug_level
  if level < debug_level:
    print ( str )

def run_alignment ( project_file_name,
                    align_all,
                    alignment_layer_index,
                    num_forward,
                    snr_skip,
                    snr_halt ):

  ''' Runs alignment from a project file. '''

  if debug_level > 0:
    print_debug ( 1, "===============================================================================" )
    print_debug ( 1, "===============================================================================" )
    print_debug ( 1, "================= Running from inside of pyswift_run_json.py ==================" )
    print_debug ( 1, "===============================================================================" )
    print_debug ( 1, "===============================================================================" )


  project_path = project_file_name ## os.path.dirname(project_file_name)
  destination_path = ""

  f = open ( project_file_name, 'r' )
  text = f.read()
  proj_dict = json.loads ( text )

  if debug_level > 75: print ( str(proj_dict) )

  print ( "Project file version " + str(proj_dict['version']) )
  if proj_dict['version'] < 0.05:
    print ( "Unable to read from versions before 0.1" )
    exit (99)
  if proj_dict['version'] > 0.15:
    print ( "Unable to read from versions above 0.1" )
    exit (99)
  print ( "Project file method " + str(proj_dict['method']) )

  if 'data' in proj_dict:
    print ( "Project file has a data section" )
    if 'destination_path' in proj_dict['data']:
      destination_path = proj_dict['data']['destination_path']
      # Make the destination absolute
      if not os.path.isabs(destination_path):
        destination_path = os.path.join ( project_path, destination_path )
      destination_path = os.path.realpath ( destination_path )
      # gui_fields.dest_label.set_text ( "Destination: " + str(destination_path) )
    if 'alignment_stack' in proj_dict['data']:
      imagestack = proj_dict['data']['alignment_stack']
      if debug_level > 65:
        for i in range(len(imagestack)):
          layer = imagestack[i]
          print ( "  layer " + str(i) + " = " + str(layer) )


      # Create a list of alignment pairs accounting for skips, start point, and number to align

      align_pairs = []  # List of images to align with each other, a repeated index means copy directly to the output (a "golden section")
      last_ref = -1
      for i in range(len(imagestack)):
        print_debug ( 50, "Aligning with method = " + imagestack[i]['align_to_ref_method']['selected_method'] )
        if imagestack[i]['skip'] == False:
          if last_ref < 0:
            # This image was not skipped, but their is no previous, so just copy to itself
            align_pairs.append ( [i, i, imagestack[i]['align_to_ref_method']] )
          else:
            # There was a previously unskipped image and this image is unskipped
            # Therefore, add this pair to the list
            align_pairs.append ( [last_ref, i, imagestack[i]['align_to_ref_method']] )
          # This unskipped image will always become the last unskipped (reference) for next unskipped
          last_ref = i
        else:
          # This should just remove those image_dict items that shouldn't show when skipped
          # This creates a blank image for the GUI. Maybe it should copy?
          # imagestack[i].image_dict['aligned'] = annotated_image(None, role="aligned")
          pass

      print_debug ( 50, "Full list after removing skips:" )
      for apair in align_pairs:
        print_debug ( 50, "  Alignment pair: " + str(apair) )

      if not align_all:
        # Retain only those pairs that start after this index
        if alignment_layer_index == 0:
          # Include the current layer to make the original copy again
          new_pairs = [ p for p in align_pairs if p[1] >= alignment_layer_index ]
        else:
          # Exclude the current layer
          new_pairs = [ p for p in align_pairs if p[1] >= alignment_layer_index ]
        align_pairs = new_pairs
        # Remove any pairs beyond the number forward
        if not (num_forward is None):
          new_pairs = [ p for p in align_pairs if p[1] < alignment_layer_index+num_forward ]
          align_pairs = new_pairs

      print_debug ( 50, "Full list after removing start and forward limits:" )
      for apair in align_pairs:
        print_debug ( 70, "  Alignment pair: " + str(apair) )

      for apair in align_pairs:
        print_debug ( 10, "  Align: " + str(imagestack[apair[1]]['images']['base']['filename']) +
                          " to " + str(imagestack[apair[0]]['images']['base']['filename']) +
                          " with ww = " + str(imagestack[apair[0]]['align_to_ref_method']['method_data']['window_size']) +
                          ", addx = " + str(imagestack[apair[0]]['align_to_ref_method']['method_data']['addx']) +
                          ", addy = " + str(imagestack[apair[0]]['align_to_ref_method']['method_data']['addy']) +
                          ", bias x = " + str(imagestack[apair[0]]['align_to_ref_method']['method_data']['bias_x_per_image']) +
                          ", bias y = " + str(imagestack[apair[0]]['align_to_ref_method']['method_data']['bias_y_per_image'])
                    )





      """
      if len(imagestack) > 0:
        alignment_layer_index = 0
        alignment_layer_list = []
        for json_alignment_layer in imagestack:
          if 'images' in json_alignment_layer:
            im_list = json_alignment_layer['images']
            if 'base' in im_list:
              base = im_list['base']
              if 'filename' in base:
                image_fname = base['filename']
                # Convert to absolute as needed
                if not os.path.isabs(image_fname):
                  image_fname = os.path.join ( project_path, image_fname )
                image_fname = os.path.realpath ( image_fname )
                print ( "Base Image = " + image_fname )
                if 'skip' in json_alignment_layer:
                  skip = json_alignment_layer['skip']

                if 'align_to_ref_method' in json_alignment_layer:
                  json_align_to_ref_method = json_alignment_layer['align_to_ref_method']
                  print ( "Method = " + str(json_align_to_ref_method['selected_method']) )
                  print ( "  opts = " + str([ str(x) for x in json_align_to_ref_method['method_options'] ]) )

                  if 'method_data' in json_align_to_ref_method:
                    pars = json_align_to_ref_method['method_data']
                    print ( "trans_ww = " + str(pars['window_size']) )
                    print ( "trans_addx = " + str(pars['addx']) )
                    print ( "trans_addy = " + str(pars['addy']) )
                    print ( "affine_enabled = " + str(True) )
                    print ( "affine_ww = " + str(pars['window_size']) )
                    print ( "affine_addx = " + str(pars['addx']) )
                    print ( "affine_addy = " + str(pars['addy']) )
                    print ( "bias_enabled = " + str(False) )
                    print ( "bias_dx = " + str(0) )
                    print ( "bias_dy = " + str(0) )
                    print ( "Got method_data" + str(pars) )
                    if 'bias_x_per_image' in pars:
                      print ( "bias_dx = " + str(pars['bias_x_per_image']) )
                    if 'bias_y_per_image' in pars:
                      print ( "bias_dy = " + str(pars['bias_y_per_image']) )

                  if 'method_results' in json_align_to_ref_method:
                    json_method_results = json_align_to_ref_method['method_results']
                    if 'cumulative_afm' in json_method_results:
                      print ( "Loading a cumulative_afm from JSON" )

                      print ( "results_dict['snr'] = " + str(json_method_results['snr']) ) # Copy
                      print ( "results_dict['affine'] = " + str([ [ c for c in r ] for r in json_method_results['affine_matrix'] ]) ) # Copy
                      print ( "results_dict['cumulative_afm'] = " + str([ [ c for c in r ] for r in json_method_results['cumulative_afm'] ]) ) # Copy

                # Load match points into the base image (if found)
                if 'metadata' in base:
                  if 'match_points' in base['metadata']:
                    mp = base['metadata']['match_points']
                    for p in mp:
                      print ( "%%%% GOT BASE MATCH POINT: " + str(p) )
                      m = graphic_marker ( p[0], p[1], 6, 'i', [1, 1, 0.5] )
                      print ( "image_dict['base'].graphics_items.append " + str( m ) )
                  if 'annotations' in base['metadata']:
                    ann_list = base['metadata']['annotations']
                    for ann_item in ann_list:
                      print ( "Base has " + str(ann_item) )
                      # print ( "image_dict[\"base\"].graphics_items " + str( graphic_primitive().from_json ( ann_item ) ) )

                # Only look for a ref or aligned if there has been a base
                if 'ref' in im_list:
                  ref = im_list['ref']
                  if 'filename' in ref:
                    image_fname = ref['filename']
                    print ( "Ref Image = " + image_fname )
                    '''
                    if len(image_fname) <= 0:
                      # Don't try to load empty images
                      print ( "image_dict['ref'] = " + str(annotated_image(None, role="ref")) )
                    else:
                      # Convert to absolute as needed
                      if not os.path.isabs(image_fname):
                        image_fname = os.path.join ( project_path, image_fname )
                      image_fname = os.path.realpath ( image_fname )
                      print ( "image_dict["ref"] = " + str(annotated_image(image_fname,role="ref")) )

                      # Load match points into the ref image (if found)
                      if 'metadata' in ref:
                        if 'match_points' in ref['metadata']:
                          mp = ref['metadata']['match_points']
                          for p in mp:
                            print ( "%%%% GOT REF MATCH POINT: " + str(p) )
                            m = graphic_marker ( p[0], p[1], 6, 'i', [1, 1, 0.5] )
                            print ( "image_dict['ref'].graphics_items.append ( m )
                        if 'annotations' in ref['metadata']:
                          ann_list = ref['metadata']['annotations']
                          for ann_item in ann_list:
                            print ( "Ref has " + str(ann_item) )
                            print ( "image_dict["ref"].graphics_items.append ( graphic_primitive().from_json ( ann_item ) )
                    '''

                if 'aligned' in im_list:
                  aligned = im_list['aligned']
                  if 'filename' in aligned:
                    image_fname = aligned['filename']
                    print ( "Aligned Image = " + image_fname )
                    '''
                    if len(image_fname) <= 0:
                      # Don't try to load empty images
                      print ( "image_dict['ref'] = " + str(annotated_image(None, role="ref")) )
                    else:
                      # Convert to absolute as needed
                      if not os.path.isabs(image_fname):
                        image_fname = os.path.join ( project_path, image_fname )
                      image_fname = os.path.realpath ( image_fname )
                      print ( "image_dict[\"aligned\"] = " + str(annotated_image(image_fname,role="aligned")) )
                    '''
                  '''
                  if 'metadata' in aligned:
                    if 'annotations' in aligned['metadata']:
                      ann_list = aligned['metadata']['annotations']
                      for ann_item in ann_list:
                        print ( "Aligned has " + str(ann_item) )
                        print ( "image_dict["aligned"].graphics_items.append ( graphic_primitive().from_json ( ann_item ) )
                  '''

                #alignment_layer_list.append ( a )
                #print ( "Internal bias_x after appending: " + str(a.bias_dx) )
      """


  print ( "Done with run_json_project.py" )


if __name__ == '__main__':
  import sys
  if len(sys.argv) > 1:
    for arg in sys.argv[1:]:
      try:
        s = int(arg)
      except:
        pass
  run_alignment()

