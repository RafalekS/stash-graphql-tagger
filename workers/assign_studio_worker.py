"""
Worker for assigning studio to scenes in bulk.
Replaces existing studio assignment.
"""
from typing import Any, Dict, List
from PyQt6 import QtCore
from .base_signals import WorkerSignals


class AssignStudioWorker(QtCore.QRunnable):
    """
    Worker to assign a studio to multiple scenes.
    Replaces the existing studio assignment for each scene.
    """
    
    def __init__(self, client, scenes: List[Dict[str, Any]], studio_id: str, dry_run: bool = False):
        super().__init__()
        self.client = client
        self.scenes = scenes
        self.studio_id = studio_id
        self.dry_run = dry_run
        self.signals = WorkerSignals()
    
    def run(self):
        """Execute studio assignment for all scenes"""
        try:
            total = len(self.scenes)
            updated = 0
            already_assigned = 0
            skipped_deleted = 0
            failed = 0
            
            for i, scene in enumerate(self.scenes):
                scene_id = scene.get("id")
                scene_title = scene.get("title", "Untitled")
                
                if not scene_id:
                    self.signals.status.emit(f"Scene missing ID: {scene_title}")
                    skipped_deleted += 1
                    continue
                
                # Check if studio is already assigned
                current_studio = scene.get("studio")
                current_studio_id = current_studio.get("id") if current_studio else None
                
                if current_studio_id == self.studio_id:
                    self.signals.status.emit(f"Scene '{scene_title}' already has this studio")
                    already_assigned += 1
                    self.signals.progress.emit(int((i + 1) / total * 100))
                    continue
                
                if self.dry_run:
                    if current_studio_id:
                        old_studio_name = current_studio.get("name", "Unknown")
                        self.signals.status.emit(f"[DRY RUN] Would replace studio for '{scene_title}' (current: {old_studio_name})")
                    else:
                        self.signals.status.emit(f"[DRY RUN] Would assign studio to '{scene_title}'")
                    updated += 1
                else:
                    # Perform the studio assignment
                    success = self._assign_studio_to_scene(scene_id, scene_title)
                    if success:
                        updated += 1
                    else:
                        failed += 1
                
                self.signals.progress.emit(int((i + 1) / total * 100))
            
            # Emit summary
            summary = {
                "updated": updated,
                "already_assigned": already_assigned,
                "skipped_deleted": skipped_deleted,
                "failed": failed
            }
            self.signals.result.emit(summary)
            
        except Exception as e:
            self.signals.error.emit(str(e))
    
    def _assign_studio_to_scene(self, scene_id: str, scene_title: str) -> bool:
        """
        Assign studio to a single scene using GraphQL mutation.
        Returns True on success, False on failure.
        """
        mutation = """
        mutation SceneUpdate($input: SceneUpdateInput!) {
            sceneUpdate(input: $input) {
                id
                studio {
                    id
                    name
                }
            }
        }
        """
        
        variables = {
            "input": {
                "id": scene_id,
                "studio_id": self.studio_id
            }
        }
        
        try:
            result = self.client.call_graphql(mutation, variables)
            
            if result and "sceneUpdate" in result:
                new_studio = result["sceneUpdate"].get("studio", {})
                studio_name = new_studio.get("name", "Unknown")
                self.signals.status.emit(f"Assigned studio '{studio_name}' to '{scene_title}'")
                return True
            else:
                self.signals.status.emit(f"Failed to assign studio to '{scene_title}': No data returned")
                return False
                
        except Exception as e:
            self.signals.status.emit(f"Error assigning studio to '{scene_title}': {str(e)}")
            return False
