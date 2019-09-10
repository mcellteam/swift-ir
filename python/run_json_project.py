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

from pyswift_gui import graphic_primitive

def main():
  import sys
  if len(sys.argv) > 1:
    for arg in sys.argv[1:]:
      try:
        s = int(arg)
      except:
        pass
  #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
  print ( "Inside run_json_project.py" )

  project_file_name = "run_project.json"
  project_path = project_file_name ## os.path.dirname(project_file_name)
  destination_path = ""

  f = open ( project_file_name, 'r' )
  text = f.read()
  proj_dict = json.loads ( text )

  print ( str(proj_dict) )

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
                      print ( "image_dict[\"base\"].graphics_items " + str( graphic_primitive().from_json ( ann_item ) ) )

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


  print ( "Done with run_json_project.py" )

if __name__ == '__main__':
  main()

