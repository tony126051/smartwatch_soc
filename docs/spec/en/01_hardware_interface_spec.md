# 01 - Hardware Interface Specification (HIS)

Document ID: `SPEC-HIS-001-EN`  
Version: `1.0.0`  
Status: `Approved / SSOT`

---

## 1. Global Memory Map

The SoC utilizes a 32-bit flat address space mapped as follows:

| Physical Address Range | Region Name | Size | Protocol / Bus | Access | Description |
|---|---|---|---|---|---|
| `0x0000_0000 - 0x0000_1FFF` | **ITCM / Boot ROM** | 8 KB | CPU Native Bus | R/X | Reset vector, boot code, instructions (`firmware.hex`) |
| `0x1000_0000 - 0x1000_1FFF` | **DTCM / Data SRAM** | 8 KB | CPU Native Bus | R/W | Stack (grows downwards from 0x1000_1FF0), global data |
| `0x4000_0000 - 0x4000_003F` | **KWS Control Regs** | 64 B | AMBA APB3 | R/W | AFE, VAD, NPU control & status registers |
| `0x4000_0400 - 0x4000_04FF` | **NPU Feature RAM** | 256 B | AMBA APB3 | R/W | $16\times16$ INT8 input feature RAM window |
| `0x4000_0500 - 0x4000_05FF` | **NPU Weight RAM** | 256 B | AMBA APB3 | R/W | Model weights INT8 upload window |
| `0x8000_0000 - 0x8000_0003` | **Debug LED Reg** | 4 B | CPU Native Bus | R/W | 8-bit board LED status and debug indicator register |

---

## 2. AMBA 3 APB Bus Protocol Specification

The KWS Hardware Subsystem (`0x4000_0000`) connects to the CPU memory bridge via an AMBA 3 APB Slave interface.

### 2.1 Bus Signal Definitions

| Signal Name | Direction (re Slave) | Width | Description |
|---|---|---|---|
| `PCLK` | Input | 1 | Master synchronous system clock (12.288 MHz) |
| `PRESETn` | Input | 1 | Asynchronous active-low reset |
| `PADDR` | Input | 12 | APB byte address offset (word-aligned, bits [1:0] = 0) |
| `PSEL` | Input | 1 | Slave module select signal |
| `PENABLE` | Input | 1 | APB strobe / enable signal (asserted in phase 2) |
| `PWRITE` | Input | 1 | Transfer direction: 1 = Write, 0 = Read |
| `PWDATA` | Input | 32 | 32-bit write data bus |
| `PRDATA` | Output | 32 | 32-bit read data bus |
| `PREADY` | Output | 1 | Slave ready: permanently tied to 1'b1 (0 wait-states) |
| `PSLVERR` | Output | 1 | Slave error: permanently tied to 1'b0 |

### 2.2 APB Read/Write Transaction Contract
1. **Setup Phase (Cycle 1)**: Master asserts `PSEL`, drives `PADDR`, `PWRITE`, and `PWDATA` (if writing). `PENABLE` is 0.
2. **Access Phase (Cycle 2)**: Master asserts `PENABLE`. Slave samples write data or drives valid read data onto `PRDATA`.
3. **Zero Wait-State**: Because `PREADY` is fixed to 1'b1, all APB read/write operations complete in exactly **2 clock cycles**.

---

## 3. Register Bitfield Definitions

Base Address: `0x4000_0000`

### 3.1 AFE_CTRL - Audio Front-End Control Register (Offset: `0x000`)
- **Reset Value**: `0x0000_0000`
- **Access**: Read / Write (R/W)

| Bitfield | Field Name | Access | Reset | Description |
|---|---|---|---|---|
| `[0]` | `AFE_EN` | R/W | 1'b0 | **AFE Enable**: `1` = Enable PDM sampling & CIC filter; `0` = Standby power-down |
| `[31:1]` | `RESERVED` | RO | 31'd0 | Reserved. Always returns 0 |

### 3.2 AFE_STATUS - Audio Front-End Status Register (Offset: `0x004`)
- **Reset Value**: `0x0000_0001`
- **Access**: Read Only (RO)

| Bitfield | Field Name | Access | Reset | Description |
|---|---|---|---|---|
| `[0]` | `FIFO_EMPTY` | RO | 1'b1 | FIFO empty flag: `1` = No PCM samples in FIFO |
| `[1]` | `FIFO_FULL` | RO | 1'b0 | FIFO full flag: `1` = FIFO capacity reached (256 samples) |
| `[16:8]` | `FIFO_COUNT` | RO | 9'd0 | Current number of 16-bit PCM samples in FIFO (0 to 256) |
| Others | `RESERVED` | RO | 0 | Reserved |

### 3.3 AFE_DATA - Audio FIFO Read Register (Offset: `0x008`)
- **Reset Value**: `0x0000_0000`
- **Access**: Read Only (RO)
- **Side Effect**: Reading this register pops one sample from the FIFO.

| Bitfield | Field Name | Access | Reset | Description |
|---|---|---|---|---|
| `[15:0]` | `PCM_SAMPLE` | RO | 16'd0 | Popped 16-bit signed PCM audio sample |
| `[31:16]` | `RESERVED` | RO | 16'd0 | Reserved. Always returns 0 |

---

### 3.4 VAD_CTRL - Voice Activity Detection Control Register (Offset: `0x010`)
- **Reset Value**: `0x0000_0000`
- **Access**: Read / Write (R/W)

| Bitfield | Field Name | Access | Reset | Description |
|---|---|---|---|---|
| `[0]` | `VAD_EN` | R/W | 1'b0 | **VAD Enable**: `1` = Enable short-time energy calculation; `0` = Disable |
| `[1]` | `VAD_IRQ_CLR` | WO | 1'b0 | **Clear Interrupt**: Write `1` to clear `irq_vad_wakeup` latch (auto-clearing) |
| `[31:2]` | `RESERVED` | RO | 30'd0 | Reserved |

### 3.5 VAD_THRESHOLD - Speech Energy Threshold Register (Offset: `0x014`)
- **Reset Value**: `200000` (`0x0003_0D40`)
- **Access**: Read / Write (R/W)

| Bitfield | Field Name | Access | Reset | Description |
|---|---|---|---|---|
| `[23:0]` | `ENERGY_THRES`| R/W | 200,000 | 160-sample short-time absolute energy threshold |
| `[31:24]` | `RESERVED` | RO | 8'd0 | Reserved |

### 3.6 VAD_HANGOVER - Hangover Counter Length Register (Offset: `0x018`)
- **Reset Value**: `3` (`0x0000_0003`)
- **Access**: Read / Write (R/W)

| Bitfield | Field Name | Access | Reset | Description |
|---|---|---|---|---|
| `[3:0]` | `HANGOVER_LEN`| R/W | 4'd3 | Number of frames to sustain active state when energy falls below threshold |
| `[31:4]` | `RESERVED` | RO | 28'd0 | Reserved |

### 3.7 VAD_ENERGY - Current Frame Energy Register (Offset: `0x01C`)
- **Reset Value**: `0x0000_0000`
- **Access**: Read Only (RO)

| Bitfield | Field Name | Access | Reset | Description |
|---|---|---|---|---|
| `[23:0]` | `CURRENT_ENERGY`| RO | 24'd0 | Accumulation result of previous 160-sample frame |
| `[24]` | `SPEECH_ACTIVE` | RO | 1'b0 | Real-time speech activity status (including hangover frames) |
| `[31:25]` | `RESERVED` | RO | 7'd0 | Reserved |

---

### 3.8 NPU_CTRL - KWS NPU Accelerator Control Register (Offset: `0x020`)
- **Reset Value**: `0x0000_0000`
- **Access**: Read / Write (R/W)

| Bitfield | Field Name | Access | Reset | Description |
|---|---|---|---|---|
| `[0]` | `START_INFER` | WO | 1'b0 | **Start Inference**: Write `1` to trigger NPU forward inference |
| `[1]` | `NPU_IRQ_CLR` | WO | 1'b0 | **Clear Interrupt**: Write `1` to clear `irq_npu_done` interrupt flag |
| `[31:2]` | `RESERVED` | RO | 30'd0 | Reserved |

### 3.9 NPU_STATUS - KWS NPU Status Register (Offset: `0x024`)
- **Reset Value**: `0x0000_0000`
- **Access**: Read Only (RO)

| Bitfield | Field Name | Access | Reset | Description |
|---|---|---|---|---|
| `[0]` | `NPU_BUSY` | RO | 1'b0 | Busy flag: `1` = NPU computing; feature RAM writes blocked |
| `[1]` | `NPU_DONE` | RO | 1'b0 | Done flag: `1` = Inference completed; scores valid |
| `[2]` | `KEYWORD_HIT` | RO | 1'b0 | Keyword decision flag: `1` = Score 1 > Score 0 |
| `[31:3]` | `RESERVED` | RO | 29'd0 | Reserved |

### 3.10 NPU_SCORE0 - Class 0 Score Register (Offset: `0x028`)
- **Reset Value**: `0x0000_0000`
- **Access**: Read Only (RO)
- **Description**: 32-bit signed two's complement integer representing Class 0 (Noise / Non-keyword) score.

### 3.11 NPU_SCORE1 - Class 1 Score Register (Offset: `0x02C`)
- **Reset Value**: `0x0000_0000`
- **Access**: Read Only (RO)
- **Description**: 32-bit signed two's complement integer representing Class 1 (Target Wakeup Keyword) score.

---

### 3.12 Feature & Weight SRAM Windows
- **`0x4000_0400 - 0x4000_04FF` (NPU_FEAT_RAM)**: 256 bytes for $16\times16$ INT8 input feature map.
- **`0x4000_0500 - 0x4000_05FF` (NPU_WGT_RAM)**: 256 bytes for neural network INT8 weights and biases.

---

## 4. Interrupt Architecture & Contracts

The SoC integrates 2 dedicated interrupt lines directly wired into PicoRV32's `cpu_irq`:

| IRQ Bit | Signal Name | Source | Trigger Mode | Priority | Service & Clear Method |
|---|---|---|---|---|---|
| `cpu_irq[0]` | `irq_vad_wakeup` | VAD Core | Rising-edge latched | High | Write `VAD_CTRL[1] = 1` |
| `cpu_irq[1]` | `irq_npu_done` | NPU FSM | Rising-edge latched | Medium | Write `NPU_CTRL[1] = 1` |

### 4.1 Interrupt Protocol Handshake
1. **Assertion**: When the triggering condition occurs, the hardware latch pulls the interrupt line high.
2. **CPU Trap**: PicoRV32 interrupts execution and jumps to `0x0000_0010`.
3. **Software Clear**: The ISR must write `1` to Bit[1] of the corresponding control register to clear the latch; otherwise, the CPU will continuously re-enter the trap upon return.

---

## 5. Top-Level Pinout

| Pin Name | Direction | Width | Drive/Type | Description |
|---|---|---|---|---|
| `clk` | Input | 1 | CMOS | 12.288 MHz master clock |
| `rst_n` | Input | 1 | Weak Pull-up | Active-low asynchronous reset |
| `pdm_clk_en` | Input | 1 | CMOS | 1.024 MHz PDM clock enable strobe |
| `pdm_data_in` | Input | 1 | PDM Mic | 1-bit PDM microphone data stream |
| `debug_leds` | Output | 8 | 4mA | 8 board debug/status LEDs |
| `soc_trap` | Output | 1 | 4mA | CPU unrecoverable trap indicator (Active High) |

---

## 6. Hardware Interface Traceability Matrix

| Requirement ID | Technical Assertion |
|---|---|
| `REQ-BUS-001` | APB3 transactions must complete in exactly 2 clock cycles (`PREADY=1`). |
| `REQ-BUS-002` | Reading `AFE_DATA` (0x008) must automatically pop one sample from the FIFO. |
| `REQ-BUS-003` | Writing 1 to `VAD_CTRL[1]` or `NPU_CTRL[1]` must clear the IRQ latch within 1 cycle. |
| `REQ-BUS-004` | Feature & Weight RAM access must support little-endian 32-bit and 8-bit operations. |
| `REQ-BUS-005` | `debug_leds` reset value is `0x00` and updated by firmware writes to `0x8000_0000`. |
