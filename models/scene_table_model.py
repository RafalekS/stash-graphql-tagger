"""
Scene table model for displaying scenes in the GUI.
"""
from typing import Any, Dict, List, Optional

from PyQt6 import QtCore

from utils import human_size, human_duration

class SceneTableModel(QtCore.QAbstractTableModel):
    # All possible columns
    ALL_COLUMNS = [
        "Select", "ID", "Title", "Studio", "Performers", "Tags", 
        "Date", "Path", "Duration", "Dimensions", "Resolution", "File Size"
    ]
    
    # Default visible columns (indices in ALL_COLUMNS)
    DEFAULT_VISIBLE = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]  # All columns visible by default

    def __init__(self, scenes: List[Dict[str, Any]] = None):
        super().__init__()
        self._scenes = scenes or []
        self._checked = [False] * len(self._scenes)
        self._visible_columns = self.DEFAULT_VISIBLE.copy()
        self._sort_column = -1  # No sorting by default
        self._sort_order = QtCore.Qt.SortOrder.AscendingOrder

    def get_visible_headers(self):
        """Get list of currently visible column headers"""
        return [self.ALL_COLUMNS[i] for i in self._visible_columns]
    
    def set_visible_columns(self, visible_indices: List[int]):
        """Set which columns are visible by their indices in ALL_COLUMNS"""
        self.beginResetModel()
        self._visible_columns = visible_indices
        self.endResetModel()
    
    def get_visible_column_index(self, all_columns_index: int) -> Optional[int]:
        """Convert ALL_COLUMNS index to visible column index, or None if hidden"""
        try:
            return self._visible_columns.index(all_columns_index)
        except ValueError:
            return None

    def rowCount(self, parent=None):
        return len(self._scenes)

    def columnCount(self, parent=None):
        return len(self._visible_columns)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        r = index.row()
        c = index.column()
        scene = self._scenes[r]
        
        # Map visible column to actual column
        actual_col = self._visible_columns[c]
        
        # Return checkbox state
        if role == QtCore.Qt.ItemDataRole.CheckStateRole and actual_col == 0:
            return QtCore.Qt.CheckState.Checked if self._checked[r] else QtCore.Qt.CheckState.Unchecked
        
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if actual_col == 1:  # ID
                return scene.get("id", "")
            if actual_col == 2:  # Title
                return scene.get("title", "")
            if actual_col == 3:  # Studio
                studio = scene.get("studio")
                if studio:
                    return studio.get("name", "")
                return ""
            if actual_col == 4:  # Performers
                performers = scene.get("performers", []) or []
                names = [p.get("name") for p in performers if p.get("name")]
                return ", ".join(names) if names else ""
            if actual_col == 5:  # Tags
                names = [t.get("name") for t in scene.get("tags", [])] if scene.get("tags") else []
                return ", ".join([n for n in names if n])
            if actual_col == 6:  # Date
                return scene.get("date", "")
            if actual_col == 7:  # Path
                return scene.get("_path", "")
            if actual_col == 8:  # Duration
                return human_duration(scene.get("_duration"))
            if actual_col == 9:  # Dimensions
                w = scene.get("_width")
                h = scene.get("_height")
                if w and h:
                    return f"{w}x{h}"
                return ""
            if actual_col == 10:  # Resolution
                return scene.get("_resolution", "")
            if actual_col == 11:  # File Size
                fs = scene.get("_filesize")
                return "" if fs is None else human_size(fs)
        
        # if role == QtCore.Qt.ItemDataRole.CheckStateRole and actual_col == 0:  # Select
            # return QtCore.Qt.CheckState.Checked if self._checked[r] else QtCore.Qt.CheckState.Unchecked
        # return None

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if orientation == QtCore.Qt.Orientation.Horizontal and role == QtCore.Qt.ItemDataRole.DisplayRole:
            if section < len(self._visible_columns):
                return self.ALL_COLUMNS[self._visible_columns[section]]
        return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.ItemFlag.ItemIsEnabled
        actual_col = self._visible_columns[index.column()]
        if actual_col == 0:  # Select column
            return QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        return QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False
        actual_col = self._visible_columns[index.column()]
        if actual_col == 0 and role == QtCore.Qt.ItemDataRole.CheckStateRole:  # Select column
            # Handle both integer and enum values for CheckState
            # PyQt6 may send integer 2 or CheckState.Checked enum
            is_checked = (value == QtCore.Qt.CheckState.Checked or value == 2)
            self._checked[index.row()] = is_checked
            self.dataChanged.emit(index, index, [QtCore.Qt.ItemDataRole.CheckStateRole])
            return True
        return False

    def setScenes(self, scenes: List[Dict[str, Any]]):
        self.beginResetModel()
        self._scenes = scenes or []
        self._checked = [False] * len(self._scenes)
        self.endResetModel()

    def get_selected_scenes(self) -> List[Dict[str, Any]]:
        return [s for s, c in zip(self._scenes, self._checked) if c]

    def select_all(self, val: bool):
        if not self._checked:
            return
        
        self.beginResetModel()
        for i in range(len(self._checked)):
            self._checked[i] = val
        self.endResetModel()

    def sort(self, column: int, order=QtCore.Qt.SortOrder.AscendingOrder):
        """Sort table by given column"""
        if column < 0 or column >= len(self._visible_columns):
            return
        
        actual_col = self._visible_columns[column]
        
        # Can't sort by Select checkbox column
        if actual_col == 0:
            return
        
        self.layoutAboutToBeChanged.emit()
        
        # Create a list of (scene, checked_state, original_index) tuples
        combined = list(zip(self._scenes, self._checked, range(len(self._scenes))))
        
        # Define sort key function
        def sort_key(item):
            scene = item[0]
            
            if actual_col == 1:  # ID
                try:
                    return int(scene.get("id", "0"))
                except:
                    return 0
            elif actual_col == 2:  # Title
                return (scene.get("title") or "").lower()
            elif actual_col == 3:  # Studio
                studio = scene.get("studio")
                return (studio.get("name", "") if studio else "").lower()
            elif actual_col == 4:  # Performers
                performers = scene.get("performers", []) or []
                names = [p.get("name") for p in performers if p.get("name")]
                return ", ".join(sorted(names)).lower() if names else ""
            elif actual_col == 5:  # Tags
                tags = scene.get("tags", []) or []
                names = [t.get("name") for t in tags if t.get("name")]
                return ", ".join(sorted(names)).lower() if names else ""
            elif actual_col == 6:  # Date
                # Handle None dates - put them at the end by using empty string
                date_val = scene.get("date")
                return date_val if date_val else ""
            elif actual_col == 7:  # Path
                return (scene.get("_path") or "").lower()
            elif actual_col == 8:  # Duration
                return scene.get("_duration") or 0
            elif actual_col == 9:  # Dimensions
                w = scene.get("_width") or 0
                h = scene.get("_height") or 0
                return w * h  # Sort by pixel count
            elif actual_col == 10:  # Resolution
                # Sort by resolution value (extract number)
                res = scene.get("_resolution", "")
                if res:
                    try:
                        return int(res.replace("p", "").replace("K", "000"))
                    except:
                        return 0
                return 0
            elif actual_col == 11:  # File Size
                return scene.get("_filesize") or 0
            else:
                return ""
        
        # Sort the combined list
        reverse = (order == QtCore.Qt.SortOrder.DescendingOrder)
        combined.sort(key=sort_key, reverse=reverse)
        
        # Unpack back into separate lists
        self._scenes = [item[0] for item in combined]
        self._checked = [item[1] for item in combined]
        
        # Store sort state
        self._sort_column = column
        self._sort_order = order
        
        self.layoutChanged.emit()

    def select_by_ids(self, id_set: set):
        if not self._checked:
            return
        for i, s in enumerate(self._scenes):
            self._checked[i] = s.get("id") in id_set
        # Get the visible column index for Select column (should be 0)
        select_col_index = self.get_visible_column_index(0)
        if select_col_index is not None:
            top_left = self.index(0, select_col_index)
            bottom_right = self.index(len(self._checked) - 1, select_col_index)
            self.dataChanged.emit(top_left, bottom_right, [QtCore.Qt.ItemDataRole.CheckStateRole])