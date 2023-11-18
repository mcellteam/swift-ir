from qtpy.QtWidgets import QFileDialog

def export_affines_dialog() -> str:
    '''Dialog for saving a datamodel. Returns 'file_path'.'''
    dialog = QFileDialog()
    dialog.setOption(QFileDialog.DontUseNativeDialog)
    dialog.setWindowTitle('Export Affine Data as .csv')
    dialog.setNameFilter("Text Files (*.csv)")
    dialog.setViewMode(QFileDialog.Detail)
    dialog.setAcceptMode(QFileDialog.AcceptSave)
    if dialog.exec() == QFileDialog.Accepted:
        return dialog.selectedFiles()[0]