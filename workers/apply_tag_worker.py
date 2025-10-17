"""
Worker for applying tags to scenes.
"""
import json
import traceback
from typing import Any, Dict, List

from PyQt6 import QtCore

from models import GraphQLClient
from .base_signals import WorkerSignals


class ApplyTagWorker(QtCore.QRunnable):
    """Worker to apply a tag to multiple scenes."""
    
    def __init__(self, client: GraphQLClient, scenes_to_update: List[Dict[str, Any]], tag_id: str, dry_run: bool = False):
        super().__init__()
        self.client = client
        self.scenes = scenes_to_update
        self.tag_id = tag_id
        self.dry_run = dry_run
        self.signals = WorkerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        try:
            total = len(self.scenes)
            updated = 0
            already_tagged = 0
            skipped_deleted = 0
            failed = 0
            self.signals.status.emit(f"Starting update of {total} scenes (dry_run={self.dry_run})")
            
            for idx, s in enumerate(self.scenes):
                scene_id = s.get("id")
                title = s.get("title", "<no title>")
                current_tag_ids = [t.get("id") for t in s.get("tags", [])] if s.get("tags") else []
                
                if self.tag_id in current_tag_ids:
                    self.signals.status.emit(f"[{idx+1}/{total}] Already tagged: {title}")
                    already_tagged += 1
                    percent = int((idx+1) / total * 100)
                    self.signals.progress.emit(percent)
                    continue
                
                new_tag_ids = current_tag_ids + [self.tag_id]
                
                if self.dry_run:
                    self.signals.status.emit(f"[{idx+1}/{total}] Dry-run: would tag '{title}' ({scene_id})")
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
                    vars = {"input": {"id": scene_id, "tag_ids": new_tag_ids}}
                    resp = self.client.call(q, vars)
                    
                    if "data" in resp and resp["data"].get("sceneUpdate", {}).get("id") == scene_id:
                        updated += 1
                        self.signals.status.emit(f"[{idx+1}/{total}] Tagged: {title}")
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
                "already_tagged": already_tagged,
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
