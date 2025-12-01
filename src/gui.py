import sys
import re
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QSplitter,
    QLineEdit,
    QMessageBox,
    QHeaderView,
    QFileDialog,
    QPlainTextEdit,
    QToolBar,
    QFrame,
    QTextEdit,
    QDialog,
    QCheckBox,
    QDialogButtonBox,
    QFormLayout,
    QAbstractItemView,
    QSlider,
    QSpinBox,
    QCompleter,
    QDockWidget,
    QTreeWidget,
    QTreeWidgetItem,
)
from PySide6.QtCore import Qt, QTimer, QRect, QSize, QPoint, QStringListModel
from PySide6.QtGui import (
    QFont,
    QColor,
    QPainter,
    QTextFormat,
    QSyntaxHighlighter,
    QTextCharFormat,
    QAction,
    QIcon,
    QBrush,
    QTextCursor,
    QKeySequence,
)

from emulator import PicoEmulator

# --- COLOR PALETTE (Dracula Inspired) ---
COLORS = {
    "bg": "#282a36",
    "fg": "#f8f8f2",
    "current_line": "#44475a",
    "executing_line": "#005f00",  # Dark Green
    "comment": "#6272a4",
    "cyan": "#8be9fd",
    "green": "#50fa7b",
    "orange": "#ffb86c",
    "pink": "#ff79c6",
    "purple": "#bd93f9",
    "red": "#ff5555",
    "yellow": "#f1fa8c",
    "selection": "#44475a",
    "input_bg": "#44475a",
    "modal_bg": "#343746",
    "breakpoint": "#ff5555",
}

# --- OPCODE REFERENCE DATA ---
# Removed JMP, CMP, BLT as requested
OPCODE_REF = [
    ("MOV", "MOV Dest, Src", "Copy value from Src to Dest"),
    ("ADD", "ADD Dest, Src1, Src2", "Dest = Src1 + Src2"),
    ("SUB", "SUB Dest, Src1, Src2", "Dest = Src1 - Src2"),
    ("MUL", "MUL Dest, Src1, Src2", "Dest = Src1 * Src2"),
    ("DIV", "DIV Dest, Src1, Src2", "Dest = Src1 // Src2"),
    ("IN", "IN Addr, Count", "Read 'Count' inputs into Addr"),
    ("OUT", "OUT Addr, Count", "Print 'Count' values from Addr"),
    ("BEQ", "BEQ Val1, Val2, Label", "Branch to Label if Val1 == Val2"),
    ("BGT", "BGT Val1, Val2, Label", "Branch to Label if Val1 > Val2"),
    ("JSR", "JSR Label", "Jump to Subroutine"),
    ("RTS", "RTS", "Return from Subroutine"),
    ("STOP", "STOP [Val]", "End Execution"),
    ("ORG", "ORG Address", "Set starting memory address"),
]


# --- SETTINGS DIALOG ---
class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(300, 150)
        self.settings = settings if settings else {}

        self.setStyleSheet(
            f"""
            QDialog {{ background-color: {COLORS['modal_bg']}; color: {COLORS['fg']}; }}
            QLabel {{ color: {COLORS['fg']}; font-size: 14px; }}
            QCheckBox {{ color: {COLORS['fg']}; spacing: 5px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; }}
        """
        )

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.cb_highlight = QCheckBox()
        self.cb_highlight.setChecked(self.settings.get("highlight_execution", True))

        lbl = QLabel("Highlight Executing Line:")
        form_layout.addRow(lbl, self.cb_highlight)

        layout.addLayout(form_layout)
        layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self):
        return {"highlight_execution": self.cb_highlight.isChecked()}


# --- SYNTAX HIGHLIGHTER ---
class AssemblyHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        keywords = [x[0] for x in OPCODE_REF]
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor(COLORS["pink"]))
        keyword_format.setFontWeight(QFont.Bold)
        for word in keywords:
            pattern = rf"\b{word}\b"
            self.highlighting_rules.append(
                (re.compile(pattern, re.IGNORECASE), keyword_format)
            )

        label_format = QTextCharFormat()
        label_format.setForeground(QColor(COLORS["green"]))
        self.highlighting_rules.append((re.compile(r"^[A-Z_0-9]+:"), label_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor(COLORS["purple"]))
        self.highlighting_rules.append((re.compile(r"\b\d+\b"), number_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor(COLORS["comment"]))
        self.highlighting_rules.append((re.compile(r";.*"), comment_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), format)


# --- CUSTOM EDITOR ---
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.lineNumberAreaPaintEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            y_pos = event.pos().y()
            cursor = self.editor.cursorForPosition(QPoint(0, y_pos))
            block = cursor.block()
            line_num = block.blockNumber()
            self.editor.toggle_breakpoint(line_num)
        super().mousePressEvent(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_lines)
        self.update_line_number_area_width(0)

        self.execution_line_index = -1
        self.show_execution_highlight = True
        self.breakpoints = set()

        font = QFont("Consolas", 12)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.highlight_lines()

        # Autocomplete Setup
        self.completer = None
        self.setup_completer()

    def setup_completer(self):
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)

        # Build keyword list
        keywords = [x[0] for x in OPCODE_REF]
        keywords += ["M", "N", "R", "A", "B", "I", "J"]
        self.completer.setModel(QStringListModel(keywords, self.completer))
        self.completer.activated.connect(self.insert_completion)

    def insert_completion(self, completion):
        if self.completer.widget() != self:
            return

        tc = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)

    def text_under_cursor(self):
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)
        return tc.selectedText()

    def focusInEvent(self, event):
        if self.completer:
            self.completer.setWidget(self)
        super().focusInEvent(event)

    def keyPressEvent(self, event):
        # 1. Handle Autocomplete Key Logic
        if self.completer and self.completer.popup().isVisible():
            if event.key() in (
                Qt.Key_Tab,
            ):
                event.ignore()
                return

        # 2. Smart Indentation logic
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            cursor = self.textCursor()
            current_line = cursor.block().text()
            indentation = ""
            match = re.match(r"^(\s+)", current_line)
            if match:
                indentation = match.group(1)

            # Use default handling for the newline, then insert spaces
            super().keyPressEvent(event)
            self.insertPlainText(indentation)
            return

        is_shortcut = (
            event.modifiers() & Qt.ControlModifier
        ) and event.key() == Qt.Key_Space
        if not self.completer or not is_shortcut:
            super().keyPressEvent(event)

        # 3. Trigger Autocomplete Popup
        ctrl_or_shift = event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)
        if not self.completer or (ctrl_or_shift and len(event.text()) == 0):
            return

        eow = "~!@#$%^&*()_+{}|:\"<>?,./;'[]\\-="
        has_modifier = (event.modifiers() != Qt.NoModifier) and not ctrl_or_shift

        completion_prefix = self.text_under_cursor()

        if not is_shortcut and (
            has_modifier
            or not event.text()
            or len(completion_prefix) < 1
            or event.text()[-1] in eow
        ):
            self.completer.popup().hide()
            return

        if completion_prefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completion_prefix)
            self.completer.popup().setCurrentIndex(
                self.completer.completionModel().index(0, 0)
            )

        cr = self.cursorRect()
        cr.setWidth(
            self.completer.popup().sizeHintForColumn(0)
            + self.completer.popup().verticalScrollBar().sizeHint().width()
        )
        self.completer.complete(cr)

    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        space = 3 + self.fontMetrics().horizontalAdvance("9") * digits
        return space + 20

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(
                0, rect.y(), self.line_number_area.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def toggle_breakpoint(self, line_num):
        if line_num in self.breakpoints:
            self.breakpoints.remove(line_num)
        else:
            self.breakpoints.add(line_num)
        self.line_number_area.update()

    def set_execution_line(self, line_idx):
        self.execution_line_index = line_idx
        self.highlight_lines()
        if line_idx >= 0:
            block = self.document().findBlockByNumber(line_idx)
            cursor = self.textCursor()
            cursor.setPosition(block.position())
            self.ensureCursorVisible()

    def highlight_lines(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor(COLORS["current_line"])
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

            if self.show_execution_highlight and self.execution_line_index >= 0:
                exec_selection = QTextEdit.ExtraSelection()
                exec_color = QColor(COLORS["executing_line"])
                exec_selection.format.setBackground(exec_color)
                exec_selection.format.setProperty(QTextFormat.FullWidthSelection, True)

                block = self.document().findBlockByNumber(self.execution_line_index)
                cursor = self.textCursor()
                cursor.setPosition(block.position())

                exec_selection.cursor = cursor
                exec_selection.cursor.clearSelection()
                extra_selections.append(exec_selection)

        self.setExtraSelections(extra_selections)

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#21222c"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        height = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor(COLORS["comment"]))

                if block_number in self.breakpoints:
                    painter.setBrush(QBrush(QColor(COLORS["breakpoint"])))
                    painter.setPen(Qt.NoPen)
                    radius = height / 3
                    cy = top + height / 2 - 2
                    cx = 8
                    painter.drawEllipse(QPoint(int(cx), int(cy)), radius, radius)
                    painter.setPen(QColor(COLORS["fg"]))

                if (
                    block_number == self.execution_line_index
                    and self.show_execution_highlight
                ):
                    painter.setPen(QColor(COLORS["green"]))
                    painter.setFont(QFont("Consolas", 10, QFont.Bold))
                else:
                    painter.setFont(QFont("Consolas", 10))

                painter.drawText(
                    0,
                    int(top),
                    self.line_number_area.width() - 5,
                    height,
                    Qt.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1


# --- REFERENCE DOCK WIDGET ---
class ReferenceDock(QDockWidget):
    def __init__(self, parent=None, editor=None):
        super().__init__("Instruction Set", parent)
        self.editor = editor
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)

        # Create Tree Widget
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Opcode", "Description"])
        self.tree.setColumnWidth(0, 70)
        self.tree.setStyleSheet(
            f"""
            QTreeWidget {{
                background-color: {COLORS['bg']};
                color: {COLORS['fg']};
                border: none;
            }}
            QHeaderView::section {{
                background-color: {COLORS['current_line']};
                color: {COLORS['cyan']};
                padding: 4px;
            }}
            QTreeWidget::item:hover {{ background-color: {COLORS['current_line']}; }}
            QTreeWidget::item:selected {{ background-color: {COLORS['selection']}; }}
        """
        )

        for op, syntax, desc in OPCODE_REF:
            item = QTreeWidgetItem([op, desc])
            # Store syntax in data for tooltip or insertion
            item.setData(0, Qt.UserRole, syntax)
            item.setToolTip(0, syntax)
            item.setToolTip(1, desc)
            # Color styling
            item.setForeground(0, QBrush(QColor(COLORS["pink"])))
            self.tree.addTopLevelItem(item)

        self.tree.itemDoubleClicked.connect(self.insert_instruction)
        self.setWidget(self.tree)

    def insert_instruction(self, item, column):
        if not self.editor:
            return
        # Insert the Opcode text
        opcode = item.text(0)
        self.editor.insertPlainText(opcode + " ")
        self.editor.setFocus()


# --- MAIN WINDOW ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PicoComputer IDE")
        self.resize(1300, 800)
        self.setWindowIcon(QIcon.fromTheme("system-run"))

        self.emu = PicoEmulator()
        self.timer = QTimer()
        self.timer.timeout.connect(self.step_execution)

        self.current_file_path = None
        self.table_items_cache = {}
        self.pc_to_line_map = {}
        self.is_auto_running = False
        self.cycle_count = 0

        # Tracking "Dirty" state to ensure we always run latest code
        self.is_code_dirty = True
        self.program_entry_point = 0

        self.app_settings = {"highlight_execution": True}

        self.apply_styles()
        self.setup_ui()
        self.load_default_code()

        # Connect editor change to dirty flag
        self.editor.textChanged.connect(self.on_code_changed)

    def apply_styles(self):
        qss = f"""
            QMainWindow {{ background-color: {COLORS['bg']}; color: {COLORS['fg']}; }}
            QWidget {{ color: {COLORS['fg']}; font-family: 'Segoe UI', sans-serif; font-size: 14px; }}
            
            QPlainTextEdit, QTextEdit {{ 
                background-color: {COLORS['bg']}; 
                color: {COLORS['fg']}; 
                border: none;
            }}
            
            QTableWidget {{ 
                background-color: {COLORS['bg']}; 
                gridline-color: {COLORS['current_line']};
                border: 1px solid {COLORS['current_line']};
                selection-background-color: {COLORS['selection']};
                color: {COLORS['fg']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['current_line']};
                color: {COLORS['cyan']};
                padding: 4px;
                border: 1px solid {COLORS['bg']};
            }}
            
            QLineEdit, QSpinBox {{ 
                background-color: {COLORS['input_bg']}; 
                border: 1px solid {COLORS['comment']}; 
                border-radius: 4px; 
                padding: 5px; 
                color: {COLORS['fg']};
            }}
            
            QSlider::groove:horizontal {{
                border: 1px solid {COLORS['current_line']};
                height: 8px;
                background: {COLORS['bg']};
                margin: 2px 0;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {COLORS['cyan']};
                border: 1px solid {COLORS['cyan']};
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }}
            
            QPushButton {{
                background-color: {COLORS['current_line']};
                color: {COLORS['cyan']};
                border: 1px solid {COLORS['comment']};
                border-radius: 4px; 
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {COLORS['comment']}; }}
            QPushButton:pressed {{ background-color: {COLORS['cyan']}; color: {COLORS['bg']}; }}
            QPushButton:disabled {{ color: {COLORS['comment']}; border-color: #333; }}
            
            QSplitter::handle {{ background-color: {COLORS['current_line']}; }}
            
            QDockWidget {{
                titlebar-close-icon: url(close.png);
                titlebar-normal-icon: url(undock.png);
            }}
            QDockWidget::title {{
                text-align: left;
                background: {COLORS['current_line']};
                padding-left: 5px;
            }}
        """
        self.setStyleSheet(qss)

    def setup_ui(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_act = QAction("Open", self)
        open_act.triggered.connect(self.open_file)
        toolbar.addAction(open_act)

        save_act = QAction("Save", self)
        save_act.triggered.connect(self.save_file)
        toolbar.addAction(save_act)

        toolbar.addSeparator()

        settings_act = QAction("Settings", self)
        settings_act.triggered.connect(self.open_settings)
        toolbar.addAction(settings_act)

        toolbar.addSeparator()

        self.act_load = QAction("Build/Load", self)
        self.act_load.triggered.connect(self.load_program)
        toolbar.addAction(self.act_load)

        self.act_run = QAction("Run", self)
        self.act_run.setShortcut("F5")
        self.act_run.triggered.connect(self.toggle_run)
        # We start enabled so user can click run to auto-build
        self.act_run.setEnabled(True)
        toolbar.addAction(self.act_run)

        self.act_step = QAction("Step", self)
        self.act_step.setShortcut("F10")
        self.act_step.triggered.connect(self.manual_step)
        self.act_step.setEnabled(False)  # Step needs valid build first
        toolbar.addAction(self.act_step)

        # --- SPEED CONTROLS START ---
        toolbar.addSeparator()

        lbl_speed = QLabel(" Delay (ms): ")
        lbl_speed.setStyleSheet(f"color: {COLORS['fg']}")
        toolbar.addWidget(lbl_speed)

        self.slider_speed = QSlider(Qt.Horizontal)
        self.slider_speed.setRange(10, 1000)
        self.slider_speed.setValue(100)
        self.slider_speed.setFixedWidth(100)
        self.slider_speed.valueChanged.connect(self.change_speed_from_slider)
        toolbar.addWidget(self.slider_speed)

        self.spin_speed = QSpinBox()
        self.spin_speed.setRange(10, 1000)
        self.spin_speed.setValue(100)
        self.spin_speed.setFixedWidth(60)
        self.spin_speed.valueChanged.connect(self.change_speed_from_spin)
        toolbar.addWidget(self.spin_speed)
        # --- SPEED CONTROLS END ---

        toolbar.addSeparator()

        # Hard Reset (The only Reset now)
        reset_act = QAction("Reset", self)
        reset_act.setToolTip("Restart program from entry point")
        reset_act.triggered.connect(self.reset_program)
        toolbar.addAction(reset_act)

        # View Toggle for Dock
        toolbar.addSeparator()
        self.view_dock_act = QAction("Ref", self)
        self.view_dock_act.setCheckable(True)
        self.view_dock_act.setChecked(True)
        self.view_dock_act.triggered.connect(self.toggle_dock)
        toolbar.addAction(self.view_dock_act)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Horizontal)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)

        lbl_code = QLabel("ASSEMBLY SOURCE")
        lbl_code.setStyleSheet(
            f"color: {COLORS['orange']}; font-weight: bold; letter-spacing: 1px;"
        )
        left_layout.addWidget(lbl_code)

        self.editor = CodeEditor()
        self.highlighter = AssemblyHighlighter(self.editor.document())
        left_layout.addWidget(self.editor)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)

        status_frame = QFrame()
        status_frame.setStyleSheet(
            f"background-color: {COLORS['current_line']}; border-radius: 5px;"
        )
        status_layout = QHBoxLayout(status_frame)

        self.lbl_status = QLabel("IDLE")
        self.lbl_status.setStyleSheet(f"color: {COLORS['pink']}; font-weight: bold;")

        self.lbl_cycles = QLabel("CYCLES: 0")
        self.lbl_cycles.setStyleSheet(
            f"color: {COLORS['yellow']}; font-family: Consolas;"
        )

        self.lbl_pc = QLabel("PC: 000")
        self.lbl_pc.setStyleSheet(f"color: {COLORS['cyan']}; font-family: Consolas;")

        status_layout.addWidget(QLabel("STATUS:"))
        status_layout.addWidget(self.lbl_status)
        status_layout.addStretch()
        status_layout.addWidget(self.lbl_cycles)
        status_layout.addSpacing(20)
        status_layout.addWidget(self.lbl_pc)
        right_layout.addWidget(status_frame)

        # Memory Table Configuration
        right_layout.addWidget(QLabel("MEMORY WATCH (Double-click Value to Edit)"))
        self.mem_table = QTableWidget()
        self.mem_table.setColumnCount(3)
        self.mem_table.setHorizontalHeaderLabels(["VAR", "ADDR", "VAL"])
        self.mem_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mem_table.verticalHeader().setVisible(False)
        self.mem_table.setShowGrid(False)
        self.mem_table.setAlternatingRowColors(True)
        self.mem_table.setStyleSheet(f"alternate-background-color: #2e303e;")

        self.mem_table.itemChanged.connect(self.handle_memory_edit)

        right_layout.addWidget(self.mem_table)

        right_layout.addWidget(QLabel("TERMINAL OUTPUT"))
        self.console_out = QTextEdit()
        self.console_out.setReadOnly(True)
        self.console_out.setFont(QFont("Consolas", 10))
        self.console_out.setStyleSheet(
            f"background-color: #1e1e1e; color: {COLORS['green']}; border: 1px solid #333;"
        )
        self.console_out.setMaximumHeight(150)
        right_layout.addWidget(self.console_out)

        self.input_container = QWidget()
        inp_layout = QHBoxLayout(self.input_container)
        inp_layout.setContentsMargins(0, 5, 0, 0)

        lbl_in = QLabel("INPUT >")
        lbl_in.setStyleSheet(f"color: {COLORS['yellow']}; font-weight: bold;")
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Waiting for IN command...")
        self.input_field.returnPressed.connect(self.handle_input)
        self.input_field.setEnabled(False)

        inp_layout.addWidget(lbl_in)
        inp_layout.addWidget(self.input_field)
        right_layout.addWidget(self.input_container)

        splitter.addWidget(left_container)
        splitter.addWidget(right_container)
        splitter.setSizes([700, 400])
        main_layout.addWidget(splitter)

        # --- REFERENCE DOCK ---
        self.dock = ReferenceDock(self, self.editor)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)

    # --- DOCK LOGIC ---
    def toggle_dock(self):
        if self.dock.isVisible():
            self.dock.close()
        else:
            self.dock.show()

    # --- SPEED CONTROL LOGIC ---
    def change_speed_from_slider(self, value):
        self.spin_speed.blockSignals(True)
        self.spin_speed.setValue(value)
        self.spin_speed.blockSignals(False)
        self.update_timer_interval(value)

    def change_speed_from_spin(self, value):
        self.slider_speed.blockSignals(True)
        self.slider_speed.setValue(value)
        self.slider_speed.blockSignals(False)
        self.update_timer_interval(value)

    def update_timer_interval(self, value):
        if self.timer.isActive():
            self.timer.setInterval(value)

    # --- LOGIC ---
    def open_settings(self):
        dlg = SettingsDialog(self, self.app_settings)
        if dlg.exec():
            self.app_settings = dlg.get_settings()
            self.editor.show_execution_highlight = self.app_settings[
                "highlight_execution"
            ]
            self.editor.highlight_lines()

    def on_code_changed(self):
        self.is_code_dirty = True
        self.lbl_status.setText("MODIFIED")
        self.lbl_status.setStyleSheet(f"color: {COLORS['orange']}; font-weight: bold;")
        # We don't disable Run, because Run will now auto-build.
        # We disable Step because stepping on dirty code is confusing.
        self.act_step.setEnabled(False)

    def load_default_code(self):
        default_code = """; Click left margin to toggle breakpoints
M = 1
N = 2
R = 3
ORG 10

IN M, 2      ; Input M & N
LOOP: 
DIV R, M, N  ; R = M / N
MUL R, R, N  ; R = int(M/N) * N
SUB R, M, R  ; R = M - R
MOV M, N     ; M = N
MOV N, R     ; N = R
BGT R, 0, LOOP
OUT M, 1     ; Output
STOP
"""
        self.editor.setPlainText(default_code)
        # Manually load it so the entry point is calculated
        self.load_program()

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Assembly File",
            "",
            "Assembly Files (*.asm *.txt);;All Files (*)",
        )
        if file_path:
            with open(file_path, "r") as f:
                self.editor.setPlainText(f.read())
            self.current_file_path = file_path
            self.console_out.append(f">>> Loaded: {file_path}")
            self.load_program()

    def save_file(self):
        if not self.current_file_path:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Assembly File", "", "Assembly Files (*.asm);;All Files (*)"
            )
            if not file_path:
                return
            self.current_file_path = file_path

        with open(self.current_file_path, "w") as f:
            f.write(self.editor.toPlainText())
        self.console_out.append(f">>> Saved: {self.current_file_path}")

    def build_sourcemap(self, code_text):
        self.pc_to_line_map = {}
        lines = code_text.split("\n")
        current_address = 0

        def is_instruction(line):
            line = line.split(";")[0].strip()
            if not line:
                return False
            if line.endswith(":"):
                return False
            parts = line.split()
            if not parts:
                return False

            nonlocal current_address
            if parts[0].upper() == "ORG" and len(parts) > 1:
                try:
                    current_address = int(parts[1])
                except:
                    pass
                return False

            if "=" in line:
                return False
            return True

        for i, line in enumerate(lines):
            if is_instruction(line):
                self.pc_to_line_map[current_address] = i
                current_address += 1

    def load_program(self):
        # 1. Sanitize Input
        code = self.editor.toPlainText()

        try:
            # 2. Parse Code
            self.emu.parse(code)
            self.build_sourcemap(code)

            # 3. Determine Entry Point
            # The emulator.parse method leaves self.emu.pc at the ORG address
            # (if defined) because of how ORG directives set pc.
            # We capture this value now as the definitive reset point.
            self.program_entry_point = self.emu.pc

            self.console_out.clear()
            self.console_out.append(
                f">>> Build Successful. Entry Point: {self.program_entry_point}"
            )

            self.act_run.setEnabled(True)
            self.act_step.setEnabled(True)
            self.lbl_status.setText("READY")
            self.lbl_status.setStyleSheet(
                f"color: {COLORS['green']}; font-weight: bold;"
            )

            self.mem_table.setRowCount(0)
            self.table_items_cache = {}
            self.editor.set_execution_line(-1)
            self.is_auto_running = False
            self.is_code_dirty = False

            # Reset Cycle Count
            self.cycle_count = 0
            self.update_ui()

            return True

        except Exception as e:
            self.console_out.append(f"ERR> {str(e)}")
            self.lbl_status.setText("PARSE ERROR")
            self.lbl_status.setStyleSheet(f"color: {COLORS['red']}; font-weight: bold;")
            QMessageBox.critical(self, "Parse Error", str(e))
            return False

    def reset_program(self):
        """Re-loads the program to ensure memory is wiped and state is fresh."""
        self.timer.stop()
        self.is_auto_running = False
        self.act_run.setText("Run")

        # Reloading ensures 'Hard Reset' behavior (Memory Cleared)
        if self.load_program():
            # Force PC to entry point in case load_program didn't set it
            # (though load_program usually sets it via parse)
            self.emu.pc = self.program_entry_point
            self.update_ui()

    def toggle_run(self):
        # Auto-Build if dirty
        if self.is_code_dirty:
            success = self.load_program()
            if not success:
                return  # Do not run if build failed

        if self.timer.isActive():
            self.timer.stop()
            self.is_auto_running = False
            self.act_run.setText("Run")
            self.lbl_status.setText("PAUSED")
            self.lbl_status.setStyleSheet(
                f"color: {COLORS['orange']}; font-weight: bold;"
            )
        else:
            if self.emu.is_finished:
                # If finished, we reset to entry point
                self.emu.pc = self.program_entry_point
                self.emu.is_finished = False
                self.emu.input_needed = 0
                self.cycle_count = 0
                self.emu.output_buffer = []
                self.console_out.append(">>> Restarting...")

            # Logic to handle starting ON a breakpoint
            current_line = self.pc_to_line_map.get(self.emu.pc, -1)
            if current_line in self.editor.breakpoints:
                self.step_execution()  # Step once to get off breakpoint
                if (
                    self.emu.is_finished
                    or self.emu.input_needed > 0
                    or not self.is_auto_running
                ):
                    return

            self.is_auto_running = True
            self.timer.start(self.slider_speed.value())
            self.act_run.setText("Stop")
            self.lbl_status.setText("RUNNING")
            self.lbl_status.setStyleSheet(
                f"color: {COLORS['green']}; font-weight: bold;"
            )

    def manual_step(self):
        if self.is_code_dirty:
            success = self.load_program()
            if not success:
                return

        self.timer.stop()
        self.is_auto_running = False
        self.act_run.setText("Run")
        self.step_execution()

    def step_execution(self):
        # 1. Breakpoint Check
        current_line = self.pc_to_line_map.get(self.emu.pc, -1)
        if self.is_auto_running and current_line in self.editor.breakpoints:
            self.timer.stop()
            self.is_auto_running = False
            self.act_run.setText("Run")
            self.lbl_status.setText("BREAKPOINT")
            self.lbl_status.setStyleSheet(f"color: {COLORS['red']}; font-weight: bold;")
            self.console_out.append(
                f"LOG> Paused at Breakpoint (Line {current_line+1})"
            )
            self.editor.set_execution_line(current_line)
            return

        # 2. Status Check (Fix for Cycle Counting Issue)
        # If already finished or waiting, do not step and do not increment cycles
        if self.emu.is_finished or self.emu.input_needed > 0:
            self.update_ui()
            return

        # 3. Perform Step
        self.emu.step()
        self.cycle_count += 1
        self.update_ui()

    def handle_memory_edit(self, item):
        if item.column() != 2:
            return

        row = item.row()
        addr_item = self.mem_table.item(row, 1)
        if not addr_item:
            return

        try:
            addr = int(addr_item.text())
            new_val_str = item.text()
            new_val = int(new_val_str)

            if isinstance(self.emu.memory, list):
                if 0 <= addr < len(self.emu.memory):
                    self.emu.memory[addr] = new_val
                    self.console_out.append(f"LOG> Memory [{addr}] set to {new_val}")

        except ValueError:
            QMessageBox.warning(self, "Invalid Value", "Please enter a valid integer.")
            self.update_ui()

    def update_ui(self):
        self.lbl_pc.setText(f"PC: {self.emu.pc}")
        self.lbl_cycles.setText(f"CYCLES: {self.cycle_count}")

        self.mem_table.blockSignals(True)

        if self.app_settings["highlight_execution"]:
            line_idx = self.pc_to_line_map.get(self.emu.pc, -1)
            self.editor.set_execution_line(line_idx)

        # Output logic
        if self.emu.output_buffer:
            for line in self.emu.output_buffer:
                self.console_out.append(f"OUT> {line}")
                self.console_out.verticalScrollBar().setValue(
                    self.console_out.verticalScrollBar().maximum()
                )
            self.emu.output_buffer = []

        # Status checks
        if self.emu.is_finished:
            self.timer.stop()
            self.is_auto_running = False
            self.act_run.setText("Run")
            if self.emu.last_error:
                self.lbl_status.setText("RUNTIME ERROR")
                self.lbl_status.setStyleSheet(
                    f"color: {COLORS['red']}; font-weight: bold;"
                )
                self.console_out.append(f"ERR> {self.emu.last_error}")
            else:
                self.lbl_status.setText("FINISHED")
                self.lbl_status.setStyleSheet(
                    f"color: {COLORS['cyan']}; font-weight: bold;"
                )
                self.console_out.append(">>> Execution Finished.")

        elif self.emu.input_needed > 0:
            if self.timer.isActive():
                self.timer.stop()
                self.act_run.setText("Run")

            self.lbl_status.setText(f"WAITING INPUT ({self.emu.input_needed})")
            self.lbl_status.setStyleSheet(
                f"color: {COLORS['yellow']}; font-weight: bold;"
            )
            self.input_field.setEnabled(True)
            self.input_field.setStyleSheet(
                f"background-color: {COLORS['yellow']}; color: black; border: 2px solid {COLORS['orange']};"
            )
            self.input_field.setFocus()
        else:
            self.input_field.setEnabled(False)
            self.input_field.setStyleSheet(
                f"background-color: {COLORS['input_bg']}; color: {COLORS['fg']};"
            )

        # Table Update
        registers_list = list(self.emu.registers.items())
        if self.mem_table.rowCount() != len(registers_list):
            self.mem_table.setRowCount(len(registers_list))

        for row, (name, addr) in enumerate(registers_list):
            try:
                if isinstance(self.emu.memory, list):
                    if 0 <= addr < len(self.emu.memory):
                        val = self.emu.memory[addr]
                    else:
                        val = "ERR"
                else:
                    val = self.emu.memory.get(addr, 0)
            except Exception:
                val = 0

            if row not in self.table_items_cache:
                i_name = QTableWidgetItem(name)
                i_addr = QTableWidgetItem(str(addr))
                i_val = QTableWidgetItem(str(val))

                i_name.setForeground(QColor(COLORS["orange"]))
                i_name.setFlags(i_name.flags() & ~Qt.ItemIsEditable)

                i_addr.setTextAlignment(Qt.AlignCenter)
                i_addr.setFlags(i_addr.flags() & ~Qt.ItemIsEditable)

                i_val.setTextAlignment(Qt.AlignCenter)
                i_val.setForeground(QColor(COLORS["cyan"]))
                i_val.setFlags(i_val.flags() | Qt.ItemIsEditable)

                self.mem_table.setItem(row, 0, i_name)
                self.mem_table.setItem(row, 1, i_addr)
                self.mem_table.setItem(row, 2, i_val)
                self.table_items_cache[row] = (i_name, i_addr, i_val)

            self.table_items_cache[row][0].setText(name)
            self.table_items_cache[row][1].setText(str(addr))

            if self.table_items_cache[row][2].text() != str(val):
                self.table_items_cache[row][2].setText(str(val))

        self.mem_table.blockSignals(False)

    def handle_input(self):
        text = self.input_field.text()
        if not text:
            return

        if self.emu.provide_input(text):
            self.console_out.append(f"IN < {text}")
            self.input_field.clear()
            self.update_ui()

            if self.emu.input_needed == 0:
                if self.is_auto_running:
                    self.act_run.setText("Stop")
                    self.lbl_status.setText("RUNNING")
                    self.lbl_status.setStyleSheet(
                        f"color: {COLORS['green']}; font-weight: bold;"
                    )
                    self.timer.start(self.slider_speed.value())
                else:
                    self.lbl_status.setText("READY")
        else:
            QMessageBox.warning(self, "Input Error", "Invalid Integer")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
