# Smartwatch SoC Simulator User & Architecture Guide

[繁體中文](../simulator_guide.md) | [English](simulator_guide.md) | [日本語](../ja/simulator_guide.md)

This simulator is a full-system, cycle-accurate, and bit-true simulation and hardware debugging environment developed specifically for the **Edge AI Smartwatch SoC**.

---

## 1. Simulator System Architecture

```
                                  [ Smartwatch SoC Simulator Architecture ]
                                                     │
          ┌──────────────────────────────────────────┴──────────────────────────────────────────┐
          ▼                                          ▼                                          ▼
    [ Audio Front-End (AFE) ]                 [ CPU Core ]                              [ On-Chip Bus ]
    - 1.024MHz PDM Receiver                   - 32-bit RISC-V (PicoRV32 RV32I)          - 8KB Boot ROM (0x0000_0000)
    - 3rd-Order CIC Decimator (R=64)          - Custom Instructions (waitirq, retirq)   - 8KB Data SRAM (0x1000_0000)
    - 256-word Audio Ring FIFO                - Dual IRQ Lines (VAD IRQ / NPU IRQ)      - APB Subsystem (0x4000_0000)
          │                                          │                                  - Debug LEDs (0x8000_0000)
          ▼                                          ▼                                          ▲
    [ Stage 1: Hardware VAD ]                 [ Stage 2: KWS NPU Accelerator ]                  │
    - 160-point Short-Time Energy Accumulator - 16x16 INT8 Feature RAM (0x400)                  │
    - Configurable Threshold & Hangover       - 256B Weight RAM (0x500)                         │
    - Rising-Edge Wakeup IRQ (irq_vad_wakeup) - DS-CNN Engine (28,688 cycles)                   │
                                              - Done IRQ (irq_npu_done) ────────────────────────┘
```

---

## 2. Simulator Module Structure (`sim/simulator/`)

| Module File | Class / Component | Description |
|---|---|---|
| [`types.py`](../../sim/simulator/types.py) | Constants & Types | Memory map addresses, register offsets, 12.288 MHz clock constants, LED codes, and 32-bit signed math helpers |
| [`cpu.py`](../../sim/simulator/cpu.py) | `RiscvCpu` | Full RV32I 37-instruction simulator, implementing PicoRV32 `waitirq`, `retirq`, `maskirq`, cycle counting, and register dump tracking |
| [`bus.py`](../../sim/simulator/bus.py) | `SoCBus` | System interconnect and memory address decoder, handling ITCM, DTCM, APB peripherals, and debug register routing |
| [`afe.py`](../../sim/simulator/afe.py) | `AudioFrontEnd` | PDM receiver, 3rd-order CIC decimator ($R=64$), and 256-sample audio FIFO |
| [`vad.py`](../../sim/simulator/vad.py) | `HardwareVad` | 160-sample short-time energy accumulator, dynamic threshold comparison, hangover counter, and wakeup interrupt generator |
| [`npu.py`](../../sim/simulator/npu.py) | `KwsNpu` | DS-CNN (Conv1, DW, PW, GAP, FC) hardware state machine, INT8 fixed-point MAC, accurately simulating 28,688 cycles |
| [`power.py`](../../sim/simulator/power.py) | `PowerProfiler` | Dynamic power profiler: Standby sleep (<20μW), CPU active (1.25mW), NPU inference (3.82mW), and battery life estimation |
| [`vcd.py`](../../sim/simulator/vcd.py) | `VcdWriter` | Generates standard IEEE 1364 VCD digital waveforms viewable in GTKWave or PulseView |
| [`soc.py`](../../sim/simulator/soc.py) | `SmartwatchSoC` | Top-level SoC simulator integrating CPU, peripherals, interrupts, audio stimulus, and cycle stepping |
| [`cli.py`](../../sim/simulator/cli.py) | `InteractiveSimulatorCLI` | Interactive command-line debugger supporting breakpoints, single-stepping, register dumps, memory inspection, and language switching |
| [`i18n.py`](../../sim/simulator/i18n.py) | Internationalization Engine | Multi-language translation dictionaries and runtime support for `zh-TW`, `en`, `zh-CN`, and `ja` |
| [`dashboard.py`](../../sim/simulator/dashboard.py) | `generate_dashboard_html` | Generates standalone interactive HTML5 visualizer dashboard with multi-language switching |

---

## 3. Simulator Execution Modes

### 3.1 Automated Regression Testing (`--mode regression`)
Verifies all 5 core subsystems (CPU instruction set, AFE CIC filter, VAD energy interrupts, NPU bit-true inference, full SoC firmware boot and wakeup sequence):
```bash
python3 sim/run_simulator.py --mode regression --lang en
```

### 3.2 End-to-End Voice Wakeup Scenario Simulation (`--mode scenario`)
Loads a real human voice stream, simulating "Boot -> Standby Sleep -> VAD Voice Detection -> CPU Wakeup -> Feature Loading -> NPU Inference -> Keyword Match -> Display ON", exporting waveforms and dashboard:
```bash
python3 sim/run_simulator.py --mode scenario --vcd sim/waves_soc.vcd --dashboard sim/simulator_dashboard.html --lang en
```

### 3.3 Interactive Terminal Debugger (`--mode interactive`)
Provides a GDB-style interactive environment:
```bash
python3 sim/run_simulator.py --mode interactive --lang en
```
Supported Commands:
- `step [N]`: Execute N instructions (default 1) with disassembly and register writeback output.
- `run [N]`: Run until next breakpoint, trap, or sleep (default 100,000 cycles).
- `break <addr>`: Set breakpoint at address (e.g. `break 0x10`).
- `delete [addr]`: Remove breakpoint or clear all breakpoints.
- `regs`: Dump all 32 RISC-V general-purpose registers (labeled with ABI names).
- `mem <addr> [len]`: Inspect memory contents (hex and ASCII).
- `status`: Display SoC status (AFE, VAD, NPU, LEDs, CPU).
- `feed [speech|tone|silence]`: Inject audio stream into microphone front-end.
- `power`: Display dynamic power analysis and projected battery life.
- `lang [code]`: Switch CLI language (`en`, `zh-TW`, `zh-CN`, `ja`).
- `reset`: Reset SoC to power-on state.
- `quit`: Exit session.

### 3.4 Interactive Web GUI (`sim/smartwatch_simulator_ui.html`)
Launch the built-in HTTP server:
```bash
python3 sim/web_server.py 8080
```
Open browser at `http://localhost:8080/`. Features include:
1. **Multi-Language Selector**: Real-time switching between English, Traditional Chinese, Simplified Chinese, and Japanese.
2. **Interactive Controls**: `Run`, `Step`, `Fast Forward 50`, `Reset`.
3. **Audio Stimulus**: Live injection of speech, silence, and tone noise.
4. **Smartwatch Display**: Simulates watchface states, standby screen, voice listening, and keyword activation.
5. **LED Indicators**: Displays 8-bit board LED codes (`0x01` Boot, `0x02` Ready, `0x04` Sleep, `0x08` Voice, `0xAA` Match, `0x55` Non-keyword).
6. **Subsystem Monitoring**: VAD STE energy bar, NPU FSM pipeline, CPU registers, and battery life projection.

---

## 4. Key Performance & Resource Metrics

- **CPU Core**: 32-bit RISC-V RV32I (PicoRV32) @ 12.288 MHz
- **Audio Interface**: 1.024 MHz PDM microphone input $\to$ 16 kHz 16-bit PCM
- **Stage 1 VAD Latency**: 10.0 ms per frame (< 20 μW standby power)
- **Stage 2 NPU Latency**: 28,688 cycles (**2.33 ms** @ 12.288 MHz)
- **On-Chip Memory**: 16 KB SRAM Total (8KB ITCM + 8KB DTCM, zero external DRAM)
- **Projected Battery Life**: **> 10 Days** under typical wearable usage (200 mAh Li-Po battery)
