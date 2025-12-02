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
        
        # VISIBILITY FIX: Track addresses that have been modified so GUI shows them
        self.touched_memory = set()

    def parse(self, source_code):
        """Parses assembly code, extracts labels/vars, and loads instructions."""
        self.reset()
        lines = source_code.split("\n")
        current_address = 0

        # Pass 1: Parsing
        for idx, line in enumerate(lines):
            # Remove comments and whitespace
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
                    # Initialize that memory location to 0 if valid
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
                self.instructions[current_address] = {
                    "text": line, 
                    "line_no": idx + 1
                }
                current_address += 1

    def resolve_value(self, operand):
        """
        Determines the value of an operand.
        1. "6"      -> 6 (Immediate Integer)
        2. "#A"     -> Value of A (The address itself, e.g., 10)
        3. "A"      -> Memory[A] (Value stored at address 10)
        4. "(A)"    -> Memory[Memory[A]] (Indirect)
        """
        operand = operand.strip().upper()

        # Case 1: Raw Number (Immediate)
        if operand.isdigit() or (operand.startswith("-") and operand[1:].isdigit()):
            return int(operand)

        # Case 2: Constant/Symbol Value (#A or #10)
        if operand.startswith("#"):
            val_str = operand[1:]
            if val_str.isdigit() or (val_str.startswith("-") and val_str[1:].isdigit()):
                return int(val_str)
            if val_str in self.registers:
                return self.registers[val_str]
            if val_str in self.labels:
                return self.labels[val_str]
            raise ValueError(f"Unknown constant: {val_str}")

        # Case 3: Indirect Addressing ((A))
        if operand.startswith("(") and operand.endswith(")"):
            inner = operand[1:-1]
            # Get the pointer address
            addr_ptr = self.resolve_address(inner)
            # Read the real address from the pointer
            real_addr = self.memory[addr_ptr]
            if 0 <= real_addr < len(self.memory):
                return self.memory[real_addr]
            raise ValueError(f"Indirect address out of bounds: {real_addr}")

        # Case 4: Direct Addressing (A)
        if operand in self.registers:
            addr = self.registers[operand]
            return self.memory[addr]

        raise ValueError(f"Unknown operand: {operand}")

    def resolve_address(self, operand):
        """
        Determines the target address for writing or pointers.
        Returns the memory INDEX, not the value at that index.
        """
        operand = operand.strip().upper()

        # If it's a number (e.g. 100)
        if operand.isdigit():
            return int(operand)

        # If it's a variable name (e.g. A)
        if operand in self.registers:
            return self.registers[operand]

        raise ValueError(f"Invalid address source: {operand}")

    def set_value(self, operand, value):
        """Writes a value to the destination defined by operand."""
        operand = operand.strip().upper()
        dest_addr = 0

        # Handle Indirect Write: MOV (ptr), 5
        if operand.startswith("(") and operand.endswith(")"):
            inner = operand[1:-1]
            ptr_addr = self.resolve_address(inner)
            dest_addr = self.memory[ptr_addr]
        else:
            # Handle Direct Write: MOV A, 5
            dest_addr = self.resolve_address(operand)

        if 0 <= dest_addr < len(self.memory):
            self.memory[dest_addr] = int(value)
            # CRITICAL: Mark this address as modified so the GUI updates it
            self.touched_memory.add(dest_addr)
        else:
            raise ValueError(f"Memory write out of bounds: {dest_addr}")

    def provide_input(self, value):
        """
        Called by GUI when user enters data.
        Updates memory and manages PC advancement.
        """
        if self.input_needed > 0:
            try:
                val = int(value)
                self.memory[self.input_dest_addr] = val
                self.touched_memory.add(self.input_dest_addr)
                
                self.input_dest_addr += 1
                self.input_needed -= 1
                
                # FIX: Only advance PC once ALL required inputs are received.
                if self.input_needed == 0:
                    self.pc += 1
                    
                return True
            except ValueError:
                return False
        return False

    def step(self):
        """Executes a single instruction."""
        # If waiting for input, do nothing.
        if self.is_finished or self.input_needed > 0:
            return

        if self.pc not in self.instructions:
            self.last_error = f"End of program or invalid PC: {self.pc}"
            self.is_finished = True
            return

        instr_data = self.instructions[self.pc]
        line = instr_data["text"]

        parts = re.split(r"[ ,]+", line)
        parts = [p.strip() for p in parts if p.strip()]

        opcode = parts[0].upper()
        args = parts[1:]

        # Default behavior: PC moves to next line.
        # We will override this for specific instructions (Jumps, IN).
        next_pc = self.pc + 1

        try:
            if opcode == "MOV":
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
                    raise ValueError("Division by zero")
                self.set_value(args[0], val1 // val2)

            elif opcode == "IN":
                # IN Address, [Count]
                addr = self.resolve_address(args[0])
                count = 1
                if len(args) > 1:
                    count = self.resolve_value(args[1])

                if count > 0:
                    self.input_needed = count
                    self.input_dest_addr = addr
                    # FIX: Do NOT advance 'next_pc' yet. 
                    # We stay on this instruction until provide_input() finishes.
                    return 

            elif opcode == "OUT":
                addr = self.resolve_address(args[0])
                count = 1
                if len(args) > 1:
                    count = self.resolve_value(args[1])

                line_out = []
                for i in range(count):
                    val = self.memory[addr + i]
                    line_out.append(str(val))
                self.output_buffer.append(" ".join(line_out))

            elif opcode == "BEQ":
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
                next_pc = self.memory[self.sp]

            elif opcode == "STOP":
                self.is_finished = True
                if args:
                    val = self.resolve_value(args[0])
                    self.output_buffer.append(f"STOP Result: {val}")

            # Apply the calculated PC
            self.pc = next_pc

        except Exception as e:
            self.last_error = f"Error line {instr_data['line_no']}: {str(e)}"
            self.is_finished = True