"""
Worker for renaming scenes.
"""
import json
import traceback
from typing import Any, Dict, List

from PyQt6 import QtCore

from models import GraphQLClient
from .base_signals import WorkerSignals


class RenameSceneWorker(QtCore.QRunnable):
    """Worker to rename multiple scenes."""

    def __init__(self, client: GraphQLClient, scenes_to_update: List[Dict[str, Any]], new_title: str, dry_run: bool = False):
        super().__init__()
        self.client = client
        self.scenes = scenes_to_update
        self.new_title = new_title
        self.dry_run = dry_run
        self.signals = WorkerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        try:
            total = len(self.scenes)
            updated = 0
            skipped_deleted = 0
            failed = 0
            self.signals.status.emit(f"Starting rename of {total} scenes (dry_run={self.dry_run})")

            for idx, s in enumerate(self.scenes):
                scene_id = s.get("id")
                old_title = s.get("title", "<no title>")

                if self.dry_run:
                    self.signals.status.emit(f"[{idx+1}/{total}] Dry-run: would rename '{old_title}' to '{self.new_title}' ({scene_id})")
                    updated += 1
                    percent = int((idx+1) / total * 100)
                    self.signals.progress.emit(percent)
                    continue

                # Perform mutation
                try:
                    q = '''
                    mutation SceneUpdate($input: SceneUpdateInput!) {
                      sceneUpdate(input: $input) {
                        id
                        title
                      }
                    }
                    '''
                    vars = {"input": {"id": scene_id, "title": self.new_title}}
                    resp = self.client.call(q, vars)

                    if "data" in resp and resp["data"].get("sceneUpdate", {}).get("id") == scene_id:
                        updated += 1
                        self.signals.status.emit(f"[{idx+1}/{total}] Renamed: '{old_title}' -> '{self.new_title}'")
                    else:
                        err_msgs = []
                        if "errors" in resp:
                            err_msgs = [e.get("message", str(e)) for e in resp["errors"]]
                        err_text = "; ".join(err_msgs) if err_msgs else json.dumps(resp)

                        if "FOREIGN KEY" in err_text.upper() or "FOREIGN KEY" in err_text:
                            skipped_deleted += 1
                            self.signals.status.emit(f"[{idx+1}/{total}] Skipped deleted (FOREIGN KEY): {old_title}")
                        else:
                            failed += 1
                            self.signals.status.emit(f"[{idx+1}/{total}] Failed: {old_title} -> {err_text}")
                except Exception as e:
                    failed += 1
                    self.signals.status.emit(f"[{idx+1}/{total}] Exception for {old_title}: {e}")

                percent = int((idx+1) / total * 100)
                self.signals.progress.emit(percent)

            summary = {
                "updated": updated,
                "skipped_deleted": skipped_deleted,
                "failed": failed
            }
            self.signals.result.emit(summary)
            self.signals.progress.emit(100)

        except Exception as e:
            self.signals.error.emit(str(e))
            tb = traceback.format_exc()
            self.signals.status.emit(tb)
        finally:
            self.signals.finished.emit()
