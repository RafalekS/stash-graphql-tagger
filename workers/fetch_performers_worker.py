"""
Worker for fetching performer information from Stash API.
"""
import json
import traceback

from PyQt6 import QtCore

from models import GraphQLClient
from .base_signals import WorkerSignals


class FetchPerformersWorker(QtCore.QRunnable):
    """Worker to search performers by name with fuzzy matching (INCLUDES modifier)"""
    
    def __init__(self, client: GraphQLClient, performer_name: str, per_page: int = 100):
        super().__init__()
        self.client = client
        self.performer_name = performer_name
        self.per_page = per_page
        self.signals = WorkerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        try:
            q = '''
            query FindPerformers($filter: FindFilterType, $performer_filter: PerformerFilterType) {
              findPerformers(filter: $filter, performer_filter: $performer_filter) {
                count
                performers {
                  id
                  name
                  disambiguation
                  scene_count
                }
              }
            }
            '''
            vars = {
                "filter": {"per_page": self.per_page},
                "performer_filter": {
                    "name": {
                        "modifier": "INCLUDES",
                        "value": self.performer_name
                    }
                }
            }
            self.signals.status.emit("Searching performers...")
            data = self.client.call(q, vars)
            self.signals.progress.emit(50)
            if "data" not in data or "findPerformers" not in data["data"]:
                raise RuntimeError("Unexpected response: " + json.dumps(data))
            count = data["data"]["findPerformers"]["count"]
            performers = data["data"]["findPerformers"]["performers"]
            self.signals.result.emit({"count": count, "performers": performers})
            self.signals.progress.emit(100)
        except Exception as e:
            self.signals.error.emit(str(e))
            tb = traceback.format_exc()
            self.signals.status.emit(tb)
        finally:
            self.signals.finished.emit()
