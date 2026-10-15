---
name: smartwatch-verilog-hw
description: >-
  Guides digital hardware RTL development, synthesis compliance, and APB3 bus integration
  for the Smartwatch SoC. Use when writing, modifying, or reviewing Verilog HDL modules in
  rtl/, implementing APB3 peripheral slaves, defining register maps, designing FSMs or MAC
  arrays, or verifying synthesizability against Verilog-2001 standards.
---

# Smartwatch SoC Verilog RTL & Hardware Interface Skill

This skill governs digital RTL hardware design, modification, and interface compliance in the `rtl/` directory, adhering to the specifications in [01_hardware_interface_spec.md](../../../docs/spec/01_hardware_interface_spec.md) and [05_ai_agent_development_guide.md](../../../docs/spec/05_ai_agent_development_guide.md).

---

## 1. Synthesizable Verilog-2001 Coding Standards

All hardware modules (`rtl/**/*.v`) must be fully synthesizable for standard EDA tools (Vivado, Design Compiler):

### 1.1 Sequential Logic (時序邏輯)
- Standard header:
  ```verilog
  always @(posedge clk or negedge rst_n) begin
      if (!rst_n) begin
          // Explicit reset assignments for all registered signals
          reg_out <= 32'd0;
      end else begin
          reg_out <= next_reg_out;
      end
  end
  ```
- **Rule**: ONLY use non-blocking assignments (`<=`).
- **Rule**: Every sequential register must have an explicit reset branch.

### 1.2 Combinational Logic (組合邏輯)
- Standard header:
  ```verilog
  always @(*) begin
      // Default assignment to prevent inferred latches
      next_state = state;
      out_signal = 1'b0;
      case (state)
          STATE_IDLE: begin ... end
          default:    begin ... end
      endcase
  end
  ```
- **Rule**: ONLY use blocking assignments (`=`).
- **Rule**: Sensitive list must be `always @(*)`.
- **Rule**: All `if-else` and `case` branches must be fully specified with `else` and `default` to **prevent latches**.

### 1.3 Absolute Hardware RTL Prohibitions
- ❌ **NO `#delay` statements** (e.g. `#10`) in any synthesizable RTL module.
- ❌ **NO `initial` blocks** in synthesizable RTL (only allowed in testbenches `sim/tb_*.v`).
- ❌ **NO floating-point types** (`real`, `float`). All arithmetic must be INT8 / INT16 / INT32 fixed-point.
- ❌ **NO unsynchronized Clock Domain Crossing (CDC)**. Audio clock (1.024 MHz) and SoC system clock (12.288 MHz) must use proper handshake or synchronizers.

---

## 2. AMBA 3 APB Bus Protocol Contract

All peripheral modules (AFE, VAD, NPU) connect through the APB3 bus.

### 2.1 Standard APB3 Slave Signals
```verilog
input  wire        pclk,       // System clock (12.288 MHz)
input  wire        presetn,    // Active-low asynchronous reset
input  wire [11:0] paddr,      // Byte address offset within peripheral
input  wire        psel,       // Peripheral select
input  wire        penable,    // Transfer enable
input  wire        pwrite,     // 1: Write, 0: Read
input  wire [31:0] pwdata,     // 32-bit Write data
output reg  [31:0] prdata,     // 32-bit Read data
output wire        pready,     // 1: Ready to complete transfer
output wire        pslverr     // 1: Slave error (Tie to 1'b0 if unused)
```

### 2.2 APB Read/Write Timing Phases
- **Setup Phase**: `psel = 1`, `penable = 0`. PADDR and PWRITE valid.
- **Access Phase**: `psel = 1`, `penable = 1`. Complete transfer when `pready = 1`.
- Standard register read template:
  ```verilog
  always @(*) begin
      if (psel && !pwrite) begin
          case (paddr[7:0])
              8'h00:   prdata = reg_afe_ctrl;
              8'h04:   prdata = reg_afe_status;
              8'h08:   prdata = reg_afe_data;
              default: prdata = 32'd0;
          endcase
      end else begin
          prdata = 32'd0;
      end
  end
  ```

---

## 3. Peripheral Register Offsets & Contracts

Base Address: `0x4000_0000`

| Offset | Name | Type | Reset Value | Description |
|---|---|---|---|---|
| `0x000` | `AFE_CTRL` | R/W | `0x0000_0000` | `[0]`: Enable, `[1]`: FIFO Clear, `[2]`: PDM Edge Select |
| `0x004` | `AFE_STATUS` | RO | `0x0000_0000` | `[0]`: FIFO Valid, `[1]`: FIFO Full, `[9:2]`: FIFO Count |
| `0x008` | `AFE_DATA` | RO | `0x0000_0000` | `[15:0]`: 16-bit PCM Sample (Pop on read) |
| `0x010` | `VAD_CTRL` | R/W | `0x0000_0000` | `[0]`: Enable, `[1]`: Clear IRQ (Write 1 to clear) |
| `0x014` | `VAD_THRESHOLD` | R/W | `32'd200000` | 24-bit Short-Time Energy detection threshold |
| `0x018` | `VAD_HANGOVER` | R/W | `32'd4` | Number of hang frames (default 4) |
| `0x01C` | `VAD_ENERGY` | RO | `0x0000_0000` | Most recent frame energy value |
| `0x020` | `NPU_CTRL` | R/W | `0x0000_0000` | `[0]`: Start inference, `[1]`: Clear IRQ |
| `0x024` | `NPU_STATUS` | RO | `0x0000_0000` | `[0]`: Busy, `[1]`: Done |
| `0x028` | `NPU_SCORE0` | RO | `0x0000_0000` | INT8 Score for Class 0 (Noise) |
| `0x02C` | `NPU_SCORE1` | RO | `0x0000_0000` | INT8 Score for Class 1 (Keyword) |
| `0x400 - 0x4FF` | Feature RAM | R/W | `0x00` | 256-byte INT8 feature window ($16 \times 16$) |
| `0x500 - 0x5FF` | Weight RAM | R/W | `0x00` | 256-byte INT8 model weights |

*Debug LED Register*: `0x8000_0000` (Native Bus, `[7:0]` display LED code).

---

## 4. Hardware Verification & Sync Steps

When modifying Verilog RTL:
1. **Sync Header**: Ensure `sw/include/soc_regs.h` matches register offsets and bit shifts.
2. **Sync Python Model**: Update `sim/simulator/` behavioral module (`afe.py`, `vad.py`, or `npu.py`).
3. **Execute Regression**:
   ```bash
   python3 sim/run_simulator.py --mode regression
   ```
4. **Export Waveform (Optional)**:
   ```bash
   python3 sim/run_simulator.py --mode scenario --vcd sim/waves_soc.vcd
   ```
