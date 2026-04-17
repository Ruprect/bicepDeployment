# gui/workers/azure_worker.py
from PyQt6.QtCore import QThread, pyqtSignal


class AzureWorker(QThread):
    result = pyqtSignal(object)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, callable, args: tuple = (), parent=None):
        super().__init__(parent)
        self._callable = callable
        self._args = args

    def run(self):
        try:
            data = self._callable(*self._args)
            self.result.emit(data)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()
