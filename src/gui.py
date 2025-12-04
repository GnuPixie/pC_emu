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
    QCompleter,
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
    QStyle,
    QDockWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QTabWidget,
    QStatusBar,
    QSpacerItem,
    QSizePolicy,
    QSpinBox,
)
from PySide6.QtCore import Qt, QTimer, QRect, QSize, QPoint, QStringListModel, QSettings
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
    QPixmap,
    QPen,
    QPainterPath,
)

# Assuming emulator.py exists in the same directory
from emulator import PicoEmulator

# --- COLOR PALETTE ---
COLORS = {
    "bg": "#282a36",
    "fg": "#f8f8f2",
    "sidebar": "#21222c",
    "current_line": "#44475a",
    "executing_line": "#005f00",
    "error_line": "#6b1818",
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
    "breakpoint": "#ff5555",
    "icon_color": "#8be9fd",  # Cyan for icons
}

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


# --- ICON FACTORY ---
class IconFactory:
    @staticmethod
    def draw_icon(shape, color=COLORS["icon_color"]):
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        pen = QPen(QColor(color))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QColor(color))

        if shape == "play":
            path = QPainterPath()
            path.moveTo(8, 6)
            path.lineTo(26, 16)
            path.lineTo(8, 26)
            path.closeSubpath()
            painter.drawPath(path)

        elif shape == "pause":
            painter.drawRect(8, 6, 5, 20)
            painter.drawRect(19, 6, 5, 20)

        elif shape == "step":
            # Arrow
            path = QPainterPath()
            path.moveTo(4, 10)
            path.lineTo(14, 16)
            path.lineTo(4, 22)
            path.closeSubpath()
            painter.drawPath(path)
            # Bar
            painter.drawRect(16, 8, 4, 16)

        elif shape == "reset":
            # Simple circular arrow
            painter.setBrush(Qt.NoBrush)
            pen.setWidth(3)
            painter.setPen(pen)
            painter.drawArc(6, 6, 20, 20, 45 * 16, 270 * 16)
            # Arrow head
            path = QPainterPath()
            path.moveTo(20, 4)
            path.lineTo(26, 10)
            path.lineTo(28, 2)
            painter.setBrush(QColor(color))
            painter.setPen(Qt.NoPen)
            painter.drawPath(path)

        elif shape == "settings":
            painter.setBrush(Qt.NoBrush)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawEllipse(8, 8, 16, 16)
            painter.drawPoint(16, 16)  # Center dot

        elif shape == "save":
            painter.drawRect(6, 6, 20, 20)
            painter.setBrush(QColor(COLORS["bg"]))
            painter.drawRect(10, 6, 12, 6)

        elif shape == "open":
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(4, 8, 24, 16)
            painter.drawLine(4, 8, 10, 2)
            painter.drawLine(10, 2, 28, 2)
            painter.drawLine(28, 2, 28, 8)

        painter.end()
        return QIcon(pixmap)


# --- SETTINGS DIALOG ---
class SettingsDialog(QDialog):
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setFixedWidth(300)

        # Style
        self.setStyleSheet(
            f"""
            QDialog {{ background: {COLORS['bg']}; color: {COLORS['fg']}; }}
            QLabel, QCheckBox {{ color: {COLORS['fg']}; font-size: 14px; }}
            QPushButton {{ background: {COLORS['current_line']}; color: {COLORS['fg']}; border: none; padding: 6px; }}
            QPushButton:hover {{ background: {COLORS['comment']}; }}
        """
        )

        layout = QVBoxLayout(self)

        self.cb_lock_editor = QCheckBox("Lock Editor while Running")
        self.cb_lock_editor.setChecked(current_settings.get("lock_editor", True))

        layout.addWidget(self.cb_lock_editor)
        layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self):
        return {"lock_editor": self.cb_lock_editor.isChecked()}


# --- CUSTOM EDITOR COMPONENTS ---
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
            # Calculate line number carefully
            cursor = self.editor.cursorForPosition(event.pos())
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
        self.error_line_index = -1
        self.show_execution_highlight = True
        self.breakpoints = set()

        font = QFont("Consolas", 12)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)

        # Completer
        self.completer = None
        self.setup_completer()

    def setup_completer(self):
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        keywords = [x[0] for x in OPCODE_REF] + ["M", "N", "R", "A", "B", "I", "J"]
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
        if self.completer and self.completer.popup().isVisible():
            if event.key() in (
                Qt.Key_Enter,
                Qt.Key_Return,
                Qt.Key_Escape,
                Qt.Key_Tab,
                Qt.Key_Backtab,
            ):
                event.ignore()
                return

        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.textCursor()
            current_line = cursor.block().text()
            indentation = ""
            match = re.match(r"^(\s+)", current_line)
            if match:
                indentation = match.group(1)
            super().keyPressEvent(event)
            self.insertPlainText(indentation)
            return

        is_shortcut = (
            event.modifiers() & Qt.ControlModifier
        ) and event.key() == Qt.Key_Space
        if not self.completer or not is_shortcut:
            super().keyPressEvent(event)

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
        # Width: Margin(5) + Dot(10) + Margin(5) + Text + Margin(5)
        space = 25 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

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
        self.error_line_index = -1
        self.highlight_lines()
        if line_idx >= 0:
            block = self.document().findBlockByNumber(line_idx)
            cursor = self.textCursor()
            cursor.setPosition(block.position())
            self.ensureCursorVisible()

    def set_error_line(self, line_idx):
        self.error_line_index = line_idx
        self.execution_line_index = -1
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
            selection.format.setBackground(QColor(COLORS["current_line"]))
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

            if self.show_execution_highlight and self.execution_line_index >= 0:
                exec_selection = QTextEdit.ExtraSelection()
                exec_selection.format.setBackground(QColor(COLORS["executing_line"]))
                exec_selection.format.setProperty(QTextFormat.FullWidthSelection, True)
                block = self.document().findBlockByNumber(self.execution_line_index)
                cursor = self.textCursor()
                cursor.setPosition(block.position())
                exec_selection.cursor = cursor
                exec_selection.cursor.clearSelection()
                extra_selections.append(exec_selection)

            if self.error_line_index >= 0:
                err_selection = QTextEdit.ExtraSelection()
                err_selection.format.setBackground(QColor(COLORS["error_line"]))
                err_selection.format.setProperty(QTextFormat.FullWidthSelection, True)
                block = self.document().findBlockByNumber(self.error_line_index)
                cursor = self.textCursor()
                cursor.setPosition(block.position())
                err_selection.cursor = cursor
                err_selection.cursor.clearSelection()
                extra_selections.append(err_selection)

        self.setExtraSelections(extra_selections)

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(COLORS["sidebar"]))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        height = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)

                # Draw Breakpoint (Circle on the Left)
                if block_number in self.breakpoints:
                    painter.setBrush(QBrush(QColor(COLORS["breakpoint"])))
                    painter.setPen(Qt.NoPen)
                    radius = 4
                    cy = top + height / 2
                    cx = 8  # Left margin
                    painter.drawEllipse(QPoint(int(cx), int(cy)), radius, radius)

                # Set Text Color
                painter.setPen(QColor(COLORS["comment"]))

                # Draw Execution Arrow (Triangle near numbers)
                if (
                    block_number == self.execution_line_index
                    and self.show_execution_highlight
                ):
                    painter.setPen(QColor(COLORS["green"]))
                    painter.setFont(QFont("Consolas", 10, QFont.Bold))
                    painter.drawText(
                        0,
                        int(top),
                        self.line_number_area.width() - 5,
                        height,
                        Qt.AlignRight,
                        "►",
                    )

                elif block_number == self.error_line_index:
                    painter.setPen(QColor(COLORS["red"]))
                    painter.setFont(QFont("Consolas", 10, QFont.Bold))
                    painter.drawText(
                        0,
                        int(top),
                        self.line_number_area.width() - 5,
                        height,
                        Qt.AlignRight,
                        "!",
                    )

                else:
                    painter.setFont(QFont("Consolas", 10))
                    # Draw text shifted right to avoid breakpoint collision
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


class AssemblyHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor(COLORS["pink"]))
        kw_fmt.setFontWeight(QFont.Bold)
        for w in [x[0] for x in OPCODE_REF]:
            self.rules.append((re.compile(rf"\b{w}\b", re.IGNORECASE), kw_fmt))
        lbl_fmt = QTextCharFormat()
        lbl_fmt.setForeground(QColor(COLORS["green"]))
        self.rules.append((re.compile(r"^[A-Z_0-9]+:"), lbl_fmt))
        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor(COLORS["purple"]))
        self.rules.append((re.compile(r"\b\d+\b"), num_fmt))
        cmt_fmt = QTextCharFormat()
        cmt_fmt.setForeground(QColor(COLORS["comment"]))
        self.rules.append((re.compile(r";.*"), cmt_fmt))

    def highlightBlock(self, text):
        for pat, fmt in self.rules:
            for m in pat.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


class QCompleter(sys.modules[__name__].QCompleter):
    pass


from PySide6.QtWidgets import QCompleter


# --- MAIN WINDOW ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PicoComputer IDE")
        self.resize(1300, 850)

        self.emu = PicoEmulator()
        self.timer = QTimer()
        self.timer.timeout.connect(self.step_execution)

        self.current_file_path = None
        self.pc_to_line_map = {}
        self.is_code_dirty = True
        self.program_entry_point = 0
        self.cycle_count = 0
        self.was_running_before_input = False

        self.settings = {"lock_editor": True}

        self.setup_ui()
        self.apply_theme()
        self.load_default_code()

    def apply_theme(self):
        self.setStyleSheet(
            f"""
            QMainWindow, QDockWidget {{ background-color: {COLORS['bg']}; color: {COLORS['fg']}; }}
            QWidget {{ font-family: 'Segoe UI', sans-serif; font-size: 13px; color: {COLORS['fg']}; }}
            
            QPlainTextEdit, QTextEdit, QTreeWidget, QTableWidget {{ 
                background-color: {COLORS['bg']}; 
                color: {COLORS['fg']}; 
                border: none;
                font-family: 'Consolas', monospace;
            }}
            
            QTableWidget {{ 
                gridline-color: {COLORS['current_line']};
                selection-background-color: {COLORS['selection']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['sidebar']};
                color: {COLORS['cyan']};
                padding: 5px;
                border: none;
                font-weight: bold;
            }}
            
            QTabWidget::pane {{ border: 1px solid {COLORS['current_line']}; }}
            QTabBar::tab {{
                background: {COLORS['sidebar']};
                color: {COLORS['comment']};
                padding: 8px 15px;
            }}
            QTabBar::tab:selected {{
                background: {COLORS['bg']};
                color: {COLORS['fg']};
                border-bottom: 2px solid {COLORS['pink']};
            }}
            
            QLineEdit, QSpinBox {{ 
                background-color: {COLORS['input_bg']}; 
                border: 1px solid {COLORS['comment']}; 
                border-radius: 4px; padding: 4px; color: {COLORS['fg']};
            }}
            
            QToolBar {{ background: {COLORS['sidebar']}; border-bottom: 1px solid {COLORS['current_line']}; spacing: 10px; padding: 5px; }}
            QToolButton {{ background: transparent; border-radius: 4px; padding: 5px; }}
            QToolButton:hover {{ background: {COLORS['current_line']}; }}
            
            QStatusBar {{ background: {COLORS['sidebar']}; color: {COLORS['comment']}; }}
        """
        )

    def setup_ui(self):
        self.editor = CodeEditor()
        self.highlighter = AssemblyHighlighter(self.editor.document())
        self.editor.textChanged.connect(self.on_code_changed)
        self.setCentralWidget(self.editor)

        self.setup_toolbar()
        self.setup_docks()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.lbl_status = QLabel(" READY ")
        self.lbl_status.setStyleSheet(
            f"background-color: {COLORS['green']}; color: #282a36; font-weight: bold; border-radius: 4px; padding: 2px 5px;"
        )

        self.lbl_pc = QLabel(" PC: 000 ")
        self.lbl_pc.setStyleSheet(
            f"color: {COLORS['cyan']}; font-family: Consolas; font-weight: bold;"
        )

        self.lbl_cycles = QLabel(" CYCLES: 0 ")
        self.lbl_cycles.setStyleSheet(
            f"color: {COLORS['yellow']}; font-family: Consolas;"
        )

        self.status_bar.addWidget(QLabel("  State: "))
        self.status_bar.addWidget(self.lbl_status)
        self.status_bar.addWidget(QLabel("  "))
        self.status_bar.addWidget(self.lbl_pc)
        self.status_bar.addWidget(self.lbl_cycles)

    def setup_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(24, 24))
        self.addToolBar(tb)

        # File
        act_open = QAction(IconFactory.draw_icon("open"), "Open", self)
        act_open.triggered.connect(self.open_file)
        tb.addAction(act_open)

        act_save = QAction(IconFactory.draw_icon("save"), "Save", self)
        act_save.triggered.connect(self.save_file)
        tb.addAction(act_save)

        tb.addSeparator()

        # Execution
        self.act_run = QAction(
            IconFactory.draw_icon("play", COLORS["green"]), "Run", self
        )
        self.act_run.setShortcut("F5")
        self.act_run.triggered.connect(self.toggle_run)
        self.act_run.setToolTip("Run / Pause (F5)")
        tb.addAction(self.act_run)

        self.act_step = QAction(
            IconFactory.draw_icon("step", COLORS["cyan"]), "Step", self
        )
        self.act_step.setShortcut("F10")
        self.act_step.triggered.connect(self.manual_step)
        self.act_step.setToolTip("Step One Instruction (F10)")
        tb.addAction(self.act_step)

        act_reset = QAction(
            IconFactory.draw_icon("reset", COLORS["orange"]), "Reset", self
        )
        act_reset.setShortcut("Ctrl+R")
        act_reset.triggered.connect(self.reset_program)
        act_reset.setToolTip("Reset Program")
        tb.addAction(act_reset)

        tb.addSeparator()

        # Settings
        act_settings = QAction(
            IconFactory.draw_icon("settings", COLORS["fg"]), "Settings", self
        )
        act_settings.triggered.connect(self.open_settings)
        tb.addAction(act_settings)

        tb.addSeparator()

        # Speed
        tb.addWidget(QLabel("  Delay (ms): "))
        self.spin_speed = QSpinBox()
        self.spin_speed.setRange(10, 2000)
        self.spin_speed.setValue(100)
        self.spin_speed.setSingleStep(50)
        self.spin_speed.setFixedWidth(70)
        self.spin_speed.valueChanged.connect(self.update_timer_interval)
        tb.addWidget(self.spin_speed)

    def setup_docks(self):
        # --- RIGHT DOCK: UNIFIED INSPECTOR ---
        self.dock_inspector = QDockWidget("Memory Inspector", self)
        self.dock_inspector.setAllowedAreas(Qt.RightDockWidgetArea)

        self.table_mem = QTableWidget(0, 3)
        self.table_mem.setHorizontalHeaderLabels(["Addr", "Name", "Value"])
        self.table_mem.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_mem.verticalHeader().setVisible(False)
        self.table_mem.itemChanged.connect(self.handle_memory_edit)

        self.dock_inspector.setWidget(self.table_mem)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_inspector)

        # --- BOTTOM DOCK: TERMINAL & REF ---
        self.dock_bottom = QDockWidget("Output & Tools", self)
        self.dock_bottom.setAllowedAreas(Qt.BottomDockWidgetArea)

        bottom_tabs = QTabWidget()

        # Tab 1: Terminal
        term_widget = QWidget()
        term_layout = QVBoxLayout(term_widget)
        term_layout.setContentsMargins(5, 5, 5, 5)
        self.console_out = QTextEdit()
        self.console_out.setReadOnly(True)
        term_layout.addWidget(self.console_out)

        inp_layout = QHBoxLayout()
        self.lbl_prompt = QLabel("Input >")
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Program is not asking for input...")
        self.input_field.setEnabled(False)
        self.input_field.returnPressed.connect(self.handle_input)

        inp_layout.addWidget(self.lbl_prompt)
        inp_layout.addWidget(self.input_field)
        term_layout.addLayout(inp_layout)

        bottom_tabs.addTab(term_widget, "Terminal")

        # Tab 2: Reference
        self.tree_ref = QTreeWidget()
        self.tree_ref.setHeaderLabels(["Opcode", "Syntax", "Description"])
        self.tree_ref.setColumnWidth(0, 60)
        self.tree_ref.setColumnWidth(1, 150)
        for op, syn, desc in OPCODE_REF:
            item = QTreeWidgetItem([op, syn, desc])
            item.setForeground(0, QBrush(QColor(COLORS["pink"])))
            item.setForeground(1, QBrush(QColor(COLORS["cyan"])))
            self.tree_ref.addTopLevelItem(item)
        self.tree_ref.itemDoubleClicked.connect(self.insert_instruction)
        bottom_tabs.addTab(self.tree_ref, "Reference")

        # Tab 3: Issues
        self.list_issues = QTextEdit()
        self.list_issues.setReadOnly(True)
        self.list_issues.setStyleSheet(f"color: {COLORS['red']};")
        bottom_tabs.addTab(self.list_issues, "Issues")

        self.dock_bottom.setWidget(bottom_tabs)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_bottom)
        self.resizeDocks([self.dock_bottom], [200], Qt.Vertical)

    def open_settings(self):
        dlg = SettingsDialog(self, self.settings)
        if dlg.exec():
            self.settings = dlg.get_data()

    def insert_instruction(self, item, col):
        text = item.text(0) + " "
        self.editor.insertPlainText(text)
        self.editor.setFocus()

    def update_timer_interval(self, value):
        if self.timer.isActive():
            self.timer.setInterval(value)

    def on_code_changed(self):
        self.is_code_dirty = True
        self.lbl_status.setText(" MODIFIED ")
        self.lbl_status.setStyleSheet(
            f"background-color: {COLORS['orange']}; color: #282a36; font-weight: bold; border-radius: 4px;"
        )
        self.act_step.setEnabled(False)

    def load_program(self):
        code = self.editor.toPlainText()
        try:
            self.emu.parse(code)
            self.build_sourcemap(code)
            self.program_entry_point = self.emu.pc

            self.list_issues.clear()
            self.list_issues.append("No issues found.")
            self.console_out.append(
                f"<span style='color:{COLORS['green']}'>Build Successful. Entry Point: {self.program_entry_point}</span>"
            )

            self.act_step.setEnabled(True)
            self.lbl_status.setText(" READY ")
            self.lbl_status.setStyleSheet(
                f"background-color: {COLORS['green']}; color: #282a36; font-weight: bold; border-radius: 4px;"
            )

            self.editor.set_execution_line(-1)
            self.is_code_dirty = False
            self.cycle_count = 0
            self.was_running_before_input = False
            self.update_ui()
            return True

        except Exception as e:
            self.lbl_status.setText(" ERROR ")
            self.lbl_status.setStyleSheet(
                f"background-color: {COLORS['red']}; color: white; font-weight: bold; border-radius: 4px;"
            )
            self.list_issues.clear()
            self.list_issues.append(str(e))
            self.console_out.append(
                f"<span style='color:{COLORS['red']}'>Build Failed. Check 'Issues' tab.</span>"
            )

            match = re.search(r"line\s+(\d+)", str(e), re.IGNORECASE)
            if match:
                line_no = int(match.group(1)) - 1
                self.editor.set_error_line(line_no)
            self.dock_bottom.widget().setCurrentIndex(2)
            return False

    def build_sourcemap(self, code_text):
        self.pc_to_line_map = {}
        lines = code_text.split("\n")
        current_address = 0

        def analyze_line(line):
            line = line.split(";")[0].strip()
            if not line or line.endswith(":"):
                return None
            if "=" in line:
                return None
            parts = line.split()
            if not parts:
                return None
            if parts[0].upper() == "ORG" and len(parts) > 1:
                try:
                    return ("ORG", int(parts[1]))
                except:
                    return None
            return ("INS", 0)

        for i, line in enumerate(lines):
            res = analyze_line(line)
            if res:
                if res[0] == "ORG":
                    current_address = res[1]
                else:
                    self.pc_to_line_map[current_address] = i
                    current_address += 1

    def toggle_run(self):
        # Build if dirty
        if self.is_code_dirty:
            if not self.load_program():
                return

        if self.timer.isActive():
            # PAUSE
            self.timer.stop()
            self.was_running_before_input = False
        else:
            # RUN
            if self.emu.is_finished:
                self.reset_program()

            # If input is needed, we can't really "run", but we set state
            if self.emu.input_needed > 0:
                self.was_running_before_input = True  # Wants to run, but waiting
                self.update_ui()
                return

            # Breakpoint handling
            curr_line = self.pc_to_line_map.get(self.emu.pc, -1)
            if curr_line in self.editor.breakpoints:
                self.step_execution()  # Step over
                if self.emu.is_finished or self.emu.input_needed:
                    return

            self.timer.start(self.spin_speed.value())

        self.update_ui()

    def manual_step(self):
        if self.is_code_dirty:
            if not self.load_program():
                return
        self.timer.stop()
        self.step_execution()
        self.update_ui()

    def step_execution(self):
        curr_line = self.pc_to_line_map.get(self.emu.pc, -1)
        if self.timer.isActive() and curr_line in self.editor.breakpoints:
            self.timer.stop()
            self.was_running_before_input = False
            self.lbl_status.setText(" BREAKPOINT ")
            self.lbl_status.setStyleSheet(
                f"background-color: {COLORS['red']}; color: white; font-weight: bold; border-radius: 4px;"
            )
            self.editor.set_execution_line(curr_line)
            self.update_ui()  # Ensure button state updates
            return

        if self.emu.is_finished or self.emu.input_needed > 0:
            self.update_ui()
            return

        try:
            self.emu.step()
            self.cycle_count += 1
            # Don't call update_ui here every ms if running fast?
            # For now, it's fine.
            self.update_ui()
        except Exception as e:
            self.timer.stop()
            self.lbl_status.setText(" CRASH ")
            self.console_out.append(
                f"<span style='color:red'>Runtime Error: {e}</span>"
            )
            self.update_ui()

    def reset_program(self):
        self.timer.stop()
        self.was_running_before_input = False
        if self.load_program():
            self.emu.pc = self.program_entry_point
            self.cycle_count = 0
            self.update_ui()

    def update_ui(self):
        # 1. Update Labels
        self.lbl_pc.setText(f" PC: {self.emu.pc} ")
        self.lbl_cycles.setText(f" CYCLES: {self.cycle_count} ")

        # 2. Highlight Editor
        line_idx = self.pc_to_line_map.get(self.emu.pc, -1)
        self.editor.set_execution_line(line_idx)

        # 3. Handle Editor Locking
        if self.settings.get("lock_editor"):
            is_running = self.timer.isActive()
            # If strictly running, lock it.
            # If paused on breakpoint or waiting for input, conceptually it is "running" the program session.
            # But usually we allow editing if paused.
            # Let's lock if timer is active OR waiting for input?
            should_lock = self.timer.isActive() or (
                self.was_running_before_input and self.emu.input_needed > 0
            )
            self.editor.setReadOnly(should_lock)
        else:
            self.editor.setReadOnly(False)

        # 4. Console Output
        if self.emu.output_buffer:
            for line in self.emu.output_buffer:
                self.console_out.append(
                    f"<span style='color:{COLORS['cyan']}'>OUT &gt; {line}</span>"
                )
            self.emu.output_buffer = []

        # 5. Determine State & Icons
        if self.emu.is_finished:
            self.timer.stop()
            self.act_run.setIcon(IconFactory.draw_icon("play", COLORS["green"]))
            self.act_run.setText("Run")
            self.lbl_status.setText(" FINISHED ")
            self.lbl_status.setStyleSheet(
                f"background-color: {COLORS['cyan']}; color: #282a36; font-weight: bold; border-radius: 4px;"
            )

        elif self.emu.input_needed > 0:
            if self.timer.isActive():
                self.was_running_before_input = True
                self.timer.stop()

            self.act_run.setIcon(
                IconFactory.draw_icon("play", COLORS["green"])
            )  # It's technically paused waiting
            self.act_run.setText(
                "Run"
            )  # Clicking Run won't do anything until input is done

            self.lbl_status.setText(" WAITING INPUT ")
            self.lbl_status.setStyleSheet(
                f"background-color: {COLORS['yellow']}; color: #282a36; font-weight: bold; border-radius: 4px;"
            )

            self.input_field.setEnabled(True)
            self.input_field.setPlaceholderText(
                f"Enter {self.emu.input_needed} value(s)..."
            )
            self.input_field.setFocus()
            self.input_field.setStyleSheet(
                f"background-color: {COLORS['yellow']}; color: black; font-weight: bold;"
            )
            self.dock_bottom.widget().setCurrentIndex(0)

        elif self.timer.isActive():
            self.act_run.setIcon(IconFactory.draw_icon("pause", COLORS["yellow"]))
            self.act_run.setText("Pause")
            self.lbl_status.setText(" RUNNING ")
            self.lbl_status.setStyleSheet(
                f"background-color: {COLORS['green']}; color: #282a36; font-weight: bold; border-radius: 4px;"
            )
            self.input_field.setEnabled(False)
            self.input_field.setStyleSheet(
                f"background-color: {COLORS['input_bg']}; color: {COLORS['fg']};"
            )

        else:
            # Paused or Ready
            self.act_run.setIcon(IconFactory.draw_icon("play", COLORS["green"]))
            self.act_run.setText("Run")
            if not self.emu.is_finished:
                self.lbl_status.setText(" PAUSED ")
                self.lbl_status.setStyleSheet(
                    f"background-color: {COLORS['orange']}; color: #282a36; font-weight: bold; border-radius: 4px;"
                )
            self.input_field.setEnabled(False)
            self.input_field.setStyleSheet(
                f"background-color: {COLORS['input_bg']}; color: {COLORS['fg']};"
            )

        self.update_inspector()

    def update_inspector(self):
        # Combined Memory Map: Address | Name (if reg) | Value

        # 1. Gather all unique addresses (Variables + Touched Memory)
        all_addrs = set(self.emu.registers.values()) | self.emu.touched_memory
        sorted_addrs = sorted(list(all_addrs))

        # Map Address -> Variable Name
        addr_to_name = {v: k for k, v in self.emu.registers.items()}

        self.table_mem.blockSignals(True)
        self.table_mem.setRowCount(len(sorted_addrs))

        for row, addr in enumerate(sorted_addrs):
            val = 0
            try:
                if isinstance(self.emu.memory, list):
                    if addr < len(self.emu.memory):
                        val = self.emu.memory[addr]
                else:
                    val = self.emu.memory.get(addr, 0)
            except:
                pass

            name = addr_to_name.get(addr, "")

            item_addr = QTableWidgetItem(str(addr))
            item_addr.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

            item_name = QTableWidgetItem(name)
            item_name.setForeground(QColor(COLORS["orange"]))
            item_name.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

            item_val = QTableWidgetItem(str(val))
            item_val.setForeground(QColor(COLORS["cyan"]))

            self.table_mem.setItem(row, 0, item_addr)
            self.table_mem.setItem(row, 1, item_name)
            self.table_mem.setItem(row, 2, item_val)

        self.table_mem.blockSignals(False)

    def handle_memory_edit(self, item):
        # Only allow editing Value column (index 2)
        if item.column() != 2:
            return

        row = item.row()
        addr_item = self.table_mem.item(row, 0)  # Address is col 0
        if not addr_item:
            return

        try:
            addr = int(addr_item.text())
            val = int(item.text())

            if isinstance(self.emu.memory, list):
                if addr < len(self.emu.memory):
                    self.emu.memory[addr] = val
            else:
                self.emu.memory[addr] = val
        except:
            pass

    def handle_input(self):
        text = self.input_field.text()
        if not text:
            return

        if self.emu.provide_input(text):
            self.console_out.append(
                f"<span style='color:{COLORS['yellow']}'>IN &lt; {text}</span>"
            )
            self.input_field.clear()
            self.update_ui()  # Updates status

            # Auto-Resume logic
            if self.emu.input_needed == 0:
                self.input_field.setEnabled(False)
                self.input_field.setStyleSheet(
                    f"background-color: {COLORS['input_bg']}; color: {COLORS['fg']};"
                )

                # If we were running before input paused us, resume now
                if self.was_running_before_input:
                    self.timer.start(self.spin_speed.value())
                    self.update_ui()
        else:
            QMessageBox.warning(self, "Input Error", "Invalid Integer Input")

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open File", "", "Assembly (*.asm *.txt)"
        )
        if path:
            with open(path, "r") as f:
                self.editor.setPlainText(f.read())
            self.current_file_path = path
            self.load_program()

    def save_file(self):
        if not self.current_file_path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save File", "", "Assembly (*.asm)"
            )
            if not path:
                return
            self.current_file_path = path
        with open(self.current_file_path, "w") as f:
            f.write(self.editor.toPlainText())

    def load_default_code(self):
        code = """; PicoComputer Example
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
OUT M, 1     ; Output GCD
STOP
"""
        self.editor.setPlainText(code)
        self.load_program()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
