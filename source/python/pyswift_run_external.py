#!/usr/bin/env python

#__import__('code').interact(local = locals())

#import numpy as np
#import cv2

import os
import sys
import shutil

from pyswift_gui import annotated_image
from pyswift_gui import graphic_dot
from pyswift_gui import graphic_text
from pyswift_gui import str2D
from pyswift_gui import print_debug

import _alignment_process


def run_alignment ( align_all,
                    alignment_layer_list,
                    alignment_layer_index,
                    num_forward,
                    snr_skip,
                    snr_halt,
                    destination_path,
                    panel_list,
                    project_file_name ):


  print_debug ( 1, "===============================================================================" )
  print_debug ( 1, "===============================================================================" )
  print_debug ( 1, "=============== Running from inside of pyswift_run_external.py ================" )
  print_debug ( 1, "===============================================================================" )
  print_debug ( 1, "===============================================================================" )

  # Set up the preferred panels as needed
  ref_panel = None
  base_panel = None
  aligned_panel = None

  # Remove all windows to force desired arrangement
  #print_debug ( 50, "Note: deleting all windows to force preferred" )
  #while len(panel_list) > 0:
  #  rem_panel_callback ( zpa_original )

  # Start by assigning any panels with roles already set
  for panel in panel_list:
    if panel.role == 'ref':
      ref_panel = panel
    if panel.role == 'base':
      base_panel = panel
    if panel.role == 'aligned':
      aligned_panel = panel

  # Assign any empty panels if needed
  for panel in panel_list:
    if panel.role == '':
      if ref_panel == None:
        panel.role = 'ref'
        ref_panel = panel
      elif base_panel == None:
        panel.role = 'base'
        base_panel = panel
      elif aligned_panel == None:
        panel.role = 'aligned'
        aligned_panel = panel

  # Finally add panels as needed
  #if ref_panel == None:
  #  add_panel_callback ( zpa_original, role='ref', point_add_enabled=True )
  #if base_panel == None:
  #  add_panel_callback ( zpa_original, role='base', point_add_enabled=True )
  #if aligned_panel == None:
  #  add_panel_callback ( zpa_original, role='aligned', point_add_enabled=False )

  # The previous logic hasn't worked, so force all panels to be as desired for now
  forced_panel_roles = ['ref', 'base', 'aligned']
  for i in range ( min ( len(panel_list), len(forced_panel_roles) ) ):
    panel_list[i].role = forced_panel_roles[i]


  # Create a list of alignment pairs accounting for skips, start point, and number to align

  align_pairs = []  # List of images to align with each other, a repeated index means copy directly to the output (a "golden section")
  last_ref = -1
  for i in range(len(alignment_layer_list)):
    print_debug ( 50, "Aligning with method " + str(alignment_layer_list[i].align_method) + " = " + alignment_layer_list[i].align_method_text )
    if alignment_layer_list[i].skip == False:
      if last_ref < 0:
        # This image was not skipped, but their is no previous, so just copy to itself
        align_pairs.append ( [i, i, alignment_layer_list[i].align_method] )
      else:
        # There was a previously unskipped image and this image is unskipped
        # Therefore, add this pair to the list
        align_pairs.append ( [last_ref, i, alignment_layer_list[i].align_method] )
      # This unskipped image will always become the last unskipped (reference) for next unskipped
      last_ref = i
    else:
      # This should just remove those image_dict items that shouldn't show when skipped
      alignment_layer_list[i].image_dict['aligned'] = annotated_image(None, role="aligned")

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
    print_debug ( 50, "  Alignment pair: " + str(apair) )

  for apair in align_pairs:
    i = apair[0] # Reference
    j = apair[1] # Current moving
    m = apair[2] # Alignment Method (0=SwimWindow, 1=MatchPoint)
    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
    print_debug ( 50, "===============================================================================" )
    print_debug ( 50, "Aligning base:" + str(j) + " to ref:" + str(i) + " with method " + str(m) + " using:" )
    print_debug ( 50, "" )
    print_debug ( 50, "  method                   = " + str(['Auto Swim Align', 'Match Point Align'][m]) )
    print_debug ( 50, "  ref                     = " + str(alignment_layer_list[i].base_image_name) )
    print_debug ( 50, "  base                   = " + str(alignment_layer_list[j].base_image_name) )
    print_debug ( 50, "  skip                     = " + str(alignment_layer_list[j].skip) )
    print_debug ( 50, "" )
    print_debug ( 50, "  Image List for Layer " + str(i) + " contains:" + str(sorted(alignment_layer_list[i].image_dict.keys(), reverse=True)) )
    # Tom: print_debug ( 50, "  Image List for Layer " + str(j) + " contains:" + str(sorted(alignment_layer_list[j].image_dict.keys(), reverse=True)) )
    for k in sorted(alignment_layer_list[j].image_dict.keys(), reverse=True):
      im = alignment_layer_list[j].image_dict[k]
      print_debug ( 50, "    " + str(k) + " alignment points: " + str(im.get_marker_points()) )
    print_debug ( 50, "" )
    print_debug ( 50, "  translation window width = " + str(alignment_layer_list[j].trans_ww) )
    print_debug ( 50, "  translation addx         = " + str(alignment_layer_list[j].trans_addx) )
    print_debug ( 50, "  translation addy         = " + str(alignment_layer_list[j].trans_addy) )
    print_debug ( 50, "" )
    print_debug ( 50, "  python_swiftir enabled           = " + str(alignment_layer_list[j].affine_enabled) )
    print_debug ( 50, "  python_swiftir window width      = " + str(alignment_layer_list[j].affine_ww) )
    print_debug ( 50, "  python_swiftir addx              = " + str(alignment_layer_list[j].affine_addx) )
    print_debug ( 50, "  python_swiftir addy              = " + str(alignment_layer_list[j].affine_addy) )
    print_debug ( 50, "" )
    print_debug ( 50, "  bias enabled             = " + str(alignment_layer_list[j].bias_enabled) )
    print_debug ( 50, "  bias dx                  = " + str(alignment_layer_list[j].bias_dx) )
    print_debug ( 50, "  bias dy                  = " + str(alignment_layer_list[j].bias_dy) )


  # Perform the actual alignment
  snr_value = sys.float_info.max
  for apair in align_pairs:
    i = apair[0] # Reference
    j = apair[1] # Current moving
    m = apair[2] # Alignment Method (0=SwimWindow, 1=MatchPoint)
    snr_value = 0


    if alignment_layer_list[j].image_dict == None:
      print_debug ( 50, "Creating image dictionary for layer " + str(j) )
      alignment_layer_list[j].image_dict = {}

    # TEMP dict to try out match point alignment
    if m==1:
      mp_base = alignment_layer_list[j].image_dict['base'].get_marker_points()
      mp_ref = alignment_layer_list[j].image_dict['ref'].get_marker_points()
      layer_dict = {
		     "images": {
				 "base": {
					   "metadata": {
							 "match_points": mp_base
					   }
				 },
				 "ref": {
					   "metadata": {
							 "match_points": mp_ref
					   }
				 }
		     },
		     "align_to_ref_method": {
					      "selected_method": "Match Point Align",
					      "method_options": [
								  "Auto Swim Align",
								  "Match Point Align"
								 ],
					      "method_data": {},
					      "method_results": {}
					    }
      }
    else:
      layer_dict = None

    annotated_img = None
    if i == j:
      # This case (i==j) means make a copy of the original in the destination location
      print_debug ( 50, "Copying ( " + alignment_layer_list[i].base_image_name + " to " + os.path.join(destination_path,os.path.basename(alignment_layer_list[i].base_image_name)) + " )" )
      shutil.copyfile      ( alignment_layer_list[i].base_image_name,           os.path.join(destination_path,os.path.basename(alignment_layer_list[i].base_image_name)) )

      # Create a new identity transform for this layer even though it's not otherwise needed
      alignment_layer_list[j].align_proc = alignment_process.alignment_process (alignment_layer_list[i].base_image_name, alignment_layer_list[j].base_image_name,
                                                                                destination_path, layer_dict=layer_dict,
                                                                                x_bias=alignment_layer_list[j].bias_dx, y_bias=alignment_layer_list[j].bias_dy,
                                                                                cumulative_afm=None)

      alignment_layer_list[j].image_dict['ref'] = annotated_image(None, role="ref")
      #alignment_layer_list[j].image_dict['base'] = annotated_image(clone_from=alignment_layer_list[j].base_annotated_image, role="base")
      alignment_layer_list[j].image_dict['aligned'] = annotated_image(clone_from=alignment_layer_list[j].base_annotated_image, role="aligned")

      snr_value = sys.float_info.max

      alignment_layer_list[j].results_dict = {}
      alignment_layer_list[j].results_dict['snr'] = snr_value
      alignment_layer_list[j].results_dict['python_swiftir'] = [ [1, 0, 0], [0, 1, 0] ]
      alignment_layer_list[j].results_dict['cumulative_afm'] = [ [1, 0, 0], [0, 1, 0] ]

      alignment_layer_list[j].image_dict['aligned'].clear_non_marker_graphics()
      alignment_layer_list[j].image_dict['aligned'].add_file_name_graphic()

      alignment_layer_list[j].image_dict['aligned'].graphics_items.append ( graphic_text(2, 26, "SNR: inf", coordsys='p', color=[1, .5, .5]) )
      alignment_layer_list[j].image_dict['aligned'].graphics_items.append ( graphic_text(2, 46, "Affine: " + str2D(alignment_layer_list[j].results_dict['python_swiftir']), coordsys='p', color=[1, .5, .5],graphic_group="Affines") )
      alignment_layer_list[j].image_dict['aligned'].graphics_items.append ( graphic_text(2, 66, "CumAff: " + str2D(alignment_layer_list[j].results_dict['cumulative_afm']), coordsys='p', color=[1, .5, .5],graphic_group="Affines") )


    else:
      # Align the image at index j with the reference at index i

      if not 'cumulative_afm' in alignment_layer_list[i].results_dict:
        print_debug ( 1, "Cannot align from here (" + str(i) + " to " + str(j) + ") without a previous cumulative python_swiftir matrix." )
        return

      prev_afm = [ [ c for c in r ] for r in alignment_layer_list[i].results_dict['cumulative_afm'] ]  # Gets the cumulative from the stored values in previous layer

      print_debug ( 40, "Aligning: i=" + str(i) + " to j=" + str(j) )
      print_debug ( 50, "  Calling align_swiftir.align_images( " + alignment_layer_list[i].base_image_name + ", " + alignment_layer_list[j].base_image_name + ", " + destination_path + " )" )

      alignment_layer_list[j].align_proc = _alignment_process.alignment_process (alignment_layer_list[i].base_image_name, alignment_layer_list[j].base_image_name,
                                                                                 destination_path, layer_dict=layer_dict,
                                                                                 x_bias=alignment_layer_list[j].bias_dx, y_bias=alignment_layer_list[j].bias_dy,
                                                                                 cumulative_afm=prev_afm)
      alignment_layer_list[j].align_proc.align()
      recipe = alignment_layer_list[j].align_proc.recipe
      new_name = os.path.join ( destination_path, os.path.basename(alignment_layer_list[j].base_image_name) )

      # Put the proper images into the proper window slots

      print_debug ( 60, "Reading in new_name from " + str(new_name) )
      annotated_img = annotated_image(new_name, role="aligned")

      annotated_img.clear_non_marker_graphics()
      annotated_img.add_file_name_graphic()

      annotated_img.graphics_items.append ( graphic_text(2, 26, "SNR: %.4g" % (recipe.ingredients[-1].snr[0]), coordsys='p', color=[1, .5, .5]) )
      annotated_img.graphics_items.append ( graphic_text(2, 46, "Affine: " + str2D(recipe.afm), coordsys='p', color=[1, .5, .5],graphic_group="Affines") )
      annotated_img.graphics_items.append ( graphic_text(2, 66, "CumAff: " + str2D(alignment_layer_list[j].align_proc.cumulative_afm), coordsys='p', color=[1, .5, .5],graphic_group="Affines") )

      alignment_layer_list[j].image_dict['ref'].clear_non_marker_graphics()
      alignment_layer_list[j].image_dict['ref'].add_file_name_graphic()

      alignment_layer_list[j].image_dict['base'].clear_non_marker_graphics()
      alignment_layer_list[j].image_dict['base'].add_file_name_graphic()

      for ri in range(len(recipe.ingredients)):
        # Make a color for this recipe item
        c = [(ri+1)%2,((ri+1)/2)%2,((ri+1)/4)%2]
        r = recipe.ingredients[ri]
        s = len(r.psta[0])
        ww = r.ww
        if type(ww) == type(1):
          # ww is an integer, so turn it into an nxn tuple
          ww = (ww,ww)
        global show_window_centers
        if True or show_window_centers:
          # Draw dots in the center of each psta (could be pmov) with SNR for each
          for wi in range(s):
            annotated_img.graphics_items.append ( graphic_dot(r.psta[0][wi],r.psta[1][wi],6,'i',color=c,graphic_group="Centers") )
            annotated_img.graphics_items.append ( graphic_text(r.psta[0][wi]+4,r.psta[1][wi],'%.1f'%r.snr[wi],'i',color=c,graphic_group="Centers") )

            alignment_layer_list[j].image_dict['ref'].graphics_items.append ( graphic_dot(r.psta[0][wi],r.psta[1][wi],6,'i',color=c,graphic_group="Centers") )
            alignment_layer_list[j].image_dict['ref'].graphics_items.append ( graphic_text(r.psta[0][wi]+4,r.psta[1][wi],'%.1f'%r.snr[wi],'i',color=c,graphic_group="Centers") )

            alignment_layer_list[j].image_dict['base'].graphics_items.append ( graphic_dot(r.psta[0][wi],r.psta[1][wi],6,'i',color=c,graphic_group="Centers") )
            alignment_layer_list[j].image_dict['base'].graphics_items.append ( graphic_text(r.psta[0][wi]+4,r.psta[1][wi],'%.1f'%r.snr[wi],'i',color=c,graphic_group="Centers") )

        print ( "Length of psta = " + str(s) )
        print ( "Length of gitems = " + str(len(annotated_img.graphics_items)) )
        print ( "Length of gi ref = " + str(len(alignment_layer_list[j].image_dict['ref'].graphics_items)) )
        print ( "Length of gi base = " + str(len(alignment_layer_list[j].image_dict['base'].graphics_items)) )

        print_debug ( 50, "  Recipe " + str(ri) + " has " + str(s) + " " + str(ww[0]) + "x" + str(ww[1]) + " windows" )

      alignment_layer_list[j].image_dict['aligned'] = annotated_img
      snr_value = recipe.ingredients[-1].snr[0]

      alignment_layer_list[j].results_dict = {}
      alignment_layer_list[j].results_dict['snr'] = snr_value
      alignment_layer_list[j].results_dict['python_swiftir'] = [ [ c for c in r ] for r in recipe.afm ]  # Make a copy
      alignment_layer_list[j].results_dict['cumulative_afm'] = [ [ c for c in r ] for r in alignment_layer_list[j].align_proc.cumulative_afm ]  # Make a copy

    # Check to see if this image should be marked for SNR skipping:
    if not (snr_skip is None):
      # An snr_skip limit has been entered
      if snr_value <= snr_skip:
        print_debug ( 20, "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" )
        print_debug ( 20, "SNR of " + str(snr_value) + " is less than SNR Skip of " + str(snr_skip) )
        print_debug ( 20, "  This layer will be marked for skipping in the next pass: " + str(j) )
        print_debug ( 20, "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" )
        alignment_layer_list[j].snr_skip = True

    # Check to see if the alignment should proceed at all
    if not (snr_halt is None):
      # An snr_halt limit has been entered
      if snr_value <= snr_halt:
        print_debug ( 10, "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" )
        print_debug ( 10, "SNR of " + str(snr_value) + " is less than SNR Halt of " + str(snr_halt) )
        print_debug ( 10, "  Alignment stopped on layer " + str(j) )
        print_debug ( 10, "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" )
        break

