# ⌚ Edge AI Smartwatch SoC Design & Verification Platform

[繁體中文](README.md) | [English](README_EN.md) | [日本語](README_JA.md)

This project provides a complete **Two-Stage Voice Wakeup System-on-Chip (SoC)** designed for ultra-low-power smartwatches. It includes golden algorithm models, Verilog RTL descriptions, RISC-V embedded firmware, and a cycle-accurate, bit-true simulator equipped with a real-time interactive HTML5 Web GUI.

<p align="center">
  <img src="docs/assets/simulator_gui_preview.png" alt="Smartwatch SoC Interactive Simulator Web GUI" width="100%" style="border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);" />
  <br>
  <em>▲ Live Interactive Web GUI Simulator featuring real-time multi-language switching, hardware FSM pipeline tracking, and dynamic power profiling.</em>
</p>

---

## 🚀 Quick Start (Under 30 Seconds)

No complicated EDA tools or toolchains required! Everything runs out-of-the-box with **Python 3**:

### 1. Launch the Interactive Web GUI Simulator (Recommended)
```bash
python3 sim/web_server.py 8080
```
Open your browser and navigate to: **`http://localhost:8080/`**
- **🌐 Multi-Language (i18n)**: Switch in real-time between **繁體中文 (Traditional Chinese)**, **English**, **简体中文 (Simplified Chinese)**, and **日本語 (Japanese)**. Preferences are automatically saved in local storage.
- **Hardware Visualization**: Real-time rendering of the smartwatch watchface, on-board 8-bit debug LEDs, RISC-V PC/registers, VAD Short-Time Energy (STE) level bar, NPU convolution pipeline status, and dynamic power profiling.
- **Interactive Controls**: Click `Step` (Single-Step), `Run` (Continuous), `Speech` (Voice Stream), `Silence` (Quiet Environment), or `Reset`.

### 2. Run Full-Chip Automated Regression Tests
```bash
python3 sim/run_simulator.py --mode regression --lang en
# Supported languages: --lang en (English), --lang zh-TW (Traditional Chinese), --lang zh-CN (Simplified Chinese), --lang ja (Japanese)
```
Automatically verifies all 5 subsystems:
1. RISC-V RV32I instruction set execution and memory read/write.
2. Audio Front-End (PDM $\to$ 3rd-order CIC decimator $\to$ 256-word FIFO).
3. Stage 1 Always-on Hardware VAD short-time energy calculation and wakeup interrupt.
4. Stage 2 KWS NPU (DS-CNN INT8) hardware matrix engine and classification scores.
5. Full-system firmware boot sequence, standby sleep, and voice wakeup sequence.

### 3. Interactive GDB-Style Terminal Debugger
```bash
python3 sim/run_simulator.py --mode interactive --lang en
```
Supported CLI commands:
- `step [N]`: Single-step N instructions with real-time disassembly and register writeback diffs.
- `run [N]`: Run until next breakpoint, trap, or sleep (default 100,000 cycles).
- `break <addr>`: Set execution breakpoint (e.g. `break 0x10`, `break 0x48`).
- `delete [addr]`: Remove specific breakpoint or clear all breakpoints.
- `regs`: Dump all 32 RISC-V general-purpose registers (labeled with standard ABI names).
- `mem <addr> [len]`: Inspect memory contents in hex and ASCII.
- `status`: Display overall SoC peripheral status (LEDs, AFE, VAD, NPU, CPU).
- `feed [speech|tone|silence]`: Inject audio into the microphone front-end.
- `power`: Real-time energy, average power (μW), and projected battery life.
- `lang [code]`: Switch CLI language (`en`, `zh-TW`, `zh-CN`, `ja`).
- `reset`: Reset all SoC registers and peripherals.
- `quit`: Exit simulation.

### 4. Export Digital Waveforms (VCD) & Architecture Dashboard
```bash
python3 sim/run_simulator.py --mode scenario --vcd sim/waves_soc.vcd --dashboard sim/simulator_dashboard.html --lang en
```
- Exports standard IEEE 1364 `.vcd` files directly viewable in **GTKWave** or **PulseView**.
- Generates a standalone interactive HTML5 dashboard [`sim/simulator_dashboard.html`](sim/simulator_dashboard.html) with multi-language support.

---

## 🏛️ Hardware Architecture Overview

All feature buffers and memory remain on-chip (**16 KB On-chip SRAM**) to prevent energy-expensive off-chip DRAM access:

```
+-----------------------------------------------------------------------------------+
|                         Smartwatch SoC Top Architecture                           |
|                                                                                   |
|  [ Audio Input ]           [ Memory Subsystem ]          [ Processing Core ]      |
|  1.024MHz PDM Mic           0x0000_0000: 8KB Boot ROM     32-bit RISC-V CPU       |
|       │                     0x1000_0000: 8KB Data SRAM    (PicoRV32 RV32I)        |
|       ▼                                                       ▲                   |
|  [ AFE Front-End ]         [ System Bus & APB ]               │ (Interrupts)      |
|  - 3-Stage CIC (R=64)       0x4000_0000: KWS Subsystem ───────┼── irq[0]: VAD IRQ |
|  - 256-word Audio FIFO      0x8000_0000: Debug LED Reg        └── irq[1]: NPU IRQ |
|       │                                                                           |
|       ▼ (16kHz PCM)                                                               |
|  [ Stage 1: Hardware VAD (Always-on) ]  ────── Voice Detected ────────┐           |
|  - 160-point Short-Time Energy (< 20μW)                                │           |
|                                                                       ▼           |
|  [ Stage 2: KWS NPU Accelerator ] ◄─────────────────────────── Wake CPU & Load Feat|
|  - 16x16 INT8 Feature RAM (0x400)                                                 |
|  - 256B Weight RAM (0x500)                                                        |
|  - DS-CNN (Conv1 -> DW -> PW -> GAP -> FC, 28,688 cycles, 2.33ms)                |
|  - Outputs Class 0 (Noise) and Class 1 (Keyword) Scores                           |
+-----------------------------------------------------------------------------------+
```

---

## 📂 Project Directory Structure

```text
smart_watch/
├── docs/                       # Specifications and manuals
│   ├── developer_onboarding_guide.md  # Onboarding guide for new engineers
│   ├── simulator_guide.md             # Detailed simulator manual & CLI guide
│   ├── system_architecture.md         # Hardware timing & architecture spec
│   └── register_map.md                # APB memory-mapped registers
├── model/                      # Python algorithm golden models
│   ├── generate_stimulus.py           # Audio stimulus generator (PDM/PCM)
│   ├── golden_vad.py                  # Short-time energy VAD golden model
│   ├── golden_mfcc.py                 # MFCC feature extraction golden model
│   ├── golden_npu.py                  # DS-CNN INT8 fixed-point inference model
│   └── golden_vectors/                # Golden test vectors and quantized weights
├── rtl/                        # Synthesizable Verilog HDL descriptions
│   ├── afe/                           # PDM receiver, CIC decimator, audio FIFO
│   ├── vad/                           # Stage-1 Always-on hardware VAD core
│   ├── npu/                           # Stage-2 KWS NPU MAC array & FSM
│   ├── cpu/                           # 32-bit RISC-V PicoRV32 processor
│   ├── bus/                           # APB bus interconnect & adapters
│   └── top/                           # Full heterogeneous SoC top-level
├── sim/                        # Verification & visualization suite
│   ├── simulator/                     # Cycle-accurate Python SoC simulator engine
│   │   ├── cpu.py, bus.py, afe.py, vad.py, npu.py, power.py, vcd.py, i18n.py ...
│   ├── run_simulator.py               # Unified simulator driver (--lang support)
│   ├── run_sim.py                     # EDA testbench script (iverilog)
│   ├── web_server.py                  # Real-time WebSocket/HTTP simulation server
│   ├── smartwatch_simulator_ui.html   # Interactive HTML5 Web GUI (i18n enabled)
│   ├── simulator_dashboard.html       # Standalone architecture dashboard
│   └── waves_soc.vcd                  # Exported digital logic waveforms
└── sw/                         # Embedded firmware & tools
    ├── app/                           # Source code (main.s, main.c)
    ├── include/                       # Register definitions (soc_regs.h)
    ├── build_firmware.py              # Pure Python lightweight RISC-V assembler
    └── firmware.hex                   # Assembled 32-bit binary machine code
```

---

## 🛠️ User Guide & Development Workflows

### 1. Modifying and Rebuilding RISC-V Firmware
The firmware source is in [`sw/app/main.s`](sw/app/main.s). Use the built-in pure Python assembler to regenerate `sw/firmware.hex`:
```bash
python3 sw/build_firmware.py sw/app/main.s sw/firmware.hex
```

### 2. Adjusting VAD Wakeup Sensitivity
Write to `0x4000_0014` (`REG_VAD_THRESHOLD`). The default threshold is `200000`. You can change this in [`sw/app/main.s`](sw/app/main.s) or via the memory write CLI command.

### 3. Debugging LED Status Codes
The on-board LED register at `0x8000_0000` indicates system phases:
- `0x01`: System booting & powering up
- `0x02`: Peripherals initialized (Ready)
- `0x04`: Deep standby sleep mode (`WFI` < 20μW)
- `0x08`: Voice detected by Stage-1 VAD $\to$ Starting Stage-2 NPU inference
- `0xAA`: Target keyword matched 🎯 $\to$ Watch screen turns on
- `0x55`: Non-keyword / noise $\to$ System returns to sleep

### 4. Technical Documentation (English)
- 🔰 Developer Onboarding Guide: [`docs/en/developer_onboarding_guide.md`](docs/en/developer_onboarding_guide.md)
- 🕹️ Simulator Architecture & CLI Guide: [`docs/en/simulator_guide.md`](docs/en/simulator_guide.md)
- 🏛️ System Architecture Specification: [`docs/en/system_architecture.md`](docs/en/system_architecture.md)
- 📋 APB Register Map Manual: [`docs/en/register_map.md`](docs/en/register_map.md)

---

## 📊 Key Specifications & PPA

- **Processor Core**: 32-bit RISC-V RV32I (PicoRV32) @ 12.288 MHz
- **Audio Interface**: 1.024 MHz PDM microphone input $\to$ 16 kHz 16-bit PCM
- **Stage-1 VAD Latency**: 10.0 ms per frame (< 20 μW standby power)
- **Stage-2 NPU Latency**: 28,688 cycles (**2.33 ms** @ 12.288 MHz)
- **On-Chip Memory**: 16 KB SRAM Total (8 KB ITCM + 8 KB DTCM, zero DRAM)
- **Battery Life Projection**: **> 10 Days** under typical wearable use (200 mAh Li-Po)

