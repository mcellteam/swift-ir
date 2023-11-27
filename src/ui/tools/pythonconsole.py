#!/usr/bin/env python3
'''
Performance:
Function 'initPythonConsole' executed in 0.5900s
'''

from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QWidget, QVBoxLayout


class PythonConsole(RichJupyterWidget):

    def __init__(self, customBanner=None, *args, **kwargs):
        super(PythonConsole, self).__init__(*args, **kwargs)
        # self.set_default_style(colors='nocolor')
        self.prompt_to_top()

        if customBanner is not None:
            self.banner = customBanner

        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel(show_banner=False)
        self.kernel_manager.kernel.gui = 'qt'
        self.kernel_client = self._kernel_manager.client()
        self.kernel_client.start_channels()
        self.setFocusPolicy(Qt.NoFocus)

        if 1:
            self.execute_command('import os, sys, copy, json, stat, time, glob')
            self.execute_command('from pprint import pformat')
            self.execute_command('import zarr')
            self.execute_command('from pathlib import Path')
            self.execute_command('import neuroglancer as ng')
            self.execute_command('from qtpy.QtWidgets import *')
            self.execute_command('from qtpy.QtCore import *')
            self.execute_command('from qtpy.QtGui import *')
            self.execute_command('import src.config as cfg')
            self.execute_command('from src.utils.readers import read')
            self.execute_command('from src.utils.writers import write')
            self.execute_command('from src.core.files import DirectoryStructure')
            # self.execute_command('from src.utils.helpers import dt, find_allocated_widgets, count_widgets, '
            #                      'obj_to_string, getData, setData, getOpt, setOpt')
            self.execute('clear')
            # self.out_prompt = 'AlignEM [<span class="out-prompt-number">%i</span>]: '

            import IPython; IPython.get_ipython().execution_count = 0
            self.print_text('AlignEM [<span class="out-prompt-number">%i</span>]: ')

        def stop():
            self.kernel_client.stop_channels()
            self.kernel_manager.shutdown_kernel()
            # guisupport.get_app_qt().exit()

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
        """Execute a command in the getFrameScale of the console widget"""
        self._execute(command, False)

    def set_color_none(self):
        """Set no color scheme"""
        self.set_default_style(colors='nocolor')

    def set_color_linux(self):
        """Set linux color scheme"""
        self.set_default_style(colors='linux')


class PythonConsoleWidget(QWidget):

    def __init__(self):
        super(PythonConsoleWidget, self).__init__()
        self.layout = QVBoxLayout()
        # self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0,0,0,0)
        self.pyconsole = PythonConsole()
        # self.pyconsole = QWidget()
        self.layout.addWidget(self.pyconsole)
        # self.setFont(QFont('Ubuntu', 10))
        self.setLayout(self.layout)
        self.setStyleSheet("font-family: 'Andale Mono', monospace; font-size: 9px;")


if __name__ == '__main__':
    app = QApplication([])
    widget = PythonConsole()
    widget.show()
    app.exec_()