'''AlignEm - Alignment Framework for multiple images

AlignEm is intended to provide a tool for supporting image alignment
using any number of technologies.
'''


new_project_template = \
{
  "version": 0.25,
  "method": "None",
  "user_settings": {
    "max_image_file_size": 100000000
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

class data_model:
  ''' Encapsulate data model dictionary and wrap with methods for convenience '''
  pass
