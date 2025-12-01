import sys
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QSplitter,
    QLineEdit,
    QMessageBox,
    QHeaderView,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QPalette

from emulator import PicoEmulator


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("picoComputer Emulator")
        self.resize(1100, 750)

        self.emu = PicoEmulator()
        self.timer = QTimer()
        self.timer.timeout.connect(self.step_execution)

        # Pamtimo redove tabele da ne bi stalno kreirali nove objekte
        self.table_items_cache = {}

        self.setup_ui()

        # Default Euklidov algoritam
        default_code = """M = 1
N = 2
R = 3
ORG 8
IN M, 2      ; Unesi M i N (npr. 25 i 10)
LOOP: 
DIV R, M, N  ; R = M / N
MUL R, R, N  ; R = int(M/N) * N
SUB R, M, R  ; R = M - R (Ostatak)
MOV M, N     ; M = N
MOV N, R     ; N = R
BGT R, 0, LOOP
OUT M, 1     ; Ispisi rezultat
STOP
"""
        self.editor.setPlainText(default_code)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        splitter = QSplitter(Qt.Horizontal)

        # --- LEVA STRANA: EDITOR ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.editor = QTextEdit()
        self.editor.setFont(QFont("Consolas", 12))
        left_layout.addWidget(QLabel("Assembly Source Code:"))
        left_layout.addWidget(self.editor)

        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load/Parse")
        self.btn_load.clicked.connect(self.load_program)

        self.btn_run = QPushButton("Run (Auto)")
        self.btn_run.clicked.connect(self.toggle_run)
        self.btn_run.setEnabled(False)

        self.btn_step = QPushButton("Step (Manual)")
        self.btn_step.clicked.connect(self.manual_step)
        self.btn_step.setEnabled(False)

        self.btn_reset = QPushButton("Reset")
        self.btn_reset.clicked.connect(self.reset_program)

        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_step)
        btn_layout.addWidget(self.btn_run)
        btn_layout.addWidget(self.btn_reset)
        left_layout.addLayout(btn_layout)

        # --- DESNA STRANA: MONITOR ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Status Panel
        status_panel = QHBoxLayout()
        self.lbl_status = QLabel("Status: IDLE")
        self.lbl_status.setFont(QFont("Arial", 10, QFont.Bold))
        self.lbl_pc = QLabel("PC: 0")
        self.lbl_pc.setFont(QFont("Arial", 10))
        status_panel.addWidget(self.lbl_status)
        status_panel.addWidget(self.lbl_pc)
        right_layout.addLayout(status_panel)

        # Tabela Memorije
        right_layout.addWidget(QLabel("Variables Watch:"))
        self.mem_table = QTableWidget()
        self.mem_table.setColumnCount(3)
        self.mem_table.setHorizontalHeaderLabels(["Name", "Address", "Value"])
        self.mem_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.mem_table)

        # Konzola i Input
        right_layout.addWidget(QLabel("Output Console:"))
        self.console_out = QTextEdit()
        self.console_out.setReadOnly(True)
        self.console_out.setFont(QFont("Consolas", 10))
        self.console_out.setMaximumHeight(150)
        right_layout.addWidget(self.console_out)

        input_layout = QHBoxLayout()
        input_label = QLabel("INPUT NEEDED:")
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type number and press Enter...")
        self.input_field.returnPressed.connect(self.handle_input)
        self.input_field.setEnabled(False)
        self.input_field.setStyleSheet("background-color: #f0f0f0; color: gray;")

        input_layout.addWidget(input_label)
        input_layout.addWidget(self.input_field)
        right_layout.addLayout(input_layout)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([600, 450])
        main_layout.addWidget(splitter)

    def load_program(self):
        code = self.editor.toPlainText()
        try:
            self.emu.parse(code)
            self.console_out.clear()
            self.console_out.append(">>> Program loaded. Press Run or Step.")
            self.btn_run.setEnabled(True)
            self.btn_step.setEnabled(True)
            self.lbl_status.setText("Status: READY")
            self.table_items_cache = {}  # Resetuj keš tabele
            self.mem_table.setRowCount(0)
            self.update_ui()
        except Exception as e:
            QMessageBox.critical(self, "Parse Error", str(e))

    def reset_program(self):
        self.timer.stop()
        self.load_program()

    def toggle_run(self):
        if self.timer.isActive():
            self.timer.stop()
            self.btn_run.setText("Run (Auto)")
            self.lbl_status.setText("Status: PAUSED")
        else:
            if self.emu.is_finished:
                self.reset_program()
            self.timer.start(100)  # Brzina izvršavanja
            self.btn_run.setText("Stop")
            self.lbl_status.setText("Status: RUNNING")

    def manual_step(self):
        self.timer.stop()
        self.btn_run.setText("Run (Auto)")
        self.step_execution()

    def step_execution(self):
        self.emu.step()
        self.update_ui()

    def update_ui(self):
        # 1. Osveži PC i Status
        self.lbl_pc.setText(f"PC: {self.emu.pc}")

        # Logika za prekid rada
        if self.emu.is_finished:
            self.timer.stop()
            self.btn_run.setText("Run (Auto)")
            if self.emu.last_error:
                self.lbl_status.setText("Status: ERROR")
                QMessageBox.critical(self, "Runtime Error", self.emu.last_error)
            else:
                self.lbl_status.setText("Status: FINISHED")
                self.console_out.append(">>> Program execution finished.")
            return

        # Logika za Input
        if self.emu.input_needed > 0:
            if self.timer.isActive():
                self.timer.stop()  # Pauziraj izvršavanje dok se ne unese broj
                self.btn_run.setText("Run (Auto)")

            self.lbl_status.setText(f"WAITING INPUT ({self.emu.input_needed} left)")
            self.lbl_status.setStyleSheet("color: red; font-weight: bold")
            self.input_field.setEnabled(True)
            self.input_field.setStyleSheet(
                "background-color: #ffffcc; color: black;"
            )  # Žuta boja
            self.input_field.setFocus()
        else:
            self.lbl_status.setStyleSheet("color: green;")
            self.input_field.setEnabled(False)
            self.input_field.setStyleSheet("background-color: #f0f0f0; color: gray;")

        # 2. Osveži Konzolu
        if self.emu.output_buffer:
            for line in self.emu.output_buffer:
                self.console_out.append(f"OUT> {line}")
            self.emu.output_buffer = []

        # 3. Osveži Tabelu (Optimizovano)
        # Prvo sinhronizuj broj redova
        registers_list = list(self.emu.registers.items())
        if self.mem_table.rowCount() != len(registers_list):
            self.mem_table.setRowCount(len(registers_list))

        for row, (name, addr) in enumerate(registers_list):
            val = self.emu.memory[addr]

            # Kreiramo iteme samo ako ne postoje
            if row not in self.table_items_cache:
                item_name = QTableWidgetItem(name)
                item_addr = QTableWidgetItem(str(addr))
                item_val = QTableWidgetItem(str(val))

                # Centriranje
                item_addr.setTextAlignment(Qt.AlignCenter)
                item_val.setTextAlignment(Qt.AlignCenter)

                self.mem_table.setItem(row, 0, item_name)
                self.mem_table.setItem(row, 1, item_addr)
                self.mem_table.setItem(row, 2, item_val)
                self.table_items_cache[row] = (item_name, item_addr, item_val)

            # Samo treba osvežiti tekst za vrednost (Name i Addr su fiksni za ovaj emulator)
            # Ali osvežimo sve za svaki slučaj ako se nešto redefinisalo
            self.table_items_cache[row][0].setText(name)
            self.table_items_cache[row][1].setText(str(addr))
            self.table_items_cache[row][2].setText(str(val))

    def handle_input(self):
        text = self.input_field.text()
        if not text:
            return

        success = self.emu.provide_input(text)
        if success:
            self.console_out.append(f"IN < {text}")
            self.input_field.clear()

            # Ako više ne treba input, automatski nastavi ako je bio auto-run
            # Ili samo osveži UI da korisnik može opet da klikne Run
            self.update_ui()

            # Ako je input završen, fokusiraj nazad editor ili dugme
            if self.emu.input_needed == 0:
                self.lbl_status.setText("Status: READY")
                # Opciono: Automatski nastavi
                # self.toggle_run()
        else:
            QMessageBox.warning(self, "Input Error", "Please enter a valid integer.")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
