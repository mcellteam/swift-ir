
import qtconsole
from IPython.lib import guisupport
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager
from qtpy.QtWidgets import QApplication
from qtpy.QtCore import Qt

class PythonConsole(RichJupyterWidget):

    def __init__(self, customBanner=None, *args, **kwargs):
        super(PythonConsole, self).__init__(*args, **kwargs)
        self.set_default_style(colors='nocolor')
        self.prompt_to_top()

        if customBanner is not None:
            self.banner = customBanner

        # self.font_size = 6
        # self.font_size = 4
        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel(show_banner=False)
        self.kernel_manager.kernel.gui = 'qt'
        self.kernel_client = self._kernel_manager.client()
        self.kernel_client.start_channels()
        self.setFocusPolicy(Qt.NoFocus)
        self.execute_command('import src.config as cfg')
        self.execute_command('from src.config import *')
        self.execute_command('from src.config import main_window')
        self.execute_command('from src.helpers import *')
        self.execute_command('import os, sys, zarr, neuroglancer')
        self.execute_command('from qtpy.QtCore import QUrl, Qt')
        self.execute_command('from qtpy import QtCore, QtGui, QtWidgets')
        self.execute('clear')
        self.out_prompt = 'AlignEM [<span class="out-prompt-number">%i</span>]: '

        import IPython; IPython.get_ipython().execution_count = 0
        self.print_text('AlignEM [<span class="out-prompt-number">%i</span>]: ')

        def stop():
            self.kernel_client.stop_channels()
            self.kernel_manager.shutdown_kernel()
            guisupport.get_app_qt().exit()

        self.exit_requested.connect(stop)

    def push_vars(self, variableDict):
        """Push dictionary variables to the Jupyter console widget"""
        self.kernel_manager.kernel.shell.push(variableDict)

    def clear(self):
        """Clears the terminal"""
        self._control.clear()
        # self.kernel_manager

    def print_text(self, text):
        """Print to the console"""
        self._append_plain_text(text)

    def execute_command(self, command):
        """Execute a command in the frame of the console widget"""
        self._execute(command, False)

    def set_color_none(self):
        """Set no color scheme"""
        self.set_default_style(colors='nocolor')

    def set_color_linux(self):
        """Set linux color scheme"""
        self.set_default_style(colors='linux')


if __name__ == '__main__':
    app = QApplication([])
    widget = PythonConsole()
    widget.show()
    app.exec_()