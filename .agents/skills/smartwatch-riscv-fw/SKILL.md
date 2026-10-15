---
name: smartwatch-riscv-fw
description: >-
  Guides RISC-V RV32I firmware development, assembly programming, and toolchain builds
  for the Smartwatch SoC. Use when modifying sw/app/main.s, writing assembly routines,
  implementing interrupt service routines (ISR), controlling hardware registers, handling
  the low-power waitirq custom instruction, or rebuilding firmware hex files.
---

# Smartwatch SoC RISC-V Firmware & Assembly Skill

This skill governs embedded software and assembly programming for the 32-bit RISC-V (PicoRV32) CPU in `sw/`, adhering to [03_firmware_and_software_spec.md](../../../docs/spec/03_firmware_and_software_spec.md).

---

## 1. Processor Core & ABI Standards

- **Core**: PicoRV32 RV32I integer core @ 12.288 MHz.
- **Calling Convention & Register Allocation**:
  - `zero` (`x0`): Constant zero.
  - `sp` (`x2`): Stack pointer, initialized to `0x1000_1FF0` (must maintain 16-byte alignment).
  - `a0` - `a7` (`x10` - `x17`): Function arguments and return values.
  - `t0` - `t6` (`x5-x7`, `x28-x31`): Caller-saved temporaries (volatile across calls).
  - `s0` - `s11` (`x8-x9`, `x18-x27`): Callee-saved preserved registers.

### 1.1 Custom Low-Power Instruction (`waitirq`)
- **Opcode**: `.word 0x0000006b`
- **Behavior**: Freezes CPU execution pipeline and clocks until an unmasked hardware interrupt is raised.
- **Usage Example**:
  ```assembly
  # Set LED to Standby Sleep (0x04)
  li   t0, 0x80000000
  li   t1, 0x04
  sw   t1, 0(t0)

  # Enter ultra-low power standby
  .word 0x0000006b    # waitirq: Sleep until VAD interrupt
  ```

---

## 2. Interrupt Vector & ISR Handshake Contract

The vector table is fixed at the start of ITCM:
- `0x0000_0000`: Reset handler (`j _start`)
- `0x0000_0010`: Interrupt service routine (`j irq_handler`)

### 2.1 Standard ISR Implementation Rule
In `irq_handler`, the firmware **must**:
1. Save volatile registers onto the stack.
2. Update debug LED to show ISR entry (`0x10`).
3. Check and acknowledge/clear the interrupt source:
   - For VAD wakeup: Write `1` to `VAD_CTRL[1]` (`0x4000_0010` with bit 1 set) to clear the hardware latch.
4. Process audio / trigger NPU inference.
5. Restore registers from the stack.
6. Return or loop back to low-power sleep (`.word 0x0000006b`).

---

## 3. Debug LED Status Codes (`0x8000_0000`)

To ensure real-time observability in both simulation and FPGA/ASIC bring-up, write status bytes to `0x8000_0000`:

| Hex Code | Symbolic Meaning | Trigger Location |
|---|---|---|
| `0x01` | Power-on Reset / Booting | `_start` entry |
| `0x02` | Peripherals Initialized | Post AFE/VAD setup |
| `0x04` | Standby Sleep (<20μW) | Right before `waitirq` |
| `0x10` | VAD Interrupt Triggered | `irq_handler` entry |
| `0x20` | Loading Features to NPU | Data transfer phase |
| `0x30` | Triggering NPU Inference | Post `NPU_CTRL[0] = 1` |
| `0x55` | Classification: Non-Keyword / Noise | Score0 >= Score1 |
| `0xAA` | Classification: Target Keyword Matched | Score1 > Score0 |
| `0xFF` | Trap / Illegal State | Unhandled exception |

---

## 4. Firmware Build & Re-Assembly Workflow

Whenever `sw/app/main.s` or related assembly is modified:

### 4.1 Assemble to Machine Code
Execute the zero-dependency pure Python assembler:
```bash
python3 sw/build_firmware.py sw/app/main.s sw/firmware.hex
```

### 4.2 Verify Hex Output
- Ensure exit code is `0`.
- Verify the instruction count reported by `build_firmware.py`.
- Run regression to verify that CPU & memory sub-test passes:
  ```bash
  python3 sim/run_simulator.py --mode regression
  ```
