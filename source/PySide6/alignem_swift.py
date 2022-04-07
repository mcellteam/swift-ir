"""
GlanceEM-SWiFT - A software tool for image alignment that is under active development.

"""

import sys, traceback, os, time, shutil, psutil, copy, argparse, cv2, json, platform, inspect
from source_tracker import get_hash_and_rev

from PySide6.QtWidgets import QInputDialog, QDialog, QPushButton, QProgressBar, QMessageBox
from PySide6.QtCore import Signal, QObject, QUrl, QThread, QThreadPool

from joel_decs import timeit, profileit, dumpit, traceit, countit
from glanceem_utils import RequestHandler, Server, get_viewer_url
# from alignem import MainWindow, create_project_structure_directories
import alignem
import pyswift_tui
import align_swiftir
import task_queue_mp as task_queue
import task_wrapper
import project_runner

# from PySide6.QtWebEngineWidgets import QWebEngineView


# options for threading:
# https://stackoverflow.com/questions/6783194/background-thread-with-qthread-in-pyqt

# Using a QRunnable
# http://qt-project.org/doc/latest/qthreadpool.html
# Note that a QRunnable isn't a subclass of QObject and therefore does
# not provide signals and slots.


main_win = None

## project_data = None  # Use from alignem

# QWebSocketCorsAuthenticator¶
# https://doc.qt.io/qtforpython/PySide6/QtWebSockets/QWebSocketCorsAuthenticator.html?highlight=cors


global_source_rev = ""
global_source_hash = ""
# global_parallel_mode = False  # jy original
global_parallel_mode = True  # jy
global_use_file_io = False

swift_roles = ['ref', 'base', 'aligned']


def print_exception():
    exi = sys.exc_info()
    alignem.print_debug(1, "  Exception type = " + str(exi[0]))
    alignem.print_debug(1, "  Exception value = " + str(exi[1]))
    alignem.print_debug(1, "  Exception trace = " + str(exi[2]))
    alignem.print_debug(1, "  Exception traceback:")
    traceback.print_tb(exi[2])


def get_best_path(file_path):
    return os.path.abspath(os.path.normpath(file_path))


def link_stack_orig():
    print('Linking stack, original | link_stack_orig...')

    alignem.print_debug(10, "Linking stack")

    ref_image_stack = []
    for layer_index in range(len(alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'])):
        if layer_index == 0:
            main_win.add_empty_to_role('ref')
        else:
            # layer = alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'][layer_index]
            prev_layer = alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'][
                layer_index - 1]
            fn = ""
            if 'base' in prev_layer['images'].keys():
                fn = prev_layer['images']['base']['filename']
            main_win.add_image_to_role(fn, 'ref')

    alignem.print_debug(50, "Loading images: " + str(ref_image_stack))
    # main_win.load_images_in_role ( 'ref', ref_image_stack )

    main_win.update_panels()
    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
    print('Exiting link_stack_orij()')


def link_stack():
    print('Linking stack | link_stack...')

    alignem.print_debug(10, "Linking stack")

    skip_list = []
    for layer_index in range(len(alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'])):
        if alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'][layer_index][
            'skip'] == True:
            skip_list.append(layer_index)

    print('\nlink_stack(): Skip List = \n' + str(skip_list) + '\n')

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
            j = layer_index - 1
            while (j in skip_list) and (j >= 0):
                j -= 1

            # Use the nearest previous non-skipped layer as ref for this layer
            if (j not in skip_list) and (j >= 0):
                ref_layer = alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'][j]
                ref_fn = ''
                if 'base' in ref_layer['images'].keys():
                    ref_fn = ref_layer['images']['base']['filename']
                if 'ref' not in base_layer['images'].keys():
                    base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
                base_layer['images']['ref']['filename'] = ref_fn

    main_win.update_panels()
    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
    print('\nskip_list =\n', str(skip_list))
    print('Exiting link_stack()')


def make_bool(thing):
    if thing:
        return True
    else:
        return False


# major overhaul #bug #caution
def ensure_proper_data_structure():
    ''' Try to ensure that the data model is usable. '''
    scales_dict = alignem.project_data['data']['scales']
    for scale_key in scales_dict.keys():
      scale = scales_dict[scale_key]
      '''
      if not 'null_cafm_trends' in scale:
        scale ['null_cafm_trends'] = null_cafm_trends.get_value()
      if not 'use_bounding_rect' in scale:
        scale ['use_bounding_rect'] = make_bool ( use_bounding_rect.get_value() )
      if not 'poly_order' in scale:
        scale ['poly_order'] = poly_order.get_value()
      '''
      #0405 #hardcode whatever values
      if not 'null_cafm_trends' in scale:
        scale ['null_cafm_trends'] = make_bool(True)
      if not 'use_bounding_rect' in scale:
        scale ['use_bounding_rect'] = make_bool(True)
      if not 'poly_order' in scale:
        scale ['poly_order'] = int(4)

        # "null_cafm_trends": true
        # "poly_order": 4
        # "use_bounding_rect": true

        for layer_index in range(len(scale['alignment_stack'])):
            layer = scale['alignment_stack'][layer_index]
            if not 'align_to_ref_method' in layer:
                layer['align_to_ref_method'] = {}
            atrm = layer['align_to_ref_method']
            if not 'method_data' in atrm:
                atrm['method_data'] = {}
            mdata = atrm['method_data']
            if not 'win_scale_factor' in mdata:
                print("  Warning: if NOT 'win_scale_factor' in mdata was run")
                # mdata['win_scale_factor'] = win_scale_factor.get_value()
                mdata['win_scale_factor'] = float(alignem.main_window.swim_input.text())

            # print("Evaluating: if not 'whitening_factor' in mdata")
            if not 'whitening_factor' in mdata:
                print("  Warning: if NOT 'whitening_factor' in mdata was run")
                # mdata['whitening_factor'] = whitening_factor.get_value()
                mdata['whitening_factor'] = float(alignem.main_window.whitening_input.text())

    print("  Exiting ensure_proper_data_structure()")


# NOTE: this is called right after importing base images (through update_linking_callback)
def link_all_stacks():
    print('Linking all stacks for each scale | link_all_stacks...')
    ensure_proper_data_structure()

    for scale_key in alignem.project_data['data']['scales'].keys():
        skip_list = []
        for layer_index in range(len(alignem.project_data['data']['scales'][scale_key]['alignment_stack'])):
            if alignem.project_data['data']['scales'][scale_key]['alignment_stack'][layer_index]['skip'] == True:
                # print('  appending layer ' + str(layer_index) + ' to skip_list')
                skip_list.append(layer_index)  # skip

        # print('  Linking all stacks, scale = ' + str(scale_key) +  ', skip_list = ' + str(skip_list))

        for layer_index in range(len(alignem.project_data['data']['scales'][scale_key]['alignment_stack'])):
            base_layer = alignem.project_data['data']['scales'][scale_key]['alignment_stack'][layer_index]

            if layer_index == 0:
                # No ref for layer 0 # <-- ******
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
                j = layer_index - 1
                while (j in skip_list) and (j >= 0):
                    j -= 1

                # Use the nearest previous non-skipped layer as ref for this layer
                if (j not in skip_list) and (j >= 0):
                    ref_layer = alignem.project_data['data']['scales'][scale_key]['alignment_stack'][j]
                    ref_fn = ''
                    if 'base' in ref_layer['images'].keys():
                        ref_fn = ref_layer['images']['base']['filename']
                    if 'ref' not in base_layer['images'].keys():
                        base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
                    base_layer['images']['ref']['filename'] = ref_fn

    main_win.update_panels()
    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
    print("  Exiting link_all_stacks()")


# NOTE: this is called right after importing base images
def update_linking_callback():
    print('Updating linking callback | update_linking_callback...')
    link_all_stacks()
    print('Exiting update_linking_callback()')


def update_skips_callback(new_state):
    print('Updating skips callback | update_skips_callback...')

    # Update all of the annotations based on the skip values
    copy_skips_to_all_scales()
    # update_skip_annotations()  # This could be done via annotations, but it's easier for now to hard-code into alignem.py
    print("Exiting update_skips_callback(new_state)")


class RunProgressDialog(QDialog):
    """
    Simple dialog that consists of a Progress Bar and a Button.
    Clicking on the button results in the start of a timer and
    updates the progress bar.
    """

    def __init__(self):
        super().__init__()
        print("RunProgressDialog constructor called")
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Progress Bar')
        self.progress = QProgressBar(self)
        self.progress.setGeometry(0, 0, 300, 25)
        self.progress.setMaximum(100)
        # self.button = QPushButton('Start', self)
        # self.button.move(0, 30)
        self.setModal(True)
        self.show()
        self.onButtonClick()

        # self.button.clicked.connect(self.onButtonClick)

    def onButtonClick(self):
        self.calc = RunnableThread()
        self.calc.countChanged.connect(self.onCountChanged)
        self.calc.start()

    def onCountChanged(self, value):
        self.progress.setValue(value)


# COUNT_LIMIT = 100 #tag ?


class RunnableThread(QThread):
    """
    Runs a counter thread.
    """
    countChanged = Signal(int)

    def run(self):
        count = 0
        while count < COUNT_LIMIT:
            count += 1
            time.sleep(0.02)
            self.countChanged.emit(count)


# window = None #tag ?


def run_progress():
    print("Running progress | run_progress...")
    global window
    alignem.print_debug(10, "Run started")
    window = RunProgressDialog()


class GenScalesDialog(QDialog):
    """
    Simple dialog that consists of a Progress Bar.
    """

    def __init__(self):
        super().__init__()
        print("GenScalesDialog constructor called")
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Generating Scales')
        self.progress = QProgressBar(self)
        self.progress.setGeometry(0, 0, 300, 25)

        total_images_to_scale = 0
        image_scales_to_run = [alignem.get_scale_val(s) for s in sorted(alignem.project_data['data']['scales'].keys())]
        for scale in image_scales_to_run:
            scale_key = str(scale)
            if not 'scale_' in scale_key:
                scale_key = 'scale_' + scale_key
            total_images_to_scale += len(alignem.project_data['data']['scales'][scale_key]['alignment_stack'])
        if total_images_to_scale <= 1:
            total_images_to_scale = 1
        print('Total images to scale = ' + str(total_images_to_scale))

        self.progress.setMaximum(total_images_to_scale)

        # self.button = QPushButton('Start', self)
        # self.button.move(0, 30)

        self.setModal(True)
        self.show()
        self.calc = GenScalesThread()
        self.calc.countChanged.connect(self.onCountChanged)
        self.calc.start()

    def onCountChanged(self, value):
        self.progress.setValue(value)


class GenScalesThread(QThread):
    countChanged = Signal(int)

    def run(self):
        print('GenScalesThread constructor called')
        # Note: all printed output has been suppressed for testing
        # alignem.print_debug ( 10, "GenScalesThread.run inside alignem_swift called" )
        # main_win.status.showMessage("Generating Scales ...")

        count = 0

        image_scales_to_run = [alignem.get_scale_val(s) for s in sorted(alignem.project_data['data']['scales'].keys())]

        # alignem.print_debug ( 40, "Create images at all scales: " + str ( image_scales_to_run ) )

        for scale in sorted(image_scales_to_run):

            # alignem.print_debug ( 70, "Creating images for scale " + str(scale) )
            # main_win.status.showMessage("Generating Scale " + str(scale) + " ...")

            scale_key = str(scale)
            if not 'scale_' in scale_key:
                scale_key = 'scale_' + scale_key

            subdir_path = os.path.join(alignem.project_data['data']['destination_path'], scale_key)
            scale_1_path = os.path.join(alignem.project_data['data']['destination_path'], 'scale_1')

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
                                destination_path = os.path.abspath(alignem.project_data['data']['destination_path'])
                                outfile_name = os.path.join(destination_path, scale_key, 'img_src', bare_file_name)
                                if scale == 1:
                                    if get_best_path(abs_file_name) != get_best_path(outfile_name):
                                        # The paths are different so make the link
                                        try:
                                            # alignem.print_debug ( 70, "UnLinking " + outfile_name )
                                            os.unlink(outfile_name)
                                        except:
                                            # alignem.print_debug ( 70, "Error UnLinking " + outfile_name )
                                            pass
                                        try:
                                            # alignem.print_debug ( 70, "Linking from " + abs_file_name + " to " + outfile_name )
                                            os.symlink(abs_file_name, outfile_name)
                                        except:
                                            # alignem.print_debug ( 5, "Unable to link from " + abs_file_name + " to " + outfile_name )
                                            # alignem.print_debug ( 5, "Copying file instead" )
                                            # Not all operating systems allow linking for all users (Windows 10, for example, requires admin rights)
                                            try:
                                                shutil.copy(abs_file_name, outfile_name)
                                            except:
                                                # alignem.print_debug ( 1, "Unable to link or copy from " + abs_file_name + " to " + outfile_name )
                                                print_exception()
                                else:
                                    try:
                                        # Do the scaling
                                        # alignem.print_debug ( 70, "Copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(scale) )

                                        if os.path.split(os.path.split(os.path.split(abs_file_name)[0])[0])[
                                            1].startswith('scale_'):
                                            # Convert the source from whatever scale is currently processed to scale_1
                                            p, f = os.path.split(abs_file_name)
                                            p, r = os.path.split(p)
                                            p, s = os.path.split(p)
                                            abs_file_name = os.path.join(p, 'scale_1', r, f)

                                        img = align_swiftir.swiftir.scaleImage(
                                            align_swiftir.swiftir.loadImage(abs_file_name), fac=scale)
                                        align_swiftir.swiftir.saveImage(img, outfile_name)
                                        # Change the base image for this scale to the new file
                                        layer['images'][role]['filename'] = outfile_name
                                    except:
                                        # alignem.print_debug ( 1, "Error copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(scale) )
                                        # print_exception()
                                        pass

                                # Update the Data Model with the new absolute file name. This replaces the originally opened file names
                                # alignem.print_debug ( 40, "Original File Name: " + str(layer['images'][role]['filename']) )
                                layer['images'][role]['filename'] = outfile_name
                                # alignem.print_debug ( 40, "Updated  File Name: " + str(layer['images'][role]['filename']) )
        # main_win.status.showMessage("Done Generating Scales")


gen_scales_dialog = None


def gen_scales_with_thread():
    print('\nCalling generate_scales_with_thread() in alignem_swift.py:\n')

    global gen_scales_dialog
    if (alignem.project_data['data']['destination_path'] == None) or (
            len(alignem.project_data['data']['destination_path']) <= 0):
        alignem.show_warning("Note", "Scales cannot be generated without a destination. Please first 'Save Project As...'")
    else:
        alignem.print_debug(10, "Generating Scales with Progress Bar ...")
        gen_scales_dialog = GenScalesDialog()
        # main_win.status.showMessage("Done Generating Scales ...")


def generate_scales_queue():
    print('Generating scales queue (generate_scales_queue called by ' + inspect.stack()[1].function + ')...')

    image_scales_to_run = [alignem.get_scale_val(s) for s in sorted(alignem.project_data['data']['scales'].keys())]

    alignem.print_debug(2, "Create images at all scales: " + str(image_scales_to_run))

    if (alignem.project_data['data']['destination_path'] == None) or (
            len(alignem.project_data['data']['destination_path']) <= 0):

        alignem.show_warning("Note", "Scales cannot be generated without a destination. Please first 'Save Project As...'")

    else:

        ### Create the queue here
        #      task_queue.DEBUG_LEVEL = alignem.DEBUG_LEVEL
        #      task_wrapper.DEBUG_LEVEL = alignem.DEBUG_LEVEL
        #      scaling_queue = task_queue.TaskQueue (sys.executable)
        #      cpus = psutil.cpu_count (logical=False)
        #      scaling_queue.start (cpus)
        #      scaling_queue.notify = False
        #      scaling_queue.passthrough_stdout = False
        #      scaling_queue.passthrough_stderr = False

        # Use task_queue_mp
        scaling_queue = task_queue.TaskQueue()
        cpus = psutil.cpu_count(logical=False)
        if cpus > 48:
            cpus = 48
        scaling_queue.start(cpus)

        for scale in sorted(image_scales_to_run):

            alignem.print_debug(70, "Creating images for scale " + str(scale))
            # main_win.status.showMessage("Generating Scale " + str(scale) + " ...")

            scale_key = str(scale)
            if not 'scale_' in scale_key:
                scale_key = 'scale_' + scale_key

            subdir_path = os.path.join(alignem.project_data['data']['destination_path'], scale_key)
            scale_1_path = os.path.join(alignem.project_data['data']['destination_path'], 'scale_1')

            create_project_structure_directories(subdir_path)

            alignem.print_debug(70, "Begin creating images at each layer for key: " + str(scale_key))

            for layer in alignem.project_data['data']['scales'][scale_key]['alignment_stack']:
                alignem.print_debug(40, "Generating images for layer: \"" + str(
                    alignem.project_data['data']['scales'][scale_key]['alignment_stack'].index(layer)) + "\"")
                # Remove previously aligned images from panel ??

                # Copy (or link) the source images to the expected scale_key"/img_src" directory
                for role in layer['images'].keys():

                    # Only copy files for roles "ref" and "base"

                    if role in ['ref', 'base']:
                        alignem.print_debug(40, "Generating images for role: \"" + role + "\"")
                        base_file_name = layer['images'][role]['filename']
                        if base_file_name != None:
                            if len(base_file_name) > 0:
                                abs_file_name = os.path.abspath(base_file_name)
                                bare_file_name = os.path.split(abs_file_name)[1]
                                destination_path = os.path.abspath(alignem.project_data['data']['destination_path'])
                                outfile_name = os.path.join(destination_path, scale_key, 'img_src', bare_file_name)
                                if scale == 1:
                                    if get_best_path(abs_file_name) != get_best_path(outfile_name):
                                        # The paths are different so make the link
                                        try:
                                            alignem.print_debug(70, "UnLinking " + outfile_name)
                                            os.unlink(outfile_name)
                                        except:
                                            alignem.print_debug(70, "Error UnLinking " + outfile_name)
                                        try:
                                            alignem.print_debug(70,
                                                                "Linking from " + abs_file_name + " to " + outfile_name)
                                            os.symlink(abs_file_name, outfile_name)
                                        except:
                                            alignem.print_debug(5,
                                                                "Unable to link from " + abs_file_name + " to " + outfile_name)
                                            alignem.print_debug(5, "Copying file instead")
                                            # Not all operating systems allow linking for all users (Windows 10, for example, requires admin rights)
                                            try:
                                                shutil.copy(abs_file_name, outfile_name)
                                            except:
                                                alignem.print_debug(1,
                                                                    "Unable to link or copy from " + abs_file_name + " to " + outfile_name)
                                                print_exception()
                                else:
                                    try:
                                        # Do the scaling
                                        alignem.print_debug(70,
                                                            "Copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(
                                                                scale))

                                        if os.path.split(os.path.split(os.path.split(abs_file_name)[0])[0])[
                                            1].startswith('scale_'):
                                            # Convert the source from whatever scale is currently processed to scale_1
                                            p, f = os.path.split(abs_file_name)
                                            p, r = os.path.split(p)
                                            p, s = os.path.split(p)
                                            abs_file_name = os.path.join(p, 'scale_1', r, f)

                                        ### Add this job to the task queue
                                        code_mode = 'c'
                                        if code_mode == 'python':
                                            scaling_queue.add_task(cmd=sys.executable,
                                                                   args=['single_scale_job.py', str(scale),
                                                                         str(abs_file_name), str(outfile_name)], wd='.')
                                        else:
                                            # Configure platform-specific path to executables for C SWiFT-IR
                                            my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
                                            my_system = platform.system()
                                            my_node = platform.node()
                                            if my_system == 'Darwin':
                                                iscale2_c = my_path + '../c/bin_darwin/iscale2'
                                            elif my_system == 'Linux':
                                                if '.tacc.utexas.edu' in my_node:
                                                    iscale2_c = my_path + '../c/bin_tacc/iscale2'
                                                else:
                                                    iscale2_c = my_path + '../c/bin_linux/iscale2'

                                            scale_arg = '+%d' % (scale)
                                            outfile_arg = 'of=%s' % (outfile_name)
                                            infile_arg = '%s' % (abs_file_name)
                                            #                        scaling_queue.add_task (cmd=iscale2_c, args=[scale_arg, outfile_arg, infile_arg], wd='.')
                                            scaling_queue.add_task([iscale2_c, scale_arg, outfile_arg, infile_arg])

                                        # These two lines generate the scales directly rather than through the queue
                                        # img = align_swiftir.swiftir.scaleImage ( align_swiftir.swiftir.loadImage(abs_file_name), fac=scale )
                                        # align_swiftir.swiftir.saveImage ( img, outfile_name )

                                        # Change the base image for this scale to the new file
                                        layer['images'][role]['filename'] = outfile_name
                                    except:
                                        alignem.print_debug(1,
                                                            "Error copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(
                                                                scale))
                                        print_exception()

                                # Update the Data Model with the new absolute file name. This replaces the originally opened file names
                                alignem.print_debug(40, "Original File Name: " + str(layer['images'][role]['filename']))
                                layer['images'][role]['filename'] = outfile_name
                                alignem.print_debug(40, "Updated  File Name: " + str(layer['images'][role]['filename']))

        ### Join the queue here to ensure that all have been generated before returning
        alignem.print_debug(1, "Waiting for Generate Scales to Complete...")
        #      scaling_queue.work_q.join() # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class
        t0 = time.time()
        scaling_queue.collect_results()  # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class
        dt = time.time() - t0
        alignem.print_debug(1, "Generate Scales Completed in %.2f seconds" % (dt))

        # Stop the queue
        #      scaling_queue.shutdown()
        scaling_queue.stop()
        del scaling_queue

    # center
    alignem.main_window.center_all_images()
    alignem.main_window.update_win_self()

    # main_win.status.showMessage("Done Generating Scales ...")


def generate_scales_optimized():
    print('Generating scales, optimized | generate_scales_optimized...')
    alignem.print_debug(1, "generate_scales_optimized inside alignem_swift called")

    image_scales_to_run = [alignem.get_scale_val(s) for s in sorted(alignem.project_data['data']['scales'].keys())]

    alignem.print_debug(2, "Create images at all scales: " + str(image_scales_to_run))

    if (alignem.project_data['data']['destination_path'] == None) or (
            len(alignem.project_data['data']['destination_path']) <= 0):

        alignem.show_warning("Note", "Scales cannot be generated without a destination. Please first 'Save Project As...'")

    else:

        ### Create the queue here
        task_queue.DEBUG_LEVEL = alignem.DEBUG_LEVEL
        task_wrapper.DEBUG_LEVEL = alignem.DEBUG_LEVEL
        scaling_queue = task_queue.TaskQueue(sys.executable)
        cpus = psutil.cpu_count(logical=False)
        #    if cpus > 32:
        #      cpus = 32
        scaling_queue.start(cpus)
        scaling_queue.notify = False
        scaling_queue.passthrough_stdout = False
        scaling_queue.passthrough_stderr = False

        # Create a list of scaling jobs to be built by looping through scales and layers
        scaling_jobs_by_input_file = {}

        for scale in sorted(image_scales_to_run):

            alignem.print_debug(70, "Creating images for scale " + str(scale))
            # main_win.status.showMessage("Generating Scale " + str(scale) + " ...")

            scale_key = str(scale)
            if not 'scale_' in scale_key:
                scale_key = 'scale_' + scale_key

            subdir_path = os.path.join(alignem.project_data['data']['destination_path'], scale_key)
            scale_1_path = os.path.join(alignem.project_data['data']['destination_path'], 'scale_1')

            create_project_structure_directories(subdir_path)

            alignem.print_debug(70, "Begin creating images at each layer for key: " + str(scale_key))

            layer_index = 0
            for layer in alignem.project_data['data']['scales'][scale_key]['alignment_stack']:
                # if not layer_index in scaling_jobs_by_input_file:
                #  scaling_jobs_by_input_file[layer_index] = []

                alignem.print_debug(40, "Generating images for layer: \"" + str(
                    alignem.project_data['data']['scales'][scale_key]['alignment_stack'].index(layer)) + "\"")
                # Remove previously aligned images from panel ??

                # Copy (or link) the source images to the expected scale_key"/img_src" directory
                for role in layer['images'].keys():

                    # Only copy files for roles "ref" and "base"

                    if role in ['ref', 'base']:
                        alignem.print_debug(40, "Generating images for role: \"" + role + "\"")
                        base_file_name = layer['images'][role]['filename']
                        if base_file_name != None:
                            if len(base_file_name) > 0:
                                abs_file_name = os.path.abspath(base_file_name)
                                bare_file_name = os.path.split(abs_file_name)[1]
                                destination_path = os.path.abspath(alignem.project_data['data']['destination_path'])
                                outfile_name = os.path.join(destination_path, scale_key, 'img_src', bare_file_name)
                                if scale == 1:
                                    # Make links or copy immediately without creating a job
                                    if get_best_path(abs_file_name) != get_best_path(outfile_name):
                                        # The paths are different so make the link
                                        try:
                                            alignem.print_debug(70, "UnLinking " + outfile_name)
                                            os.unlink(outfile_name)
                                        except:
                                            alignem.print_debug(70, "Error UnLinking " + outfile_name)
                                        try:
                                            alignem.print_debug(70,
                                                                "Linking from " + abs_file_name + " to " + outfile_name)
                                            os.symlink(abs_file_name, outfile_name)
                                        except:
                                            alignem.print_debug(5,
                                                                "Unable to link from " + abs_file_name + " to " + outfile_name)
                                            alignem.print_debug(5, "Copying file instead")
                                            # Not all operating systems allow linking for all users (Windows 10, for example, requires admin rights)
                                            try:
                                                shutil.copy(abs_file_name, outfile_name)
                                            except:
                                                alignem.print_debug(1,
                                                                    "Unable to link or copy from " + abs_file_name + " to " + outfile_name)
                                                print_exception()
                                else:
                                    try:
                                        # Do the scaling
                                        alignem.print_debug(70,
                                                            "Copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(
                                                                scale))

                                        if os.path.split(os.path.split(os.path.split(abs_file_name)[0])[0])[
                                            1].startswith('scale_'):
                                            # Convert the source from whatever scale is currently processed to scale_1
                                            p, f = os.path.split(abs_file_name)
                                            p, r = os.path.split(p)
                                            p, s = os.path.split(p)
                                            abs_file_name = os.path.join(p, 'scale_1', r, f)

                                        ### Add this job to the task queue or job list
                                        if not (abs_file_name in scaling_jobs_by_input_file.keys()):
                                            scaling_jobs_by_input_file[abs_file_name] = []
                                        scaling_jobs_by_input_file[abs_file_name].append(
                                            {'scale': scale, 'target': outfile_name})
                                        # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
                                        # scaling_queue.add_task (cmd=sys.executable, args=['single_scale_job.py', str (scale), str (abs_file_name), str(outfile_name)], wd='.')
                                        # These two lines generate the scales directly rather than through the queue
                                        # img = align_swiftir.swiftir.scaleImage ( align_swiftir.swiftir.loadImage(abs_file_name), fac=scale )
                                        # align_swiftir.swiftir.saveImage ( img, outfile_name )

                                        # Change the base image for this scale to the new file
                                        layer['images'][role]['filename'] = outfile_name
                                    except:
                                        alignem.print_debug(1,
                                                            "Error copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(
                                                                scale))
                                        print_exception()

                                # Update the Data Model with the new absolute file name. This replaces the originally opened file names
                                alignem.print_debug(40, "Original File Name: " + str(layer['images'][role]['filename']))
                                layer['images'][role]['filename'] = outfile_name
                                alignem.print_debug(40, "Updated  File Name: " + str(layer['images'][role]['filename']))

                layer_index += 1

        print("Jobs to Scale: " + str(scaling_jobs_by_input_file))
        print()
        job_keys = sorted(scaling_jobs_by_input_file.keys())
        for k in job_keys:
            print(" Scaling " + str(k))
            arg_list = ['multi_scale_job.py', k]
            for s in scaling_jobs_by_input_file[k]:
                arg_list.append(str(s['scale']))
                arg_list.append(str(s['target']))
            scaling_queue.add_task(cmd=sys.executable, args=arg_list, wd='.')

        ### Join the queue here to ensure that all have been generated before returning
        alignem.print_debug(1, "Waiting for TaskQueue.join to return")
        scaling_queue.work_q.join()  # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class

        scaling_queue.shutdown()
        del scaling_queue
    print("Exiting generate_scales_optimized()")

    # main_win.status.showMessage("Done Generating Scales ...")


def get_file_io_mode():
    print('Getting file IO mode | get_file_io_mode...')
    ### All of this code is just trying to find the right menu item for the "Use File I/O" check box:
    file_io_mode = False
    menubar = alignem.main_window.menu
    menubar_items = [menubar.children()[x].title() for x in range(len(menubar.children())) if
                     'title' in dir(menubar.children()[x])]
    submenus = [menubar.children()[x] for x in range(len(menubar.children())) if 'title' in dir(menubar.children()[x])]
    alignem.print_debug(40, "Menubar contains: " + str(menubar_items))
    setmenu_index = -1
    for m in menubar_items:
        if "Set" in m:
            setmenu_index = menubar_items.index(m)
    alignem.print_debug(40, "Set menu is item " + str(setmenu_index))
    if setmenu_index >= 0:
        set_menu = submenus[setmenu_index]
        set_menu_actions = set_menu.actions()
        use_file_io = None  # This will be the widget (menu item)
        for action in set_menu_actions:
            if "Use File I/O" in action.text():
                use_file_io = action
                break
        if use_file_io != None:
            # Then we've found the actual widget, so get its value
            if use_file_io.isChecked():
                file_io_mode = True
    return (file_io_mode)

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


# Call this function when run_json_project returns with need_to_write_json=false
def update_datamodel(updated_model):
    print('\nUpdating data model | update_datamodel...\n')
    alignem.print_debug(1, 100 * "+")
    alignem.print_debug(1, "run_json_project returned with need_to_write_json=false")
    alignem.print_debug(1, 100 * "+")
    # Load the alignment stack after the alignment has completed
    aln_image_stack = []
    scale_to_run_text = alignem.project_data['data']['current_scale']
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
                aligned_name = os.path.join(os.path.abspath(alignem.project_data['data']['destination_path']),
                                            scale_to_run_text, 'img_aligned', os.path.split(image_name)[-1])
            else:
                name_parts = os.path.split(image_name)
                if len(name_parts) >= 2:
                    aligned_name = os.path.join(os.path.split(name_parts[0])[0],
                                                os.path.join('img_aligned', name_parts[1]))
        aln_image_stack.append(aligned_name)
        alignem.print_debug(30, "Adding aligned image " + aligned_name)
        layer['images']['aligned'] = {}
        layer['images']['aligned']['filename'] = aligned_name
    try:
        main_win.load_images_in_role('aligned', aln_image_stack)
    except:
        alignem.print_debug(1, "Error from main_win.load_images_in_role.")
        print_exception()
        pass
    refresh_all()

    # center
    # main_win.center_all_images()
    # main_win.update_win_self()
    alignem.main_window.center_all_images()
    alignem.main_window.update_win_self()


# affine
combo_name_to_dm_name = {'Init Affine': 'init_affine', 'Refine Affine': 'refine_affine', 'Apply Affine': 'apply_affine'}
dm_name_to_combo_name = {'init_affine': 'Init Affine', 'refine_affine': 'Refine Affine', 'apply_affine': 'Apply Affine'}

# I think implementing these here rather than inside of MainWindow is more "data driven" and thus better.
# def isProjectOpen():
#     """
#     Checks if there is a project open
#
#     """
#
#     # if not alignem.project_data["data"]["source_path"]:
#     if not alignem.project_data['data']['source_path']:
#         print("alignem.project_data['data']['source_path'] = ", alignem.project_data['data']['source_path'])
#         print("isProjectLoaded() is returning False")
#         return  False
#     else:
#         print("isProjectLoaded() is returning True")
#         return True

def isDestinationSet():
    """
    Checks if there is a project open

    """

    # if not alignem.project_data["data"]["source_path"]:
    if not alignem.project_data['data']['destination_path']:
        # print("alignem.project_data['data']['destination_path'] = ", alignem.project_data['data']['destination_path'])
        # print("isDestinationSet is returning False")
        return  False
    else:
        # print("isDestinationSet is returning True")
        return True

def isProjectScaled():
    """
    Checks if there exists any stacks of scaled images

    #fix Note: This will return False if no scales have been generated, but code should be dynamic enough to run alignment
    functions even for a project that does not need scales.

    """
    if len(alignem.project_data['data']['scales']) < 2:
        # print("isProjectScaled() is returning False")
        return False
    else:
        # print("isProjectScaled() is returning False")
        return True

def isAlignmentOfCurrentScale():
    """
    Checks if there exists a set of aligned images at the current scale
    """
    if len(alignem.project_data["data"]["scales"][alignem.get_cur_scale()]["alignment_stack"]) < 1:
        print("isAlignmentOfCurrentScale is returning False, val = ", len(alignem.project_data["data"]["scales"][alignem.get_cur_scale()]["alignment_stack"]))
        return False
    else:
        print("isAlignmentOfCurrentScale is returning True, val = ", len(alignem.project_data["data"]["scales"][alignem.get_cur_scale()]["alignment_stack"]))
        return True

def getNumOfScales():
    """
    Returns the number of scales for the open project

    """
    return len(alignem.project_data['data']['scales'])

def getNumAligned():
    """
    Returns the count aligned images for the current scale

    """
    try:
        path = os.path.join(alignem.project_data['data']['destination_path'], get_cur_scale(), 'img_aligned')
        count = len([name for name in os.listdir(path) if os.path.isfile(os.path.join(path, name))])
        print('Returning # aligned images at current scale: ', count)
        return int(count)
    except:
        return int(0)

#dialog #controlflow
def align_all_or_some(first_layer=0, num_layers=-1, prompt=True):
    print('\nalign_all_or_some(...):\n')
    actually_remove = True

    """
    TODO: Need to check if images have been imported
    
    """

    if isDestinationSet():
        pass
    else:
        print("(!) User clicked align but the destination is not set. Aborting alignment.")
        alignem.main_window.set_status("Destination not set!")
        alignem.show_warning("Warning", "Project cannot be aligned at this stage.\n\n"
                                        "Typical workflow:\n"
                                        "* (1) Open a project or import images and save.\n"
                                        "* (2) Generate a set of scaled images and save.\n"
                                        "(3) Align each scale starting with the coarsest.\n"
                                        "(4) Export project to Zarr format.\n"
                                        "(5) View data in Neuroglancer client")
        print("Aborting align_all_or_some due to 'isDestinationSet()' conditional.")

        return


    if isProjectScaled():
        #debug isProjectScaled() might be returning True incorrectly sometimes
        pass
    else:
        print(" (!) User clicked align but scales have not been generated yet. Aborting.")
        alignem.main_window.set_status("Scales must be generated prior to alignment.")
        alignem.show_warning("Warning", "Project cannot be aligned at this stage.\n\n"
                                        "Typical workflow:\n"
                                        "(1) Open a project or import images and save.\n"
                                        "* (2) Generate a set of scaled images and save.\n"
                                        "(3) Align each scale starting with the coarsest.\n"
                                        "(4) Export project to Zarr format.\n"
                                        "(5) View data in Neuroglancer client")
        print("Aborting align_all_or_some due to 'isProjectScaled()' conditional.")
        return


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
        print('thing_to_do=', thing_to_do)
        scale_to_run_text = alignem.project_data['data']['current_scale']
        this_scale = alignem.project_data['data']['scales'][scale_to_run_text]
        this_scale['method_data']['alignment_option'] = str(combo_name_to_dm_name[thing_to_do])
        # alignem.print_debug(5, '')
        alignem.print_debug(5, 40 * '@=' + '@')
        # alignem.print_debug(5, 40 * '=@' + '=')
        # alignem.print_debug(5, 40 * '@=' + '@')
        # alignem.print_debug(5, '')
        # alignem.print_debug ( 5, "Doing " + thing_to_do + " which is: " + str(combo_name_to_dm_name[thing_to_do])) #jy
        # alignem.print_debug(5, '')
        # alignem.print_debug(5, 40 * '@=' + '@')
        # alignem.print_debug(5, 40 * '=@' + '=')
        # alignem.print_debug(5, 40 * '@=' + '@')
        alignem.print_debug(5, '')
        align_layers(first_layer, num_layers) # <-- CALL TO 'align_layers'
        refresh_all()

    # center
    alignem.main_window.center_all_images()
    alignem.main_window.update_win_self()
    print("Exiting align_all_or_some(...)")


def align_forward():
    print('\nAligning forward | align_forward...\n')
    num_layers = num_fwd.get_value()
    first_layer = alignem.project_data['data']['current_layer']
    alignem.print_debug(5, "Inside 'align_forward' with first_layer=" + str(first_layer))
    align_all_or_some(first_layer, num_layers, prompt=True)
    refresh_all()


def regenerate_aligned(first_layer=0, num_layers=-1, prompt=True):
    print('\nRegenerating aligned | regenerate_aligned...\n')
    #    print ( "Regenerate Aligned ... not working yet.")
    #    return

    actually_remove = True
    if prompt:
        actually_remove = alignem.request_confirmation("Note", "Do you want to delete aligned images from " + str(
            first_layer) + "?")

    if actually_remove:
        alignem.print_debug(5, "Removing aligned from scale " + str(
            alignem.get_cur_scale()) + " forward from layer " + str(first_layer) + "  (align_all_or_some)")

        remove_aligned(starting_layer=first_layer, prompt=False, clear_results=False)
        alignem.print_debug(30, "Regenerating Aligned Images from layer " + str(first_layer) + " ...")
        # alignem.print_debug(70, "Control Model = " + str(control_model))

        scale_to_run_text = alignem.project_data['data']['current_scale']

        dm = copy.deepcopy(alignem.project_data)

        code_mode = 'c'

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

        refresh_all()

    # center
    alignem.main_window.center_all_images()
    alignem.main_window.update_win_self()
    refresh_all()


def jump_to_layer():
    print('Jumping to layer | jump_to_layer...')
    requested_layer = jump_to_val.get_value()
    alignem.print_debug(3, "Jump to layer " + str(requested_layer))
    num_layers = len(alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack'])
    if requested_layer >= num_layers:  # Limit to largest
        requested_layer = num_layers - 1
    if requested_layer < 0:  # Consider negative values as indexes from the end
        requested_layer = num_layers + requested_layer
    if requested_layer < 0:  # If the end index was greater than the length, just show 0
        requested_layer = 0
    alignem.project_data['data']['current_layer'] = requested_layer
    main_win.image_panel.update_multi_self()


def center_all():
    print('Centering all | center_all...')
    main_win.center_all_images()


def refresh_all():
    print('Refreshing all | refresh_all...')
    # main_win.refresh_all_images () #bug
    alignem.main_window.refresh_all_images()  # fix


def remove_aligned(starting_layer=0, prompt=True, clear_results=True):
    print('Removing alilgned | remove_aligned...')
    alignem.print_debug(5, "Removing aligned from scale " + str(alignem.get_cur_scale()) + " forward from layer " + str(
        starting_layer) + "  (remove_aligned)")
    actually_remove = True
    if prompt:
        actually_remove = alignem.request_confirmation("Note", "Do you want to delete aligned images?")
    if actually_remove:
        alignem.print_debug(5, "Removing aligned images ...")

        delete_list = []

        layer_index = 0
        for layer in alignem.project_data['data']['scales'][alignem.get_cur_scale()]['alignment_stack']:
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
        refresh_all()


def method_debug():
    print('method_debug() was called...')
    alignem.print_debug(1, "In Method debug for " + str(__name__))
    __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


def notyet():
    print("notyet() was called...")
    # alignem.print_debug(0, "Function not implemented yet. Skip = " + str(skip.value)) #skip
    alignem.print_debug(0, "Function not implemented yet. Skip = " + alignem.main_window.toggle_skip.isChecked())



def view_change_callback(prev_scale_key, next_scale_key, prev_layer_num, next_layer_num, new_data_model=False):
    print('Viewing change callback (view_change_callback was called by ' + inspect.stack()[1].function + ')...')
    print("  Changing from scale,layer " + str((prev_scale_key, prev_layer_num)) + " to " + str(
        (next_scale_key, next_layer_num)))

    if alignem.project_data != None:

        # copy_from_widgets_to_data_model = True
        # copy_from_data_model_to_widgets = True
        copy_from_widgets_to_data_model = False
        copy_from_data_model_to_widgets = False

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
            print("  (!) Attempting copy_from_widgets_to_data_model...")
            # Start with the scale-level items

            # Build any scale-level structures that might be needed
            if not 'method_data' in alignem.project_data['data']['scales'][prev_scale_key]:
                alignem.project_data['data']['scales'][prev_scale_key]['method_data'] = {}

            # Copy the scale-level data
            # alignem.project_data['data']['scales'][prev_scale_key]['null_cafm_trends'] = make_bool(null_cafm_trends.get_value())
            # alignem.project_data['data']['scales'][prev_scale_key]['use_bounding_rect'] = make_bool(use_bounding_rect.get_value())
            # alignem.project_data['data']['scales'][prev_scale_key]['poly_order'] = poly_order.get_value()

            #0405 #hardcode whatever values
            #todo #0406 NEED BIAS CONTROL i.e.
            # bias controls: CUMULATIVE AFFINE MATRIX CHECKBOX, POLY ORDER
            # NEED ALL 3 OF THESE, BOUNDING RECTANGLE LAST
            # NOTE: THESE SETTINGS AFFECT HOW ALIGNED IMAGES ARE DISPLAYED (ALIGNMENT DOES NOT CHANGE)
            alignem.project_data['data']['scales'][prev_scale_key]['null_cafm_trends'] = bool(False)
            alignem.project_data['data']['scales'][prev_scale_key]['poly_order'] = int(0)
            alignem.project_data['data']['scales'][prev_scale_key]['use_bounding_rect'] = bool(False)

            #affine #combobox            #0405 #testing
            alignem.project_data['data']['scales'][prev_scale_key]['method_data']['alignment_option'] = str(
                combo_name_to_dm_name[init_ref_app.get_value()])
            print("  combo_name_to_dm_name[alignem.main_window.affine_combobox.currentText()] = ",  combo_name_to_dm_name[alignem.main_window.affine_combobox.currentText()])
            print("  alignem.main_window.affine_combobox.currentText() = ", alignem.main_window.affine_combobox.currentText())
            alignem.project_data['data']['scales'][prev_scale_key]['method_data']['alignment_option'] = str(
                combo_name_to_dm_name[alignem.main_window.affine_combobox.currentText()])

            alignem.print_debug(25, "In DM: Null Bias = " + str(
                alignem.project_data['data']['scales'][prev_scale_key]['null_cafm_trends']))
            alignem.print_debug(25, "In DM: Use Bound = " + str(
                alignem.project_data['data']['scales'][prev_scale_key]['use_bounding_rect']))

            # Next copy the layer-level items
            if prev_layer != None:

                # Build any layer-level structures that might be needed in the data model
                if not 'align_to_ref_method' in prev_layer:
                    prev_layer['align_to_ref_method'] = {}
                if not 'method_data' in prev_layer['align_to_ref_method']:
                    prev_layer['align_to_ref_method']['method_data'] = {}

                # Copy the layer-level data
                # prev_layer['skip'] = make_bool(skip.get_value()) #skip
                # prev_layer['skip'] = alignem.main_window.toggle_skip.isChecked() #no longer necessary
                prev_layer['align_to_ref_method']['method_data'][
                    'whitening_factor'] = alignem.main_window.whitening_input.text
                prev_layer['align_to_ref_method']['method_data'][
                    'win_scale_factor'] = alignem.main_window.swim_input.text

        # Second copy from the data model to the widgets if desired (check each along the way)
        if copy_from_data_model_to_widgets:
            alignem.ignore_changes = True  # tag #odd
            # Start with the scale-level items
            #0405
            if 'null_cafm_trends' in alignem.project_data['data']['scales'][next_scale_key]:
                null_cafm_trends.set_value(alignem.project_data['data']['scales'][next_scale_key]['null_cafm_trends'])
            if 'use_bounding_rect' in alignem.project_data['data']['scales'][next_scale_key]:
                use_bounding_rect.set_value(alignem.project_data['data']['scales'][next_scale_key]['use_bounding_rect'])

            #jy-remove-x
            if 'poly_order' in alignem.project_data['data']['scales'][next_scale_key]:
                poly_order.set_value(alignem.project_data['data']['scales'][next_scale_key]['poly_order'])

            # affine #combobox
            if 'method_data' in alignem.project_data['data']['scales'][next_scale_key]:
                # if 'alignment_option' in alignem.project_data['data']['scales'][next_scale_key]['method_data']:
                #     new_option = alignem.project_data['data']['scales'][next_scale_key]['method_data']['alignment_option']
                #     init_ref_app.set_value(dm_name_to_combo_name[new_option])

                if 'alignment_option' in alignem.project_data['data']['scales'][next_scale_key]['method_data']:
                    new_option = alignem.project_data['data']['scales'][next_scale_key]['method_data'][
                        'alignment_option']
                    # init_ref_app.set_value(dm_name_to_combo_name[new_option])
                    print('  Setting affine_combobox: ' + dm_name_to_combo_name[new_option])
                    alignem.main_window.affine_combobox.setCurrentText(dm_name_to_combo_name[new_option])

            # Next copy the layer-level items

            if next_layer != None:  # next_layer refers to the current layer
                # print('  next_layer = ',next_layer)
                # Copy the layer-level data
                # print("  Evaluating: if 'skip' in next_layer ")
                if 'skip' in next_layer:
                    # print("=> True")
                    # #skip.set_value(next_layer['skip']) #skip
                    # print("    alignem.main_window.toggle_skip.isChecked() => ", alignem.main_window.toggle_skip.isChecked())
                    # print("    Possibly setting checked state of toggle_skip...")
                    # print("    Evaluating: not bool(next_layer['skip']) => ", next_layer['skip'])
                    # #alignem.main_window.toggle_skip.setChecked(not bool(next_layer['skip'])) #toggle #toggleskip #setchecked #checked
                    # print("    alignem.main_window.toggle_skip.isChecked() = ", alignem.main_window.toggle_skip.isChecked())

                    # print("  next_layer['skip'] = ", next_layer['skip']) # <- last code removed
                    pass

                    # alignem.main_window.toggle_skip.setChecked(not bool(next_layer['skip']))

                    # skip.set_value(next_layer['skip']) #original

                if 'align_to_ref_method' in next_layer:
                    if 'method_data' in next_layer['align_to_ref_method']:
                        if 'whitening_factor' in next_layer['align_to_ref_method']['method_data']:
                            # print("  next_layer['align_to_ref_method']['method_data']['whitening_factor'] = ", next_layer['align_to_ref_method']['method_data']['whitening_factor'])
                            print("  Setting 'whitening_input': " + str(
                                next_layer['align_to_ref_method']['method_data']['whitening_factor']))
                            # whitening_factor.set_value(next_layer['align_to_ref_method']['method_data']['whitening_factor'])
                            alignem.main_window.whitening_input.setText(
                                str(next_layer['align_to_ref_method']['method_data']['whitening_factor']))
                        if 'win_scale_factor' in next_layer['align_to_ref_method']['method_data']:
                            print("  Setting 'swim_input': " + str(
                                (next_layer['align_to_ref_method']['method_data']['win_scale_factor'])))
                            alignem.main_window.swim_input.setText(
                                str(next_layer['align_to_ref_method']['method_data']['win_scale_factor']))

            alignem.ignore_changes = False
    else:
        print('  (!) alignem.project_data not found')

    # # THIS MIGHT NOT BE THE BEST PLACE FOR THIS, ARBITRARY LOCATION
    # scale = alignem.project_data['data']['scales'][alignem.project_data['data']['current_scale']]
    # layer = scale['alignment_stack'][alignem.project_data['data']['current_layer']]
    # alignem.main_window.whitening_input.setText(str(
    #     scale['alignment_stack'][alignem.project_data['data']['current_layer']]['align_to_ref_method'][
    #         'method_data'][
    #         'whitening_factor']))
    # alignem.main_window.swim_input.setText(str(
    #     scale['alignment_stack'][alignem.project_data['data']['current_layer']]['align_to_ref_method'][
    #         'method_data'][
    #         'win_scale_factor']))

    print("view_change_callback has completed.\n")


def mouse_down_callback(role, screen_coords, image_coords, button):
    # global match_pt_mode
    # if match_pt_mode.get_value():
    # print("mouse_down_callback was called but there is nothing to do.")
    return  # monkeypatch


def mouse_move_callback(role, screen_coords, image_coords, button):
    # global match_pt_mode
    # if match_pt_mode.get_value():
    return  # monkeypatch #jy-remove

    print("view_match_crop.get_value() = ", view_match_crop.get_value())
    if view_match_crop.get_value() == 'Match':
        return (True)  # Lets the framework know that the move has been handled
    else:
        return (False)  # Lets the framework know that the move has not been handled


def crop_mode_callback():
    print("\nCalling crop_mode_callback() in alignem_swift.py:\n")
    # return (view_match_crop.get_value())
    #0405 return whatever #jy
    return 'View'


def clear_match_points():
    print('\nCalling clear_match_points() in alignem_swift.py:\n')

    # global match_pt_mode
    # if not match_pt_mode.get_value():
    if view_match_crop.get_value() != 'Match':
        alignem.print_debug(1, "\nMust be in \"Match\" mode to delete all match points.")
    else:
        alignem.print_debug(20, "Deleting all match points for this layer")
        scale_key = alignem.project_data['data']['current_scale']
        layer_num = alignem.project_data['data']['current_layer']
        stack = alignem.project_data['data']['scales'][scale_key]['alignment_stack']
        layer = stack[layer_num]

        for role in layer['images'].keys():
            if 'metadata' in layer['images'][role]:
                layer['images'][role]['metadata']['match_points'] = []
                layer['images'][role]['metadata']['annotations'] = []
        main_win.update_panels()
        main_win.refresh_all_images()


def clear_all_skips():
    print('Clearing all skips | clear_all_skips...')
    image_scale_keys = [s for s in sorted(alignem.project_data['data']['scales'].keys())]
    for scale in image_scale_keys:
        scale_key = str(scale)
        for layer in alignem.project_data['data']['scales'][scale_key]['alignment_stack']:
            layer['skip'] = False

    # main_win.status_skips_label.setText(str(skip_list))  # settext #status
    # skip.set_value(False) #skip


def copy_skips_to_all_scales():
    print('Copying skips to all scales | copy_skips_to_all_scales...')
    source_scale_key = alignem.project_data['data']['current_scale']
    if not 'scale_' in str(source_scale_key):
        source_scale_key = 'scale_' + str(source_scale_key)
    scales = alignem.project_data['data']['scales']
    image_scale_keys = [s for s in sorted(scales.keys())]
    for scale in image_scale_keys:
        scale_key = str(scale)
        if not 'scale_' in str(scale_key):
            scale_key = 'scale_' + str(scale_key)
        if scale_key != source_scale_key:
            for l in range(len(scales[source_scale_key]['alignment_stack'])):
                if l < len(scales[scale_key]['alignment_stack']):
                    scales[scale_key]['alignment_stack'][l]['skip'] = scales[source_scale_key]['alignment_stack'][l][
                        'skip']  # <----
    # Not needed: skip.set_value(scales[source_scale_key]['alignment_stack'][alignem.project_data['data']['current_layer']]['skip']


# skip
def update_skip_annotations():
    print('\nUpdating skip annotations | update_skip_annotations\n')
    alignem.print_debug(80, "update_skip_annotations called")
    # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
    remove_list = []
    add_list = []
    for sk, scale in alignem.project_data['data']['scales'].items():
        for layer in scale['alignment_stack']:
            layer_num = scale['alignment_stack'].index(layer)
            for ik, im in layer['images'].items():
                if not 'metadata' in im:
                    im['metadata'] = {}
                if not 'annotations' in im['metadata']:
                    im['metadata']['annotations'] = []
                ann = im['metadata']['annotations']
                if layer['skip']:
                    # Check and set as needed
                    already_skipped = False
                    for a in ann:
                        if a.startswith('skipped'):
                            already_skipped = True
                            break
                    if not already_skipped:
                        add_list.append((sk, layer_num, ik))
                        ann.append('skipped(1)')
                else:
                    # Remove all "skipped"
                    for a in ann:
                        if a.startswith('skipped'):
                            remove_list.append((sk, layer_num, ik))
                            ann.remove(a)
    for item in remove_list:
        alignem.print_debug(80, "Removed skip from " + str(item))
    for item in add_list:
        alignem.print_debug(80, "Added skip to " + str(item))


#
# #jy
# def export_zarr():
#     destination_path = os.path.abspath(alignem.project_data['data']['destination_path'])
#     print("destination_path= ",destination_path)
#
#     cwd = os.getcwd()
#     print("\ncwd=",cwd)
#
#     #print("\nproject_data...\n",alignem.project_data)
#     scale_1_path = os.path.join(alignem.project_data['data']['destination_path'], 'scale_1') # scale_1_path= scale_1
#     aligned_path = os.path.join(scale_1_path, 'img_aligned') #aligned_path= scale_1/img_aligned
#
#     aligned_path_full = os.path.join(cwd, aligned_path)
#     print("aligned_path_full= ", aligned_path_full)
#
#     clevel = str(clevel_val.get_value())
#     cname = str(cname_type.get_value())
#     n_scales = str(n_scales_val.get_value())
#     print("cname:",cname)
#     print("type(cname):", type(cname))
#     # cname: none
#     # type(cname): <class 'str'>
#
#     if cname == "none":
#         print("cname is none.")
#         os.system("./make_zarr.py " + aligned_path_full + " -c '64,64,64' -nS " + n_scales + " -nC 1 -d " + destination_path)
#     else:
#         #os.system("./make_zarr.py volume_josef_small --chunks '1,5332,5332' --no_compression True")
#         os.system("./make_zarr.py " + aligned_path_full + " -c '64,64,64' -nS " + n_scales + " -cN " + cname + " -cL " + clevel + " -d " + destination_path)
#
# #jy
# def neuroglancer_view():
#     destination_path = os.path.abspath(alignem.project_data['data']['destination_path'])
#     zarr_project_path = os.path.join(destination_path, "project.zarr")
#     os.chdir(zarr_project_path)
#
#     # zarray_path =  os.path.join(destination_path, "project.zarr", "img_aligned_zarr", "s0", ".zarray")
#
#     # with open(zarray_path) as f:
#     #     zarray_keys = json.load(f)
#
#     # chunks = zarray_keys["chunks"]
#     # cname = zarray_keys["compressor"]["cname"]
#     # clevel = zarray_keys["compressor"]["clevel"]
#
#     """
#     if not demo_bool.get_value():
#         os.system("./glanceem_ng.py " + zarr_project_path + " --view single")
#
#     if demo_bool.get_value():
#         example_path = '/Users/joelyancey/glanceem_feb/glanceem_demo_1/project.zarr'
#         os.system("./glanceem_ng.py " + example_path + " --view row")
#     """
#
#     # from PyQt5.QtCore import QProcess
#     # process = QProcess()
#     # process.start("./glanceem_ng.py " + zarr_project_path + " --view single")
#     # process.waitForStarted()
#     # process.waitForFinished()
#     # process.readAll()
#     # process.close()
#
#     # def message(self, s):
#     #     self.text.appendPlainText(s)
#     #
#     # def start_process(self):
#     #     self.message("Executing process.")
#     #     self.p = QProcess()  # Keep a reference to the QProcess (e.g. on self) while it's running.
#     #     self.p.start("python3", ["./glanceem_ng.py ", zarr_project_path, "--view single"])
#     #
#     # start_process(self)
#
#     bind = '127.0.0.1'
#     port = 9000
#     view = 'single'
#
#     #http-server -p 3000 --cors
#     # p = QProcess()
#     # p.start("http-server", ["-p",3000, "--cors"])
#
#
#
#
#     # print("neuroglancer_view(): Calling get_viewer_url(zarr_project_path)...")
#     # viewer_url = get_viewer_url(zarr_project_path)
#     # print("viewer_url: ", viewer_url)
#     #
#     # print("neuroglancer_view(): Calling web = QWebEngineView()...")
#     # web = QWebEngineView()
#     #
#     # print("neuroglancer_view(): Calling os.chdir(zarr_project_path)...")
#     # os.chdir(zarr_project_path)
#     # print("neuroglancer_view(): zarr_project_path: ",zarr_project_path)
#     #
#     # print("neuroglancer_view(): Running web.load(QUrl(viewer_url)...")
#     # web.load(QUrl(viewer_url))
#     #
#     # print("neuroglancer_view(): Running web.show()...")
#     # web.show()
#     #
#     # sys.exit(app.exec_())
#
#     # p = QProcess()
#     # #p.start("python3", ["./glanceem_ng.py " + zarr_project_path + " --view single"])
#     # p.start("python3", ["./glanceem_ng.py ", zarr_project_path, "--view single"])


# main
if __name__ == "__main__":
    options = argparse.ArgumentParser()
    options.add_argument("-d", "--debug", type=int, required=False, default=10,
                         help="Print more information with larger DEBUG (0 to 100)")
    options.add_argument("-p", "--parallel", type=int, required=False, default=1, help="Run in parallel")
    options.add_argument("-l", "--preload", type=int, required=False, default=3,
                         help="Preload +/-, total to preload = 2n-1")
    options.add_argument("-c", "--use_c_version", type=int, required=False, default=1,
                         help="Run the C versions of SWiFT tools")
    options.add_argument("-f", "--use_file_io", type=int, required=False, default=0,
                         help="Use files to gather output from tasks")
    args = options.parse_args()
    alignem.DEBUG_LEVEL = int(args.debug)
    print("cli args:", args)

    global enable_stats
    enable_stats = 0
    main_window_size_x = 1420
    main_window_size_y = 700

    if args.parallel != None:
        global_parallel_mode = args.parallel != 0

    if args.use_c_version != None:
        alignem.use_c_version = args.use_c_version != 0

    if args.use_file_io != None:
        global_use_file_io = args.use_file_io != 0

    if args.preload != None:
        alignem.preloading_range = int(args.preload)
        if alignem.preloading_range < 1:
            alignem.preloading_range = 1

    my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
    source_list = [
        my_path + "alignem_swift.py",
        my_path + "alignem_data_model.py",
        my_path + "alignem.py",
        my_path + "swift_project.py",
        my_path + "pyswift_tui.py",
        my_path + "swiftir.py",
        my_path + "align_swiftir.py",
        my_path + "source_tracker.py",
        my_path + "task_queue.py",
        my_path + "task_queue2.py",
        my_path + "task_wrapper.py",
        my_path + "single_scale_job.py",
        my_path + "multi_scale_job.py",
        my_path + "project_runner.py",
        my_path + "single_alignment_job.py",
        my_path + "single_crop_job.py",

        # jy
        my_path + "stylesheet.qss",
        my_path + "make_zarr.py",
        # my_path + "glanceem_ng.py",
        my_path + "glanceem_utils.py"
    ]
    # global_source_hash, global_source_rev = get_hash_and_rev (source_list, "source_info.json")
    # control_model[0].append ( [ "                                              "
    #                             "                                              "
    #                             "                                              "
    #                             "                                              "
    #                             "                                              "
    #                             "Source Tag: " + str(global_source_rev) + "   /   "
    #                             "Source Hash: " + str(global_source_hash) ] )

    print("\nRunning with source hash: " + str(global_source_hash) +
          ", tagged as revision: " + str(global_source_rev) +
          ", parallel mode = " + str(global_parallel_mode) + "\n")

    # main_win = alignem.MainWindow(control_model=control_model, title="GlanceEM_SWiFT")
    main_win = alignem.MainWindow(title="GlanceEM_SWiFT")

    # # this works to set a background:
    # stylesheet = """
    #     MainWindow {
    #         background-image: url("romain-lemaire-night.jpg");
    #         background-repeat: no-repeat;
    #         background-position: center;
    #     }
    # """
    # main_win.setStyleSheet(stylesheet)

    main_win.register_view_change_callback(view_change_callback)
    main_win.register_mouse_move_callback(mouse_move_callback)
    main_win.register_mouse_down_callback(mouse_down_callback)
    alignem.crop_mode_callback = crop_mode_callback
    alignem.update_linking_callback = update_linking_callback
    alignem.update_skips_callback = update_skips_callback

    # main_win.resize(1420,655)  #original This value is typically chosen to show all widget text
    main_win.resize(main_window_size_x, main_window_size_y)  # This value is typically chosen to show all widget text

    # main_win.register_project_open ( open_json_project )
    # main_win.register_project_save ( save_json_project )
    # main_win.register_gen_scales ( generate_scales )

    alignem.print_debug(30, "================= Defining Roles =================")

    main_win.define_roles(swift_roles)

    alignem.run_app(main_win)
