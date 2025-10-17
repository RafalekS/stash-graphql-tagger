"""
Worker for fetching studio information from Stash API.
"""
import json
import traceback

from PyQt6 import QtCore

from models import GraphQLClient
from .base_signals import WorkerSignals


class FetchStudiosWorker(QtCore.QRunnable):
    """Worker to search studios by name with fuzzy matching (INCLUDES modifier)"""
    
    def __init__(self, client: GraphQLClient, studio_name: str, per_page: int = 100):
        super().__init__()
        self.client = client
        self.studio_name = studio_name
        self.per_page = per_page
        self.signals = WorkerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        try:
            q = '''
            query FindStudios($filter: FindFilterType, $studio_filter: StudioFilterType) {
              findStudios(filter: $filter, studio_filter: $studio_filter) {
                count
                studios {
                  id
                  name
                  scene_count
                  parent_studio {
                    id
                    name
                  }
                }
              }
            }
            '''
            vars = {
                "filter": {"per_page": self.per_page},
                "studio_filter": {
                    "name": {
                        "modifier": "INCLUDES",
                        "value": self.studio_name
                    }
                }
            }
            self.signals.status.emit("Searching studios...")
            data = self.client.call(q, vars)
            self.signals.progress.emit(50)
            if "data" not in data or "findStudios" not in data["data"]:
                raise RuntimeError("Unexpected response: " + json.dumps(data))
            count = data["data"]["findStudios"]["count"]
            studios = data["data"]["findStudios"]["studios"]
            self.signals.result.emit({"count": count, "studios": studios})
            self.signals.progress.emit(100)
        except Exception as e:
            self.signals.error.emit(str(e))
            tb = traceback.format_exc()
            self.signals.status.emit(tb)
        finally:
            self.signals.finished.emit()
