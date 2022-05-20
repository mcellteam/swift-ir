import alignem
import project_runner
from glanceem_utils import isProjectScaled

def align_all_or_some(first_layer=0, num_layers=-1, prompt=True):
    print('\nalign_all_or_some(...):\n')
    actually_remove = True

    print("  actually_remove = ", actually_remove)

    '''
    TODO: Need to check if images have been imported
    '''

    # destination will always be correctly set now due to improved control logic
    # if project_data['data']['destination_path']:
    #     print('align_all_or_some | project destination is apparently set')
    #     pass
    # else:
    #     print("(!) User clicked align but the destination is not set. Aborting alignment.")
    #     alignem.main_window.set_status("Destination not set!")
    #     alignem.show_warning("Warning", "Something is wrong with the project. Project file does not have destination set.\n\n"
    #                                     "Typical workflow:\n"
    #                                     "--> (1) Open a project or import images and save.\n"
    #                                     "--> (2) Generate a set of scaled images and save.\n"
    #                                     "(3) Align each scale starting with the coarsest.\n"
    #                                     "(4) Export project to Zarr format.\n"
    #                                     "(5) View data in Neuroglancer client")
    #     print("Aborting align_all_or_some due to 'isDestinationSet()' conditional.")
    #     return


    if isProjectScaled():
        print("  project is scaled")
        #debug isProjectScaled() might be returning True incorrectly sometimes
        pass
    else:
        print(" (!) User clicked align but scales have not been generated yet. Aborting.")
        alignem.main_window.set_status("Scales must be generated prior to alignment.")
        alignem.show_warning("Warning", "Project cannot be aligned at this stage.\n\n"
                                        "Typical workflow:\n"
                                        "(1) Open a project or import images and save.\n"
                                        "--> (2) Generate a set of scaled images and save.\n"
                                        "(3) Align each scale starting with the coarsest.\n"
                                        "(4) Export project to Zarr format.\n"
                                        "(5) View data in Neuroglancer client")
        print("Aborting align_all_or_some due to 'isProjectScaled()' conditional.")
        return

    alignem.main_window.set_status('Aligning %s...' % str(alignem.get_cur_scale()))

    # print("isAlignmentOfCurrentScale() = ", isAlignmentOfCurrentScale())
    # # if prompt: #original
    # if isAlignmentOfCurrentScale():
    #     # cb = QCheckBox("Do not show this again.")
    #     # NOTE: this should only show if there is already an existing alignment at this scale...
    #     msg = QMessageBox(QMessageBox.Question,
    #                       "Confirm ",
    #                       "Warning: Re-generating the alignment at any scale deletes all alignments.",
    #                       buttons = QMessageBox.Cancel | QMessageBox.Ok)
    #     msg.setIcon(QMessageBox.Question)
    #     # msg.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok)
    #     msg.setDefaultButton(QMessageBox.Ok)
    #     reply = msg.exec_()
    #
    #     if reply != QMessageBox.Ok:
    #         print("Reponse was not 'Ok'. Aborting...")
    #         return
    #     else:
    #         actually_remove = True
    #         print("Reponse was 'Ok'. Continuing...")
    #         pass
    #
    #     # actually_remove = alignem.request_confirmation("Note", "Warning: Re-generating the alignment at any scale " \
    #     #                                                "will delete all alignments.")
    #     print("(!!!) actually_remove = ", actually_remove)

    if actually_remove:
        alignem.print_debug(5, "Removing aligned from scale " + str(
            alignem.get_cur_scale()) + " forward from layer " + str(first_layer) + "  (align_all_or_some)")

        remove_aligned(starting_layer=first_layer, prompt=False)
        alignem.print_debug(30, "Aligning Forward with SWiFT-IR from layer " + str(first_layer) + " ...")
        # alignem.print_debug(70, "Control Model = " + str(control_model))

        print('Reading affine combo box...')
        # thing_to_do #init_ref_app
        # thing_to_do = init_ref_app.get_value () #jy #mod #change #march #wtf
        thing_to_do = alignem.main_window.affine_combobox.currentText()  # jy #mod #change #march #wtf #combobox
        print('selected affine is ', thing_to_do)
        scale_to_run_text = alignem.project_data['data']['current_scale']
        print('scale is ', scale_to_run_text)
        print('updating project file with this scales selected affine...')
        this_scale = alignem.project_data['data']['scales'][scale_to_run_text]
        this_scale['method_data']['alignment_option'] = str(combo_name_to_dm_name[thing_to_do])
        # alignem.print_debug(5, '')
        alignem.print_debug(5, 40 * '@=' + '@')
        alignem.print_debug(5, '')

        print("Calling align_layers w/ first_layer = " + str(first_layer) + "  | num_layers = " + str(num_layers))
        align_layers(first_layer, num_layers) # <-- CALL TO 'align_layers'

        refresh_all()

        alignem.main_window.set_status('Alignment of %s complete.' % str(alignem.get_cur_scale()))


    # center
    print("Wrapping up align_all_or_some(...)")
    alignem.main_window.center_all_images()
    alignem.main_window.update_win_self()

    # alignem.main_window.toggle_on_export_and_view_groupbox()
    alignem.main_window.set_progress_stage_3()

    print("Exiting align_all_or_some(...)")



# generate_scales_queue calls this w/ defaults in debugger
def align_layers(first_layer=0, num_layers=-1):
    print('\nAligning layers | align_layers...\n')
    alignem.print_debug(30, 100 * '=')
    if num_layers < 0:
        alignem.print_debug(30, "Aligning all layers starting with " + str(first_layer) + " using SWiFT-IR ...")
    else:
        alignem.print_debug(30, "Aligning layers " + str(first_layer) + " through " + str(
            first_layer + num_layers - 1) + " using SWiFT-IR ...")
    alignem.print_debug(30, 100 * '=')

    remove_aligned(starting_layer=first_layer, prompt=False)

    ensure_proper_data_structure()

    code_mode = 'c'

    global_use_file_io = get_file_io_mode()

    # Check that there is a place to put the aligned images

    print(
        "\nif (alignem.project_data['data']['destination_path'] == None) or (len(alignem.project_data['data']['destination_path']) <= 0):")
    print("alignem.project_data['data']['destination_path'] == None...",
          alignem.project_data['data']['destination_path'] == None)
    print("len(alignem.project_data['data']['destination_path']) <= 0...",
          len(alignem.project_data['data']['destination_path']) <= 0)

    if (alignem.project_data['data']['destination_path'] == None) or (
            len(alignem.project_data['data']['destination_path']) <= 0):
        print("...if statement was TRUE...")
        alignem.print_debug(1, "Error: Cannot align without destination set (use File/Set Destination)")
        alignem.show_warning("Note", "Error cannot align. Fix me.")

    else:
        print("...ELSE statement was run...")
        alignem.print_debug(10, "Aligning with output in " + alignem.project_data['data']['destination_path'])
        scale_to_run_text = alignem.project_data['data']['current_scale']
        alignem.print_debug(10, "Aligning scale " + str(scale_to_run_text))

        # Create the expected directory structure for pyswift_tui.py
        source_dir = os.path.join(alignem.project_data['data']['destination_path'], scale_to_run_text, "img_src")
        alignem.makedirs_exist_ok(source_dir, exist_ok=True)
        target_dir = os.path.join(alignem.project_data['data']['destination_path'], scale_to_run_text, "img_aligned")
        alignem.makedirs_exist_ok(target_dir, exist_ok=True)

        # Create links or copy files in the expected directory structure
        # os.symlink(src, dst, target_is_directory=False, *, dir_fd=None)
        this_scale = alignem.project_data['data']['scales'][scale_to_run_text]
        stack_at_this_scale = alignem.project_data['data']['scales'][scale_to_run_text]['alignment_stack']

    if False:
        for layer in stack_at_this_scale:
            image_name = None
            if 'base' in layer['images'].keys():
                image = layer['images']['base']
                try:
                    image_name = os.path.basename(image['filename'])
                    destination_image_name = os.path.join(source_dir, image_name)
                    shutil.copyfile(image.image_file_name, destination_image_name)
                except:
                    pass

    # Copy the data model for this project to add local fields
    dm = copy.deepcopy(alignem.project_data)
    # Add fields needed for SWiFT:
    stack_at_this_scale = dm['data']['scales'][scale_to_run_text]['alignment_stack']  # tag2
    for layer in stack_at_this_scale:
        layer['align_to_ref_method']['method_data']['bias_x_per_image'] = 0.0
        layer['align_to_ref_method']['method_data']['bias_y_per_image'] = 0.0
        layer['align_to_ref_method']['selected_method'] = 'Auto Swim Align'

    print('Run the project via pyswift_tui...')
    # Run the project via pyswift_tui
    # pyswift_tui.DEBUG_LEVEL = alignem.DEBUG_LEVEL
    print("global_parallel_mode = ", global_parallel_mode)
    if global_parallel_mode:
        print("  Running in global parallel mode...")
        running_project = project_runner.project_runner(project=dm,
                                                        use_scale=alignem.get_scale_val(scale_to_run_text),
                                                        swiftir_code_mode=code_mode,
                                                        start_layer=first_layer,
                                                        num_layers=num_layers,
                                                        use_file_io=global_use_file_io)
        #        running_project.start()
        #0405 #debug
        print("this_scale['method_data']['alignment_option'] = ", this_scale['method_data']['alignment_option'])
        running_project.do_alignment(alignment_option=this_scale['method_data']['alignment_option'], generate_images=True)
        updated_model = running_project.get_updated_data_model()
        need_to_write_json = running_project.need_to_write_json
        alignem.print_debug(30, "Return from project_runner.project_runner: need_to_write_json = " + str(
            need_to_write_json))
    else:
        print("  align_layers is doing the else...")
        #conditional #else # this conditional appears only to activate with new control panel
        updated_model, need_to_write_json = pyswift_tui.run_json_project(project=dm,
                                                                         alignment_option=this_scale['method_data'][
                                                                             'alignment_option'],
                                                                         use_scale=alignem.get_scale_val(
                                                                             scale_to_run_text),
                                                                         swiftir_code_mode=code_mode,
                                                                         start_layer=first_layer,
                                                                         num_layers=num_layers)

        print("Return from pyswift_tui.run_json_project: need_to_write_json = " + str(need_to_write_json))

    if need_to_write_json:
        alignem.project_data = updated_model
    else:
        update_datamodel(updated_model)

    alignem.main_window.center_all_images()
    print("Exiting align_layers(...)")

# def regenerate_aligned(first_layer=0, num_layers=-1, prompt=True):
#     print('\nRegenerating aligned | regenerate_aligned...\n')
#     #    print ( "Regenerate Aligned ... not working yet.")
#     #    return
#
#     actually_remove = True
#     if prompt:
#         actually_remove = alignem.request_confirmation("Note", "Do you want to delete aligned images from " + str(
#             first_layer) + "?")
#
#     if actually_remove:
#         alignem.print_debug(5, "Removing aligned from scale " + str(
#             alignem.get_cur_scale()) + " forward from layer " + str(first_layer) + "  (align_all_or_some)")
#
#         remove_aligned(starting_layer=first_layer, prompt=False, clear_results=False)
#         alignem.print_debug(30, "Regenerating Aligned Images from layer " + str(first_layer) + " ...")
#         # alignem.print_debug(70, "Control Model = " + str(control_model))
#
#         scale_to_run_text = alignem.project_data['data']['current_scale']
#
#         dm = copy.deepcopy(alignem.project_data)
#
#         code_mode = 'c' #jy force c mode for now
#         print('Setting: running_project = project_runner.project_runner(...)')
#         running_project = project_runner.project_runner(project=dm,
#                                                         use_scale=alignem.get_scale_val(scale_to_run_text),
#                                                         swiftir_code_mode=code_mode,
#                                                         start_layer=first_layer,
#                                                         num_layers=num_layers,
#                                                         use_file_io=global_use_file_io)
#         print('Calling: running_project.generate_aligned_images()')
#         running_project.generate_aligned_images()
#         print('Setting: updated_model = running_project.get_updated_data_model() | type=',type(updated_model))
#         updated_model = running_project.get_updated_data_model()
#         print('Setting: need_to_write_json = running_project.need_to_write_json | need_to_write_json = ', need_to_write_json)
#         need_to_write_json = running_project.need_to_write_json
#
#         if need_to_write_json:
#             alignem.project_data = updated_model
#         else:
#             update_datamodel(updated_model)
#
#         refresh_all()
#
#     # center
#     print("Wrapping up align_layers...")
#     alignem.main_window.center_all_images()
#     alignem.main_window.update_win_self()
#     refresh_all()
#     print("Exit align_layers")




# def align_forward():
#     print('\nAligning forward | align_forward...\n')
#     num_layers = num_fwd.get_value()
#     first_layer = alignem.project_data['data']['current_layer']
#     alignem.print_debug(5, "Inside 'align_forward' with first_layer=" + str(first_layer))
#     align_all_or_some(first_layer, num_layers, prompt=True)
#     refresh_all()