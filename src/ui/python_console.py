from qtpy.QtWidgets import QApplication
from qtpy.QtCore import Qt
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager
from IPython.lib import guisupport

import src.config as cfg

from qtconsole.manager import QtKernelManager
import IPython.lib
import IPython

'''
jupyter-console==6.4.4
pyqtconsole==1.2.2 # <-- Uninstalled
qtconsole==5.3.1

jupyter-console==6.4.4
qtconsole==5.3.1

Attempting:
pipenv uninstall jupyter-client
pipenv install jupyter-client==6.1.12
# I noticed that no jupyter-console at this point was in my pipfile.lock
pipenv lock
'''

class PythonConsole(RichJupyterWidget):

    def __init__(self, customBanner=None, *args, **kwargs):
        super(PythonConsole, self).__init__(*args, **kwargs)

        # self.set_default_style(colors='linux')
        self.set_default_style(colors='nocolor')
        self.prompt_to_top()

        if customBanner is not None:
            self.banner = customBanner

        # self.font_size = 6
        self.font_size = 4
        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel(show_banner=False)
        self.kernel_manager.kernel.gui = 'qt'
        self.kernel_client = self._kernel_manager.client()
        self.kernel_client.start_channels()

        self.setFocusPolicy(Qt.NoFocus)

        self.execute_command('import os, sys, zarr, neuroglancer')
        self.execute_command('from src.config import *')
        self.execute_command('from src.config import main_window')
        self.execute_command('from src.helpers import *')
        self.execute_command('import src.config as cfg')
        # self.clear()
        self.execute('clear')
        # self.clear_output()

        self.out_prompt = 'AlignEM [<span class="out-prompt-number">%i</span>]: '

        import IPython; IPython.get_ipython().execution_count = 0
        self.print_text('AlignEM [<span class="out-prompt-number">%i</span>]: ')





        def stop():
            self.kernel_client.stop_channels()
            self.kernel_manager.shutdown_kernel()
            guisupport.get_app_qt().exit()

        self.exit_requested.connect(stop)

    def push_vars(self, variableDict):
        """
        Given a dictionary containing name / value pairs, push those variables
        to the Jupyter console widget
        """
        self.kernel_manager.kernel.shell.push(variableDict)

    def clear(self):
        """
        Clears the terminal
        """
        self._control.clear()

        # self.kernel_manager

    def print_text(self, text):
        """
        Prints some plain text to the console
        """
        self._append_plain_text(text)

    def execute_command(self, command):
        """
        Execute a command in the frame of the console widget
        """
        self._execute(command, False)

    def set_color_none(self):
        self.set_default_style(colors='nocolor')

    def set_color_linux(self):
        self.set_default_style(colors='linux')



if __name__ == '__main__':
    app = QApplication([])
    widget = PythonConsole()
    widget.show()
    app.exec_()