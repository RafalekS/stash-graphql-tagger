"""
Worker for searching scenes from Stash API.
"""
import json
import traceback
from typing import Any, Dict, List
from PyQt6 import QtCore

from models import GraphQLClient
from .base import WorkerSignals



class SearchScenesWorker(QtCore.QRunnable):
    def __init__(self, client: GraphQLClient, search_term: str, performer_ids: List[str] = None,
                 performer_logic: str = "AND", studio_id: str = None, date_from: str = None,
                 date_to: str = None, duration_value1: int = None, duration_value2: int = None,
                 duration_operator: str = "BETWEEN", path_query: str = None, resolution_enum: str = None,
                 resolution_operator: str = "EQUALS", per_page: int = 1000):
        super().__init__()
        self.client = client
        self.search_term = search_term
        self.performer_ids = performer_ids or []
        self.performer_logic = performer_logic  # "AND" or "OR"
        self.studio_id = studio_id
        self.date_from = date_from  # YYYY-MM-DD format
        self.date_to = date_to  # YYYY-MM-DD format
        self.duration_value1 = duration_value1  # seconds (int)
        self.duration_value2 = duration_value2  # seconds (int) - only for BETWEEN
        self.duration_operator = duration_operator  # EQUALS, NOT_EQUALS, GREATER_THAN, LESS_THAN, BETWEEN
        self.path_query = path_query  # Path/filename search string
        self.resolution_enum = resolution_enum  # GraphQL ResolutionEnum value (VERY_LOW, LOW, STANDARD_HD, FULL_HD, etc.)
        self.resolution_operator = resolution_operator  # EQUALS, NOT_EQUALS, GREATER_THAN, LESS_THAN (no BETWEEN support)
        self.per_page = per_page
        self.signals = WorkerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        try:
            q = '''
            query FindScenes($filter: FindFilterType, $scene_filter: SceneFilterType) {
              findScenes(filter: $filter, scene_filter: $scene_filter) {
                count
                scenes {
                  id
                  title
                  date
                  tags {
                    id
                    name
                  }
                  performers {
                    id
                    name
                  }
                  studio {
                    id
                    name
                  }
                  files {
                    size
                    duration
                    width
                    height
                    path
                    video_codec
                  }
                }
              }
            }
            '''
            scene_filter = {}
            
            # Add title search if provided
            if self.search_term:
                scene_filter["title"] = {
                    "modifier": "INCLUDES",
                    "value": self.search_term
                }
            
            # Add performer filter if provided
            if self.performer_ids:
                modifier = "INCLUDES_ALL" if self.performer_logic == "AND" else "INCLUDES"
                scene_filter["performers"] = {
                    "value": self.performer_ids,
                    "modifier": modifier
                }
            
            # Add studio filter if provided
            if self.studio_id:
                scene_filter["studios"] = {
                    "value": [self.studio_id],
                    "modifier": "INCLUDES"
                }
            
            # Add date range filter if provided
            if self.date_from and self.date_to:
                scene_filter["date"] = {
                    "value": self.date_from,
                    "value2": self.date_to,
                    "modifier": "BETWEEN"
                }
            elif self.date_from:
                # Only start date provided
                scene_filter["date"] = {
                    "value": self.date_from,
                    "modifier": "GREATER_THAN"
                }
            elif self.date_to:
                # Only end date provided
                scene_filter["date"] = {
                    "value": self.date_to,
                    "modifier": "LESS_THAN"
                }
            
            # Add duration filter if provided
            if self.duration_value1 is not None:
                if self.duration_operator == "BETWEEN" and self.duration_value2 is not None:
                    scene_filter["duration"] = {
                        "value": self.duration_value1,
                        "value2": self.duration_value2,
                        "modifier": "BETWEEN"
                    }
                else:
                    # Single value operators
                    scene_filter["duration"] = {
                        "value": self.duration_value1,
                        "modifier": self.duration_operator
                    }
            
            # Add path filter if provided (SERVER-SIDE search)
            if self.path_query:
                scene_filter["path"] = {
                    "value": self.path_query,
                    "modifier": "INCLUDES"
                }

            # Add resolution filter if provided (SERVER-SIDE filter)
            if self.resolution_enum:
                scene_filter["resolution"] = {
                    "value": self.resolution_enum,
                    "modifier": self.resolution_operator
                }

            vars = {
                "filter": {"per_page": self.per_page},
                "scene_filter": scene_filter
            }
            self.signals.status.emit("Searching scenes...")
            data = self.client.call(q, vars)
            if "data" not in data or "findScenes" not in data["data"]:
                raise RuntimeError("Unexpected response: " + json.dumps(data))
            count = data["data"]["findScenes"]["count"]
            scenes = data["data"]["findScenes"]["scenes"]
            # Extract file metadata (handle multiple files per scene)
            for s in scenes:
                try:
                    files = s.get("files", []) or []
                    sizes = []
                    durations = []
                    paths = []
                    widths = []
                    heights = []
                    
                    for f in files:
                        # Size parsing
                        v = f.get("size")
                        if v is not None:
                            if isinstance(v, (int, float)):
                                try:
                                    sizes.append(int(v))
                                except Exception:
                                    pass
                            else:
                                v_str = str(v).strip().replace(",", "")
                                try:
                                    sizes.append(int(v_str))
                                except Exception:
                                    try:
                                        sizes.append(int(float(v_str)))
                                    except Exception:
                                        pass
                        
                        # Duration (in seconds as float)
                        dur = f.get("duration")
                        if dur is not None:
                            try:
                                durations.append(float(dur))
                            except Exception:
                                pass
                        
                        # Path
                        path = f.get("path")
                        if path:
                            paths.append(str(path))
                        
                        # Width and Height
                        w = f.get("width")
                        h = f.get("height")
                        if w is not None:
                            try:
                                widths.append(int(w))
                            except Exception:
                                pass
                        if h is not None:
                            try:
                                heights.append(int(h))
                            except Exception:
                                pass
                    
                    # Store processed metadata
                    s["_filesize"] = max(sizes) if sizes else None
                    s["_duration"] = max(durations) if durations else None
                    s["_path"] = paths[0] if paths else None  # Use first file path
                    s["_width"] = max(widths) if widths else None
                    s["_height"] = max(heights) if heights else None
                    
                    # Calculate resolution label
                    if s["_height"]:
                        h = s["_height"]
                        if h >= 2160:
                            s["_resolution"] = "4K"
                        elif h >= 1440:
                            s["_resolution"] = "1440p"
                        elif h >= 1080:
                            s["_resolution"] = "1080p"
                        elif h >= 720:
                            s["_resolution"] = "720p"
                        elif h >= 480:
                            s["_resolution"] = "480p"
                        else:
                            s["_resolution"] = f"{h}p"
                    else:
                        s["_resolution"] = None
                        
                except Exception:
                    s["_filesize"] = None
                    s["_duration"] = None
                    s["_path"] = None
                    s["_width"] = None
                    s["_height"] = None
                    s["_resolution"] = None
            self.signals.result.emit({"count": count, "scenes": scenes})
            self.signals.progress.emit(100)
        except Exception as e:
            self.signals.error.emit(str(e))
            tb = traceback.format_exc()
            self.signals.status.emit(tb)
        finally:
            self.signals.finished.emit()