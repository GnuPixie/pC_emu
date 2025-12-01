import re


class PicoEmulator:
    def __init__(self):
        self.reset()

    def reset(self):
        self.memory = [0] * 65536  # 64K memorije
        self.pc = 0  # Program Counter
        self.sp = 65500  # Stack Pointer
        self.registers = {}  # Simbolička imena (A, B, N...) -> adrese
        self.labels = {}  # Labele za skokove
        self.instructions = {}  # Mapa adresa -> instrukcija
        self.is_running = False
        self.is_finished = False
        self.output_buffer = []
        self.input_needed = 0  # Koliko još brojeva se čeka
        self.input_dest_addr = 0  # Gde se upisuje input
        self.last_error = ""

    def parse(self, source_code):
        self.reset()
        lines = source_code.split("\n")
        current_address = 0

        for idx, line in enumerate(lines):
            # Ukloni komentare i whitespace
            line = line.split(";")[0].strip()
            if not line:
                continue

            # 1. Definicija promenljive: X = 10
            if "=" in line:
                parts = line.split("=")
                name = parts[0].strip().upper()
                try:
                    val = int(parts[1].strip())
                    self.registers[name] = val
                    # Inicijalizacija memorije na 0 ako je u opsegu
                    if 0 <= val < len(self.memory):
                        self.memory[val] = 0
                except ValueError:
                    pass
                continue

            # 2. ORG direktiva
            if line.upper().startswith("ORG"):
                try:
                    parts = line.split()
                    current_address = int(parts[1])
                    self.pc = current_address
                except:
                    pass
                continue

            # 3. Labele: LOOP: ADD...
            if ":" in line:
                label_part, instr_part = line.split(":", 1)
                label_name = label_part.strip().upper()
                self.labels[label_name] = current_address
                line = instr_part.strip()

            # Ako je ostala instrukcija
            if line:
                self.instructions[current_address] = {"text": line, "line_no": idx + 1}
                current_address += 1

    def resolve_value(self, operand):
        """
        Ključna logika za picoComputer adresiranje:
        1. "6"      -> Broj 6 (Immediate)
        2. "#A"     -> Vrednost simbola A (Adresa od A, tj. Immediate)
        3. "A"      -> Memorija[A] (Direct)
        4. "(A)"    -> Memorija[Memorija[A]] (Indirect)
        """
        operand = operand.strip().upper()

        # Slučaj 1: Čist broj (npr. "6" ili "-1")
        # U ovom asembleru, ovo je NEPOSREDNA vrednost.
        if operand.isdigit() or (operand.startswith("-") and operand[1:].isdigit()):
            return int(operand)

        # Slučaj 2: Simbolička konstanta (#A) ili eksplicitna konstanta (#6)
        if operand.startswith("#"):
            val_str = operand[1:]
            if val_str.isdigit() or (val_str.startswith("-") and val_str[1:].isdigit()):
                return int(val_str)
            if val_str in self.registers:
                return self.registers[val_str]  # Vraća adresu (vrednost simbola)
            if val_str in self.labels:
                return self.labels[val_str]
            raise ValueError(f"Nepoznata konstanta: {val_str}")

        # Slučaj 3: Indirektno adresiranje ((X))
        if operand.startswith("(") and operand.endswith(")"):
            inner = operand[1:-1]
            # Ovde nam treba adresa pokazivača.
            # Ako je inner "A", resolve_address("A") vraca adresu od A.
            addr_ptr = self.resolve_address(inner)
            real_addr = self.memory[addr_ptr]
            if 0 <= real_addr < len(self.memory):
                return self.memory[real_addr]
            raise ValueError(f"Indirektna adresa van opsega: {real_addr}")

        # Slučaj 4: Direktno adresiranje (Simbol "A")
        # Ako je operand simbol, čitamo iz memorije sa te adrese.
        if operand in self.registers:
            addr = self.registers[operand]
            return self.memory[addr]

        raise ValueError(f"Nepoznat operand: {operand}")

    def resolve_address(self, operand):
        """
        Koristi se kada nam treba *lokacija* (za upis ili pokazivač), a ne vrednost.
        """
        operand = operand.strip().upper()

        # Ako je broj (npr. MOV 100, 5 -> upisi u adresu 100)
        if operand.isdigit():
            return int(operand)

        # Ako je simbol (npr. MOV A, 5 -> upisi u adresu od A)
        if operand in self.registers:
            return self.registers[operand]

        raise ValueError(f"Nije validna adresa: {operand}")

    def set_value(self, operand, value):
        operand = operand.strip().upper()
        dest_addr = 0

        # Indirektno upisivanje ((X))
        if operand.startswith("(") and operand.endswith(")"):
            inner = operand[1:-1]
            ptr_addr = self.resolve_address(inner)
            dest_addr = self.memory[ptr_addr]
        else:
            # Direktno upisivanje (X ili 100)
            dest_addr = self.resolve_address(operand)

        if 0 <= dest_addr < len(self.memory):
            self.memory[dest_addr] = int(value)
        else:
            raise ValueError(f"Upis van memorije: {dest_addr}")

    def step(self):
        if self.is_finished or self.input_needed > 0:
            return

        if self.pc not in self.instructions:
            self.last_error = f"Kraj programa ili nepoznata adresa {self.pc}"
            self.is_finished = True
            return

        instr_data = self.instructions[self.pc]
        line = instr_data["text"]

        parts = re.split(r"[ ,]+", line)
        parts = [p.strip() for p in parts if p.strip()]

        opcode = parts[0].upper()
        args = parts[1:]

        next_pc = self.pc + 1

        try:
            if opcode == "MOV":
                # MOV Dest, Src
                val = self.resolve_value(args[1])
                self.set_value(args[0], val)

            elif opcode == "ADD":
                val1 = self.resolve_value(args[1])
                val2 = self.resolve_value(args[2])
                self.set_value(args[0], val1 + val2)

            elif opcode == "SUB":
                val1 = self.resolve_value(args[1])
                val2 = self.resolve_value(args[2])
                self.set_value(args[0], val1 - val2)

            elif opcode == "MUL":
                val1 = self.resolve_value(args[1])
                val2 = self.resolve_value(args[2])
                self.set_value(args[0], val1 * val2)

            elif opcode == "DIV":
                val1 = self.resolve_value(args[1])
                val2 = self.resolve_value(args[2])
                if val2 == 0:
                    raise ValueError("Deljenje nulom")
                self.set_value(args[0], val1 // val2)

            elif opcode == "IN":
                # IN Adresa, Broj
                count = self.resolve_value(
                    args[1]
                )  # Ovde je '1' ili '2' zapravo broj (Immediate)
                addr = self.resolve_address(args[0])

                if count > 0:
                    self.input_needed = count
                    self.input_dest_addr = addr
                    self.pc = next_pc
                    return

            elif opcode == "OUT":
                # OUT Adresa, Broj
                addr = self.resolve_address(args[0])
                count = self.resolve_value(args[1])  # I ovde je '1' immediate broj
                line_out = []
                for i in range(count):
                    val = self.memory[addr + i]
                    line_out.append(str(val))
                self.output_buffer.append(" ".join(line_out))

            elif opcode == "BEQ":
                val1 = self.resolve_value(args[0])
                val2 = self.resolve_value(args[1])  # '0' je ovde broj 0
                label = args[2].upper()
                if val1 == val2:
                    if label in self.labels:
                        next_pc = self.labels[label]
                    else:
                        raise ValueError(f"Nepoznata labela: {label}")

            elif opcode == "BGT":
                val1 = self.resolve_value(args[0])
                val2 = self.resolve_value(args[1])  # '0' je broj 0
                label = args[2].upper()
                if val1 > val2:
                    if label in self.labels:
                        next_pc = self.labels[label]
                    else:
                        raise ValueError(f"Nepoznata labela: {label}")

            elif opcode == "JSR":
                label = args[0].upper()
                self.memory[self.sp] = next_pc
                self.sp -= 1
                if label in self.labels:
                    next_pc = self.labels[label]
                else:
                    raise ValueError(f"Nepoznata labela: {label}")

            elif opcode == "RTS":
                self.sp += 1
                next_pc = self.memory[self.sp]

            elif opcode == "STOP":
                self.is_finished = True
                if args:
                    val = self.resolve_value(args[0])
                    self.output_buffer.append(f"STOP Result: {val}")

            self.pc = next_pc

        except Exception as e:
            self.last_error = f"Greška linija {instr_data['line_no']}: {str(e)}"
            self.is_finished = True

    def provide_input(self, value):
        if self.input_needed > 0:
            try:
                val = int(value)
                self.memory[self.input_dest_addr] = val
                self.input_dest_addr += 1
                self.input_needed -= 1
                return True
            except ValueError:
                return False
        return False
