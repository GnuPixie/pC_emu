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
)
from PySide6.QtCore import Qt, QTimer, QRect, QSize
from PySide6.QtGui import (
    QFont,
    QColor,
    QPainter,
    QTextFormat,
    QSyntaxHighlighter,
    QTextCharFormat,
    QAction,
    QIcon,
)

# Import your existing emulator logic
from emulator import PicoEmulator

# --- COLOR PALETTE (Dracula Inspired) ---
COLORS = {
    "bg": "#282a36",
    "fg": "#f8f8f2",
    "current_line": "#44475a",
    "executing_line": "#005f00",  # Dark Green for running line
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
}


# --- SETTINGS DIALOG ---
class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(300, 150)
        self.settings = settings if settings else {}

        # Apply Theme
        self.setStyleSheet(
            f"""
            QDialog {{ background-color: {COLORS['modal_bg']}; color: {COLORS['fg']}; }}
            QLabel {{ color: {COLORS['fg']}; font-size: 14px; }}
            QCheckBox {{ color: {COLORS['fg']}; spacing: 5px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; }}
        """
        )

        layout = QVBoxLayout(self)

        # Form
        form_layout = QFormLayout()

        self.cb_highlight = QCheckBox()
        self.cb_highlight.setChecked(self.settings.get("highlight_execution", True))

        lbl = QLabel("Highlight Executing Line:")
        form_layout.addRow(lbl, self.cb_highlight)

        layout.addLayout(form_layout)
        layout.addStretch()

        # Buttons
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

        keywords = [
            "MOV",
            "ADD",
            "SUB",
            "MUL",
            "DIV",
            "IN",
            "OUT",
            "CMP",
            "JMP",
            "BEQ",
            "BGT",
            "BLT",
            "STOP",
            "ORG",
        ]
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

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.lineNumberAreaPaintEvent(event)


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

        font = QFont("Consolas", 12)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.highlight_lines()

    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        space = 3 + self.fontMetrics().horizontalAdvance("9") * digits
        return space + 10

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

    def set_execution_line(self, line_idx):
        self.execution_line_index = line_idx
        self.highlight_lines()

        # Scroll to line if it's out of view
        if line_idx >= 0:
            block = self.document().findBlockByNumber(line_idx)
            cursor = self.textCursor()
            cursor.setPosition(block.position())
            self.ensureCursorVisible()

    def highlight_lines(self):
        extra_selections = []

        if not self.isReadOnly():
            # 1. Highlight current cursor line (Grey)
            selection = QTextEdit.ExtraSelection()
            line_color = QColor(COLORS["current_line"])
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

            # 2. Highlight Execution Line (Green) - Only if enabled
            if self.show_execution_highlight and self.execution_line_index >= 0:
                exec_selection = QTextEdit.ExtraSelection()
                exec_color = QColor(COLORS["executing_line"])  # Greenish
                exec_selection.format.setBackground(exec_color)
                exec_selection.format.setProperty(QTextFormat.FullWidthSelection, True)

                # Create cursor at specific line
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

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor(COLORS["comment"]))
                # If this is the executing line, make the number bright green
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
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1


# --- MAIN WINDOW ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PicoComputer IDE")
        self.resize(1200, 800)
        self.setWindowIcon(QIcon.fromTheme("system-run"))

        self.emu = PicoEmulator()
        self.timer = QTimer()
        self.timer.timeout.connect(self.step_execution)

        self.current_file_path = None
        self.table_items_cache = {}
        self.pc_to_line_map = {}  # Maps memory address -> text line index
        self.is_auto_running = False  # Tracks if we should resume after input

        # Default Settings
        self.app_settings = {"highlight_execution": True}

        self.apply_styles()
        self.setup_ui()
        self.load_default_code()

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
            }}
            QHeaderView::section {{
                background-color: {COLORS['current_line']};
                color: {COLORS['cyan']};
                padding: 4px;
                border: 1px solid {COLORS['bg']};
            }}
            
            QLineEdit {{ 
                background-color: {COLORS['input_bg']}; 
                border: 1px solid {COLORS['comment']}; 
                border-radius: 4px; 
                padding: 5px; 
                color: {COLORS['fg']};
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
            
            QScrollBar:vertical {{
                border: none;
                background: {COLORS['bg']};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['comment']};
                min-height: 20px;
                border-radius: 5px;
            }}
        """
        self.setStyleSheet(qss)

    def setup_ui(self):
        # --- TOOLBAR ---
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # File Actions
        open_act = QAction("Open", self)
        open_act.triggered.connect(self.open_file)
        toolbar.addAction(open_act)

        save_act = QAction("Save", self)
        save_act.triggered.connect(self.save_file)
        toolbar.addAction(save_act)

        toolbar.addSeparator()

        # Settings Action
        settings_act = QAction("Settings", self)
        settings_act.triggered.connect(self.open_settings)
        toolbar.addAction(settings_act)

        toolbar.addSeparator()

        # Emulator Actions
        self.act_load = QAction("Build/Load", self)
        self.act_load.triggered.connect(self.load_program)
        toolbar.addAction(self.act_load)

        self.act_run = QAction("Run", self)
        self.act_run.setShortcut("F5")
        self.act_run.triggered.connect(self.toggle_run)
        self.act_run.setEnabled(False)
        toolbar.addAction(self.act_run)

        self.act_step = QAction("Step", self)
        self.act_step.setShortcut("F10")
        self.act_step.triggered.connect(self.manual_step)
        self.act_step.setEnabled(False)
        toolbar.addAction(self.act_step)

        reset_act = QAction("Reset", self)
        reset_act.triggered.connect(self.reset_program)
        toolbar.addAction(reset_act)

        # --- CENTRAL LAYOUT ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Horizontal)

        # --- LEFT: EDITOR ---
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

        # --- RIGHT: MONITOR ---
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Status Bar
        status_frame = QFrame()
        status_frame.setStyleSheet(
            f"background-color: {COLORS['current_line']}; border-radius: 5px;"
        )
        status_layout = QHBoxLayout(status_frame)

        self.lbl_status = QLabel("IDLE")
        self.lbl_status.setStyleSheet(f"color: {COLORS['pink']}; font-weight: bold;")
        self.lbl_pc = QLabel("PC: 000")
        self.lbl_pc.setStyleSheet(f"color: {COLORS['cyan']}; font-family: Consolas;")

        status_layout.addWidget(QLabel("STATUS:"))
        status_layout.addWidget(self.lbl_status)
        status_layout.addStretch()
        status_layout.addWidget(self.lbl_pc)
        right_layout.addWidget(status_frame)

        # Memory Table
        right_layout.addWidget(QLabel("MEMORY WATCH"))
        self.mem_table = QTableWidget()
        self.mem_table.setColumnCount(3)
        self.mem_table.setHorizontalHeaderLabels(["VAR", "ADDR", "VAL"])
        self.mem_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mem_table.verticalHeader().setVisible(False)
        self.mem_table.setShowGrid(False)
        self.mem_table.setAlternatingRowColors(True)
        self.mem_table.setStyleSheet(f"alternate-background-color: #2e303e;")
        right_layout.addWidget(self.mem_table)

        # Console
        right_layout.addWidget(QLabel("TERMINAL OUTPUT"))
        self.console_out = QTextEdit()
        self.console_out.setReadOnly(True)
        self.console_out.setFont(QFont("Consolas", 10))
        self.console_out.setStyleSheet(
            f"background-color: #1e1e1e; color: {COLORS['green']}; border: 1px solid #333;"
        )
        self.console_out.setMaximumHeight(150)
        right_layout.addWidget(self.console_out)

        # Input Area
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

    # --- LOGIC ---
    def open_settings(self):
        dlg = SettingsDialog(self, self.app_settings)
        if dlg.exec():
            self.app_settings = dlg.get_settings()
            # Update Editor based on new settings
            self.editor.show_execution_highlight = self.app_settings[
                "highlight_execution"
            ]
            self.editor.highlight_lines()  # Refresh

    def load_default_code(self):
        default_code = """;
M = 1
N = 2
R = 3
ORG 8

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
        """
        Attempts to map Memory Addresses (PC) to Text Line Numbers.
        """
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
                current_address += 1  # Assume 1 word per instruction

    def load_program(self):
        code = self.editor.toPlainText()
        try:
            self.emu.parse(code)
            self.build_sourcemap(code)

            self.console_out.clear()
            self.console_out.append(">>> Build Successful. Ready.")
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
            self.update_ui()
        except Exception as e:
            self.console_out.append(f"ERR> {str(e)}")
            self.lbl_status.setText("PARSE ERROR")
            self.lbl_status.setStyleSheet(f"color: {COLORS['red']}; font-weight: bold;")
            QMessageBox.critical(self, "Parse Error", str(e))

    def reset_program(self):
        self.timer.stop()
        self.is_auto_running = False
        self.load_program()

    def toggle_run(self):
        if self.timer.isActive():
            self.timer.stop()
            self.is_auto_running = False  # User manually paused
            self.act_run.setText("Run")
            self.lbl_status.setText("PAUSED")
            self.lbl_status.setStyleSheet(
                f"color: {COLORS['orange']}; font-weight: bold;"
            )
        else:
            if self.emu.is_finished:
                self.reset_program()

            self.is_auto_running = True  # User started running
            self.timer.start(100)
            self.act_run.setText("Stop")
            self.lbl_status.setText("RUNNING")
            self.lbl_status.setStyleSheet(
                f"color: {COLORS['green']}; font-weight: bold;"
            )

    def manual_step(self):
        self.timer.stop()
        self.is_auto_running = False
        self.act_run.setText("Run")
        self.step_execution()

    def step_execution(self):
        self.emu.step()
        self.update_ui()

    def update_ui(self):
        self.lbl_pc.setText(f"PC: {self.emu.pc}")

        # Highlight current line
        if self.app_settings["highlight_execution"]:
            line_idx = self.pc_to_line_map.get(self.emu.pc, -1)
            self.editor.set_execution_line(line_idx)

        # Finished?
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
            return

        # Input needed?
        if self.emu.input_needed > 0:
            if self.timer.isActive():
                self.timer.stop()  # Pause loop to wait for input
                # We keep is_auto_running = True so we know to resume later
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

        # Console Output
        if self.emu.output_buffer:
            for line in self.emu.output_buffer:
                self.console_out.append(f"OUT> {line}")
                self.console_out.verticalScrollBar().setValue(
                    self.console_out.verticalScrollBar().maximum()
                )
            self.emu.output_buffer = []

        # Table Update
        registers_list = list(self.emu.registers.items())
        if self.mem_table.rowCount() != len(registers_list):
            self.mem_table.setRowCount(len(registers_list))

        for row, (name, addr) in enumerate(registers_list):
            # SAFE MEMORY ACCESS FIX
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
                i_addr.setTextAlignment(Qt.AlignCenter)
                i_val.setTextAlignment(Qt.AlignCenter)
                i_val.setForeground(QColor(COLORS["cyan"]))

                self.mem_table.setItem(row, 0, i_name)
                self.mem_table.setItem(row, 1, i_addr)
                self.mem_table.setItem(row, 2, i_val)
                self.table_items_cache[row] = (i_name, i_addr, i_val)

            self.table_items_cache[row][0].setText(name)
            self.table_items_cache[row][1].setText(str(addr))
            self.table_items_cache[row][2].setText(str(val))

    def handle_input(self):
        text = self.input_field.text()
        if not text:
            return

        # Provide input to emulator
        if self.emu.provide_input(text):
            self.console_out.append(f"IN < {text}")
            self.input_field.clear()
            self.update_ui()

            # Check if we should resume auto-running
            if self.emu.input_needed == 0:
                if self.is_auto_running:
                    self.act_run.setText("Stop")
                    self.lbl_status.setText("RUNNING")
                    self.lbl_status.setStyleSheet(
                        f"color: {COLORS['green']}; font-weight: bold;"
                    )
                    self.timer.start(100)  # Resume execution automatically
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
