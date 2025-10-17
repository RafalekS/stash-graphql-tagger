

# Stash GraphQL Tagger - Development Progress

## Project Overview
Python GUI application for managing Stash media library through GraphQL API.

**Main File:** `C:\Scripts\python\stashapp\stashapp_graphgl.py` (~2350 lines)
**Config:** `C:\Scripts\python\stashapp\config\stashapp_config.ini`
**Last Updated:** 2025-10-17 (Phase 1.8 completed - Scene renaming implemented)

---

## Current Status

### Project Structure
```
C:\Scripts\python\stashapp\
├── stashapp_graphgl.py (main GUI - MainWindow class)
├── config/stashapp_config.ini
├── ui/graphql.ico
├── utils/ (helpers.py)
├── models/ (graphql_client.py, scene_table_model.py)
├── workers/ (8 worker files for async operations)
└── help/ (progress.md, stashapp_graphql_schema.graphql)
```

### ✅ Completed Phases
- **Phase 0.1.3**: UI refinements with customizable section ordering, colors, fonts
- **Phase 0.2**: Fixed checkbox toggle bug and path/filename filter bug
- **Phase 0.3**: UI reorganization - combined sections, Tag Management moved to sidebar, descriptive config names, hide feature
- **Phase 0.4**: 3-column layout - efficient space utilization with configurable column assignments
- **Phase 0.5**: Tab-based UI with comprehensive Settings tab - visual controls for all config options
- **Phase 0.6**: Section background colors and fonts - customizable section colors with immediate preview updates
- **Phase 1.7**: Resolution/dimensions filtering - search by resolution (720p, 1080p, 4K, etc.)
- **Phase 1.8**: Scene renaming (bulk title updates via GraphQL API)

### What Works
- Search: title, performer (AND/OR), studio, date range, duration, file size, path/filename, resolution
- Bulk operations: tag/performer/studio assignment, scene renaming, CSV export/import
- UI: Tab-based interface with Search and Settings tabs, 3-column resizable layout, adjustable results table height, 12 customizable columns
- Settings: all persist to config.ini (window size, columns, filters, column assignments)
- Global dry-run mode
- Settings Tab: Connection settings (URL, API key), visual section reordering (up/down buttons), column assignment dropdowns, section visibility toggles, general settings (per page, dry run, auto-create tag), section color customization with live preview, button color customization
- Section management: reorderable with drag-free up/down buttons, hideable sections via checkboxes, column assignments via dropdowns, customizable background and font colors
- Combined Title/Filename search section
- Tag Management in right sidebar
- Compact Performer, Duration, FileSize, Date, and Resolution sections
- Clean right sidebar with only Tag Management, Progress Log, Bulk Operations, and Search button
- Section colors: Background colors, font colors, and button colors all customizable with immediate updates

---

## ✅ PHASE 0.3: UI Reorganization - COMPLETED

**File to modify:** `C:\Scripts\python\stashapp\stashapp_graphgl.py`

### ✅ Task 1: Combine Title + Path Sections - COMPLETED
**Implementation:**
- Deleted `_create_scene_title_section()` and `_create_path_filter_section()`
- Created new `_create_title_filename_section()` combining both
- Updated section ID mapping: reduced from 7 to 6 sections
- Updated all section references and color mappings

---

### ✅ Task 2: Move Tag Management to Right Sidebar - COMPLETED
**Implementation:**
- Moved Tag Management from left panel to top of right sidebar
- Updated layout creation in `__init__()` method
- Right sidebar now shows: Tag Management → Progress & Status Log → Settings → Bulk Operations → Search

---

### ✅ Task 3: Use Descriptive Config Names - COMPLETED
**Implementation:**
- Added section name mappings: TitleFilename, Performer, Studio, Duration, FileSize, Date
- Updated `_load_section_order()` to parse descriptive names (with backwards compatibility for numeric format)
- Updated `save_config()` to write descriptive names
- Updated all config documentation to reflect new format
- Config now uses: `order = TitleFilename, Performer, Studio, Duration, FileSize, Date`

---

### ✅ Task 4: Add Section Hide Feature - COMPLETED
**Implementation:**
- Added `hidden_sections` list to track which sections to hide
- Updated `_load_section_order()` to load hide setting from config
- Updated `_create_left_panel_sections()` to skip rendering hidden sections
- Updated `save_config()` to persist hide setting
- Added comprehensive documentation for hide feature in config file
- Example usage: `hide = Duration, FileSize` (hides Duration and FileSize filters)

---

## Testing Checklist (For Phase 0.3)

- [x] Combined Title/Filename section works correctly
- [x] Tag Management appears at top of right sidebar
- [x] Config uses descriptive names (TitleFilename, Performer, etc.)
- [x] Section ordering still works with new names
- [x] Hide feature works (test hiding 1-2 sections)
- [x] All existing search/filter functionality unchanged
- [x] Settings persist correctly after restart
- [x] Backwards compatibility with old numeric config format works

**Status:** All features tested and working successfully!

---

## ✅ PHASE 0.5: Tab-Based UI with Settings Tab - COMPLETED

**File modified:** `C:\Scripts\python\stashapp\stashapp_graphgl.py`

### ✅ Task 1: Create Tab Widget Structure - COMPLETED
**Implementation:**
- Replaced main window layout with `QTabWidget` as central widget
- Tab 1: "Search" - Contains all search filters, results table, and right sidebar
- Tab 2: "Settings" - Contains all configuration options
- Search tab maintains existing 3-column layout with resizable splitters

### ✅ Task 2: Comprehensive Settings Tab - COMPLETED
**Implementation:**
- **Connection Settings:** Editable GraphQL URL and API key fields with Apply button
- **General Settings:** Scenes per page, dry run mode, auto-create tag (synced with Search tab)
- **Section Display Order:** Visual list with up/down arrow buttons for reordering, changes apply immediately
- **Section Column Assignment:** Dropdown for each section to assign to Column 1 or Column 2, instant updates
- **Section Visibility:** Reused checkboxes in compact 2-column grid for show/hide functionality
- Settings content uses 80% width (centered) for better appearance and readability
- Fully scrollable for future additions

### ✅ Task 3: Clean Right Sidebar - COMPLETED
**Implementation:**
- Removed Settings group from right sidebar (now in Settings tab)
- Removed Section Visibility group from right sidebar (now in Settings tab)
- Right sidebar now only contains:
  - Tag Management (frequently used during search workflow)
  - Progress & Status Log (need to monitor during operations)
  - Bulk Operations (Export/Import CSV)
  - Search button
- Much cleaner and more focused user experience

**Benefits:**
- No more manual config file editing for common settings
- Visual section reordering with immediate feedback
- Clean separation between search workflow and configuration
- Settings are centralized and easy to find
- More space for filter sections in Search tab

---

## Future Phases (Quick Reference)

**Phase 1.9:** File operations on disk (rename/move files - requires direct filesystem access, not GraphQL)
**Phase 2.x:** More bulk operations (tag removal, ratings, organized/o-counter)
**Phase 3.x:** Advanced tag management (hierarchy, merging)
**Phase 4.x:** Pagination, thumbnails, dark mode

---

## Technical Notes

**Dependencies:** Python 3.8+, PyQt6, requests

**Key Methods in stashapp_graphgl.py:**
- `load_config()` / `save_config()`: Config persistence
- `_create_left_panel_sections()`: Orchestrates left panel section creation
- `_create_right_sidebar()`: Builds right sidebar
- `_load_section_order()`: Loads section order from config
- Individual section methods: `_create_[name]_section()` return QGroupBox widgets

**Config Location:** `C:\Scripts\python\stashapp\config\stashapp_config.ini`

**GraphQL patterns:** INCLUDES (fuzzy), INCLUDES_ALL (AND), BETWEEN (ranges), ISO dates (YYYY-MM-DD)

---

## ✅ PHASE 1.8: Scene Renaming - COMPLETED

**Files created:**
- `workers/rename_scene_worker.py` - Async worker for bulk scene title updates

**Files modified:**
- `stashapp_graphgl.py` - Added rename UI, handlers, worker integration
- `workers/__init__.py` - Exported RenameSceneWorker

**Implementation:**
- Bulk rename UI in right sidebar Bulk Operations section
- Text input field for new title with placeholder text
- Rename button with confirmation dialog
- Async worker using sceneUpdate GraphQL mutation
- Dry-run mode support
- Progress tracking and status logging
- Auto-refresh results after successful rename
- Summary dialog showing renamed/skipped/failed counts

**Features:**
- Rename multiple selected scenes to same title
- Handles deleted scenes gracefully (FOREIGN KEY errors)
- Integrates with existing dry-run mode
- Updates displayed results automatically after rename

---

## For Claude Code - Session Resume Information

**CURRENT STATUS: Phase 1.8 Complete - Ready for Phase 2.x**

### Last Session Summary (2025-10-17)
- Completed Phase 1.8: Bulk scene renaming via GraphQL API
- Fixed button color errors (removed non-existent button references)
- Fixed connection settings log error (changed log_message to log.append)
- Implemented immediate color preview updates for sections
- Created `workers/rename_scene_worker.py` for async rename operations
- Added rename UI to Bulk Operations section in right sidebar

### Working Features (Tested & Verified)
- Scene title bulk renaming with confirmation dialog
- Section background colors with live preview
- Button color customization
- Dry-run mode for all bulk operations
- Auto-refresh after successful rename operations
- Error handling for deleted scenes (FOREIGN KEY)

### Known Issues & Limitations
- **Phase 1.9 skipped:** File renaming on disk not available via GraphQL API (would require direct filesystem operations)
- No GraphQL mutation exists for physical file operations

### File Structure Summary
```
stashapp_graphgl.py          # Main GUI (~2350 lines)
├── Tab 1: Search
│   ├── Column 1: TitleFilename, Performer sections
│   ├── Column 2: Studio, Duration, FileSize, Date, Resolution sections
│   └── Column 3 (Right Sidebar):
│       ├── Tag Management
│       ├── Progress & Status Log
│       ├── Bulk Operations (TAG, RENAME, CSV)
│       └── Search button
└── Tab 2: Settings
    ├── Connection settings (URL, API key)
    ├── General settings (per_page, dry_run, auto_create_tag)
    ├── Section order/visibility/columns
    └── Color customization (sections, fonts, buttons)

workers/
├── rename_scene_worker.py   # NEW: Scene title renaming
├── apply_tag_worker.py
├── assign_performers_worker.py
├── assign_studio_worker.py
└── find_scenes_worker.py
```

### Next Steps - Phase 2.x: Additional Bulk Operations

**Priority 1 - Tag Operations:**
- Add tag removal from selected scenes
- Implement tag replacement (remove old, add new)
- Bulk tag merging functionality

**Priority 2 - Scene Metadata:**
- Bulk rating updates (rating100 field)
- Organized flag toggle (mark scenes as organized)
- O-counter updates (view count management)
- Date field bulk updates

**Priority 3 - Advanced Features:**
- Bulk performer removal
- Bulk studio removal
- Scene details/description bulk updates
- Code field bulk updates

**Implementation Pattern:**
1. Create new worker in `workers/` directory (follow existing patterns)
2. Add UI elements to appropriate section (likely Bulk Operations or Tag Management)
3. Import worker in `stashapp_graphql.py`
4. Add worker to `workers/__init__.py`
5. Create handler method (e.g., `on_remove_tag()`)
6. Connect button to handler
7. Add button to `_apply_button_colors()` list if needed
8. Test with dry-run mode first

**GraphQL Mutations Available:**
- `sceneUpdate(input: SceneUpdateInput!)` - Single scene updates
- `bulkSceneUpdate(input: BulkSceneUpdateInput!)` - Bulk operations
- Fields: title, code, details, date, rating100, organized, studio_id, performer_ids, tag_ids

**Key Development Constraints:**
- DO NOT use emojis in code
- DO NOT start processes - ask user to test
- Modify files directly (not artifacts)
- Keep methods under 100 lines where possible
- Test incrementally after each change
- Use existing worker patterns for consistency
- Follow Qt threading model (QRunnable + signals)

### Code Patterns to Follow

**Worker Pattern:**
```python
class NewOperationWorker(QtCore.QRunnable):
    def __init__(self, client, scenes, param, dry_run=False):
        super().__init__()
        self.client = client
        self.scenes = scenes
        self.param = param
        self.dry_run = dry_run
        self.signals = WorkerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        # Iterate scenes, call GraphQL, emit signals
```

**Handler Pattern:**
```python
def on_new_operation(self):
    selected = self.table_model.get_selected_scenes()
    if not selected:
        QtWidgets.QMessageBox.warning(self, "No selection", "...")
        return

    # Get user input, confirm
    dry_run = bool(self.dryrun_checkbox.isChecked())
    worker = NewOperationWorker(self.client, selected, param, dry_run)
    worker.signals.result.connect(self._on_operation_summary)
    worker.signals.error.connect(lambda e: self._log("Error: " + e))
    worker.signals.progress.connect(self.progress.setValue)
    worker.signals.status.connect(self._log)
    self.pool.start(worker)
```

### Testing Checklist for New Features
- [ ] Dry-run mode shows correct preview
- [ ] Actual operation updates scenes correctly
- [ ] Progress bar updates during operation
- [ ] Status log shows detailed messages
- [ ] Summary dialog displays correct counts
- [ ] Handles deleted scenes gracefully
- [ ] Auto-refresh works if needed
- [ ] Button styling applied correctly

**END OF PROGRESS DOCUMENT**
