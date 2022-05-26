'''
RECIPE1 for SWiFT-IR alignment.

'''

import os
import copy
import alignem
import project_runner
import pyswift_tui
from glanceem_utils import get_image_size, isProjectScaled, getCurScale, update_datamodel, isAlignmentOfCurrentScale, \
    requestConfirmation, areImagesImported, getNumImportedImages

def align_all_or_some(first_layer=0, num_layers=-1, prompt=True):
    '''
    Align the images of current scale according to Recipe1.

    RENAME THIS FUNCTION
    '''

    '''TODO: Need to check if images have been imported'''
    print('\n\nalign_all_or_some:')

    if areImagesImported():
        print("align_all_or_some | Images are imported - Continuing")
        pass
    else:
        print("align_all_or_some | User selected align but areImagesImported() returned False - Exiting")
        alignem.main_window.set_status("Scales must be generated prior to alignment.")
        alignem.show_warning("Warning", "Project cannot be aligned at this stage.\n\n"
                                        "Typical workflow:\n"
                                        "--> (1) Open a project or import images and save.\n"
                                        "--> (2) Generate a set of scaled images and save.\n"
                                        "(3) Align each scale starting with the coarsest.\n"
                                        "(4) Export project to Zarr format.\n"
                                        "(5) View data in Neuroglancer client")
        return

    if isProjectScaled():
        print("align_all_or_some | Images are scaled - Continuing")
        # debug isProjectScaled() might be returning True incorrectly sometimes
        pass
    else:
        print("align_all_or_some | User clicked align but isProjectScaled() returned False - Exiting")
        alignem.main_window.set_status("Scales must be generated prior to alignment.")
        alignem.show_warning("Warning", "Project cannot be aligned at this stage.\n\n"
                                        "Typical workflow:\n"
                                        "(1) Open a project or import images and save.\n"
                                        "--> (2) Generate a set of scaled images and save.\n"
                                        "(3) Align each scale starting with the coarsest.\n"
                                        "(4) Export project to Zarr format.\n"
                                        "(5) View data in Neuroglancer client")
        return

    n_imgs = getNumImportedImages()

    alignem.main_window.read_gui_update_project_data()

    cur_scale = getCurScale()

    img_size = get_image_size(
        alignem.project_data['data']['scales'][cur_scale]['alignment_stack'][0]['images']['base']['filename'])

    alignem.main_window.set_status('Aligning %s images at scale %s (%s x %s pixels)...' % (n_imgs, cur_scale[-1], img_size[0], img_size[1]))

    remove_aligned(starting_layer=first_layer, prompt=False)
    alignem.print_debug(30, "Aligning Forward with SWiFT-IR from layer " + str(first_layer) + " ...")
    # alignem.print_debug(70, "Control Model = " + str(control_model))

    combo_name_to_dm_name = {'Init Affine': 'init_affine', 'Refine Affine': 'refine_affine', 'Apply Affine': 'apply_affine'}
    dm_name_to_combo_name = {'init_affine': 'Init Affine', 'refine_affine': 'Refine Affine', 'apply_affine': 'Apply Affine'}

    # thing_to_do = init_ref_app.get_value ()
    thing_to_do = alignem.main_window.affine_combobox.currentText()  # jy #mod #change #march #wtf #combobox
    print('align_all_or_some | selected affine is ', thing_to_do)
    scale_to_run_text = alignem.project_data['data']['current_scale']
    print('align_all_or_some | scale is ', scale_to_run_text)
    print('align_all_or_some | updating project file with this scales selected affine...')
    this_scale = alignem.project_data['data']['scales'][scale_to_run_text]
    this_scale['method_data']['alignment_option'] = str(combo_name_to_dm_name[thing_to_do])
    # alignem.print_debug(5, '')
    alignem.print_debug(5, 40 * '@=' + '@')
    alignem.print_debug(5, '')

    print("align_all_or_some | Calling align_layers w/ first_layer = " + str(first_layer) + "  | num_layers = " + str(num_layers))
    align_layers(first_layer, num_layers)  # <-- CALL TO 'align_layers'

    alignem.main_window.refresh_all_images()

    alignem.main_window.set_status('Alignment of scale %s images (%s x %s pixels) is complete.' % (cur_scale[-1], img_size[0], img_size[1]))

    print("align_all_or_some | Wrapping up")
    alignem.main_window.center_all_images()
    alignem.main_window.update_win_self()

    # alignem.main_window.toggle_on_export_and_view_groupbox()
    alignem.main_window.set_progress_stage_3()

    # print('Incrementing user scale')
    # alignem.main_window.scales_combobox.setCurrentIndex(alignem.main_window.scales_combobox.count() - 1)

    print("\nalign_all_or_some | Exiting\n")


# generate_scales_queue calls this w/ defaults in debugger
def align_layers(first_layer=0, num_layers=-1):
    '''
    Aligns the layers.
    '''

    print('align_layers(first_layer=%d, num_layers=%d):' % (first_layer,first_layer+num_layers-1))
    alignem.print_debug(30, 100 * '=')
    if num_layers < 0:
        print("align_layers | Aligning all layers starting with %s using SWiFT-IR..." % str(first_layer))
    else:
        print('align_layers | Aligning using SWiFT-IR ...' % (first_layer,first_layer+num_layers-1))

    remove_aligned(starting_layer=first_layer, prompt=False)

    # ensure_proper_data_structure()

    code_mode = 'c'
    global_parallel_mode = True
    global_use_file_io = False

    # Check that there is a place to put the aligned images
    if (alignem.project_data['data']['destination_path'] == None) or (len(alignem.project_data['data']['destination_path']) <= 0):
        print('align_layers | Error: Cannot align without destination set (use File/Set Destination)')
        alignem.show_warning('Note', 'Error cannot align. Fix me.')

    else:
        print('Aligning with output in ' + alignem.project_data['data']['destination_path'])
        scale_to_run_text = alignem.project_data['data']['current_scale']
        print("align_layers | Aligning scale %s..." % str(scale_to_run_text))

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

    print('align_layers | Run the project via pyswift_tui...')
    # Run the project via pyswift_tui
    # pyswift_tui.DEBUG_LEVEL = alignem.DEBUG_LEVEL
    if global_parallel_mode:
        print("align_layers | Running in global parallel mode")
        running_project = project_runner.project_runner(project=dm,
                                                        use_scale=alignem.get_scale_val(scale_to_run_text),
                                                        swiftir_code_mode=code_mode,
                                                        start_layer=first_layer,
                                                        num_layers=num_layers,
                                                        use_file_io=global_use_file_io)
        #        running_project.start()
        # 0405 #debug
        print("align_layers | alignment_option is ", this_scale['method_data']['alignment_option'])
        running_project.do_alignment(alignment_option=this_scale['method_data']['alignment_option'],generate_images=True)
        updated_model = running_project.get_updated_data_model()
        need_to_write_json = running_project.need_to_write_json
    else:
        print("align_layers | NOT running in global parallel mode")
        # conditional #else # this conditional appears only to activate with new control panel
        updated_model, need_to_write_json = pyswift_tui.run_json_project(project=dm,
                                                                         alignment_option=this_scale['method_data'][
                                                                             'alignment_option'],
                                                                         use_scale=alignem.get_scale_val(
                                                                             scale_to_run_text),
                                                                         swiftir_code_mode=code_mode,
                                                                         start_layer=first_layer,
                                                                         num_layers=num_layers)


    print('align_layers | need_to_write_json = %s' % str(need_to_write_json))
    if need_to_write_json:
        alignem.project_data = updated_model
    else:
        update_datamodel(updated_model)

    alignem.main_window.center_all_images()
    print("align_layers | EXITING")



def regenerate_aligned(first_layer=0, num_layers=-1, prompt=True):
    '''
    Regenerate aligned images for current scale, taking into account polynomial order (null bias) and bounding box toggle.
    NOTE:
    Fundamental differences between 'regenerate_aligned' and 'align_all_or_some'...
    (a) for 'regenerate_aligned' the call to 'project_runner.project_runner' is not immediately followed by a
    'running_project.do_alignment' call.
    (b) 'regenerate_aligned' calls 'generate_aligned_images()' explicitly in this script, while 'align_all_or_some' calls
    the same function implicitly when 'running_project.do_alignment' gets called (assuming 'generate_images=True' is
    passed into the function call)
    '''
    print('\n\nregenerate_aligned(first_layer=%d, num_layers=%d, prompt=%s):' % (first_layer, num_layers, prompt))

    if isAlignmentOfCurrentScale():
        pass
    else:
        print('regenerate_aligned | WARNING | Cannot regenerate images until the transformation matrices have been computed')
        alignem.show_warning("Note","Warning: Transformation matrices have not been computed yet. Please align this scale first.")
        return

    alignem.main_window.read_gui_update_project_data()
    cur_scale = getCurScale()

    if prompt:
        actually_remove = requestConfirmation('Note','Confirm remove aligned images for scale %s.' % cur_scale[-1])


    if actually_remove:
        '''IMPORTANT FUNCTION CALL'''
        alignem.main_window.read_gui_update_project_data()

        # alignem.print_debug(5, "Removing aligned from scale " + cur_scale + " forward from layer " + str(first_layer) + "  (align_all_or_some)")
        print('regenerate_aligned | Removing aligned from scale %s' % cur_scale)

        remove_aligned(starting_layer=first_layer, prompt=False, clear_results=False)
        scale_to_run_text = alignem.project_data['data']['current_scale']
        dm = copy.deepcopy(alignem.project_data)

        code_mode = 'c'
        global_parallel_mode = True
        global_use_file_io = False

        '''NOTE: IDENTICAL FUNCTION CALL TO 'align_layers' '''
        running_project = project_runner.project_runner(project=dm,
                                                        use_scale=alignem.get_scale_val(scale_to_run_text),
                                                        swiftir_code_mode=code_mode,
                                                        start_layer=first_layer,
                                                        num_layers=num_layers,
                                                        use_file_io=global_use_file_io)
        running_project.generate_aligned_images()
        updated_model = running_project.get_updated_data_model()
        need_to_write_json = running_project.need_to_write_json

        if need_to_write_json:
            alignem.project_data = updated_model
        else:
            update_datamodel(updated_model)

        alignem.main_window.refresh_all_images()

        alignem.main_window.set_status('Regenerating alignment of %s complete.' % cur_scale)

    print("regenerate_aligned | Wrapping up...")
    alignem.main_window.center_all_images()
    alignem.main_window.update_win_self()

    # alignem.main_window.toggle_on_export_and_view_groupbox()
    alignem.main_window.set_progress_stage_3()

    print("regenerate_aligned | Exiting.")


def remove_aligned(starting_layer=0, prompt=True, clear_results=True):
    '''
    Remove aligned images.
    '''

    print('\n\nremove_aligned:')
    cur_scale = getCurScale()

    if prompt:
        confirm = requestConfirmation('Note', 'Confirm remove aligned images for scale %s.' % cur_scale[-1])
        if not confirm:
            print('remove_aligned | User did not confirm - Exiting')
            return

    print("remove_aligned | Removing aligned from scale %s forward from layer %s..." % (cur_scale[-1], str(starting_layer)))

    delete_list = []

    layer_index = 0
    for layer in alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack']:
        if layer_index >= starting_layer:
            alignem.print_debug(5, "Removing Aligned from Layer " + str(layer_index))
            if 'aligned' in layer['images'].keys():
                delete_list.append(layer['images']['aligned']['filename'])
                print("  Removing " + str(layer['images']['aligned']['filename']))
                layer['images'].pop('aligned')
                if clear_results:
                    # Remove the method results since they are no longer applicable
                    if 'align_to_ref_method' in layer.keys():
                        if 'method_results' in layer['align_to_ref_method']:
                            # Set the "method_results" to an empty dictionary to signify no results:
                            layer['align_to_ref_method']['method_results'] = {}
        layer_index += 1

    # alignem.image_library.remove_all_images()

    for fname in delete_list:
        if fname != None:
            if os.path.exists(fname):
                os.remove(fname)
                alignem.image_library.remove_image_reference(fname)

    alignem.main_window.update_panels()
    alignem.main_window.refresh_all_images()

    print('\nremove_aligned | EXITING\n')


def remove_aligned(starting_layer=0, prompt=True, clear_results=True):

    print("\nremove_aligned(starting_layer=%d, prompt=%s, clear_results=%s):" % (starting_layer, str(prompt), str(clear_results)))

    actually_remove = True
    if prompt:
        actually_remove = alignem.request_confirmation("Note", "Do you want to delete aligned images?")
    if actually_remove:
        alignem.print_debug(5, "Removing aligned images ...")

        delete_list = []

        layer_index = 0
        for layer in alignem.project_data['data']['scales'][getCurScale()]['alignment_stack']:
            if layer_index >= starting_layer:
                alignem.print_debug(5, "Removing Aligned from Layer " + str(layer_index))
                if 'aligned' in layer['images'].keys():
                    delete_list.append(layer['images']['aligned']['filename'])
                    alignem.print_debug(5, "  Removing " + str(layer['images']['aligned']['filename']))
                    layer['images'].pop('aligned')

                    if clear_results:
                        # Remove the method results since they are no longer applicable
                        if 'align_to_ref_method' in layer.keys():
                            if 'method_results' in layer['align_to_ref_method']:
                                # Set the "method_results" to an empty dictionary to signify no results:
                                layer['align_to_ref_method']['method_results'] = {}
            layer_index += 1

        # alignem.image_library.remove_all_images()

        for fname in delete_list:
            if fname != None:
                if os.path.exists(fname):
                    os.remove(fname)
                    alignem.image_library.remove_image_reference(fname)

        # main_win.update_panels() #bug
        alignem.main_window.update_panels()  # fix
        alignem.main_window.refresh_all_images()









'''
>>> project_data.keys()
dict_keys(['data', 'method', 'user_settings', 'version'])

>>> project_data['data'].keys()
dict_keys(['current_layer', 'current_scale', 'destination_path', 'panel_roles', 'scales', 'source_path'])

>>> project_data['data']['scales']['scale_1'].keys()
dict_keys(['alignment_stack', 'method_data', 'null_cafm_trends', 'poly_order', 'use_bounding_rect'])

NOTE: directly index layers (stored in a list). First layer stores different data from the other layers, no need for ref.
>>> project_data['data']['scales']['scale_1']['alignment_stack'][0]
{'align_to_ref_method': {'method_data': {'alignment_option': 'refine_affine', 'bias_rot_per_image': 0.0, 'bias_scale_x_per_image': 1.0, 'bias_scale_y_per_image': 1.0, 'bias_skew_x_per_image': 0.0, 'bias_x_per_image': 0.0, 'bias_y_per_image': 0.0, 'whitening_factor': -0.68, 'win_scale_factor': 0.8125}, 'method_options': ['None'], 'method_results': {'affine_matrix': [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], 'cumulative_afm': [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], 'snr': [0.0], 'snr_report': 'SNR: --'}, 'selected_method': 'Auto Swim Align'}, 'images': {'aligned': {'filename': '/Users/joelyancey/glanceEM_SWiFT/test_projects/r34_apical_vijay/scale_1/img_aligned/R34CA1-BS12.101.tif', 'metadata': {'annotations': [], 'match_points': []}}, 'base': {'filename': '/Users/joelyancey/glanceEM_SWiFT/test_projects/r34_apical_vijay/scale_1/img_src/R34CA1-BS12.101.tif', 'metadata': {'annotations': [], 'match_points': []}}, 'ref': {'filename': '', 'metadata': {'annotations': [], 'match_points': []}}}, 'skip': False}


WHEN (A) NO PROJECT IS STARTED, (B) NO IMAGES HAVE BEEN IMPORTED:
>>> len(project_data['data']['scales']['scale_1']['alignment_stack'])
0
>>> project_data['data']['scales']['scale_1']['alignment_stack']
[]

WHEN (A) PROJECT IS STARTED, (B) NO IMAGES HAVE BEEN IMPORTED (SAME AS ABOVE):
>>> len(project_data['data']['scales']['scale_1']['alignment_stack'])
0
>>> project_data['data']['scales']['scale_1']['alignment_stack']
[]

WHEN (A) PROJECT IS STARTED, (B) 10 IMAGES HAVE BEEN IMPORTED, (C) PRE-SAVE
>>> len(project_data['data']['scales']['scale_1']['alignment_stack'])
10
>>> len(project_data['data']['scales']['scale_1']['alignment_stack'][0])
3


'''