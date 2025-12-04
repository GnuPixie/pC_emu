import re


class PicoEmulator:
    def __init__(self):
        self.reset()

    def reset(self):
        """Resets the emulator state to initial values."""
        self.memory = [0] * 65536  # 64K memory space
        self.pc = 0  # Program Counter
        self.sp = 65500  # Stack Pointer (starts high, grows down)
        self.registers = {}  # Symbol map (e.g., {"A": 10, "LOOP": 5})
        self.labels = {}  # Jump label map
        self.instructions = {}  # Map: Address -> Instruction Data

        self.is_running = False
        self.is_finished = False

        self.output_buffer = []  # Stores print outputs
        self.last_error = ""

        # Input handling state
        self.input_needed = 0
        self.input_dest_addr = 0

        # Track modified memory for GUI updates
        self.touched_memory = set()

    def parse(self, source_code):
        """Parses assembly code, extracts labels/vars, and loads instructions."""
        self.reset()
        lines = source_code.split("\n")
        current_address = 0

        # Pass 1: Parsing
        for idx, line in enumerate(lines):
            # Strip comments and whitespace
            line = line.split(";")[0].strip()
            if not line:
                continue

            # 1. Variable Definition (e.g., A = 10)
            if "=" in line:
                parts = line.split("=")
                name = parts[0].strip().upper()
                try:
                    val = int(parts[1].strip())
                    self.registers[name] = val
                    # Initialize memory location if it falls in FDA (0-7) or generic RAM
                    if 0 <= val < len(self.memory):
                        self.memory[val] = 0
                        self.touched_memory.add(val)
                except ValueError:
                    pass
                continue

            # 2. ORG Directive (e.g., ORG 100)
            if line.upper().startswith("ORG"):
                try:
                    parts = line.split()
                    current_address = int(parts[1])
                    self.pc = current_address  # Set start PC to ORG
                except:
                    pass
                continue

            # 3. Label Definition (e.g., LOOP:)
            if ":" in line:
                label_part, instr_part = line.split(":", 1)
                label_name = label_part.strip().upper()
                self.labels[label_name] = current_address
                line = instr_part.strip()

            # 4. Instruction Store
            if line:
                self.instructions[current_address] = {"text": line, "line_no": idx + 1}
                current_address += 1

    def resolve_symbol(self, token):
        """Resolves a raw string symbol to an address/value constant."""
        token = token.strip().upper()
        if token.isdigit() or (token.startswith("-") and token[1:].isdigit()):
            return int(token)
        if token in self.registers:
            return self.registers[token]
        if token in self.labels:
            return self.labels[token]
        raise ValueError(f"Unknown symbol: {token}")

    def resolve_value(self, operand):
        """
        GETTER: Determines the value of an operand for calculation.

        Syntaxes supported:
        1. "100"    -> Immediate Integer 100
        2. "#A"     -> Immediate value of symbol A (e.g., 5)
        3. "#100"   -> Immediate Integer 100
        4. "A"      -> Direct: Returns Memory[A] (e.g., Memory[5])
        5. "(A)"    -> Indirect: Returns Memory[Memory[A]]
        """
        operand = operand.strip().upper()

        # Case 1: Indirect Addressing ((A))
        if operand.startswith("(") and operand.endswith(")"):
            inner = operand[1:-1]
            # Address where the pointer is stored
            ptr_loc = self.resolve_symbol(inner)
            # The actual target address
            real_addr = self.memory[ptr_loc]
            if 0 <= real_addr < len(self.memory):
                return self.memory[real_addr]
            raise ValueError(f"Indirect access out of bounds: {real_addr}")

        # Case 2: Immediate Value (#A or #100)
        if operand.startswith("#"):
            return self.resolve_symbol(operand[1:])

        # Case 3: Raw Number (treated as Immediate in math, but Context matters)
        # In pC, "ADD A, 5, B" -> 5 is immediate.
        # But "ADD A, B, C" -> B and C are addresses.
        # This function assumes if it's a number, it's a value.
        if operand.isdigit() or (operand.startswith("-") and operand[1:].isdigit()):
            return int(operand)

        # Case 4: Direct Addressing (A)
        # It's a symbol (register/variable name), so we read the memory at that location.
        addr = self.resolve_symbol(operand)
        if 0 <= addr < len(self.memory):
            return self.memory[addr]

        raise ValueError(f"Memory access out of bounds: {addr}")

    def resolve_write_target(self, operand):
        """
        SETTER HELPER: determines the specific memory INDEX to write to.

        Syntaxes supported:
        1. "A"      -> Returns value of A (e.g., 5). We will write to Memory[5].
        2. "(A)"    -> Read Memory[A] (e.g., 100). We will write to Memory[100].
        """
        operand = operand.strip().upper()

        # Indirect Write: MOV (A), ...
        if operand.startswith("(") and operand.endswith(")"):
            inner = operand[1:-1]
            ptr_loc = self.resolve_symbol(inner)  # e.g., 5
            target_addr = self.memory[ptr_loc]  # e.g., 100
            return target_addr

        # Direct Write: MOV A, ...
        return self.resolve_symbol(operand)

    def set_value(self, operand, value):
        """Writes value to the memory location calculated from operand."""
        dest_addr = self.resolve_write_target(operand)

        if 0 <= dest_addr < len(self.memory):
            self.memory[dest_addr] = int(value)
            self.touched_memory.add(dest_addr)
        else:
            raise ValueError(f"Memory write out of bounds: {dest_addr}")

    def provide_input(self, value):
        """Called by GUI to provide input."""
        if self.input_needed > 0:
            try:
                val = int(value)
                self.memory[self.input_dest_addr] = val
                self.touched_memory.add(self.input_dest_addr)

                self.input_dest_addr += 1
                self.input_needed -= 1

                # Only advance PC if we are done with all inputs for this instruction
                if self.input_needed == 0:
                    self.pc += 1

                return True
            except ValueError:
                return False
        return False

    def step(self):
        """Executes a single instruction."""
        if self.is_finished or self.input_needed > 0:
            return

        if self.pc not in self.instructions:
            self.last_error = f"End of program or invalid PC: {self.pc}"
            self.is_finished = True
            return

        instr_data = self.instructions[self.pc]
        line = instr_data["text"]

        # --- IMPROVED TOKENIZER ---
        # 1. Split Opcode (first word) from arguments
        #    "BEQ (a1),( a2), eq" -> opcode="BEQ", rest="(a1),( a2), eq"
        parts = line.split(maxsplit=1)
        opcode = parts[0].upper()
        args = []
        if len(parts) > 1:
            # 2. Split by comma to handle spaces within parentheses safely
            args = [arg.strip() for arg in parts[1].split(",")]

        next_pc = self.pc + 1

        try:
            if opcode == "MOV":
                # MOV Dest, Src
                val = self.resolve_value(args[1])
                self.set_value(args[0], val)

            elif opcode in ["ADD", "SUB", "MUL", "DIV"]:
                # Arithmetic: OP Dest, Src1, Src2
                val1 = self.resolve_value(args[1])
                val2 = self.resolve_value(args[2])

                res = 0
                if opcode == "ADD":
                    res = val1 + val2
                elif opcode == "SUB":
                    res = val1 - val2
                elif opcode == "MUL":
                    res = val1 * val2
                elif opcode == "DIV":
                    if val2 == 0:
                        raise ValueError("Division by zero")
                    res = val1 // val2

                self.set_value(args[0], res)

            elif opcode == "IN":
                # IN Address, [Count]
                # Supports Indirect: IN (A), 2
                target_addr = self.resolve_write_target(args[0])

                count = 1
                if len(args) > 1:
                    count = self.resolve_value(args[1])

                if count > 0:
                    self.input_needed = count
                    self.input_dest_addr = target_addr
                    # Do NOT advance PC yet
                    return

            elif opcode == "OUT":
                # OUT Address, [Count]
                # Supports Indirect: OUT (A) via resolve_value logic

                # Logic check: OUT expects a value source.
                # If args[0] is A, we want Mem[A].
                # If args[0] is (A), we want Mem[Mem[A]].
                # This is exactly what resolve_value does if we treat it as a value source.
                # However, for array output, we need the start address.

                # If format is OUT A, 5 -> We need address of A (which is A's value).
                # If format is OUT (A), 5 -> We need address pointed to by A.

                start_addr = 0
                raw_arg = args[0].strip().upper()

                # Check direct vs indirect manually to get the Start Address
                if raw_arg.startswith("(") and raw_arg.endswith(")"):
                    inner = raw_arg[1:-1]
                    ptr_loc = self.resolve_symbol(inner)
                    start_addr = self.memory[ptr_loc]
                else:
                    # Direct: OUT A -> Start address is value of symbol A
                    start_addr = self.resolve_symbol(raw_arg)

                count = 1
                if len(args) > 1:
                    count = self.resolve_value(args[1])

                line_out = []
                for i in range(count):
                    curr = start_addr + i
                    if curr < len(self.memory):
                        line_out.append(str(self.memory[curr]))
                self.output_buffer.append(" ".join(line_out))

            elif opcode == "BEQ":
                # BEQ Val1, Val2, Label
                val1 = self.resolve_value(args[0])
                val2 = self.resolve_value(args[1])
                label = args[2].upper()

                if val1 == val2:
                    if label in self.labels:
                        next_pc = self.labels[label]
                    else:
                        raise ValueError(f"Unknown label: {label}")

            elif opcode == "BGT":
                val1 = self.resolve_value(args[0])
                val2 = self.resolve_value(args[1])
                label = args[2].upper()

                if val1 > val2:
                    if label in self.labels:
                        next_pc = self.labels[label]
                    else:
                        raise ValueError(f"Unknown label: {label}")

            elif opcode == "JSR":
                label = args[0].upper()
                self.memory[self.sp] = next_pc
                self.touched_memory.add(self.sp)
                self.sp -= 1
                if label in self.labels:
                    next_pc = self.labels[label]
                else:
                    raise ValueError(f"Unknown label: {label}")

            elif opcode == "RTS":
                self.sp += 1
                if self.sp >= len(self.memory):
                    raise ValueError("Stack underflow")
                next_pc = self.memory[self.sp]

            elif opcode == "STOP":
                self.is_finished = True
                if args:
                    val = self.resolve_value(args[0])
                    self.output_buffer.append(f"STOP Result: {val}")

            self.pc = next_pc

        except Exception as e:
            self.last_error = f"Error line {instr_data['line_no']}: {str(e)}"
            self.is_finished = True
