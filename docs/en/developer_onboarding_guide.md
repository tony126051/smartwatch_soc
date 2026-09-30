# 🔰 Developer Onboarding Guide

[繁體中文](../developer_onboarding_guide.md) | [English](developer_onboarding_guide.md) | [日本語](../ja/developer_onboarding_guide.md)

Welcome to the **Edge AI Smartwatch SoC Design Project**! This guide is tailored for new engineers (Algorithm, Digital IC Design, and Firmware Engineers) to help you understand the full-system architecture, start the simulator, modify firmware, and run hardware verification in **less than 10 minutes**.

---

## 1. Core Concept: Two-Stage Wakeup Architecture

To address the challenge of ultra-small smartwatch battery capacities (~200 mAh) needing to listen **24/7 Always-on**, this SoC utilizes a strict two-stage filtering hierarchy:

```
[Ambient Audio] ──> [1.024MHz PDM Mic] ──> [3-Stage CIC (R=64)] ──> 16kHz 16-bit PCM
                                                                           │
┌──────────────────────────────────────────────────────────────────────────┘
▼
【Stage 1: Hardware VAD (Always-on)】
  - Algorithm: 160-sample (10 ms frame) Short-Time Energy (STE) accumulator
  - Standby Power: < 20 μW
  - Normal State: During silence, CPU, NPU, and display stay in deep sleep (WFI)
  - Trigger: When energy exceeds threshold (default 200,000), fires IRQ `irq_vad_wakeup`
        │
        ▼ (Wakes CPU)
【Processor Coordination: 32-bit RISC-V CPU】
  - CPU boots up from sleep, clears VAD interrupt flag
  - Moves audio feature frame to NPU Feature RAM (0x4000_0400)
  - Triggers NPU execution (NPU_CTRL = 1)
        │
        ▼
【Stage 2: KWS NPU Accelerator】
  - Lightweight CNN: DS-CNN (Depthwise Separable CNN), full INT8 fixed-point arithmetic
  - Fixed hardware latency: 28,688 cycles (2.33 ms @ 12.288 MHz, ~3.82 mW)
  - Fires inference completion interrupt `irq_npu_done`
        │
        ▼
【Decision Output】
  - Evaluates scores: Class 1 (Target Keyword) vs Class 0 (Background Noise)
  - If keyword matches: Writes `0xAA` to debug LED, turns on smartwatch screen, boots OS
  - If non-keyword: Writes `0x55` to debug LED, CPU immediately returns to `waitirq` deep sleep
```

---

## 2. Environment Verification

This project is built with **zero external heavy toolchain dependencies**:
- **Operating Systems**: Linux / macOS / Windows (WSL)
- **Primary Dependency**: `Python 3.8+` (uses standard library, no complex packages required)
- **Optional Tools**: GTKWave / PulseView (for viewing `.vcd` waveform files)

Check your environment:
```bash
python3 --version
```

---

## 3. Common Developer Workflows (Day-to-Day Tasks)

### Task A: Launch the Visual Web GUI Simulator
```bash
python3 sim/web_server.py 8080
```
- Open browser at `http://localhost:8080/`.
- Switch languages directly from the top menu (English, Traditional Chinese, Simplified Chinese, Japanese).
- Interactively click `Step`, `Speech`, `Tone`, and watch the screen turn on, LEDs update, and registers change.

### Task B: Modify and Rebuild RISC-V Firmware
The firmware source is in [`sw/app/main.s`](../../sw/app/main.s). After editing the assembly code, run the bundled assembler:
```bash
python3 sw/build_firmware.py sw/app/main.s sw/firmware.hex
```
The simulator and RTL immediately execute the updated [`sw/firmware.hex`](../../sw/firmware.hex).

### Task C: Run Automated Regression Tests
Before submitting any code changes, always verify all tests:
```bash
python3 sim/run_simulator.py --mode regression --lang en
```
Ensure all 5 tests report `[PASS]`.

### Task D: Use GDB-Style Interactive Terminal Debugger
To inspect registers or set breakpoints at interrupt vectors:
```bash
python3 sim/run_simulator.py --mode interactive --lang en
```
Common commands:
```text
[SoC @ 0x00000000 | LED 0x00] > step 5       # Step 5 instructions
[SoC @ 0x00000020 | LED 0x01] > regs         # Dump 32 RISC-V registers
[SoC @ 0x00000020 | LED 0x01] > break 0x10   # Breakpoint at ISR entry
[SoC @ 0x00000020 | LED 0x01] > feed speech  # Inject speech audio
[SoC @ 0x00000020 | LED 0x01] > run          # Run until breakpoint or sleep
[SoC @ 0x00000010 | LED 0x08] > mem 0x10000000 16 # Inspect memory
[SoC @ 0x00000010 | LED 0x08] > power        # Check power & battery estimate
```

### Task E: Export Digital Waveforms (VCD)
```bash
python3 sim/run_simulator.py --mode scenario --vcd sim/waves_soc.vcd --dashboard sim/simulator_dashboard.html --lang en
```
Open `sim/waves_soc.vcd` with GTKWave or inspect `sim/simulator_dashboard.html` in your browser.

---

## 4. Subsystem Code & Architecture Navigation

- **Algorithm Golden Models** ([`model/`](../../model/)):
  - `golden_vad.py`: Pure Python bit-true reference for short-time energy VAD.
  - `golden_npu.py`: DS-CNN fixed-point inference model with INT8 weights.
  - `golden_vectors/`: Exported golden vectors and stimulus files.
- **Synthesizable Verilog RTL** ([`rtl/`](../../rtl/)):
  - `afe/`: PDM receiver, 3-stage CIC decimator, and audio FIFO.
  - `vad/`: Stage-1 always-on hardware VAD core.
  - `npu/`: Stage-2 KWS NPU MAC array and hardware FSM.
  - `cpu/`: 32-bit RISC-V PicoRV32 core.
  - `bus/`: APB slave adapter.
  - `top/`: Smartwatch SoC top integration.
- **Simulator Framework** ([`sim/`](../../sim/)):
  - `simulator/`: Python cycle-accurate hardware simulation library.
  - `web_server.py`: Real-time HTTP backend for Web GUI.
  - `smartwatch_simulator_ui.html`: Multi-language HTML5 interactive interface.
- **Embedded Firmware** ([`sw/`](../../sw/)):
  - `app/main.s`: Bootloader, peripheral setup, ISR, and sleep control.
  - `build_firmware.py`: Pure Python lightweight RISC-V assembler.
