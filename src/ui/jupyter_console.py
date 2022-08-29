from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager
from IPython.lib import guisupport



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

class JupyterConsole(RichJupyterWidget):

    def __init__(self, customBanner=None, *args, **kwargs):
        super(JupyterConsole, self).__init__(*args, **kwargs)

        self.set_default_style(colors='linux')
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



if __name__ == '__main__':
    app = QApplication([])
    widget = JupyterConsole()
    widget.show()
    app.exec_()