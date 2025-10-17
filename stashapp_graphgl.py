#!/usr/bin/env python3
# stash_tagger_gui.py
"""
Stash GraphQL tagger GUI — updated.

New features:
 - If tag not found, optionally create it (uses tagCreate mutation).
 - Export selected scenes to CSV, import CSV (scene id) to pre-select.
 - Scenes table shows tag NAMES and IDs.
 - Search scenes by file size: client-side min/max filter (bytes).
 - Scenes query now requests tags { id name } and files { size }.
 - Dry-run still available.

Dependencies:
    pip install PyQt6 requests

Run:
    python3 stash_tagger_gui.py
"""
import sys
import csv
import json
import os
import traceback
from typing import Any, Dict, List, Optional
from configparser import ConfigParser

import requests
from PyQt6 import QtCore, QtWidgets, QtGui

from utils import human_size, human_duration, parse_duration_input, parse_filesize_input
from models import GraphQLClient, SceneTableModel
from workers import (
    WorkerSignals,
    FetchTagWorker,
    FetchPerformersWorker,
    FetchStudiosWorker,
    SearchScenesWorker,
    ApplyTagWorker,
    AssignPerformersWorker,
    AssignStudioWorker,
    RenameSceneWorker
)
# ----------------------------
# GUI table model
# ----------------------------


# ----------------------------
# GUI
# ----------------------------
class MainWindow(QtWidgets.QMainWindow):
    # Config file path - stored in /config/ subdirectory
    CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "stashapp_config.ini")
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stash Tagger GUI — mildly resentful")
        self.setMinimumSize(1000, 700)
        
        # Set application icon
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "graphql.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))

        # Create tab widget as central widget
        self.tab_widget = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # ========== TAB 1: SEARCH ==========
        search_tab = QtWidgets.QWidget()
        self.tab_widget.addTab(search_tab, "Search")

        search_tab_layout = QtWidgets.QVBoxLayout(search_tab)
        search_tab_layout.setContentsMargins(0, 0, 0, 0)

        # Create main vertical splitter for resizable top/bottom sections
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        search_tab_layout.addWidget(main_splitter)
        
        # ========== TOP SECTION (3-column horizontal split) ==========
        top_widget = QtWidgets.QWidget()
        top_layout = QtWidgets.QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        main_splitter.addWidget(top_widget)

        self.top_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        top_layout.addWidget(self.top_splitter)

        # COLUMN 1 (Left sections)
        column1_panel = QtWidgets.QWidget()
        self.column1_layout = QtWidgets.QVBoxLayout(column1_panel)
        self.column1_layout.setContentsMargins(0, 0, 0, 0)
        self.top_splitter.addWidget(column1_panel)

        # COLUMN 2 (Middle sections)
        column2_panel = QtWidgets.QWidget()
        self.column2_layout = QtWidgets.QVBoxLayout(column2_panel)
        self.column2_layout.setContentsMargins(0, 0, 0, 0)
        self.top_splitter.addWidget(column2_panel)
        
        # Section ordering system
        self.left_sections = {}  # Will store {id: widget} pairs
        self.section_order = [1, 2, 3, 4, 5, 6, 7]  # Default order (7 sections now)
        self.hidden_sections = []  # List of section IDs to hide

        # Section name mapping for config
        self.section_id_to_name = {
            1: "TitleFilename",
            2: "Performer",
            3: "Studio",
            4: "Duration",
            5: "FileSize",
            6: "Date",
            7: "Resolution"
        }
        self.section_name_to_id = {v: k for k, v in self.section_id_to_name.items()}

        # Column assignments for 3-column layout (1, 2, or 3)
        # Default: Column 1 = TitleFilename, Performer; Column 2 = Studio, Duration, FileSize, Date, Resolution
        self.section_columns = {
            1: 1,  # TitleFilename -> Column 1
            2: 1,  # Performer -> Column 1
            3: 2,  # Studio -> Column 2
            4: 2,  # Duration -> Column 2
            5: 2,  # FileSize -> Column 2
            6: 2,  # Date -> Column 2
            7: 2   # Resolution -> Column 2
        }
        
        # Color settings (defaults) - MUST BE SET BEFORE CREATING SECTIONS
        # Pre-load color settings from config before creating UI
        self.section_backgrounds_enabled: bool = False
        self.section_colors = {
            1: "#E8F4F8",  # Title/Filename - Light blue
            2: "#F0E8F8",  # Performer - Light purple
            3: "#F8F0E8",  # Studio - Light orange
            4: "#F8E8E8",  # Duration - Light red
            5: "#F8F8E8",  # File Size - Light yellow
            6: "#E8E8F8",  # Date - Light lavender
            7: "#E8F8E8",  # Resolution - Light cyan
        }
        self.tag_management_color: str = "#FFE8E8"  # Light pink
        self.button_color: str = "#4A90E2"  # Blue
        self.button_text_color: str = "#FFFFFF"  # White

        # Section font colors (for text within sections)
        self.section_font_colors = {
            1: "#000000",  # Black
            2: "#000000",
            3: "#000000",
            4: "#000000",
            5: "#000000",
            6: "#000000",
            7: "#000000"
        }

        # Section font names
        self.section_font_names = {
            1: "Arial",
            2: "Arial",
            3: "Arial",
            4: "Arial",
            5: "Arial",
            6: "Arial",
            7: "Arial"
        }

        # Font settings (defaults) - MUST BE SET BEFORE CREATING SECTIONS
        self.button_font_name: str = "Arial"
        self.button_font_size: int = 9
        self.section_title_font_name: str = "Arial"
        self.section_title_font_size: int = 10
        self.results_font_name: str = "Consolas"
        self.results_font_size: int = 9
        self.log_font_name: str = "Courier New"
        self.log_font_size: int = 8

        # Pre-load color and font settings from config BEFORE creating sections
        self._preload_appearance_settings()
        
        # Load section order from config BEFORE creating sections
        self._load_section_order()

        # Create all sections and distribute them across columns
        self._create_and_distribute_sections()

        # COLUMN 3 (Right sidebar - Tag Management, Progress, Settings, etc.)
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.top_splitter.addWidget(right_panel)
        
        # ========== RIGHT SIDEBAR SECTIONS ==========

        # ========== 4. TAG MANAGEMENT (Right Sidebar - TOP) ==========
        tag_group = QtWidgets.QGroupBox("Tag Management")
        tag_layout = QtWidgets.QGridLayout(tag_group)
        right_layout.addWidget(tag_group)

        # Apply color if enabled
        if self.section_backgrounds_enabled:
            tag_group.setAutoFillBackground(True)
            palette = tag_group.palette()
            palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(self.tag_management_color))
            tag_group.setPalette(palette)

        tag_layout.addWidget(QtWidgets.QLabel("Tag name:"), 0, 0)
        self.tag_edit = QtWidgets.QLineEdit()
        self.tag_edit.setPlaceholderText("Enter tag name to assign")
        tag_layout.addWidget(self.tag_edit, 0, 1, 1, 3)

        self.auto_create_checkbox = QtWidgets.QCheckBox("Auto-create tag if it doesn't exist")
        self.auto_create_checkbox.setChecked(True)
        tag_layout.addWidget(self.auto_create_checkbox, 1, 0, 1, 2)

        # Assign Tag button
        self.apply_tag_btn = QtWidgets.QPushButton("Assign Tag to Selected")
        tag_layout.addWidget(self.apply_tag_btn, 1, 3)


        # ========== 5. PROGRESS & STATUS LOG (Right Sidebar) ==========
        progress_log_group = QtWidgets.QGroupBox("Progress & Status Log")
        progress_log_layout = QtWidgets.QVBoxLayout(progress_log_group)
        right_layout.addWidget(progress_log_group)
        
        progress_row_layout = QtWidgets.QHBoxLayout()
        progress_row_layout.addWidget(QtWidgets.QLabel("Progress:"))
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        progress_row_layout.addWidget(self.progress, 1)
        progress_log_layout.addLayout(progress_row_layout)
        
        progress_log_layout.addWidget(QtWidgets.QLabel("Status Log:"))
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(100)
        progress_log_layout.addWidget(self.log)
        
        
        
        
        # Create settings widgets (used in Settings tab, not displayed here)
        self.per_page_spin = QtWidgets.QSpinBox()
        self.per_page_spin.setRange(1, 9000)
        self.per_page_spin.setValue(100)

        self.dryrun_checkbox = QtWidgets.QCheckBox("Preview changes without applying")

        # Create section visibility checkboxes (used in Settings tab)
        self.section_visibility_checkboxes = {}
        section_ids = [1, 2, 3, 4, 5, 6, 7]  # Now 7 sections including Resolution
        for section_id in section_ids:
            section_name = self.section_id_to_name[section_id]
            checkbox = QtWidgets.QCheckBox(section_name)
            checkbox.setChecked(section_id not in self.hidden_sections)
            checkbox.stateChanged.connect(lambda state, sid=section_id: self._on_section_visibility_changed(sid, state))
            self.section_visibility_checkboxes[section_id] = checkbox

        # ========== 6. BULK OPERATIONS GROUP (Right Sidebar) ==========
        bulk_ops_group = QtWidgets.QGroupBox("Bulk Operations")
        bulk_ops_layout = QtWidgets.QVBoxLayout(bulk_ops_group)
        right_layout.addWidget(bulk_ops_group)

        # Rename section
        bulk_ops_layout.addWidget(QtWidgets.QLabel("Rename Selected:"))
        self.rename_input = QtWidgets.QLineEdit()
        self.rename_input.setPlaceholderText("New title for selected scenes")
        bulk_ops_layout.addWidget(self.rename_input)
        self.rename_btn = QtWidgets.QPushButton("Rename Selected Scenes")
        bulk_ops_layout.addWidget(self.rename_btn)

        # CSV operations
        bulk_ops_layout.addWidget(QtWidgets.QLabel("CSV Operations:"))
        self.export_csv_btn = QtWidgets.QPushButton("Export Selected to CSV")
        self.import_csv_btn = QtWidgets.QPushButton("Import CSV (select scenes)")
        bulk_ops_layout.addWidget(self.export_csv_btn)
        bulk_ops_layout.addWidget(self.import_csv_btn)


        # ========== 7. SEARCH SCENES SECTION (Right Sidebar - BOTTOM) ==========
        search_scenes_group = QtWidgets.QGroupBox("Search")
        search_scenes_layout = QtWidgets.QVBoxLayout(search_scenes_group)
        right_layout.addWidget(search_scenes_group)

        self.search_scenes_btn = QtWidgets.QPushButton("Search Scenes")
        # Match Export CSV button width and double the height
        self.search_scenes_btn.setMinimumWidth(self.export_csv_btn.sizeHint().width())
        self.search_scenes_btn.setMinimumHeight(self.export_csv_btn.sizeHint().height() * 2)
        search_scenes_layout.addWidget(self.search_scenes_btn)

        # Add stretch to right panel so sections stay at top
        right_layout.addStretch()

        # Set top splitter properties and initial sizes for 3-column layout
        self.top_splitter.setChildrenCollapsible(False)
        # Initial sizes: Column 1 (30%), Column 2 (30%), Column 3/Sidebar (40%)
        total_width = 1000  # Default initial width
        self.top_splitter.setSizes([int(total_width * 0.3), int(total_width * 0.3), int(total_width * 0.4)])
        
        
        # ========== BOTTOM SECTION: RESULTS TABLE (Full Width, Resizable) ==========
        results_widget = QtWidgets.QWidget()
        results_layout = QtWidgets.QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)
        main_splitter.addWidget(results_widget)
        
        results_toolbar_layout = QtWidgets.QHBoxLayout()
        results_layout.addLayout(results_toolbar_layout)
        
        results_toolbar_layout.addWidget(QtWidgets.QLabel("Results:"))
        self.select_all_btn = QtWidgets.QPushButton("Select All")
        self.select_none_btn = QtWidgets.QPushButton("Select None")
        self.column_visibility_btn = QtWidgets.QPushButton("Show/Hide Columns")
        results_toolbar_layout.addWidget(self.select_all_btn)
        results_toolbar_layout.addWidget(self.select_none_btn)
        results_toolbar_layout.addWidget(self.column_visibility_btn)
        results_toolbar_layout.addStretch()

        # Table - flexible height, spans full width
        self.table_model = SceneTableModel([])
        self.table_view = QtWidgets.QTableView()
        self.table_view.setModel(self.table_model)
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.CurrentChanged | QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked)
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().setSectionsClickable(True)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        results_layout.addWidget(self.table_view)
        
        # Set main splitter properties
        main_splitter.setChildrenCollapsible(False)
        # Initial sizes: 40% top, 60% bottom
        main_splitter.setSizes([400, 600])

        # Threadpool
        self.pool = QtCore.QThreadPool.globalInstance()

        # Connections
        # self.get_tag_btn.clicked.connect(self.on_get_tag)
        self.search_scenes_btn.clicked.connect(self.on_search_scenes)
        self.apply_tag_btn.clicked.connect(self.on_apply_tag)
        self.select_all_btn.clicked.connect(self.on_select_all)
        self.select_none_btn.clicked.connect(self.on_select_none)
        self.export_csv_btn.clicked.connect(self.on_export_csv)
        self.import_csv_btn.clicked.connect(self.on_import_csv)
        self.rename_btn.clicked.connect(self.on_rename_scenes)
        self.search_performers_btn.clicked.connect(self.on_search_performers)
        self.clear_performers_btn.clicked.connect(self.on_clear_performers)
        self.search_studios_btn.clicked.connect(self.on_search_studios)
        self.clear_studio_btn.clicked.connect(self.on_clear_studio)
        self.column_visibility_btn.clicked.connect(self.on_column_visibility)
        self.assign_performers_btn.clicked.connect(self.on_assign_performers)
        self.assign_studio_btn.clicked.connect(self.on_assign_studio)

        # internal state
        self.client: Optional[GraphQLClient] = None
        self.last_tag_id: Optional[str] = None
        self.last_tag_name: Optional[str] = None
        self.last_scenes: List[Dict[str, Any]] = []
        self.selected_performers: Dict[str, str] = {}  # {id: name}
        self.selected_studio: Optional[Dict[str, str]] = None  # {id: str, name: str}
        
        # Connection settings (stored in config, not in UI)
        self.graphql_url: str = "http://192.168.0.166:9977/graphql"
        self.api_key: str = ""
        


        # Load saved configuration
        self.load_config()

        # Create Settings tab after config is loaded
        self._create_settings_tab()

    def _log(self, msg: str):
        self.log.append(msg)

    def _get_section_stylesheet(self, section_id):
        """Generate stylesheet for a section with background and font styling"""
        if not self.section_backgrounds_enabled:
            return ""

        bg_color = self.section_colors[section_id]
        font_color = self.section_font_colors[section_id]
        font_name = self.section_font_names[section_id]

        return f"""
            QGroupBox {{
                background-color: {bg_color};
                color: {font_color};
                font-family: {font_name};
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding: 15px 5px 5px 5px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
                color: {font_color};
                font-family: {font_name};
            }}
            QLabel {{
                color: {font_color};
                font-family: {font_name};
            }}
            QLineEdit, QComboBox, QSpinBox, QDateEdit {{
                color: {font_color};
                font-family: {font_name};
            }}
        """

    def _preload_appearance_settings(self):
        """Load color and font settings from config BEFORE creating UI elements"""
        if not os.path.exists(self.CONFIG_FILE):
            return

        try:
            config = ConfigParser()
            config.read(self.CONFIG_FILE)

            # Load color settings
            if config.has_section('Colors'):
                if config.has_option('Colors', 'section_backgrounds'):
                    self.section_backgrounds_enabled = config.getboolean('Colors', 'section_backgrounds')

                for i in range(1, 8):  # 7 sections
                    if config.has_option('Colors', f'section_{i}_color'):
                        self.section_colors[i] = config.get('Colors', f'section_{i}_color')
                    if config.has_option('Colors', f'section_{i}_font_color'):
                        self.section_font_colors[i] = config.get('Colors', f'section_{i}_font_color')
                    if config.has_option('Colors', f'section_{i}_font_name'):
                        self.section_font_names[i] = config.get('Colors', f'section_{i}_font_name')

                if config.has_option('Colors', 'tag_management_color'):
                    self.tag_management_color = config.get('Colors', 'tag_management_color')
                if config.has_option('Colors', 'button_color'):
                    self.button_color = config.get('Colors', 'button_color')
                if config.has_option('Colors', 'button_text_color'):
                    self.button_text_color = config.get('Colors', 'button_text_color')

            # Load font settings
            if config.has_section('Fonts'):
                if config.has_option('Fonts', 'button_font'):
                    self.button_font_name = config.get('Fonts', 'button_font')
                if config.has_option('Fonts', 'button_size'):
                    self.button_font_size = config.getint('Fonts', 'button_size')
                if config.has_option('Fonts', 'section_title_font'):
                    self.section_title_font_name = config.get('Fonts', 'section_title_font')
                if config.has_option('Fonts', 'section_title_size'):
                    self.section_title_font_size = config.getint('Fonts', 'section_title_size')
                if config.has_option('Fonts', 'results_font'):
                    self.results_font_name = config.get('Fonts', 'results_font')
                if config.has_option('Fonts', 'results_size'):
                    self.results_font_size = config.getint('Fonts', 'results_size')
                if config.has_option('Fonts', 'log_font'):
                    self.log_font_name = config.get('Fonts', 'log_font')
                if config.has_option('Fonts', 'log_size'):
                    self.log_font_size = config.getint('Fonts', 'log_size')

        except Exception as e:
            print(f"Error preloading appearance settings: {e}")

    def _load_section_order(self):
        """Load section order, hidden sections, and column assignments from config"""
        if not os.path.exists(self.CONFIG_FILE):
            return  # Use defaults

        try:
            config = ConfigParser()
            config.read(self.CONFIG_FILE)

            if config.has_section('Sections'):
                # Load section order
                if config.has_option('Sections', 'order'):
                    order_str = config.get('Sections', 'order').strip()
                    if order_str:
                        # Try to parse as descriptive names first
                        parts = [p.strip() for p in order_str.split(',')]
                        if all(p in self.section_name_to_id for p in parts):
                            # Descriptive names format
                            self.section_order = [self.section_name_to_id[p] for p in parts]
                            # Add missing sections (for backwards compatibility when new sections are added)
                            all_sections = {1, 2, 3, 4, 5, 6, 7}
                            missing = all_sections - set(self.section_order)
                            if missing:
                                self.section_order.extend(sorted(missing))
                        else:
                            # Try old numeric format for backwards compatibility
                            try:
                                self.section_order = [int(i) for i in parts]
                                # Add missing sections
                                all_sections = {1, 2, 3, 4, 5, 6, 7}
                                missing = all_sections - set(self.section_order)
                                if missing:
                                    self.section_order.extend(sorted(missing))
                            except ValueError:
                                self.section_order = [1, 2, 3, 4, 5, 6, 7]

                # Load hidden sections
                if config.has_option('Sections', 'hide'):
                    hide_str = config.get('Sections', 'hide').strip()
                    if hide_str:
                        parts = [p.strip() for p in hide_str.split(',')]
                        # Try to parse as descriptive names
                        if all(p in self.section_name_to_id for p in parts):
                            self.hidden_sections = [self.section_name_to_id[p] for p in parts]
                        else:
                            # Try numeric format for backwards compatibility
                            try:
                                self.hidden_sections = [int(i) for i in parts]
                            except ValueError:
                                self.hidden_sections = []

                # Load column assignments (format: "TitleFilename:1, Performer:1, Studio:2, ...")
                if config.has_option('Sections', 'columns'):
                    columns_str = config.get('Sections', 'columns').strip()
                    if columns_str:
                        parts = [p.strip() for p in columns_str.split(',')]
                        for part in parts:
                            if ':' in part:
                                section_name, column_str = part.split(':', 1)
                                section_name = section_name.strip()
                                column_str = column_str.strip()
                                if section_name in self.section_name_to_id:
                                    try:
                                        column = int(column_str)
                                        if column in [1, 2]:  # Only columns 1 and 2 for sections
                                            section_id = self.section_name_to_id[section_name]
                                            self.section_columns[section_id] = column
                                    except ValueError:
                                        pass
        except Exception:
            pass  # Use defaults

    # def _apply_fonts(self):
        # """Apply font settings to UI widgets"""
        # # Apply to results table
        # results_font = QtGui.QFont(self.results_font_name, self.results_font_size)
        # self.table_view.setFont(results_font)
        
        # # Apply to log
        # log_font = QtGui.QFont(self.log_font_name, self.log_font_size)
        # self.log.setFont(log_font)
        
        # # Apply to all buttons - collect all QPushButton widgets
        # button_font = QtGui.QFont(self.button_font_name, self.button_font_size)
        # for button in self.findChildren(QtWidgets.QPushButton):
            # button.setFont(button_font)
        
        # # Apply to all QGroupBox titles
        # section_font = QtGui.QFont(self.section_title_font_name, self.section_title_font_size)
        # section_font.setBold(True)
        # for groupbox in self.findChildren(QtWidgets.QGroupBox):
            # groupbox.setFont(section_font)
    def _apply_fonts(self):
        """Apply font settings to UI widgets"""
        # Apply to results table
        results_font = QtGui.QFont(self.results_font_name, self.results_font_size)
        self.table_view.setFont(results_font)
        
        # Apply to log
        log_font = QtGui.QFont(self.log_font_name, self.log_font_size)
        self.log.setFont(log_font)
        
        # Apply to all buttons - collect all QPushButton widgets
        button_font = QtGui.QFont(self.button_font_name, self.button_font_size)
        for button in self.findChildren(QtWidgets.QPushButton):
            button.setFont(button_font)
            # Also apply button colors if enabled
            if self.section_backgrounds_enabled:
                button.setStyleSheet(f"QPushButton {{ background-color: {self.button_color}; color: {self.button_text_color}; }}")
        
        # Apply ONLY to QGroupBox titles (not the entire groupbox)
        # We'll use a custom property to style just the title
        for groupbox in self.findChildren(QtWidgets.QGroupBox):
            # Create font for the title only
            title_font = QtGui.QFont(self.section_title_font_name, self.section_title_font_size)
            title_font.setBold(True)
            
            # Apply using stylesheet to target only the title
            groupbox.setStyleSheet(groupbox.styleSheet() + f"""
                QGroupBox::title {{
                    font-family: '{self.section_title_font_name}';
                    font-size: {self.section_title_font_size}pt;
                    font-weight: bold;
                }}
            """)




    def _create_and_distribute_sections(self):
        """Create all sections and distribute them across columns based on configuration"""
        # Create all sections
        self.left_sections[1] = self._create_title_filename_section()  # Combined title + path
        self.left_sections[2] = self._create_performer_section()
        self.left_sections[3] = self._create_studio_section()
        self.left_sections[4] = self._create_duration_filter_section()
        self.left_sections[5] = self._create_filesize_filter_section()
        self.left_sections[6] = self._create_date_filter_section()
        self.left_sections[7] = self._create_resolution_filter_section()

        # Distribute sections to columns based on section_columns mapping
        for section_id in self.section_order:
            if section_id in self.left_sections and section_id not in self.hidden_sections:
                section_widget = self.left_sections[section_id]
                column = self.section_columns.get(section_id, 1)  # Default to column 1

                if column == 1:
                    self.column1_layout.addWidget(section_widget)
                elif column == 2:
                    self.column2_layout.addWidget(section_widget)
                # Column 3 is reserved for right sidebar (Tag Management, Progress, etc.)
                
    def _create_title_filename_section(self):
        """Create combined Title/Filename Search section"""
        group = QtWidgets.QGroupBox("Title/Filename Search")
        layout = QtWidgets.QGridLayout(group)

        # Title search
        layout.addWidget(QtWidgets.QLabel("Title contains:"), 0, 0)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search by scene title")
        layout.addWidget(self.search_edit, 0, 1, 1, 3)

        # Path/Filename search
        layout.addWidget(QtWidgets.QLabel("Search in path:"), 1, 0)
        self.path_search_edit = QtWidgets.QLineEdit()
        self.path_search_edit.setPlaceholderText("Search in file paths (case-insensitive)")
        layout.addWidget(self.path_search_edit, 1, 1, 1, 3)

        self.enable_path_filter_checkbox = QtWidgets.QCheckBox("Enable path filter")
        self.enable_path_filter_checkbox.setChecked(False)
        layout.addWidget(self.enable_path_filter_checkbox, 2, 1)

        # Apply styling if enabled
        group.setStyleSheet(self._get_section_stylesheet(1))

        return group

    def _create_performer_section(self):
        """Create Performer Search section"""
        group = QtWidgets.QGroupBox("Performer Search")
        layout = QtWidgets.QGridLayout(group)

        # Search row
        layout.addWidget(QtWidgets.QLabel("Performer search:"), 0, 0)
        self.performer_search_edit = QtWidgets.QLineEdit()
        self.performer_search_edit.setPlaceholderText("Enter performer name for fuzzy search")
        layout.addWidget(self.performer_search_edit, 0, 1)

        self.search_performers_btn = QtWidgets.QPushButton("Search Performers")
        layout.addWidget(self.search_performers_btn, 0, 2)

        self.performer_logic_combo = QtWidgets.QComboBox()
        self.performer_logic_combo.addItems(["AND (all selected)", "OR (any selected)"])
        layout.addWidget(self.performer_logic_combo, 0, 3)

        # Selected performers list and buttons
        layout.addWidget(QtWidgets.QLabel("Selected performers:"), 1, 0)

        # Performer list - reduced to 3 rows
        self.performer_list = QtWidgets.QListWidget()
        self.performer_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)
        # Calculate height for exactly 3 rows (approximate: item height ~20px + margins)
        self.performer_list.setFixedHeight(70)
        layout.addWidget(self.performer_list, 1, 1, 2, 2)  # Span 2 rows, 2 columns

        # Buttons stacked vertically next to the list
        self.clear_performers_btn = QtWidgets.QPushButton("Clear Selection")
        layout.addWidget(self.clear_performers_btn, 1, 3)

        self.assign_performers_btn = QtWidgets.QPushButton("Assign Performers to Selected")
        layout.addWidget(self.assign_performers_btn, 2, 3)

        # Apply styling if enabled
        group.setStyleSheet(self._get_section_stylesheet(2))

        return group
    
    def _create_studio_section(self):
        """Create Studio Search section"""
        group = QtWidgets.QGroupBox("Studio Search")
        layout = QtWidgets.QGridLayout(group)
        
        layout.addWidget(QtWidgets.QLabel("Studio search:"), 0, 0)
        self.studio_search_edit = QtWidgets.QLineEdit()
        self.studio_search_edit.setPlaceholderText("Enter studio name for fuzzy search")
        layout.addWidget(self.studio_search_edit, 0, 1)
        
        self.search_studios_btn = QtWidgets.QPushButton("Search Studios")
        layout.addWidget(self.search_studios_btn, 0, 2)
        
        self.studio_label = QtWidgets.QLabel("No studio selected")
        layout.addWidget(self.studio_label, 0, 3)
        
        self.clear_studio_btn = QtWidgets.QPushButton("Clear Studio")
        layout.addWidget(self.clear_studio_btn, 1, 2)
        
        self.assign_studio_btn = QtWidgets.QPushButton("Assign Studio")
        layout.addWidget(self.assign_studio_btn, 1, 3)
        
# Apply color if enabled
        if self.section_backgrounds_enabled:
            group.setStyleSheet(f"""
                QGroupBox {{
                    background-color: {self.section_colors[3]};
                    border: 2px solid #cccccc;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding: 15px 5px 5px 5px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    left: 10px;
                    padding: 0 5px;
                }}
            """)
        
        return group
    
    def _create_duration_filter_section(self):
        """Create Duration Filter section"""
        group = QtWidgets.QGroupBox("Duration Filter")
        layout = QtWidgets.QGridLayout(group)

        # Compact single-row layout
        self.duration_operator_combo = QtWidgets.QComboBox()
        self.duration_operator_combo.addItems([
            "= (equals)",
            "!= (not equals)",
            "> (greater than)",
            ">= (greater than or equal)",
            "< (less than)",
            "<= (less than or equal)",
            "between"
        ])
        self.duration_operator_combo.setCurrentIndex(6)
        self.duration_operator_combo.setMaximumWidth(150)
        layout.addWidget(self.duration_operator_combo, 0, 0)

        self.duration_value1_edit = QtWidgets.QLineEdit()
        self.duration_value1_edit.setPlaceholderText("e.g. 10:00")
        layout.addWidget(self.duration_value1_edit, 0, 1)

        self.duration_value2_edit = QtWidgets.QLineEdit()
        self.duration_value2_edit.setPlaceholderText("e.g. 60:00")
        layout.addWidget(self.duration_value2_edit, 0, 2)

        self.enable_duration_filter_checkbox = QtWidgets.QCheckBox("Enable")
        self.enable_duration_filter_checkbox.setChecked(False)
        layout.addWidget(self.enable_duration_filter_checkbox, 0, 3)
        
        self.duration_operator_combo.currentIndexChanged.connect(self._on_duration_operator_changed)
        
        # Apply styling if enabled
        group.setStyleSheet(self._get_section_stylesheet(4))

        return group

    def _create_filesize_filter_section(self):
        """Create File Size Filter section"""
        group = QtWidgets.QGroupBox("File Size Filter")
        layout = QtWidgets.QGridLayout(group)

        # Compact single-row layout
        self.filesize_operator_combo = QtWidgets.QComboBox()
        self.filesize_operator_combo.addItems([
            "= (equals)",
            "!= (not equals)",
            "> (greater than)",
            ">= (greater than or equal)",
            "< (less than)",
            "<= (less than or equal)",
            "between"
        ])
        self.filesize_operator_combo.setCurrentIndex(6)
        self.filesize_operator_combo.setMaximumWidth(150)
        layout.addWidget(self.filesize_operator_combo, 0, 0)

        # Value 1 with unit
        filesize_value1_layout = QtWidgets.QHBoxLayout()
        self.filesize_value1_edit = QtWidgets.QLineEdit()
        self.filesize_value1_edit.setPlaceholderText("100")
        self.filesize_value1_edit.setMaximumWidth(80)
        self.filesize_unit1_combo = QtWidgets.QComboBox()
        self.filesize_unit1_combo.addItems(["B", "KB", "MB", "GB"])
        self.filesize_unit1_combo.setCurrentIndex(2)
        self.filesize_unit1_combo.setMaximumWidth(50)
        filesize_value1_layout.addWidget(self.filesize_value1_edit)
        filesize_value1_layout.addWidget(self.filesize_unit1_combo)
        filesize_value1_layout.addStretch()
        layout.addLayout(filesize_value1_layout, 0, 1)

        # Value 2 with unit
        filesize_value2_layout = QtWidgets.QHBoxLayout()
        self.filesize_value2_edit = QtWidgets.QLineEdit()
        self.filesize_value2_edit.setPlaceholderText("500")
        self.filesize_value2_edit.setMaximumWidth(80)
        self.filesize_unit2_combo = QtWidgets.QComboBox()
        self.filesize_unit2_combo.addItems(["B", "KB", "MB", "GB"])
        self.filesize_unit2_combo.setCurrentIndex(2)
        self.filesize_unit2_combo.setMaximumWidth(50)
        filesize_value2_layout.addWidget(self.filesize_value2_edit)
        filesize_value2_layout.addWidget(self.filesize_unit2_combo)
        filesize_value2_layout.addStretch()
        layout.addLayout(filesize_value2_layout, 0, 2)

        self.enable_filesize_filter_checkbox = QtWidgets.QCheckBox("Enable")
        self.enable_filesize_filter_checkbox.setChecked(False)
        layout.addWidget(self.enable_filesize_filter_checkbox, 0, 3)
        
        self.filesize_operator_combo.currentIndexChanged.connect(self._on_filesize_operator_changed)
        
        # Apply styling if enabled
        group.setStyleSheet(self._get_section_stylesheet(5))

        return group

    def _create_date_filter_section(self):
        """Create Date Range Filter section"""
        group = QtWidgets.QGroupBox("Date Range Filter")
        layout = QtWidgets.QGridLayout(group)

        # Compact single-row layout
        self.date_from_edit = QtWidgets.QDateEdit()
        self.date_from_edit.setCalendarPopup(True)
        self.date_from_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_from_edit.setSpecialValueText("No start date")
        self.date_from_edit.setDate(QtCore.QDate(2000, 1, 1))
        self.date_from_edit.clearMinimumDate()
        self.date_from_edit.clearMaximumDate()
        layout.addWidget(self.date_from_edit, 0, 0)

        layout.addWidget(QtWidgets.QLabel("to"), 0, 1, QtCore.Qt.AlignmentFlag.AlignCenter)

        self.date_to_edit = QtWidgets.QDateEdit()
        self.date_to_edit.setCalendarPopup(True)
        self.date_to_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_to_edit.setSpecialValueText("No end date")
        self.date_to_edit.setDate(QtCore.QDate.currentDate())
        self.date_to_edit.clearMinimumDate()
        self.date_to_edit.clearMaximumDate()
        layout.addWidget(self.date_to_edit, 0, 2)

        self.enable_date_filter_checkbox = QtWidgets.QCheckBox("Enable")
        self.enable_date_filter_checkbox.setChecked(False)
        layout.addWidget(self.enable_date_filter_checkbox, 0, 3)
        
        # Apply styling if enabled
        group.setStyleSheet(self._get_section_stylesheet(6))

        return group

    def _create_resolution_filter_section(self):
        """Create Resolution Filter section"""
        group = QtWidgets.QGroupBox("Resolution Filter")
        layout = QtWidgets.QGridLayout(group)

        # Compact single-row layout
        self.resolution_operator_combo = QtWidgets.QComboBox()
        self.resolution_operator_combo.addItems([
            "= (equals)",
            "!= (not equals)",
            "> (greater than)",
            "< (less than)"
        ])
        self.resolution_operator_combo.setCurrentIndex(0)  # Equals by default
        self.resolution_operator_combo.setMaximumWidth(150)
        layout.addWidget(self.resolution_operator_combo, 0, 0)

        self.resolution_combo = QtWidgets.QComboBox()
        self.resolution_combo.addItems([
            "240p (VERY_LOW)",
            "360p (LOW/R360P)",
            "480p (STANDARD)",
            "720p (WEB_HD/STANDARD_HD)",
            "1080p (FULL_HD)",
            "1440p (QUAD_HD)",
            "1920p (VR_HD)",
            "4K (FOUR_K)",
            "5K (FIVE_K)",
            "6K (SIX_K)",
            "8K (EIGHT_K)"
        ])
        self.resolution_combo.setCurrentIndex(4)  # 1080p default
        layout.addWidget(self.resolution_combo, 0, 1)

        self.enable_resolution_filter_checkbox = QtWidgets.QCheckBox("Enable")
        self.enable_resolution_filter_checkbox.setChecked(False)
        layout.addWidget(self.enable_resolution_filter_checkbox, 0, 2)

        # Apply styling if enabled
        group.setStyleSheet(self._get_section_stylesheet(7))

        return group

    def _on_duration_operator_changed(self):
        """Show/hide second duration value field based on operator"""
        operator_index = self.duration_operator_combo.currentIndex()
        # Show second value only for "between" operator (index 6)
        is_between = (operator_index == 6)
        self.duration_value2_edit.setVisible(is_between)

    def _on_filesize_operator_changed(self):
        """Show/hide second file size value field based on operator"""
        operator_index = self.filesize_operator_combo.currentIndex()
        # Show second value only for "between" operator (index 6)
        is_between = (operator_index == 6)
        self.filesize_value2_edit.setVisible(is_between)
        self.filesize_unit2_combo.setVisible(is_between)

    def _on_section_visibility_changed(self, section_id, state):
        """Show/hide a section based on checkbox state"""
        if section_id in self.left_sections:
            if state == QtCore.Qt.CheckState.Checked.value:
                # Show section - remove from hidden list
                if section_id in self.hidden_sections:
                    self.hidden_sections.remove(section_id)
            else:
                # Hide section - add to hidden list
                if section_id not in self.hidden_sections:
                    self.hidden_sections.append(section_id)

            # Rebuild the layout to properly show/hide sections
            self._rebuild_sections_layout()

    def _create_settings_tab(self):
        """Create Settings tab with visual controls for all configuration"""
        settings_tab = QtWidgets.QWidget()
        self.tab_widget.addTab(settings_tab, "Settings")

        settings_main_layout = QtWidgets.QHBoxLayout(settings_tab)
        settings_main_layout.addStretch(1)  # 10% left margin

        settings_scroll = QtWidgets.QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        settings_main_layout.addWidget(settings_scroll, 8)  # 80% center content

        settings_main_layout.addStretch(1)  # 10% right margin

        settings_content = QtWidgets.QWidget()
        settings_scroll.setWidget(settings_content)
        settings_layout = QtWidgets.QVBoxLayout(settings_content)

        # ========== CONNECTION SETTINGS ==========
        conn_group = QtWidgets.QGroupBox("Connection Settings")
        conn_layout = QtWidgets.QGridLayout(conn_group)
        settings_layout.addWidget(conn_group)

        conn_layout.addWidget(QtWidgets.QLabel("GraphQL URL:"), 0, 0)
        self.settings_graphql_url = QtWidgets.QLineEdit()
        self.settings_graphql_url.setPlaceholderText("http://localhost:9999/graphql")
        self.settings_graphql_url.setText(self.graphql_url)
        conn_layout.addWidget(self.settings_graphql_url, 0, 1)

        conn_layout.addWidget(QtWidgets.QLabel("API Key:"), 1, 0)
        self.settings_api_key = QtWidgets.QLineEdit()
        self.settings_api_key.setPlaceholderText("Leave empty if not required")
        self.settings_api_key.setText(self.api_key)
        conn_layout.addWidget(self.settings_api_key, 1, 1)

        # ========== GENERAL SETTINGS ==========
        general_group = QtWidgets.QGroupBox("General Settings")
        general_layout = QtWidgets.QGridLayout(general_group)
        settings_layout.addWidget(general_group)

        general_layout.addWidget(QtWidgets.QLabel("Scenes per page:"), 0, 0)
        self.settings_per_page = QtWidgets.QSpinBox()
        self.settings_per_page.setRange(1, 4000)
        self.settings_per_page.setValue(self.per_page_spin.value())
        general_layout.addWidget(self.settings_per_page, 0, 1)

        self.settings_dryrun = QtWidgets.QCheckBox("Dry run mode (preview changes without applying)")
        self.settings_dryrun.setChecked(self.dryrun_checkbox.isChecked())
        general_layout.addWidget(self.settings_dryrun, 1, 0, 1, 2)

        self.settings_auto_create = QtWidgets.QCheckBox("Auto-create tag if it doesn't exist")
        self.settings_auto_create.setChecked(self.auto_create_checkbox.isChecked())
        general_layout.addWidget(self.settings_auto_create, 2, 0, 1, 2)

        # Sync settings between tabs
        self.settings_per_page.valueChanged.connect(lambda v: self.per_page_spin.setValue(v))
        self.per_page_spin.valueChanged.connect(lambda v: self.settings_per_page.setValue(v))
        self.settings_dryrun.stateChanged.connect(lambda s: self.dryrun_checkbox.setChecked(s))
        self.dryrun_checkbox.stateChanged.connect(lambda s: self.settings_dryrun.setChecked(s))
        self.settings_auto_create.stateChanged.connect(lambda s: self.auto_create_checkbox.setChecked(s))
        self.auto_create_checkbox.stateChanged.connect(lambda s: self.settings_auto_create.setChecked(s))

        # ========== SECTION ORDER SETTINGS ==========
        order_group = QtWidgets.QGroupBox("Section Display Order")
        order_layout = QtWidgets.QVBoxLayout(order_group)
        settings_layout.addWidget(order_group)

        order_desc = QtWidgets.QLabel("Use Up/Down buttons to reorder sections. Changes apply immediately to the Search tab.")
        order_desc.setWordWrap(True)
        order_layout.addWidget(order_desc)

        order_controls_layout = QtWidgets.QHBoxLayout()
        order_layout.addLayout(order_controls_layout)

        self.section_order_list = QtWidgets.QListWidget()
        self.section_order_list.setMaximumHeight(150)
        for section_id in self.section_order:
            self.section_order_list.addItem(self.section_id_to_name[section_id])
        order_controls_layout.addWidget(self.section_order_list)

        order_buttons_layout = QtWidgets.QVBoxLayout()
        order_controls_layout.addLayout(order_buttons_layout)

        self.move_up_btn = QtWidgets.QPushButton("↑ Move Up")
        self.move_down_btn = QtWidgets.QPushButton("↓ Move Down")
        self.move_up_btn.clicked.connect(self._move_section_up)
        self.move_down_btn.clicked.connect(self._move_section_down)
        order_buttons_layout.addWidget(self.move_up_btn)
        order_buttons_layout.addWidget(self.move_down_btn)
        order_buttons_layout.addStretch()

        # ========== SECTION COLUMN ASSIGNMENT ==========
        column_assign_group = QtWidgets.QGroupBox("Section Column Assignment")
        column_assign_layout = QtWidgets.QGridLayout(column_assign_group)
        settings_layout.addWidget(column_assign_group)

        column_assign_desc = QtWidgets.QLabel("Assign each section to Column 1 (left) or Column 2 (middle):")
        column_assign_desc.setWordWrap(True)
        column_assign_layout.addWidget(column_assign_desc, 0, 0, 1, 2)

        self.section_column_combos = {}
        row = 1
        for section_id in [1, 2, 3, 4, 5, 6, 7]:  # Now 7 sections including Resolution
            section_name = self.section_id_to_name[section_id]
            column_assign_layout.addWidget(QtWidgets.QLabel(f"{section_name}:"), row, 0)
            combo = QtWidgets.QComboBox()
            combo.addItems(["Column 1 (Left)", "Column 2 (Middle)"])
            current_column = self.section_columns.get(section_id, 1)
            combo.setCurrentIndex(current_column - 1)
            combo.currentIndexChanged.connect(lambda idx, sid=section_id: self._on_section_column_changed(sid, idx))
            self.section_column_combos[section_id] = combo
            column_assign_layout.addWidget(combo, row, 1)
            row += 1

        # ========== SECTION VISIBILITY ==========
        visibility_group = QtWidgets.QGroupBox("Section Visibility")
        visibility_layout = QtWidgets.QGridLayout(visibility_group)
        settings_layout.addWidget(visibility_group)

        visibility_desc = QtWidgets.QLabel("Show/hide sections (unchecked sections will be hidden):")
        visibility_desc.setWordWrap(True)
        visibility_layout.addWidget(visibility_desc, 0, 0, 1, 2)

        # Reuse existing section_visibility_checkboxes from right sidebar
        row = 1
        for idx, section_id in enumerate([1, 2, 3, 4, 5, 6, 7]):  # Now 7 sections including Resolution
            visibility_layout.addWidget(self.section_visibility_checkboxes[section_id], row + idx // 2, idx % 2)

        # ========== COLOR CUSTOMIZATION ==========
        color_group = QtWidgets.QGroupBox("Color Customization")
        color_layout = QtWidgets.QGridLayout(color_group)
        settings_layout.addWidget(color_group)

        # Enable/disable section backgrounds
        self.enable_section_colors_checkbox = QtWidgets.QCheckBox("Enable section background colors")
        self.enable_section_colors_checkbox.setChecked(self.section_backgrounds_enabled)
        self.enable_section_colors_checkbox.stateChanged.connect(self._on_section_colors_enabled_changed)
        color_layout.addWidget(self.enable_section_colors_checkbox, 0, 0, 1, 3)

        # Section colors and fonts - header row
        color_layout.addWidget(QtWidgets.QLabel("Section:"), 1, 0)
        color_layout.addWidget(QtWidgets.QLabel("Background:"), 1, 1)
        color_layout.addWidget(QtWidgets.QLabel("Font Color:"), 1, 2)
        color_layout.addWidget(QtWidgets.QLabel("Font Name:"), 1, 3)

        self.section_color_buttons = {}
        self.section_font_color_buttons = {}
        self.section_font_name_combos = {}
        row = 2

        # Common fonts list
        common_fonts = ["Arial", "Calibri", "Consolas", "Courier New", "Georgia", "Tahoma", "Times New Roman", "Trebuchet MS", "Verdana"]

        for section_id in [1, 2, 3, 4, 5, 6, 7]:
            section_name = self.section_id_to_name[section_id]
            color_layout.addWidget(QtWidgets.QLabel(f"{section_name}:"), row, 0)

            # Background color button
            color_btn = QtWidgets.QPushButton()
            color_btn.setMaximumWidth(80)
            color_btn.setStyleSheet(f"background-color: {self.section_colors[section_id]}; border: 1px solid #999;")
            color_btn.clicked.connect(lambda checked, sid=section_id: self._pick_section_color(sid))
            self.section_color_buttons[section_id] = color_btn
            color_layout.addWidget(color_btn, row, 1)

            # Font color button
            font_color_btn = QtWidgets.QPushButton()
            font_color_btn.setMaximumWidth(80)
            font_color_btn.setStyleSheet(f"background-color: {self.section_font_colors[section_id]}; border: 1px solid #999;")
            font_color_btn.clicked.connect(lambda checked, sid=section_id: self._pick_section_font_color(sid))
            self.section_font_color_buttons[section_id] = font_color_btn
            color_layout.addWidget(font_color_btn, row, 2)

            # Font name dropdown
            font_combo = QtWidgets.QComboBox()
            font_combo.addItems(common_fonts)
            font_combo.setCurrentText(self.section_font_names[section_id])
            font_combo.currentTextChanged.connect(lambda text, sid=section_id: self._on_section_font_name_changed(sid, text))
            self.section_font_name_combos[section_id] = font_combo
            color_layout.addWidget(font_combo, row, 3)

            row += 1

        # Tag Management color
        color_layout.addWidget(QtWidgets.QLabel("Tag Management:"), row, 0)
        self.tag_color_button = QtWidgets.QPushButton()
        self.tag_color_button.setMaximumWidth(100)
        self.tag_color_button.setStyleSheet(f"background-color: {self.tag_management_color}; border: 1px solid #999;")
        self.tag_color_button.clicked.connect(self._pick_tag_color)
        color_layout.addWidget(self.tag_color_button, row, 1)
        row += 1

        # Button colors
        color_layout.addWidget(QtWidgets.QLabel("Button Colors:"), row, 0, 1, 3)
        row += 1

        color_layout.addWidget(QtWidgets.QLabel("Button Background:"), row, 0)
        self.button_bg_color_button = QtWidgets.QPushButton()
        self.button_bg_color_button.setMaximumWidth(100)
        self.button_bg_color_button.setStyleSheet(f"background-color: {self.button_color}; border: 1px solid #999;")
        self.button_bg_color_button.clicked.connect(self._pick_button_bg_color)
        color_layout.addWidget(self.button_bg_color_button, row, 1)
        row += 1

        color_layout.addWidget(QtWidgets.QLabel("Button Text:"), row, 0)
        self.button_text_color_button = QtWidgets.QPushButton()
        self.button_text_color_button.setMaximumWidth(100)
        self.button_text_color_button.setStyleSheet(f"background-color: {self.button_text_color}; border: 1px solid #999;")
        self.button_text_color_button.clicked.connect(self._pick_button_text_color)
        color_layout.addWidget(self.button_text_color_button, row, 1)

        # ========== APPLY SETTINGS BUTTON ==========
        apply_layout = QtWidgets.QHBoxLayout()
        settings_layout.addLayout(apply_layout)

        apply_layout.addStretch()
        self.apply_settings_btn = QtWidgets.QPushButton("Apply Connection Settings")
        self.apply_settings_btn.clicked.connect(self._apply_connection_settings)
        apply_layout.addWidget(self.apply_settings_btn)

        settings_layout.addStretch()

    def _move_section_up(self):
        """Move selected section up in display order"""
        current_row = self.section_order_list.currentRow()
        if current_row > 0:
            # Swap in section_order list
            self.section_order[current_row], self.section_order[current_row - 1] = \
                self.section_order[current_row - 1], self.section_order[current_row]
            # Update UI list
            item = self.section_order_list.takeItem(current_row)
            self.section_order_list.insertItem(current_row - 1, item)
            self.section_order_list.setCurrentRow(current_row - 1)
            # Rebuild sections layout
            self._rebuild_sections_layout()

    def _move_section_down(self):
        """Move selected section down in display order"""
        current_row = self.section_order_list.currentRow()
        if current_row < len(self.section_order) - 1 and current_row >= 0:
            # Swap in section_order list
            self.section_order[current_row], self.section_order[current_row + 1] = \
                self.section_order[current_row + 1], self.section_order[current_row]
            # Update UI list
            item = self.section_order_list.takeItem(current_row)
            self.section_order_list.insertItem(current_row + 1, item)
            self.section_order_list.setCurrentRow(current_row + 1)
            # Rebuild sections layout
            self._rebuild_sections_layout()

    def _rebuild_sections_layout(self):
        """Rebuild the sections layout based on current order and recreate with new colors"""
        # Clear existing widgets from columns
        for i in reversed(range(self.column1_layout.count())):
            widget = self.column1_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        for i in reversed(range(self.column2_layout.count())):
            widget = self.column2_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Recreate all sections with updated colors
        self.left_sections[1] = self._create_title_filename_section()
        self.left_sections[2] = self._create_performer_section()
        self.left_sections[3] = self._create_studio_section()
        self.left_sections[4] = self._create_duration_filter_section()
        self.left_sections[5] = self._create_filesize_filter_section()
        self.left_sections[6] = self._create_date_filter_section()
        self.left_sections[7] = self._create_resolution_filter_section()

        # Distribute sections to columns based on section_columns mapping
        for section_id in self.section_order:
            if section_id in self.left_sections and section_id not in self.hidden_sections:
                section_widget = self.left_sections[section_id]
                column = self.section_columns.get(section_id, 1)

                if column == 1:
                    self.column1_layout.addWidget(section_widget)
                elif column == 2:
                    self.column2_layout.addWidget(section_widget)

    def _on_section_column_changed(self, section_id, combo_index):
        """Handle section column assignment change"""
        new_column = combo_index + 1  # combo_index 0 = column 1, combo_index 1 = column 2
        self.section_columns[section_id] = new_column
        # Rebuild sections layout to reflect change
        self._rebuild_sections_layout()

    def _on_section_colors_enabled_changed(self, state):
        """Enable/disable section background colors"""
        self.section_backgrounds_enabled = bool(state)
        # Rebuild sections to apply/remove colors
        self._rebuild_sections_layout()

    def _pick_section_color(self, section_id):
        """Open color picker for a section"""
        current_color = QtGui.QColor(self.section_colors[section_id])
        color = QtWidgets.QColorDialog.getColor(current_color, self, f"Pick color for {self.section_id_to_name[section_id]}")
        if color.isValid():
            color_hex = color.name()
            self.section_colors[section_id] = color_hex
            self.section_color_buttons[section_id].setStyleSheet(f"background-color: {color_hex}; border: 1px solid #999;")
            # Rebuild sections to apply new color
            self._rebuild_sections_layout()

    def _pick_section_font_color(self, section_id):
        """Open color picker for section font color"""
        current_color = QtGui.QColor(self.section_font_colors[section_id])
        color = QtWidgets.QColorDialog.getColor(current_color, self, f"Pick font color for {self.section_id_to_name[section_id]}")
        if color.isValid():
            color_hex = color.name()
            self.section_font_colors[section_id] = color_hex
            self.section_font_color_buttons[section_id].setStyleSheet(f"background-color: {color_hex}; border: 1px solid #999;")
            # Rebuild sections to apply new font color
            self._rebuild_sections_layout()

    def _on_section_font_name_changed(self, section_id, font_name):
        """Handle section font name change"""
        self.section_font_names[section_id] = font_name
        # Rebuild sections to apply new font
        self._rebuild_sections_layout()

    def _pick_tag_color(self):
        """Open color picker for Tag Management section"""
        current_color = QtGui.QColor(self.tag_management_color)
        color = QtWidgets.QColorDialog.getColor(current_color, self, "Pick color for Tag Management")
        if color.isValid():
            color_hex = color.name()
            self.tag_management_color = color_hex
            self.tag_color_button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #999;")
            # Rebuild sections to apply new color
            self._rebuild_sections_layout()

    def _pick_button_bg_color(self):
        """Open color picker for button background"""
        current_color = QtGui.QColor(self.button_color)
        color = QtWidgets.QColorDialog.getColor(current_color, self, "Pick button background color")
        if color.isValid():
            color_hex = color.name()
            self.button_color = color_hex
            self.button_bg_color_button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #999;")
            # Apply to all buttons
            self._apply_button_colors()

    def _pick_button_text_color(self):
        """Open color picker for button text"""
        current_color = QtGui.QColor(self.button_text_color)
        color = QtWidgets.QColorDialog.getColor(current_color, self, "Pick button text color")
        if color.isValid():
            color_hex = color.name()
            self.button_text_color = color_hex
            self.button_text_color_button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #999;")
            # Apply to all buttons
            self._apply_button_colors()

    def _apply_button_colors(self):
        """Apply button colors to action buttons (not color picker buttons)"""
        if self.section_backgrounds_enabled:
            # Only apply to specific action buttons, not ALL buttons (to avoid affecting color pickers)
            action_buttons = [
                self.search_scenes_btn,
                self.search_performers_btn,
                self.clear_performers_btn,
                self.assign_performers_btn,
                self.search_studios_btn,
                self.clear_studio_btn,
                self.assign_studio_btn,
                self.apply_tag_btn,
                self.rename_btn,
                self.export_csv_btn,
                self.import_csv_btn,
                self.apply_settings_btn,
                self.move_up_btn,
                self.move_down_btn
            ]
            for button in action_buttons:
                if button:  # Check if button exists
                    button.setStyleSheet(f"QPushButton {{ background-color: {self.button_color}; color: {self.button_text_color}; }}")

    def _apply_connection_settings(self):
        """Apply connection settings (URL and API key)"""
        self.graphql_url = self.settings_graphql_url.text().strip()
        self.api_key = self.settings_api_key.text().strip()
        self.log.append("Connection settings updated. Restart application or test with a search.")

    def _build_client(self) -> GraphQLClient:
        url = self.graphql_url.strip()
        if not url:
            raise RuntimeError("GraphQL URL must not be empty")
        api_key = self.api_key.strip()
        headers = {"Content-Type": "application/json"}
        if api_key:
            if ":" in api_key:
                parts = api_key.split(":", 1)
                headers[parts[0].strip()] = parts[1].strip()
            elif " " in api_key:
                # e.g. "Authorization Bearer <token>"
                # naive split first token as header name
                parts = api_key.split(" ", 1)
                headers[parts[0].strip()] = parts[1].strip()
            else:
                headers["ApiKey"] = api_key
        return GraphQLClient(url, headers)

    def load_config(self):
        """Load configuration from config.ini file"""
        # Ensure config directory exists
        config_dir = os.path.dirname(self.CONFIG_FILE)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
            
        if not os.path.exists(self.CONFIG_FILE):
            self._log("No config file found. Using defaults.")
            return
        
        try:
            config = ConfigParser()
            config.read(self.CONFIG_FILE)
            
            # [Connection] section
            if config.has_section('Connection'):
                if config.has_option('Connection', 'graphql_url'):
                    self.graphql_url = config.get('Connection', 'graphql_url')
                if config.has_option('Connection', 'api_key'):
                    self.api_key = config.get('Connection', 'api_key')
            
            # [Settings] section
            if config.has_section('Settings'):
                if config.has_option('Settings', 'per_page'):
                    self.per_page_spin.setValue(config.getint('Settings', 'per_page'))
                if config.has_option('Settings', 'dry_run'):
                    self.dryrun_checkbox.setChecked(config.getboolean('Settings', 'dry_run'))
                if config.has_option('Settings', 'auto_create_tag'):
                    self.auto_create_checkbox.setChecked(config.getboolean('Settings', 'auto_create_tag'))
            
            # [Window] section
            if config.has_section('Window'):
                if config.has_option('Window', 'geometry'):
                    geom_str = config.get('Window', 'geometry')
                    # Format: x,y,width,height
                    parts = geom_str.split(',')
                    if len(parts) == 4:
                        x, y, w, h = map(int, parts)
                        self.setGeometry(x, y, w, h)
                
                # Column widths (3-column layout)
                if config.has_option('Window', 'column1_width') and \
                   config.has_option('Window', 'column2_width') and \
                   config.has_option('Window', 'sidebar_width'):
                    # Load all three saved column widths
                    col1_width = max(100, config.getint('Window', 'column1_width'))
                    col2_width = max(100, config.getint('Window', 'column2_width'))
                    sidebar_width = max(100, config.getint('Window', 'sidebar_width'))
                    self.top_splitter.setSizes([col1_width, col2_width, sidebar_width])
                elif config.has_option('Window', 'sidebar_width'):
                    # Backwards compatibility: only sidebar_width was saved
                    sidebar_width = config.getint('Window', 'sidebar_width')
                    sidebar_width = max(100, sidebar_width)
                    total_width = self.width()
                    remaining_width = total_width - sidebar_width
                    col1_width = int(remaining_width * 0.5)
                    col2_width = remaining_width - col1_width
                    self.top_splitter.setSizes([col1_width, col2_width, sidebar_width])
            
            # [Columns] section
            if config.has_section('Columns'):
                if config.has_option('Columns', 'visible'):
                    visible_str = config.get('Columns', 'visible')
                    if visible_str:
                        visible_indices = [int(i) for i in visible_str.split(',')]
                        # Ensure "Select" column (index 0) is always first
                        if 0 not in visible_indices:
                            visible_indices.insert(0, 0)
                        elif visible_indices[0] != 0:
                            visible_indices.remove(0)
                            visible_indices.insert(0, 0)
                        self.table_model.set_visible_columns(visible_indices)
                
                if config.has_option('Columns', 'widths'):
                    widths_str = config.get('Columns', 'widths')
                    if widths_str:
                        widths = [int(w) for w in widths_str.split(',')]
                        header = self.table_view.horizontalHeader()
                        for i, width in enumerate(widths):
                            if i < header.count():
                                header.resizeSection(i, width)
            
            # [Sections] section - Note: section order is already loaded in _load_section_order()
            # This section is kept for backwards compatibility but doesn't override the earlier load
            
            # [Colors] section
            if config.has_section('Colors'):
                if config.has_option('Colors', 'section_backgrounds'):
                    self.section_backgrounds_enabled = config.getboolean('Colors', 'section_backgrounds')

                # Load individual section colors (now 6 sections instead of 7)
                for i in range(1, 8):  # Now 7 sections
                    if config.has_option('Colors', f'section_{i}_color'):
                        self.section_colors[i] = config.get('Colors', f'section_{i}_color')
                
                if config.has_option('Colors', 'tag_management_color'):
                    self.tag_management_color = config.get('Colors', 'tag_management_color')
                if config.has_option('Colors', 'button_color'):
                    self.button_color = config.get('Colors', 'button_color')
                if config.has_option('Colors', 'button_text_color'):
                    self.button_text_color = config.get('Colors', 'button_text_color')
            
            # [Fonts] section
            if config.has_section('Fonts'):
                if config.has_option('Fonts', 'button_font'):
                    self.button_font_name = config.get('Fonts', 'button_font')
                if config.has_option('Fonts', 'button_size'):
                    self.button_font_size = config.getint('Fonts', 'button_size')
                if config.has_option('Fonts', 'section_title_font'):
                    self.section_title_font_name = config.get('Fonts', 'section_title_font')
                if config.has_option('Fonts', 'section_title_size'):
                    self.section_title_font_size = config.getint('Fonts', 'section_title_size')
                if config.has_option('Fonts', 'results_font'):
                    self.results_font_name = config.get('Fonts', 'results_font')
                if config.has_option('Fonts', 'results_size'):
                    self.results_font_size = config.getint('Fonts', 'results_size')
                if config.has_option('Fonts', 'log_font'):
                    self.log_font_name = config.get('Fonts', 'log_font')
                if config.has_option('Fonts', 'log_size'):
                    self.log_font_size = config.getint('Fonts', 'log_size')
                
                # Apply fonts to widgets
                self._apply_fonts()
            
            self._log(f"Configuration loaded from {self.CONFIG_FILE}")
        except Exception as e:
            self._log(f"Error loading config: {e}")

    def save_config(self):
        """Save configuration to config.ini file"""
        try:
            # Ensure config directory exists
            config_dir = os.path.dirname(self.CONFIG_FILE)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                
            config = ConfigParser()
            
            # [Connection] section
            config.add_section('Connection')
            config.set('Connection', 'graphql_url', self.graphql_url)
            config.set('Connection', 'api_key', self.api_key)
            
            # [Settings] section
            config.add_section('Settings')
            config.set('Settings', 'per_page', str(self.per_page_spin.value()))
            config.set('Settings', 'dry_run', str(self.dryrun_checkbox.isChecked()))
            config.set('Settings', 'auto_create_tag', str(self.auto_create_checkbox.isChecked()))
            
            # [Window] section
            config.add_section('Window')
            geom = self.geometry()
            geom_str = f"{geom.x()},{geom.y()},{geom.width()},{geom.height()}"
            config.set('Window', 'geometry', geom_str)
            
            # Save all three column widths from 3-column splitter
            splitter_sizes = self.top_splitter.sizes()
            if len(splitter_sizes) == 3:
                col1_width = max(100, splitter_sizes[0])  # Column 1 width
                col2_width = max(100, splitter_sizes[1])  # Column 2 width
                col3_width = max(100, splitter_sizes[2])  # Column 3 (sidebar) width
                config.set('Window', 'column1_width', str(col1_width))
                config.set('Window', 'column2_width', str(col2_width))
                config.set('Window', 'sidebar_width', str(col3_width))
            
            # [Columns] section
            config.add_section('Columns')
            visible_str = ','.join(map(str, self.table_model._visible_columns))
            config.set('Columns', 'visible', visible_str)

            # [Sections] section
            config.add_section('Sections')
            # Save using descriptive names
            order_names = [self.section_id_to_name[i] for i in self.section_order]
            order_str = ', '.join(order_names)
            config.set('Sections', 'order', order_str)

            # Save hidden sections
            if self.hidden_sections:
                hidden_names = [self.section_id_to_name[i] for i in self.hidden_sections]
                hide_str = ', '.join(hidden_names)
            else:
                hide_str = ''
            config.set('Sections', 'hide', hide_str)

            # Save column assignments (format: "TitleFilename:1, Performer:1, Studio:2, ...")
            column_assignments = []
            for section_id, column in sorted(self.section_columns.items()):
                section_name = self.section_id_to_name[section_id]
                column_assignments.append(f"{section_name}:{column}")
            columns_str = ', '.join(column_assignments)
            config.set('Sections', 'columns', columns_str)

            # Save column widths
            header = self.table_view.horizontalHeader()
            widths = [header.sectionSize(i) for i in range(header.count())]
            widths_str = ','.join(map(str, widths))
            config.set('Columns', 'widths', widths_str)
            
            # [Colors] section
            config.add_section('Colors')
            config.set('Colors', 'section_backgrounds', str(self.section_backgrounds_enabled))
            for i in range(1, 8):  # Now 7 sections
                config.set('Colors', f'section_{i}_color', self.section_colors[i])
                config.set('Colors', f'section_{i}_font_color', self.section_font_colors[i])
                config.set('Colors', f'section_{i}_font_name', self.section_font_names[i])
            config.set('Colors', 'tag_management_color', self.tag_management_color)
            config.set('Colors', 'button_color', self.button_color)
            config.set('Colors', 'button_text_color', self.button_text_color)
            
            # [Fonts] section
            config.add_section('Fonts')
            config.set('Fonts', 'button_font', self.button_font_name)
            config.set('Fonts', 'button_size', str(self.button_font_size))
            config.set('Fonts', 'section_title_font', self.section_title_font_name)
            config.set('Fonts', 'section_title_size', str(self.section_title_font_size))
            config.set('Fonts', 'results_font', self.results_font_name)
            config.set('Fonts', 'results_size', str(self.results_font_size))
            config.set('Fonts', 'log_font', self.log_font_name)
            config.set('Fonts', 'log_size', str(self.log_font_size))
            
            # Write to file
            with open(self.CONFIG_FILE, 'w') as f:
                config.write(f)
            
            # Append descriptive comments to make config file user-friendly
            with open(self.CONFIG_FILE, 'a') as f:
                f.write('\n')
                f.write('; ========================================\n')
                f.write('; Configuration Guide\n')
                f.write('; ========================================\n')
                f.write(';\n')
                f.write('; [Connection]\n')
                f.write(';   graphql_url = Your Stash GraphQL API endpoint URL\n')
                f.write(';                 Example: http://192.168.0.166:9977/graphql\n')
                f.write(';   api_key = Your Stash API authentication key (leave empty if not required)\n')
                f.write(';\n')
                f.write('; [Settings]\n')
                f.write(';   per_page = Number of scenes to fetch per search query\n')
                f.write(';              Valid range: 1-1000 (default: 100)\n')
                f.write(';   dry_run = Preview mode - shows what would change without actually modifying data\n')
                f.write(';             Values: True (preview only) or False (apply changes)\n')
                f.write(';   auto_create_tag = Automatically create tags if they don\'t exist in Stash\n')
                f.write(';                     Values: True (auto-create) or False (error if tag missing)\n')
                f.write(';\n')
                f.write('; [Window]\n')
                f.write(';   geometry = Window position and size on screen\n')
                f.write(';              Format: x,y,width,height (in pixels)\n')
                f.write(';              Example: 100,100,1200,800 means window at position (100,100) with size 1200x800\n')
                f.write(';   sidebar_width = Width of the right sidebar panel in pixels\n')
                f.write(';                   Minimum: 100, typical: 300-400\n')
                f.write(';\n')
                f.write('; [Columns]\n')
                f.write(';   visible = Comma-separated list of column indices to display in results table\n')
                f.write(';             Column index reference:\n')
                f.write(';               0 = Select (checkbox - always shown first)\n')
                f.write(';               1 = ID (scene database ID)\n')
                f.write(';               2 = Title (scene title)\n')
                f.write(';               3 = Date (scene date)\n')
                f.write(';               4 = Rating (scene rating)\n')
                f.write(';               5 = O-Counter (organized count)\n')
                f.write(';               6 = Duration (video length)\n')
                f.write(';               7 = File Size (total file size)\n')
                f.write(';               8 = Path (file path/location)\n')
                f.write(';               9 = Performers (performer names)\n')
                f.write(';              10 = Studio (studio name)\n')
                f.write(';              11 = Tags (tag names and IDs)\n')
                f.write(';             Example: 0,1,2,3,6,7,8,9,10,11 (shows all except Rating and O-Counter)\n')
                f.write(';\n')
                f.write(';   widths = Comma-separated list of column widths in pixels\n')
                f.write(';            Must match the number of visible columns\n')
                f.write(';            Example: 50,80,300,100,80,100,80,120,400,150,150,200\n')
                f.write(';\n')
                f.write('; [Sections]\n')
                f.write(';   order = Section display order (change order, then restart application)\n')
                f.write(';           Use descriptive section names (comma-separated, case-sensitive)\n')
                f.write(';           Default order: TitleFilename, Performer, Studio, Duration, FileSize, Date\n')
                f.write(';\n')
                f.write(';   hide = Comma-separated list of sections to hide\n')
                f.write(';          Use same section names as in \'order\' setting\n')
                f.write(';          Hidden sections will not be displayed and will not take up space\n')
                f.write(';          Leave empty to show all sections\n')
                f.write(';          Example: hide = Duration, FileSize  (hides Duration and FileSize filters)\n')
                f.write(';\n')
                f.write(';   columns = Column assignment for each section (3-column layout)\n')
                f.write(';             Format: SectionName:ColumnNumber (comma-separated)\n')
                f.write(';             Column 1 = Left column, Column 2 = Middle column, Column 3 = Right sidebar (fixed)\n')
                f.write(';             Default: TitleFilename:1, Performer:1, Studio:2, Duration:2, FileSize:2, Date:2\n')
                f.write(';             Example: TitleFilename:1, Performer:2, Studio:1, Duration:2, FileSize:2, Date:1\n')
                f.write(';\n')
                f.write(';           Section Name Reference:\n')
                f.write(';             TitleFilename = Title/Filename Search - Search by title or file path\n')
                f.write(';             Performer = Performer Search - Search and filter by performers (AND/OR logic)\n')
                f.write(';             Studio = Studio Search - Search and filter by studio\n')
                f.write(';             Duration = Duration Filter - Filter by video duration (with operators)\n')
                f.write(';             FileSize = File Size Filter - Filter by file size (with operators)\n')
                f.write(';             Date = Date Range Filter - Filter by scene date range\n')
                f.write(';\n')
                f.write(';           Example custom orders:\n')
                f.write(';             order = TitleFilename, Performer, Studio, Date, Duration, FileSize  (Date before Duration/FileSize)\n')
                f.write(';             order = Date, FileSize, Duration, Studio, Performer, TitleFilename  (Reverse order - filters first)\n')
                f.write(';             order = Performer, Studio, TitleFilename, Duration, FileSize, Date  (Performers and Studio at top)\n')
                f.write(';\n')
                f.write('; [Colors]\n')
                f.write(';   section_backgrounds = Enable/disable colored backgrounds for sections\n')
                f.write(';                         Values: True (colored) or False (default/no color)\n')
                f.write(';   section_1_color = Background color for Section 1 (Title/Filename Search)\n')
                f.write(';                     Format: Hex color code (e.g., #E8F4F8 for light blue)\n')
                f.write(';   section_2_color = Background color for Section 2 (Performer Search)\n')
                f.write(';                     Default: #F0E8F8 (light purple)\n')
                f.write(';   section_3_color = Background color for Section 3 (Studio Search)\n')
                f.write(';                     Default: #F8F0E8 (light orange)\n')
                f.write(';   section_4_color = Background color for Section 4 (Duration Filter)\n')
                f.write(';                     Default: #F8E8E8 (light red)\n')
                f.write(';   section_5_color = Background color for Section 5 (File Size Filter)\n')
                f.write(';                     Default: #F8F8E8 (light yellow)\n')
                f.write(';   section_6_color = Background color for Section 6 (Date Range Filter)\n')
                f.write(';                     Default: #E8E8F8 (light lavender)\n')
                f.write(';   tag_management_color = Background color for Tag Management section\n')
                f.write(';                          Default: #FFE8E8 (light pink)\n')
                f.write(';   button_color = Background color for all buttons\n')
                f.write(';                  Default: #4A90E2 (blue)\n')
                f.write(';   button_text_color = Text color for all buttons\n')
                f.write(';                       Default: #FFFFFF (white)\n')
                f.write(';\n')
                f.write('; [Fonts]\n')
                f.write(';   button_font = Font family for all buttons\n')
                f.write(';                 Default: Arial\n')
                f.write(';   button_size = Font size for all buttons in points\n')
                f.write(';                 Default: 9\n')
                f.write(';   section_title_font = Font family for section titles (QGroupBox headers)\n')
                f.write(';                        Default: Arial\n')
                f.write(';   section_title_size = Font size for section titles in points\n')
                f.write(';                        Default: 10 (displayed in bold)\n')
                f.write(';   results_font = Font family for results table\n')
                f.write(';                  Default: Consolas (monospace for better alignment)\n')
                f.write(';   results_size = Font size for results table in points\n')
                f.write(';                  Default: 9\n')
                f.write(';   log_font = Font family for status log text area\n')
                f.write(';              Default: Courier New (monospace for readability)\n')
                f.write(';   log_size = Font size for status log in points\n')
                f.write(';              Default: 8\n')
                f.write(';\n')
            
            self._log(f"Configuration saved to {self.CONFIG_FILE}")
        except Exception as e:
            self._log(f"Error saving config: {e}")

    def closeEvent(self, event):
        """Save config when window closes"""
        self.save_config()
        event.accept()

    def on_get_tag(self):
        try:
            self.client = self._build_client()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Config error", str(e))
            return
        tag_name = self.tag_edit.text().strip()
        if not tag_name:
            QtWidgets.QMessageBox.warning(self, "Missing", "Please enter a tag name.")
            return
        worker = FetchTagWorker(self.client, tag_name)
        worker.signals.result.connect(self._on_tag_fetched)
        worker.signals.error.connect(self._on_tag_error)
        worker.signals.progress.connect(self.progress.setValue)
        worker.signals.status.connect(self._log)
        self.pool.start(worker)
        self._log("Started tag lookup...")

    def _on_tag_fetched(self, res):
        self.last_tag_id = res.get("id")
        self.last_tag_name = res.get("name")
        self._log(f"Found Tag ID: {self.last_tag_id} (name: {self.last_tag_name})")
        QtWidgets.QMessageBox.information(self, "Tag found", f"Tag ID: {self.last_tag_id}\nName: {self.last_tag_name}")

    def _on_tag_error(self, msg: str):
        # special case for TAG_NOT_FOUND
        if isinstance(msg, str) and msg.startswith("TAG_NOT_FOUND:"):
            tagname = msg.split(":", 1)[1]
            self._log(f"Tag '{tagname}' not found.")
            if self.auto_create_checkbox.isChecked():
                reply = QtWidgets.QMessageBox.question(self, "Create tag?",
                    f"Tag '{tagname}' not found. Create it now?",
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                    try:
                        self._log("Creating tag...")
                        created_id = self.client.create_tag(tagname)
                        self.last_tag_id = created_id
                        self.last_tag_name = tagname
                        self._log(f"Created tag '{tagname}' with id {created_id}")
                        QtWidgets.QMessageBox.information(self, "Tag created", f"Tag '{tagname}' created with ID {created_id}")
                    except Exception as e:
                        QtWidgets.QMessageBox.critical(self, "Create failed", str(e))
                        self._log("Create failed: " + str(e))
                else:
                    self._log("User chose not to create tag.")
            else:
                QtWidgets.QMessageBox.information(self, "Tag missing", f"Tag '{tagname}' not found and auto-create is disabled.")
        else:
            # generic error
            self._log("Error: " + str(msg))
            QtWidgets.QMessageBox.critical(self, "GraphQL error", str(msg))

    def on_select_all(self):
        """Select all scenes and force view update"""
        self.table_model.select_all(True)
        self.table_view.viewport().update()
    
    def on_select_none(self):
        """Deselect all scenes and force view update"""
        self.table_model.select_all(False)
        self.table_view.viewport().update()

    def on_search_scenes(self):
        try:
            self.client = self._build_client()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Config error", str(e))
            return
        search_term = self.search_edit.text().strip()
        
        # Get selected performer IDs
        performer_ids = list(self.selected_performers.keys())
        performer_logic = "AND" if self.performer_logic_combo.currentIndex() == 0 else "OR"
        
        # Get selected studio ID
        studio_id = self.selected_studio.get("id") if self.selected_studio else None
        
        # Get date range if enabled
        date_from = None
        date_to = None
        if self.enable_date_filter_checkbox.isChecked():
            date_from = self.date_from_edit.date().toString("yyyy-MM-dd")
            date_to = self.date_to_edit.date().toString("yyyy-MM-dd")
            self._log(f"Date filter enabled: {date_from} to {date_to}")
        
        # Get duration range if enabled
        duration_value1 = None
        duration_value2 = None
        duration_operator = "BETWEEN"
        if self.enable_duration_filter_checkbox.isChecked():
            # Map combo box index to GraphQL operator
            operator_map = {
                0: "EQUALS",
                1: "NOT_EQUALS", 
                2: "GREATER_THAN",
                3: "GREATER_THAN",  # >= will be handled as > for now (GraphQL limitation)
                4: "LESS_THAN",
                5: "LESS_THAN",  # <= will be handled as < for now (GraphQL limitation)
                6: "BETWEEN"
            }
            operator_index = self.duration_operator_combo.currentIndex()
            duration_operator = operator_map[operator_index]
            
            value1_input = self.duration_value1_edit.text().strip()
            if not value1_input:
                QtWidgets.QMessageBox.warning(self, "Missing value", 
                    "Please enter a duration value.")
                return
            
            duration_value1 = parse_duration_input(value1_input)
            if duration_value1 is None:
                QtWidgets.QMessageBox.warning(self, "Invalid duration", 
                    f"Invalid duration format: '{value1_input}'. Use MM:SS or seconds.")
                return
            
            # For BETWEEN operator, need second value
            if duration_operator == "BETWEEN":
                value2_input = self.duration_value2_edit.text().strip()
                if not value2_input:
                    QtWidgets.QMessageBox.warning(self, "Missing value", 
                        "Please enter a second duration value for 'between' operator.")
                    return
                
                duration_value2 = parse_duration_input(value2_input)
                if duration_value2 is None:
                    QtWidgets.QMessageBox.warning(self, "Invalid duration", 
                        f"Invalid duration format: '{value2_input}'. Use MM:SS or seconds.")
                    return
                
                self._log(f"Duration filter enabled: BETWEEN {duration_value1} and {duration_value2} seconds")
            else:
                operator_text = self.duration_operator_combo.currentText().split()[0]
                self._log(f"Duration filter enabled: {operator_text} {duration_value1} seconds")
        
        # Get path/filename filter if enabled (SERVER-SIDE)
        path_query = None
        if self.enable_path_filter_checkbox.isChecked():
            path_query = self.path_search_edit.text().strip()
            if not path_query:
                QtWidgets.QMessageBox.warning(self, "Missing value", 
                    "Please enter a path to search.")
                return
            
            self._log(f"Path filter enabled: searching for '{path_query}' in file paths (server-side)")
        
        # Check if resolution filter is enabled and get value
        resolution_enum = None
        resolution_operator = "EQUALS"
        resolution_enabled = self.enable_resolution_filter_checkbox.isChecked()
        if resolution_enabled:
            # Map dropdown index to GraphQL ResolutionEnum
            resolution_map = {
                0: "VERY_LOW",      # 240p
                1: "LOW",           # 360p
                2: "STANDARD",      # 480p
                3: "STANDARD_HD",   # 720p
                4: "FULL_HD",       # 1080p
                5: "QUAD_HD",       # 1440p
                6: "VR_HD",         # 1920p
                7: "FOUR_K",        # 4K
                8: "FIVE_K",        # 5K
                9: "SIX_K",         # 6K
                10: "EIGHT_K"       # 8K
            }

            # Map operator combo index to GraphQL operator
            operator_map = {
                0: "EQUALS",
                1: "NOT_EQUALS",
                2: "GREATER_THAN",
                3: "LESS_THAN"
            }
            operator_index = self.resolution_operator_combo.currentIndex()
            resolution_operator = operator_map[operator_index]

            resolution_index = self.resolution_combo.currentIndex()
            resolution_enum = resolution_map.get(resolution_index)

            operator_text = self.resolution_operator_combo.currentText().split()[0]
            self._log(f"Resolution filter enabled: {operator_text} {resolution_enum}")

        # Allow searching with just performers or studio (no title search required)
        if (not search_term and not performer_ids and not studio_id and
            not (date_from or date_to) and duration_value1 is None and
            not self.enable_filesize_filter_checkbox.isChecked() and
            not path_query and not resolution_enabled):
            QtWidgets.QMessageBox.warning(self, "Missing",
                "Please enter a search term, select performers, select a studio, enable date filtering, enable duration filtering, enable file size filtering, enable path filtering, or enable resolution filtering.")
            return
        
        per_page = self.per_page_spin.value()
        
        # If file size filter is enabled, we need to fetch ALL scenes for client-side filtering
        if self.enable_filesize_filter_checkbox.isChecked():
            self._log("File size filter enabled - fetching all scenes for client-side filtering...")
            per_page = 10000  # Fetch a large number to get all scenes
        
        worker = SearchScenesWorker(self.client, search_term, performer_ids, performer_logic,
                                 studio_id, date_from, date_to, duration_value1, duration_value2,
                                 duration_operator, path_query, resolution_enum, resolution_operator, per_page)
        worker.signals.result.connect(self._on_scenes_found)
        worker.signals.error.connect(lambda e: (self._log("Error: " + e), QtWidgets.QMessageBox.critical(self, "GraphQL error", e)))
        worker.signals.progress.connect(self.progress.setValue)
        worker.signals.status.connect(self._log)
        self.pool.start(worker)
        self._log("Started searching scenes...")

    def on_search_performers(self):
        try:
            self.client = self._build_client()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Config error", str(e))
            return
        performer_name = self.performer_search_edit.text().strip()
        if not performer_name:
            QtWidgets.QMessageBox.warning(self, "Missing", "Please enter a performer name to search.")
            return
        worker = FetchPerformersWorker(self.client, performer_name)
        worker.signals.result.connect(self._on_performers_found)
        worker.signals.error.connect(lambda e: (self._log("Error: " + e), QtWidgets.QMessageBox.critical(self, "GraphQL error", e)))
        worker.signals.progress.connect(self.progress.setValue)
        worker.signals.status.connect(self._log)
        self.pool.start(worker)
        self._log("Started searching performers...")

    def _on_performers_found(self, result):
        count = result.get("count", 0)
        performers = result.get("performers", [])
        self._log(f"Found {count} performers matching search.")
        
        if not performers:
            QtWidgets.QMessageBox.information(self, "No results", "No performers found matching your search.")
            return
        
        # Show dialog to select performers
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Performers")
        dialog.setMinimumSize(500, 400)
        layout = QtWidgets.QVBoxLayout(dialog)
        
        label = QtWidgets.QLabel(f"Found {count} performers. Select performers to filter scenes:")
        layout.addWidget(label)
        
        list_widget = QtWidgets.QListWidget()
        list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)
        for p in performers:
            item_text = f"{p.get('name', 'Unknown')} (ID: {p.get('id')}, Scenes: {p.get('scene_count', 0)})"
            if p.get('disambiguation'):
                item_text += f" - {p.get('disambiguation')}"
            item = QtWidgets.QListWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, p)
            list_widget.addItem(item)
        layout.addWidget(list_widget)
        
        btn_layout = QtWidgets.QHBoxLayout()
        select_btn = QtWidgets.QPushButton("Add Selected")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_layout.addWidget(select_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        select_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            selected_items = list_widget.selectedItems()
            for item in selected_items:
                p = item.data(QtCore.Qt.ItemDataRole.UserRole)
                p_id = p.get("id")
                p_name = p.get("name", "Unknown")
                if p_id not in self.selected_performers:
                    self.selected_performers[p_id] = p_name
                    self.performer_list.addItem(f"{p_name} (ID: {p_id})")
            self._log(f"Added {len(selected_items)} performers to selection.")

    def on_clear_performers(self):
        self.selected_performers.clear()
        self.performer_list.clear()
        self._log("Cleared performer selection.")

    def on_search_studios(self):
        try:
            self.client = self._build_client()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Config error", str(e))
            return
        studio_name = self.studio_search_edit.text().strip()
        if not studio_name:
            QtWidgets.QMessageBox.warning(self, "Missing", "Please enter a studio name to search.")
            return
        worker = FetchStudiosWorker(self.client, studio_name)
        worker.signals.result.connect(self._on_studios_found)
        worker.signals.error.connect(lambda e: (self._log("Error: " + e), QtWidgets.QMessageBox.critical(self, "GraphQL error", e)))
        worker.signals.progress.connect(self.progress.setValue)
        worker.signals.status.connect(self._log)
        self.pool.start(worker)
        self._log("Started searching studios...")

    def _on_studios_found(self, result):
        count = result.get("count", 0)
        studios = result.get("studios", [])
        self._log(f"Found {count} studios matching search.")
        
        if not studios:
            QtWidgets.QMessageBox.information(self, "No results", "No studios found matching your search.")
            return
        
        # Show dialog to select ONE studio
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Studio")
        dialog.setMinimumSize(500, 400)
        layout = QtWidgets.QVBoxLayout(dialog)
        
        label = QtWidgets.QLabel(f"Found {count} studios. Select ONE studio to filter scenes:")
        layout.addWidget(label)
        
        list_widget = QtWidgets.QListWidget()
        list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        for s in studios:
            parent_info = ""
            if s.get('parent_studio'):
                parent_info = f" (Parent: {s['parent_studio'].get('name', 'Unknown')})"
            item_text = f"{s.get('name', 'Unknown')} (ID: {s.get('id')}, Scenes: {s.get('scene_count', 0)}){parent_info}"
            item = QtWidgets.QListWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, s)
            list_widget.addItem(item)
        layout.addWidget(list_widget)
        
        btn_layout = QtWidgets.QHBoxLayout()
        select_btn = QtWidgets.QPushButton("Select Studio")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_layout.addWidget(select_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        select_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            selected_items = list_widget.selectedItems()
            if selected_items:
                s = selected_items[0].data(QtCore.Qt.ItemDataRole.UserRole)
                self.selected_studio = {"id": s.get("id"), "name": s.get("name", "Unknown")}
                self.studio_label.setText(f"Studio: {self.selected_studio['name']}")
                self._log(f"Selected studio: {self.selected_studio['name']} (ID: {self.selected_studio['id']})")

    def on_clear_studio(self):
        self.selected_studio = None
        self.studio_label.setText("No studio selected")
        self._log("Cleared studio selection.")

    def on_column_visibility(self):
        """Show dialog to select which columns to display and reorder them"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Show/Hide & Reorder Columns")
        dialog.setMinimumSize(400, 500)
        layout = QtWidgets.QVBoxLayout(dialog)
        
        label = QtWidgets.QLabel("Select and reorder columns to display:")
        layout.addWidget(label)
        
        # Create a list widget for drag-drop reordering
        list_widget = QtWidgets.QListWidget()
        list_widget.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        
        # Populate with currently visible columns in their current order
        for col_idx in self.table_model._visible_columns:
            col_name = self.table_model.ALL_COLUMNS[col_idx]
            item = QtWidgets.QListWidgetItem(col_name)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, col_idx)
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.CheckState.Checked)
            # Disable dragging for "Select" column (must stay first)
            if col_idx == 0:
                item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsDragEnabled & ~QtCore.Qt.ItemFlag.ItemIsDropEnabled)
                item.setToolTip("Select column must always be first and visible")
            list_widget.addItem(item)
        
        # Add unchecked items for hidden columns at the end
        for col_idx, col_name in enumerate(self.table_model.ALL_COLUMNS):
            if col_idx not in self.table_model._visible_columns and col_idx != 0:
                item = QtWidgets.QListWidgetItem(col_name)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, col_idx)
                item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                list_widget.addItem(item)
        
        layout.addWidget(list_widget)
        
        # Up/Down buttons for alternative reordering method
        reorder_layout = QtWidgets.QHBoxLayout()
        move_up_btn = QtWidgets.QPushButton("Move Up")
        move_down_btn = QtWidgets.QPushButton("Move Down")
        reorder_layout.addWidget(move_up_btn)
        reorder_layout.addWidget(move_down_btn)
        layout.addLayout(reorder_layout)
        
        def move_up():
            current_row = list_widget.currentRow()
            if current_row > 1:  # Can't move above row 1 (row 0 is Select, always first)
                item = list_widget.takeItem(current_row)
                list_widget.insertItem(current_row - 1, item)
                list_widget.setCurrentRow(current_row - 1)
        
        def move_down():
            current_row = list_widget.currentRow()
            if current_row >= 1 and current_row < list_widget.count() - 1:  # Row 0 is Select, can't move
                item = list_widget.takeItem(current_row)
                list_widget.insertItem(current_row + 1, item)
                list_widget.setCurrentRow(current_row + 1)
        
        move_up_btn.clicked.connect(move_up)
        move_down_btn.clicked.connect(move_down)
        
        # Apply/Cancel buttons
        btn_layout = QtWidgets.QHBoxLayout()
        apply_btn = QtWidgets.QPushButton("Apply")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        apply_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # Build new visible columns list based on order and check state
            new_visible = []
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item.checkState() == QtCore.Qt.CheckState.Checked:
                    col_idx = item.data(QtCore.Qt.ItemDataRole.UserRole)
                    new_visible.append(col_idx)
            
            # Ensure "Select" column is always first
            if 0 not in new_visible:
                new_visible.insert(0, 0)
            elif new_visible[0] != 0:
                new_visible.remove(0)
                new_visible.insert(0, 0)
            
            self.table_model.set_visible_columns(new_visible)
            self._log(f"Column visibility and order updated. Showing {len(new_visible)} columns.")

    def _on_scenes_found(self, result):
        count = result.get("count", 0)
        scenes = result.get("scenes", [])
        
        self._log(f"GraphQL query returned {count} total scenes, fetched {len(scenes)} scenes.")
        
        # Apply file size filters client-side if enabled
        if self.enable_filesize_filter_checkbox.isChecked():
            # Map combo box index to operator
            operator_map = {
                0: "EQUALS",
                1: "NOT_EQUALS",
                2: "GREATER_THAN",
                3: "GREATER_THAN",  # >= will be handled as >
                4: "LESS_THAN",
                5: "LESS_THAN",  # <= will be handled as <
                6: "BETWEEN"
            }
            operator_index = self.filesize_operator_combo.currentIndex()
            filesize_operator = operator_map[operator_index]
            
            value1_input = self.filesize_value1_edit.text().strip()
            if not value1_input:
                QtWidgets.QMessageBox.warning(self, "Missing value", 
                    "Please enter a file size value.")
                return
            
            unit1 = self.filesize_unit1_combo.currentText()
            filesize_value1 = parse_filesize_input(value1_input, unit1)
            if filesize_value1 is None:
                QtWidgets.QMessageBox.warning(self, "Invalid file size", 
                    f"Invalid file size format: '{value1_input}'. Use a number.")
                return
            
            filesize_value2 = None
            if filesize_operator == "BETWEEN":
                value2_input = self.filesize_value2_edit.text().strip()
                if not value2_input:
                    QtWidgets.QMessageBox.warning(self, "Missing value", 
                        "Please enter a second file size value for 'between' operator.")
                    return
                
                unit2 = self.filesize_unit2_combo.currentText()
                filesize_value2 = parse_filesize_input(value2_input, unit2)
                if filesize_value2 is None:
                    QtWidgets.QMessageBox.warning(self, "Invalid file size", 
                        f"Invalid file size format: '{value2_input}'. Use a number.")
                    return
            
            # Filter scenes based on operator
            def size_ok(s):
                fs = s.get("_filesize")
                if fs is None:
                    return False  # Exclude scenes with no file size info when filter is active
                
                if filesize_operator == "EQUALS":
                    return fs == filesize_value1
                elif filesize_operator == "NOT_EQUALS":
                    return fs != filesize_value1
                elif filesize_operator == "GREATER_THAN":
                    return fs > filesize_value1
                elif filesize_operator == "LESS_THAN":
                    return fs < filesize_value1
                elif filesize_operator == "BETWEEN":
                    return filesize_value1 <= fs <= filesize_value2
                return True
            
            before_filesize_filter = len(scenes)
            filtered = [s for s in scenes if size_ok(s)]
            scenes_filtered_by_size = before_filesize_filter - len(filtered)
            
            operator_text = self.filesize_operator_combo.currentText().split()[0]
            if filesize_operator == "BETWEEN":
                self._log(f"File size filter applied: BETWEEN {human_size(filesize_value1)} and {human_size(filesize_value2)} - filtered out {scenes_filtered_by_size} scenes")
            else:
                self._log(f"File size filter applied: {operator_text} {human_size(filesize_value1)} - filtered out {scenes_filtered_by_size} scenes")
        else:
            filtered = scenes
        
        self.last_scenes = filtered
        self.table_model.setScenes(filtered)
        
        # Improved logging to show both server count and filtered count
        if len(scenes) < count:
            self._log(f"GraphQL returned {len(scenes)} of {count} total scenes (limited by per_page setting).")
        else:
            self._log(f"GraphQL returned all {len(scenes)} scenes.")
        
        if len(filtered) < len(scenes):
            self._log(f"After client-side file size filter: showing {len(filtered)} of {len(scenes)} fetched scenes.")
        else:
            self._log(f"Showing all {len(filtered)} scenes.")
        
        # auto-select all shown by default
        self.table_model.select_all(True)

    def on_apply_tag(self):
        if not self.last_tag_id:
            reply = QtWidgets.QMessageBox.question(self, "No tag ID",
                                                   "No Tag ID found. Do you want to fetch tag ID first?",
                                                   QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self.on_get_tag()
            return
        selected = self.table_model.get_selected_scenes()
        if not selected:
            QtWidgets.QMessageBox.warning(self, "No selection", "No scenes selected to update.")
            return
        dry_run = bool(self.dryrun_checkbox.isChecked())
        worker = ApplyTagWorker(self.client, selected, self.last_tag_id, dry_run=dry_run)
        worker.signals.result.connect(self._on_update_summary)
        worker.signals.error.connect(lambda e: self._log("Error: " + e))
        worker.signals.progress.connect(self.progress.setValue)
        worker.signals.status.connect(self._log)
        self.pool.start(worker)
        self._log("Started updating scenes...")

    def _on_update_summary(self, summary):
        self._log("Summary: " + json.dumps(summary))
        QtWidgets.QMessageBox.information(self, "Done", f"Summary:\nUpdated: {summary.get('updated')}\n"
                                                        f"Already tagged: {summary.get('already_tagged')}\n"
                                                        f"Skipped deleted: {summary.get('skipped_deleted')}\n"
                                                        f"Failed: {summary.get('failed')}")

    def on_rename_scenes(self):
        """Rename selected scenes to a new title"""
        new_title = self.rename_input.text().strip()
        if not new_title:
            QtWidgets.QMessageBox.warning(self, "Missing title", "Please enter a new title for the selected scenes.")
            return

        selected = self.table_model.get_selected_scenes()
        if not selected:
            QtWidgets.QMessageBox.warning(self, "No selection", "No scenes selected to rename.")
            return

        # Confirm rename operation
        count = len(selected)
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Rename",
            f"Rename {count} selected scene(s) to:\n\"{new_title}\"\n\nContinue?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        dry_run = bool(self.dryrun_checkbox.isChecked())
        worker = RenameSceneWorker(self.client, selected, new_title, dry_run=dry_run)
        worker.signals.result.connect(self._on_rename_summary)
        worker.signals.error.connect(lambda e: self._log("Error: " + e))
        worker.signals.progress.connect(self.progress.setValue)
        worker.signals.status.connect(self._log)
        self.pool.start(worker)
        self._log(f"Started renaming {count} scenes to '{new_title}'...")

    def _on_rename_summary(self, summary):
        """Handle rename operation summary"""
        self._log("Rename Summary: " + json.dumps(summary))
        QtWidgets.QMessageBox.information(
            self,
            "Rename Complete",
            f"Summary:\nRenamed: {summary.get('updated')}\n"
            f"Skipped deleted: {summary.get('skipped_deleted')}\n"
            f"Failed: {summary.get('failed')}"
        )
        # Refresh the results to show new titles
        if summary.get('updated', 0) > 0 and not self.dryrun_checkbox.isChecked():
            self._log("Refreshing results to show updated titles...")
            self.on_search_scenes()

    def on_assign_performers(self):
        """Assign performers to selected scenes"""
        selected = self.table_model.get_selected_scenes()
        if not selected:
            QtWidgets.QMessageBox.warning(self, "No selection", "No scenes selected to update.")
            return
        
        # Show dialog to search and select performers
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Assign Performers to Selected Scenes")
        dialog.setMinimumSize(500, 400)
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Search field
        search_layout = QtWidgets.QHBoxLayout()
        search_label = QtWidgets.QLabel("Search performers:")
        search_edit = QtWidgets.QLineEdit()
        search_edit.setPlaceholderText("Enter performer name to search")
        search_btn = QtWidgets.QPushButton("Search")
        search_layout.addWidget(search_label)
        search_layout.addWidget(search_edit)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)
        
        # List widget for results
        list_widget = QtWidgets.QListWidget()
        list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)
        layout.addWidget(list_widget)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        assign_btn = QtWidgets.QPushButton("Assign Selected Performers")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_layout.addWidget(assign_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        # Track performers
        performers_data = []
        
        def do_search():
            try:
                self.client = self._build_client()
            except Exception as e:
                QtWidgets.QMessageBox.critical(dialog, "Config error", str(e))
                return
            
            performer_name = search_edit.text().strip()
            if not performer_name:
                QtWidgets.QMessageBox.warning(dialog, "Missing", "Please enter a performer name to search.")
                return
            
            # Use FetchPerformersWorker
            worker = FetchPerformersWorker(self.client, performer_name)
            
            def on_performers_found(result):
                count = result.get("count", 0)
                performers = result.get("performers", [])
                self._log(f"Found {count} performers matching '{performer_name}'")
                
                if not performers:
                    QtWidgets.QMessageBox.information(dialog, "No results", "No performers found matching your search.")
                    return
                
                list_widget.clear()
                performers_data.clear()
                for p in performers:
                    item_text = f"{p.get('name', 'Unknown')} (ID: {p.get('id')}, Scenes: {p.get('scene_count', 0)})"
                    if p.get('disambiguation'):
                        item_text += f" - {p.get('disambiguation')}"
                    item = QtWidgets.QListWidgetItem(item_text)
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, p)
                    list_widget.addItem(item)
                    performers_data.append(p)
            
            worker.signals.result.connect(on_performers_found)
            worker.signals.error.connect(lambda e: QtWidgets.QMessageBox.critical(dialog, "Search error", e))
            worker.signals.progress.connect(self.progress.setValue)
            worker.signals.status.connect(self._log)
            self.pool.start(worker)
        
        search_btn.clicked.connect(do_search)
        search_edit.returnPressed.connect(do_search)
        
        def do_assign():
            selected_items = list_widget.selectedItems()
            if not selected_items:
                QtWidgets.QMessageBox.warning(dialog, "No selection", "Please select at least one performer to assign.")
                return
            
            # Get performer IDs
            performer_ids = [item.data(QtCore.Qt.ItemDataRole.UserRole).get("id") for item in selected_items]
            performer_names = [item.data(QtCore.Qt.ItemDataRole.UserRole).get("name", "Unknown") for item in selected_items]
            
            self._log(f"Assigning {len(performer_ids)} performer(s) to {len(selected)} scene(s): {', '.join(performer_names)}")
            
            dry_run = bool(self.dryrun_checkbox.isChecked())
            worker = AssignPerformersWorker(self.client, selected, performer_ids, dry_run=dry_run)
            worker.signals.result.connect(self._on_performer_assignment_summary)
            worker.signals.error.connect(lambda e: self._log("Error: " + e))
            worker.signals.progress.connect(self.progress.setValue)
            worker.signals.status.connect(self._log)
            self.pool.start(worker)
            
            dialog.accept()
        
        assign_btn.clicked.connect(do_assign)
        cancel_btn.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def _on_performer_assignment_summary(self, summary):
        self._log("Performer assignment summary: " + json.dumps(summary))
        QtWidgets.QMessageBox.information(self, "Done", f"Summary:\nUpdated: {summary.get('updated')}\n"
                                                        f"Already assigned: {summary.get('already_assigned')}\n"
                                                        f"Skipped deleted: {summary.get('skipped_deleted')}\n"
                                                        f"Failed: {summary.get('failed')}")
    
    def on_assign_studio(self):
        """Assign studio to selected scenes"""
        selected = self.table_model.get_selected_scenes()
        if not selected:
            QtWidgets.QMessageBox.warning(self, "No selection", "No scenes selected to update.")
            return
        
        # Check if a studio is selected
        if not self.selected_studio:
            QtWidgets.QMessageBox.warning(self, "No studio selected", 
                                         "Please search for and select a studio first using the Studio search section above.")
            return
        
        studio_id = self.selected_studio.get("id")
        studio_name = self.selected_studio.get("name", "Unknown")
        
        # Confirm assignment
        reply = QtWidgets.QMessageBox.question(
            self, 
            "Confirm Studio Assignment",
            f"Assign studio '{studio_name}' to {len(selected)} selected scene(s)?\n\n"
            f"This will REPLACE any existing studio assignments.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        
        try:
            self.client = self._build_client()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Config error", str(e))
            return
        
        self._log(f"Assigning studio '{studio_name}' to {len(selected)} scene(s)...")
        
        dry_run = bool(self.dryrun_checkbox.isChecked())
        worker = AssignStudioWorker(self.client, selected, studio_id, dry_run=dry_run)
        worker.signals.result.connect(self._on_studio_assignment_summary)
        worker.signals.error.connect(lambda e: self._log("Error: " + e))
        worker.signals.progress.connect(self.progress.setValue)
        worker.signals.status.connect(self._log)
        self.pool.start(worker)
    
    def _on_studio_assignment_summary(self, summary):
        self._log("Studio assignment summary: " + json.dumps(summary))
        QtWidgets.QMessageBox.information(self, "Done", f"Summary:\nUpdated: {summary.get('updated')}\n"
                                                        f"Already assigned: {summary.get('already_assigned')}\n"
                                                        f"Skipped deleted: {summary.get('skipped_deleted')}\n"
                                                        f"Failed: {summary.get('failed')}")

    def on_export_csv(self):
        selected = self.table_model.get_selected_scenes()
        if not selected:
            QtWidgets.QMessageBox.warning(self, "No selection", "No scenes selected to export.")
            return
        fname, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save CSV", os.path.expanduser("~/scenes_export.csv"), "CSV files (*.csv);;All files (*)")
        if not fname:
            return
        try:
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["id", "title", "tag_ids", "tag_names", "file_size"])
                for s in selected:
                    tag_ids = ",".join([t.get("id") for t in s.get("tags", [])]) if s.get("tags") else ""
                    tag_names = ",".join([t.get("name") for t in s.get("tags", [])]) if s.get("tags") else ""
                    fs = s.get("_filesize")
                    writer.writerow([s.get("id"), s.get("title"), tag_ids, tag_names, "" if fs is None else str(fs)])
            self._log(f"Exported {len(selected)} scenes to {fname}")
            QtWidgets.QMessageBox.information(self, "Export complete", f"Wrote {len(selected)} rows to {fname}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export failed", str(e))
            self._log("Export failed: " + str(e))

    def on_import_csv(self):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open CSV", os.path.expanduser("~"), "CSV files (*.csv);;All files (*)")
        if not fname:
            return
        try:
            ids = set()
            with open(fname, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                # support both 'id' column and first column fallback
                for row in reader:
                    if "id" in row and row["id"].strip():
                        ids.add(row["id"].strip())
                    else:
                        # try first column if 'id' header missing
                        vals = list(row.values())
                        if vals and vals[0].strip():
                            ids.add(vals[0].strip())
            if not ids:
                QtWidgets.QMessageBox.warning(self, "No ids found", "No scene ids were found in the CSV.")
                return
            self.table_model.select_by_ids(ids)
            self._log(f"Selected scenes from CSV: {len(ids)} ids applied (only those present in current results will be selected).")
            QtWidgets.QMessageBox.information(self, "Import complete", f"Marked rows matching {len(ids)} ids (within current results).")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import failed", str(e))
            self._log("Import failed: " + str(e))

# ----------------------------
# Main
# ----------------------------
def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()