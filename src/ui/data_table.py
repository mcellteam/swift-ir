#!/usr/bin/env python3
'''
Simple interface for loading and computing averages of tabular spinehead datamodel.
Demo GUI script for Mohammad spinehead volume project.
2022-10-23 - CNL - Joel Yancey.

Demonstrates:
- Loading datamodel from CSV file via cli and open file dialog
- Displaying datamodel in pretty project_table
- Selecting project_table datamodel and returning pandas dataframe
- Performing some analysis on arbitrary user datamodel
- Using classes from Qt documentation ('PandasModel')
- QApplication, QMainWindow, QWidget,  QFileDialog, QTableView, QPushButton, QTabWidget, QGridLayout, QHBoxLayout,
  QErrorMessage, QGroupBox, QTextEdit, QSplitter, QStatusBar

Launch the GUI either by:
    python3 data_table.py
    python3 data_table.py -f Dentate_PSD_SDSA_Oml_Iml.csv

Dependencies:
    pip install PyQt5 qtconsole scipy

To create requirements.txt:
     pip freeze > requirements.txt

'''


import sys
import inspect
import argparse
import pandas as pd
# from _py_console import PythonConsole

from qtpy.QtCore import QSize, Qt, Slot, QCoreApplication, QAbstractTableModel, QModelIndex
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QTabWidget, QGridLayout, \
    QHBoxLayout, QFileDialog, QTableView, QErrorMessage, QGroupBox, QTextEdit, QSplitter, QStatusBar, \
    QAbstractItemView

__all__ = ['DataTable']


class DataTable(QMainWindow):

    def __init__(self, file=None):
        '''This is the constructor'''
        super().__init__()

        self.setupUI()

        self._file = file # path to a file on disk
        if self._file != None:
            self.import_data(self._file)
            self.load_dataframe()

        self._selected_rows = []

    def import_data(self, path):
        '''Import Data From CSV File Into Pandas Dataframe'''
        print('Reading CSV datamodel into pandas dataframe...')
        self._dataframe = pd.read_csv(path)

    def load_dataframe(self):
        '''Load Dataframe Into GUI Table'''
        if isinstance(self._dataframe, pd.DataFrame):
            my_pandas_model = PandasModel(self._dataframe)
            self.table_widget.setModel(my_pandas_model)
            self.table_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
            self.selection_model = self.table_widget.selectionModel()
            # This line connects  'self.userSelectionChanged' method/function (Slot)
            # to 'self.selection_model.userSelectionChanged' (Signal)
            self.selection_model.selectionChanged.connect(self.selected_rows_changed)
        else:
            error_dialog = QErrorMessage()
            error_dialog.showMessage('No datamodel loaded!')

    def selection(self):
        '''Return Pandas Dataframe From Selection'''
        return self._dataframe.iloc[self._selection_indexes]

    def clear_selection(self):
        '''Clear User Selection'''
        self._selected_rows = []
        self.table_widget.clearSelection()
        self.display_results('')
        print('Selection Cleared')


    def selected_rows_changed(self):
        '''Slot That Connects To Selection Changed Signal
        cur_method(self.selection()['Group_1'])) = <class 'pandas.core.series.Series'>
        cur_method(self.selection()) = <class 'pandas.core.frame.DataFrame'>
        '''

        # print("cur_method(self.selection()['Group_1'])) %s" % cur_method(self.selection()['Group_1']))
        # print("cur_method(self.selection()) %s" % cur_method(self.selection()) )

        # This returns the name of the function callER (the function that called this function). Useful trick.
        # We want to short-ciruit this function when called automatically by 'self.clear_selection'
        caller = inspect.stack()[1].function
        if caller != 'clear_selection':
            print('Selection Changed!')
            selection = self.table_widget.selectedIndexes()
            self._selection_indexes = list(set([row.row() for row in selection]))
            if selection is not []:
                print(self.selection())
                print(len(self.selection()))
                self.status_bar.showMessage('Selected Rows: %s' % str(self._selection_indexes))
                print('Selected Rows: %s' % str(self._selection_indexes))

                self.display_results('%s\n\n----Selected Averages----\n'
                                     'Average Group 1 : %f\n'
                                     'Average Group 2 : %f'
                                     'First value of Group_1 : %f'
                                     % (str(self.selection()), self.grp1_avg(), self.grp2_avg(), self.grp1_squared()))

    def grp1_avg(self):
        '''Compute Group 1 Average From Selection
        cur_method(self.selection()) = <class 'pandas.core.frame.DataFrame'>
        *** Now that we know the cur_method, we can see that '.mean()' is a method/function belonging to a pandas
        dataframe... If we wanted to do something other than average, we would want to look at pandas
        documentation: https://pandas.pydata.org/pandas-docs/stable/user_guide/basics.html ***
        '''
        return float(self.selection()['Group_1'].mean()) 

    def grp2_avg(self):
        '''Compute Group 2 Average From Selection'''
        return float(self.selection()['Group_2'].mean())


    # Equivalent to... def grp1_squared(self, row_index):
    def grp1_squared(self) -> float:
        '''Squares the value at requested row index'''
        result = float(self.selection()['Group_1'].values[0])
        print(result)
        return result
        # return self.selection()['Group_1'].values[row_index]


    def display_results(self, text):
        '''Display Text In Read-only Text Widget'''
        self.results_widget.setText(text)

    def setupUI(self):
        '''Setup the UI'''
        self.setWindowTitle("Demo GUI - Spinehead")
        self.resize(QSize(700, 700))  # size of main window
        self.tab_widget = QTabWidget()
        self.status_bar = QStatusBar()

        tab1 = QWidget()
        tab2 = QWidget()
        tab3 = QWidget()
        tab1_layout = QGridLayout()
        tab2_layout = QGridLayout()
        tab3_layout = QGridLayout()
        tab1.setLayout(tab1_layout)
        tab2.setLayout(tab2_layout)
        tab3.setLayout(tab3_layout)
        self.tab_widget.addTab(tab1, "Data")
        self.tab_widget.addTab(tab2, "Another Tab")
        self.tab_widget.addTab(tab3, "Python")

        self.clear_button = QPushButton('Clear')
        self.clear_button.setFixedSize(QSize(120, 28))
        self.clear_button.clicked.connect(self.clear_selection)

        self.quit_button = QPushButton('Quit')
        self.quit_button.setFixedSize(QSize(120, 28))
        self.quit_button.clicked.connect(QCoreApplication.instance().quit)

        self.buttons = QGroupBox('Control Panel')
        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.addWidget(self.clear_button)
        self.buttons_layout.addWidget(self.quit_button)
        self.buttons_layout.addStretch()
        self.buttons.setLayout(self.buttons_layout)

        self.table_widget = QTableView()
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSelectionBehavior(QTableView.SelectRows)

        self.results_widget = QTextEdit('Results')
        self.results_widget.setReadOnly(True)

        # self._py_console = PythonConsole()
        # tab3_layout.addWidget(self._py_console,0, 0)

        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(self.table_widget)
        self.splitter.addWidget(self.results_widget)

        tab1_layout.addWidget(self.splitter, 0, 0)
        tab1_layout.addWidget(self.buttons, 1, 0)


class PandasModel(QAbstractTableModel):
    """A previewmodel to interface a Qt project_table with pandas dataframe.
    Adapted from Qt Documentation Example:
    https://doc.qt.io/qtforpython/examples/example_external__pandas.html"""
    def __init__(self, dataframe: pd.DataFrame, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self._dataframe = dataframe

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent == QModelIndex(): return len(self._dataframe)

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent == QModelIndex(): return len(self._dataframe.columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole):
        if not index.isValid(): return None
        # if role == Qt.DisplayRole:
        #     return str(self._dataframe.iloc[index.row(), index.column()])

        if role == Qt.DisplayRole:
            return data   # Pass the datamodel to our delegate to draw.
        if role == Qt.ToolTipRole:
            return data.title

    def headerData(self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal: return str(self._dataframe.columns[section])
            if orientation == Qt.Vertical: return str(self._dataframe.index[section])


if __name__== "__main__":
    app = QApplication(sys.argv)
    options = argparse.ArgumentParser()
    options.add_argument("-f", "--file", type=str, required=False)
    args = options.parse_args()

    '''Allow GUI to be launched with datamodel file already loaded (use cli argument --file or -f)'''
    if args.file != None:
        window = DataTable(file=args.file)
    else:
        window = DataTable()

    window.show()
    sys.exit(app.exec())

