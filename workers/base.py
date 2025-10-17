"""
Base worker signals for Qt threaded operations.
"""
from PyQt6 import QtCore


class WorkerSignals(QtCore.QObject):
    """Signals for worker threads to communicate with main thread."""
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)
    progress = QtCore.pyqtSignal(int)           # percentage
    result = QtCore.pyqtSignal(object)          # arbitrary result
    status = QtCore.pyqtSignal(str)
