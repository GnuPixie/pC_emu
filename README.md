# PicoComputer IDE - Feature Roadmap

## Phase 1: Quick Wins & Metrics

_Features that are easy to implement but add immediate value._

- [x] **Execution Speed Slider**
- [x] Add `QSlider` to toolbar (Range: 10ms - 1000ms).
- [x] Connect `valueChanged` to `timer.setInterval()`.
- [x] **Cycle Counter**
- [x] Add `self.cycles = 0` to tracking variables.
- [x] Increment on every `step_execution`.
- [x] Display next to PC label (e.g., `CYCLES: 42`).
- [x] **Reset "Hard" vs "Soft"**
- [x] **Soft Reset:** Reset PC to start address, keep memory/registers.
- [x] **Hard Reset:** Wipe all memory/registers to 0 and reload code.

## Phase 2: Editor Experience

_Making the coding experience smoother._

- [ ] **Instruction Autocomplete**
  - [ ] Implement `QCompleter` on the `CodeEditor`.
  - [ ] Populate with standard keywords (`MOV`, `ADD`, `JMP`, etc.).
  - [ ] **Bonus:** Dynamically add defined Labels to the suggestion list.
- [ ] **Smart Indentation**
  - [ ] When pressing Enter, match the indentation level of the previous line.
- [ ] **Reference Dock**
  - [ ] Create a `QDockWidget` pinned to the right side.
  - [ ] Display a static HTML/Text list of all available opcodes and their syntax.
  - [ ] Make opcodes clickable to insert them into the editor.

## Phase 3: Advanced Debugging (The "Killer" Features)

_Features that make this a serious educational tool._

- [ ] **"Time Travel" (Step Back)**
  - [ ] Implement `emulator.snapshot()` to return a deep copy of state (RAM + Regs + PC).
  - [ ] Create a `history = []` stack in MainWindow.
  - [ ] Push state to stack before every `step()`.
  - [ ] Add "Step Back" button to pop stack and restore state.
- [ ] **Visual Memory Map (Grid View)**
  - [ ] Create a 10x10 Grid (GraphicsView or Table) representing 100 memory slots.
  - [ ] **Color Coding:**
    - Grey: Empty (0)
    - Blue: Read access
    - Green: Write access (fade out color over time).

## Phase 4: Structural Changes

_Large architectural changes._

- [ ] **File Tabs**
  - [ ] Replace single `CodeEditor` with `QTabWidget`.
  - [ ] Manage separate `filepath` and `dirty` states for each tab.
- [ ] **Syntax Error Markers**
  - [ ] Instead of a popup box on error, highlight the specific line in Red in the editor.
  - [ ] Add a tooltip explaining the error on hover.
