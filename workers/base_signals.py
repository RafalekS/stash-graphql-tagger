"""
Base worker signals for Qt threading.
"""
from PyQt6 import QtCore


class WorkerSignals(QtCore.QObject):
    """Signals used by worker threads to communicate with the main thread."""
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)
    progress = QtCore.pyqtSignal(int)           # percentage
    result = QtCore.pyqtSignal(object)          # arbitrary result
    status = QtCore.pyqtSignal(str)
