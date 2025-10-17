"""
Worker for fetching tag information from Stash API.
"""
import json
import traceback

from PyQt6 import QtCore

from models import GraphQLClient
from .base_signals import WorkerSignals


class FetchTagWorker(QtCore.QRunnable):
    """Worker to fetch tag by name."""
    
    def __init__(self, client: GraphQLClient, tag_name: str):
        super().__init__()
        self.client = client
        self.tag_name = tag_name
        self.signals = WorkerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        try:
            q = '''
            query FindTags($tag_filter: TagFilterType) {
              findTags(tag_filter: $tag_filter) {
                count
                tags {
                  id
                  name
                }
              }
            }
            '''
            vars = {
                "tag_filter": {
                    "name": {
                        "modifier": "EQUALS",
                        "value": self.tag_name
                    }
                }
            }
            self.signals.status.emit("Querying tag by name...")
            data = self.client.call(q, vars)
            self.signals.progress.emit(50)
            if "data" not in data or "findTags" not in data["data"]:
                raise RuntimeError("Unexpected response: " + json.dumps(data))
            count = data["data"]["findTags"]["count"]
            if count == 0:
                # Emit a special error text so main thread can offer to create it
                self.signals.error.emit(f"TAG_NOT_FOUND:{self.tag_name}")
                self.signals.status.emit(f"Tag '{self.tag_name}' not found.")
                return
            tag = data["data"]["findTags"]["tags"][0]
            tag_id = tag["id"]
            tag_name = tag.get("name", "")
            self.signals.result.emit({"id": tag_id, "name": tag_name})
            self.signals.progress.emit(100)
        except Exception as e:
            self.signals.error.emit(str(e))
            tb = traceback.format_exc()
            self.signals.status.emit(tb)
        finally:
            self.signals.finished.emit()
