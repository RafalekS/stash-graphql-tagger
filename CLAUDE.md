# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Stash GraphQL Tagger** - A PyQt6 desktop application for managing a Stash media library through its GraphQL API. The application provides search, filtering, tagging, and bulk operations for adult media content.

**Main entry point:** `stashapp_graphgl.py` (~1390 lines)
**Config file:** `config/stashapp_config.ini`

## Architecture

### Core Structure

The application follows a modular architecture with clear separation of concerns:

- **Main GUI (`stashapp_graphgl.py`)**: Contains the `MainWindow` class that orchestrates all UI components and business logic
- **Models (`models/`)**: Data handling and API communication
  - `graphql_client.py`: GraphQL API client with request handling
  - `scene_table_model.py`: Qt table model for displaying scene data with 12 customizable columns
- **Workers (`workers/`)**: Qt QRunnable classes for async operations to prevent UI blocking
  - `base_signals.py`: Shared signal definitions for worker-to-main-thread communication
  - `fetch_*_worker.py`: API query workers (tags, performers, studios)
  - `apply_tag_worker.py`, `assign_performers_worker.py`, `assign_studio_worker.py`: Mutation workers
  - `find_scenes_worker.py`: Scene search worker with complex filter support
- **Utils (`utils/`)**: Helper functions for formatting (file sizes, durations) and parsing user input

### Threading Model

All GraphQL operations run on Qt's thread pool via `QRunnable` workers. Workers communicate via PyQt signals:
- `finished`: Operation complete
- `error`: Error occurred (str message)
- `progress`: Progress update (0-100 int)
- `result`: Operation result (object)
- `status`: Status message for log (str)

Main thread updates UI in response to these signals.

### Configuration System

The app uses `configparser` with `config/stashapp_config.ini`:
- **[Connection]**: GraphQL endpoint URL and optional API key
- **[Settings]**: per_page (1-1000), dry_run mode, auto_create_tag
- **[Window]**: geometry (x,y,width,height), sidebar_width
- **[Columns]**: visible column indices (0-11), column widths
- **[Sections]**: order of left panel sections (1-7), hide list (future feature)
- **[Colors]**: section backgrounds, per-section colors, button colors
- **[Fonts]**: customizable fonts for buttons, section titles, results table, log

Configuration is loaded at startup in `load_config()` and saved on window close via `save_config()`.

### Section System

Left panel uses an orderable section system:
1. Scene Title Search
2. Performer Search (AND/OR logic)
3. Studio Search
4. Path/Filename Filter
5. Duration Filter
6. File Size Filter
7. Date Range Filter

Each section is created by a dedicated method (`_create_*_section()`) returning a `QGroupBox`. Section order is controlled by the config file and sections are rendered in `_create_left_panel_sections()`.

## Development Commands

### Running the Application

```bash
python stashapp_graphgl.py
```

**Dependencies:**
```bash
pip install PyQt6 requests
```

No formal requirements.txt exists; dependencies are listed in the main file header.

### Testing

No automated tests exist. Manual testing workflow:
1. Run the application
2. Test search with various filter combinations
3. Verify dry-run mode shows correct changes
4. Test bulk operations (tag/performer/studio assignment)
5. Verify CSV export/import functionality
6. Check that settings persist after restart

## GraphQL API Patterns

The Stash GraphQL API uses specific patterns:

**Search modifiers:**
- `INCLUDES`: Fuzzy/substring match (OR logic for arrays)
- `INCLUDES_ALL`: AND logic for array values
- `EQUALS`: Exact match
- `BETWEEN`: Range queries (dates, durations)
- `GREATER_THAN`, `LESS_THAN`: Comparison operators

**Date format:** ISO 8601 (YYYY-MM-DD)

**Duration:** Stored as float (seconds)

**File metadata:** Accessed via `scene.files[]` array (scenes can have multiple files)

## Key Implementation Details

### Scene Search (find_scenes_worker.py)

The worker builds a complex `scene_filter` object with multiple criteria:
- Title search uses `INCLUDES` modifier
- Performer filtering supports AND (`INCLUDES_ALL`) or OR (`INCLUDES`) logic
- Duration and file size filtering uses operator-based modifiers
- Path filtering is SERVER-SIDE via GraphQL (not client-side)
- Results include file metadata (size, duration, dimensions, path, codec)

Post-processing extracts max file size/duration/resolution from multi-file scenes.

### Table Model (scene_table_model.py)

`SceneTableModel` extends `QAbstractTableModel`:
- 12 total columns: Select, ID, Title, Studio, Performers, Tags, Date, Path, Duration, Dimensions, Resolution, File Size
- Column visibility controlled via indices (stored in config)
- Select column uses Qt's checkable items system
- Sorting implemented for all columns with appropriate key functions
- `_checked` list maintains selection state parallel to `_scenes` data

### Bulk Operations

All bulk operations follow the same pattern:
1. User selects scenes via checkboxes
2. User specifies tag/performer/studio
3. Worker iterates through selected scenes
4. For each scene:
   - Check if already has the tag/performer/studio (skip if yes)
   - Build mutation with merged IDs (preserve existing + add new)
   - Execute mutation or log dry-run message
   - Handle FOREIGN KEY errors (deleted scenes) gracefully
5. Emit summary with counts (updated, already_tagged, skipped_deleted, failed)

### Error Handling

- GraphQL errors from Stash API are captured and displayed
- FOREIGN KEY errors indicate deleted scenes and are tracked separately
- Workers catch all exceptions and emit via error signal
- Traceback displayed in status log for debugging

## Current Development Status

**Phase 0.3** (ready to implement per progress.md):
1. Combine Title + Path sections into single "Title/Filename Search"
2. Move Tag Management to right sidebar
3. Use descriptive config names (Scene, Performer, Studio, etc.) instead of numbers
4. Add section hide feature

**Known issues:**
- Section background colors not rendering (parked for later)

**Future phases:** Collapsible sections, resolution/codec filtering, scene renaming/moving, advanced tag management, pagination, thumbnails, dark mode

## Coding Guidelines

1. **No emojis in code** - Keep code professional
2. **Methods under 100 lines** - Break up large methods
3. **Use filesystem tools** - Don't use bash for file operations
4. **Test incrementally** - Test after each significant change
5. **Update progress.md** - Document completion of phases
6. **Preserve existing functionality** - Don't break working features
7. **Follow Qt patterns** - Use signals/slots, respect thread safety
