"""AlignEm - Alignment Framework for multiple images

AlignEm is intended to provide a tool for supporting image alignment
using any number of technologies.
"""

def upgrade_data_model(data_model):
  # Upgrade the "Data Model"
  if data_model['version'] != new_project_template['version']:

    # Begin the upgrade process:

    if data_model['version'] <= 0.26:
      print ( "\n\nUpgrading data model from " + str(data_model['version']) + " to " + str(0.27) )
      # Need to modify the data model from 0.26 or lower up to 0.27
      # The "alignment_option" had been in the method_data at each layer
      # This new version defines it only at the scale level
      # So loop through each scale and move the alignment_option from the layer to the scale
      for scale_key in data_model['data']['scales'].keys():
        scale = data_model['data']['scales'][scale_key]
        stack = scale['alignment_stack']
        current_alignment_options = []
        for layer in stack:
          if "align_to_ref_method" in layer:
            align_method = layer['align_to_ref_method']
            if 'method_data' in align_method:
              if 'alignment_option' in align_method['method_data']:
                current_alignment_options.append(align_method['method_data']['alignment_option'])
        # The current_alignment_options list now holds all of the options for this scale (if any)
        # Start by setting the default for the scale option to "init_affine" if none are found
        scale_option = "init_affine"
        # If any options were found in this scale, search through them for most common
        if len(current_alignment_options) > 0:
          # They should all be the same at this scale, so set to the first
          scale_option = current_alignment_options[0]
          # But check if any are different and then find the most common
          if current_alignment_options.count(current_alignment_options[0]) != len(current_alignment_options):
            # There are some that are different, so find the most common option
            scale_option = max ( set(current_alignment_options), key=current_alignment_options.count )
        # At this point "scale_option" should be the one to use
        if not ('method_data' in scale):
          # Ensure that there's some method data
          scale['method_data'] = {}
        # Finally set the value
        scale['method_data']["alignment_option"] = scale_option
      # Now the data model is at 0.27, so give it the appropriate version
      data_model ['version'] = 0.27

    if data_model ['version'] == 0.27:
      print ( "\n\nUpgrading data model from " + str(data_model['version']) + " to " + str(0.28) )
      # Need to modify the data model from 0.27 up to 0.28
      # The "alignment_option" had been left in the method_data at each layer
      # This new version removes that option from the layer method data
      # So loop through each scale and remove the alignment_option from the layer
      for scale_key in data_model['data']['scales'].keys():
        scale = data_model['data']['scales'][scale_key]
        stack = scale['alignment_stack']
        current_alignment_options = []
        for layer in stack:
          if "align_to_ref_method" in layer:
            align_method = layer['align_to_ref_method']
            if 'method_data' in align_method:
              if 'alignment_option' in align_method['method_data']:
                align_method ['method_data'].pop('alignment_option')
      # Now the data model is at 0.28, so give it the appropriate version
      data_model ['version'] = 0.28

    if data_model ['version'] == 0.28:
      print ( "\n\nUpgrading data model from " + str(data_model['version']) + " to " + str(0.29) )
      # Need to modify the data model from 0.28 up to 0.29
      # The "use_c_version" was added to the "user_settings" dictionary
      data_model['user_settings']['use_c_version'] = True
      # Now the data model is at 0.29, so give it the appropriate version
      data_model ['version'] = 0.29

    if data_model ['version'] == 0.29:
      print ( "\n\nUpgrading data model from " + str(data_model['version']) + " to " + str(0.30) )
      # Need to modify the data model from 0.29 up to 0.30
      # The "poly_order" was added to the "scales" dictionary
      for scale_key in data_model['data']['scales'].keys():
        scale = data_model['data']['scales'][scale_key]
        scale['poly_order'] = 4
      # Now the data model is at 0.30, so give it the appropriate version
      data_model ['version'] = 0.30

    if data_model ['version'] == 0.30:
      print ( "\n\nUpgrading data model from " + str(data_model['version']) + " to " + str(0.31) )
      # Need to modify the data model from 0.30 up to 0.31
      # The "skipped(1)" annotation is currently unused (now hard-coded in alignem.py)
      # Remove alll "skipped(1)" annotations since they can not otherwise be removed
      for scale_key in data_model['data']['scales'].keys():
        scale = data_model['data']['scales'][scale_key]
        stack = scale['alignment_stack']
        for layer in stack:
          for role in layer['images'].keys():
            image = layer['images'][role]
            print ("Checking for annotations in image...")
            if 'metadata' in image.keys():
              print ("Checking for annotations in metadata...")
              m = image['metadata']
              if 'annotations' in m.keys():
                print ( "Removing any \"skipped()\" annotations ... ")
                m['annotations'] = [ a for a in m['annotations'] if not a.startswith('skipped') ]
      # Now the data model is at 0.31, so give it the appropriate version
      data_model ['version'] = 0.31

    # Make the final test
    if data_model ['version'] != new_project_template['version']:
      # The data model could not be upgraded, so return a string with the error
      data_model = 'Version mismatch. Expected "' + str(new_project_template['version']) + '" but found ' + str(data_model['version'])

  return data_model


new_project_template = \
{
  "version": 0.31,
  "method": "None",
  "user_settings": {
    "max_image_file_size": 100000000,
    "use_c_version": True
  },
  "data": {
    "source_path": "",
    "destination_path": "",
    "current_layer": 0,
    "current_scale": "scale_1",
    "panel_roles": [
      "ref",
      "base",
      "aligned"
    ],
    "scales": {
      "scale_1": {
        "method_data": {
          "alignment_option": "init_affine"
        },
        "null_cafm_trends": False,
        "use_bounding_rect": False,
        "alignment_stack": []
      }
    }
  }
}


new_layer_template = \
{
  "align_to_ref_method": {
    "method_data": {
    },
    "method_options": [
      "None"
    ],
    "selected_method": "None",
    "method_results": {
    }
  },
  "images": {},
  "skip": False
}


new_image_template = \
{
  "filename": "",
  "metadata": {
    "annotations": [],
    "match_points": []
  }
}

class DataModel:
  """ Encapsulate data model dictionary and wrap with methods for convenience """
  pass
