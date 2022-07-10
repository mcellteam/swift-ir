#!/usr/bin/env python3

# This program is just a stub to call run_json_project
# This function could be done in the main of py itself,
# but since that file is being simultaneously changed for other
# reasons, it makes sense to have a separate runner stub. At some
# point this functionality could be added back or refactored other ways.


import os
import sys
import json


if __name__ == '__main__':
    '''This is passed by 'project_runner' into 'task_queue_mp' as the task argument for worker threads '''

    print('single_alignment_job.py >>>>>>>>')

    if len(sys.argv) != 8:
        # print ( "Error: " + sys.argv[0] + " requires 7 arguments (only got " + str(len(sys.argv)) + ")" )
        pass
    else:
        this_file = sys.argv[0]
        project_name = sys.argv[1]
        alignment_option = sys.argv[2]
        use_scale = int(sys.argv[3].strip())
        swiftir_code_mode = sys.argv[4]
        start_layer = int(sys.argv[5].strip())
        num_layers = int(sys.argv[6].strip())
        use_file_io = (int(sys.argv[7].strip()) != 0)

        # 0620 uncommenting below
        print("Inside single_alignment_job with: \n" +
              '  this_file         = ' + str(this_file) + ', ' +
              '  project_name      = ' + str(project_name) + ', ' +
              '  alignment_option  = ' + str(alignment_option) + ', ' +
              '  use_scale         = ' + str(use_scale) + ', ' +
              '  swiftir_code_mode = ' + str(swiftir_code_mode) + ', ' +
              '  start_layer       = ' + str(start_layer) + ', ' +
              '  num_layers        = ' + str(num_layers) + ', ' +
              '  use_file_io       = ' + str(use_file_io))

        # Read the project from the JSON file
        f = open(project_name, 'r')
        text = f.read()
        f.close()
        project_dict = json.loads(text)

        # print ( "project_dict.keys() = " + str(project_dict.keys()) )
        # print ( str(project_dict['data']['scales']['scale_%d'%use_scale]['alignment_stack'][0]['images']['ref']['filename']) )

        # print ( "\n\n\nBefore running JSON DATA MODEL\n\n" )
        import package.config as cfg
        import run_json_project
        updated_model, need_to_write_json = run_json_project.run_json_project(
                project=project_dict,
                alignment_option=alignment_option,
                use_scale=use_scale,
                swiftir_code_mode=cfg.CODE_MODE,
                start_layer=start_layer,
                num_layers=num_layers)

        # print ( "\n\nAfter running JSON DATA MODEL")

        # Send the updated data model and need_to_write_json back to the project runner via stdout
        jde = json.JSONEncoder(indent=1, separators=(",", ": "), sort_keys=True)
        run_output_json = jde.encode({'data_model': updated_model, 'need_to_write_json': need_to_write_json})

        print('single_alignment_job | use_file_io =', use_file_io)
        if use_file_io:

            # Write the output JSON to a file
            # The job file name will already be located in the project directory, so use its path
            # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })

            # fout.write ( "Scale = " + str(use_scale) + "\n" )
            # Set default path in the project directory (in case no scale is given)
            out_name = os.path.join(project_dict['data']['destination_path'],
                                    "single_alignment_out_%d.json" % start_layer)
            if use_scale > 0:
                # Set path for the selected scale:
                out_name = os.path.join(project_dict['data']['destination_path'], "scale_%d" % use_scale,
                                        "single_alignment_out_%d.json" % start_layer)
            # out_name = "single_alignment_out_%d.json" % start_layer
            fout = open(out_name, 'w')
            # fout.write("project_name: " + str(project_name) + '\n')
            # fout.write("project_name: " + str(os.path.split(project_name)[0]) + '\n')
            # fout.write ( "Scale = " + str(use_scale) + "\n" )
            fout.write(run_output_json)
            fout.close()
            print('<<<<<<<< single_alignment_job.py')
        else:
            # jy This only runs if file IO mode is OFF
            # Write the output JSON to stdout with some markers to separate it from any other reasonable output
            print("---JSON-DELIMITER---")
            # print ( run_output_json )
            print('...placeholder for long JSON string...')
            print("---JSON-DELIMITER---")

        # print ( "\n\n\n JSON DATA MODEL:\n" + str(proj_json) + "\n\n" )
        # flush()
        sys.stdout.close()
        sys.stderr.close()

        print('<<<<<<<< single_alignment_job.py')
