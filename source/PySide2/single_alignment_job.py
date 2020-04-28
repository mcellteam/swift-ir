#!/usr/bin/env python3

# This program is just a stub to call pyswift_tui.run_json_project
# This function could be done in the main of pyswift_tui.py itself,
# but since that file is being simultaneously changed for other
# reasons, it makes sense to have a separate runner stub. At some
# point this functionality could be added back or refactored other ways.

import sys
import pyswift_tui

if __name__ == '__main__':

  if len(sys.argv) != 7:
    print ( "Error: " + sys.argv[0] + " requires 7 arguments (only got " + str(len(sys.argv)) + ")" )
  else:
    this_file = sys.argv[0]
    project_name = sys.argv[1]
    alignment_option = sys.argv[2]
    use_scale = sys.argv[3]
    swiftir_code_mode = sys.argv[4]
    start_layer = sys.argv[5]
    num_layers = sys.argv[6]

    print ( "Inside single_alignment_job with " +
                                         str(self.project) +
                                         str(self.alignment_option) +
                                         str(self.use_scale) +
                                         str(self.swifir_code_mode) +
                                         str(self.start_layer) +
                                         str(self.num_layers) )

    updated_model, need_to_write_json = pyswift_tui.run_json_project (
                                         project = self.project,
                                         alignment_option = self.alignment_option,
                                         use_scale = self.use_scale,
                                         swiftir_code_mode = self.swifir_code_mode,
                                         start_layer = self.start_layer,
                                         num_layers = self.num_layers )
