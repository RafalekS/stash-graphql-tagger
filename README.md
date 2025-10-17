# Stash GraphQL Tagger

A powerful PyQt6 desktop application for managing your Stash media library through the GraphQL API. Search, filter, tag, and perform bulk operations on your scenes with an intuitive GUI.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Features

### Search & Filter
- **Title/Filename Search**: Search by scene title or file path
- **Performer Search**: Filter by performers (AND/OR logic)
- **Studio Filter**: Search by studio
- **Date Range**: Filter scenes by date
- **Duration Filter**: Filter by video length
- **File Size Filter**: Filter by file size
- **Resolution Filter**: Filter by video resolution (720p, 1080p, 4K, etc.)

### Bulk Operations
- **Tag Management**: Add tags to multiple scenes at once
- **Scene Renaming**: Rename multiple scenes with one click
- **Performer Assignment**: Assign performers to selected scenes
- **Studio Assignment**: Assign studio to selected scenes
- **CSV Export/Import**: Export scene data or import selections

### Customization
- **Tab-Based Interface**: Separate Search and Settings tabs
- **3-Column Layout**: Resizable columns with configurable section placement
- **Color Customization**: Customize section backgrounds, fonts, and button colors with live preview
- **Section Management**: Reorder, hide/show, and assign sections to columns
- **12 Customizable Columns**: Show/hide table columns as needed
- **Dry-Run Mode**: Preview changes before applying them

### Advanced Features
- **Async Operations**: All API calls run in background threads (no UI blocking)
- **Progress Tracking**: Real-time progress bars and status logging
- **Error Handling**: Graceful handling of deleted scenes and API errors
- **Auto-Refresh**: Automatically refresh results after successful operations
- **Persistent Settings**: All preferences saved to config file

## Installation

### Requirements
- Python 3.8 or higher
- PyQt6
- requests

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/stash-graphql-tagger.git
cd stash-graphql-tagger
```

2. Install dependencies:
```bash
pip install PyQt6 requests
```

3. Configure connection (first run):
   - Launch the application
   - Go to Settings tab
   - Enter your Stash GraphQL endpoint URL (e.g., `http://localhost:9999/graphql`)
   - (Optional) Enter API key if required
   - Click Apply

## Usage

### Running the Application

```bash
python stashapp_graphgl.py
```

### Basic Workflow

1. **Configure Connection**: Go to Settings tab, enter your Stash URL
2. **Search Scenes**: Use search filters in left/middle columns
3. **Select Scenes**: Check the boxes next to scenes you want to modify
4. **Perform Operations**: Use Tag Management or Bulk Operations sections
5. **Enable Dry-Run**: Test operations safely before applying changes

### Search Tips
- Use AND logic for performers when you want scenes with ALL selected performers
- Use OR logic to find scenes with ANY of the selected performers
- Duration filter supports `>`, `<`, `=` operators (e.g., `>30` for videos over 30 minutes)
- File size filter supports `>`, `<`, `=` operators (e.g., `>1GB`)

### Bulk Renaming
1. Search and select scenes
2. In Bulk Operations section, enter new title
3. Click "Rename Selected Scenes"
4. Confirm the operation
5. Results automatically refresh after rename

## Configuration

Settings are stored in `config/stashapp_config.ini`:

- **Connection**: GraphQL URL and API key
- **General**: Scenes per page, dry-run mode, auto-create tags
- **Window**: Size, position, splitter positions
- **Sections**: Order, visibility, column assignments
- **Columns**: Visible columns and widths
- **Colors**: Section backgrounds, fonts, button colors
- **Fonts**: Custom fonts for UI elements

## Project Structure

```
stashapp_graphgl.py          # Main GUI application
config/
  └── stashapp_config.ini    # Configuration file
models/
  ├── graphql_client.py      # GraphQL API client
  └── scene_table_model.py   # Qt table model
workers/
  ├── apply_tag_worker.py
  ├── assign_performers_worker.py
  ├── assign_studio_worker.py
  ├── find_scenes_worker.py
  ├── rename_scene_worker.py
  └── fetch_*_worker.py      # Various fetch workers
utils/
  └── helpers.py             # Utility functions
ui/
  └── graphql.ico            # Application icon
help/
  ├── progress.md            # Development progress
  └── stashapp_graphql_schema.graphql
```

## Development

### Architecture
- **MainWindow**: PyQt6 GUI with tab-based interface
- **Workers**: Qt QRunnable classes for async operations
- **Models**: GraphQL client and table model
- **Signals/Slots**: Thread-safe communication between workers and GUI

### Adding New Features
See `help/progress.md` for detailed development roadmap and code patterns.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Roadmap

### Completed
- ✅ Phase 0.1-0.6: UI foundation and customization
- ✅ Phase 1.7: Resolution filtering
- ✅ Phase 1.8: Scene renaming

### Planned
- Phase 2.x: Additional bulk operations (tag removal, ratings, organized flag)
- Phase 3.x: Advanced tag management (hierarchy, merging)
- Phase 4.x: Pagination, thumbnails, dark mode

See `help/progress.md` for detailed progress tracking.

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built for [Stash](https://github.com/stashapp/stash) - an organizer for your media collection
- Uses PyQt6 for the GUI framework
- GraphQL API integration for all data operations

## Support

For issues, questions, or feature requests, please open an issue on GitHub.
