"""
Worker for assigning performers to scenes.
"""
import json
import traceback
from typing import Any, Dict, List

from PyQt6 import QtCore

from models import GraphQLClient
from .base_signals import WorkerSignals


class AssignPerformersWorker(QtCore.QRunnable):
    def __init__(self, client: GraphQLClient, scenes_to_update: List[Dict[str, Any]], performer_ids: List[str], dry_run: bool = False):
        super().__init__()
        self.client = client
        self.scenes = scenes_to_update
        self.performer_ids = performer_ids
        self.dry_run = dry_run
        self.signals = WorkerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        try:
            total = len(self.scenes)
            updated = 0
            already_assigned = 0
            skipped_deleted = 0
            failed = 0
            self.signals.status.emit(f"Starting performer assignment for {total} scenes (dry_run={self.dry_run})")
            for idx, s in enumerate(self.scenes):
                scene_id = s.get("id")
                title = s.get("title", "<no title>")
                current_performer_ids = [p.get("id") for p in s.get("performers", [])] if s.get("performers") else []
                
                # Check if all performers are already assigned
                all_already_assigned = all(pid in current_performer_ids for pid in self.performer_ids)
                if all_already_assigned:
                    self.signals.status.emit(f"[{idx+1}/{total}] Already assigned: {title}")
                    already_assigned += 1
                    percent = int((idx+1) / total * 100)
                    self.signals.progress.emit(percent)
                    continue
                
                # Merge performer IDs (preserve existing, add new)
                new_performer_ids = list(set(current_performer_ids + self.performer_ids))
                
                if self.dry_run:
                    self.signals.status.emit(f"[{idx+1}/{total}] Dry-run: would assign performers to '{title}' ({scene_id})")
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
                      }
                    }
                    '''
                    vars = {"input": {"id": scene_id, "performer_ids": new_performer_ids}}
                    resp = self.client.call(q, vars)
                    if "data" in resp and resp["data"].get("sceneUpdate", {}).get("id") == scene_id:
                        updated += 1
                        self.signals.status.emit(f"[{idx+1}/{total}] Assigned performers: {title}")
                    else:
                        err_msgs = []
                        if "errors" in resp:
                            err_msgs = [e.get("message", str(e)) for e in resp["errors"]]
                        err_text = "; ".join(err_msgs) if err_msgs else json.dumps(resp)
                        if "FOREIGN KEY" in err_text.upper() or "FOREIGN KEY" in err_text:
                            skipped_deleted += 1
                            self.signals.status.emit(f"[{idx+1}/{total}] Skipped deleted (FOREIGN KEY): {title}")
                        else:
                            failed += 1
                            self.signals.status.emit(f"[{idx+1}/{total}] Failed: {title} -> {err_text}")
                except Exception as e:
                    failed += 1
                    self.signals.status.emit(f"[{idx+1}/{total}] Exception for {title}: {e}")
                percent = int((idx+1) / total * 100)
                self.signals.progress.emit(percent)
            summary = {
                "updated": updated,
                "already_assigned": already_assigned,
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
