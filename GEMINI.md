# Smartwatch SoC - Antigravity Agent Guidelines

This workspace follows **Spec-Driven Development (SDD)** with formal specifications in [`docs/spec/`](docs/spec/README.md) as the Single Source of Truth (SSOT).

---

## 1. Project Invariants

1. **Spec First**: Always consult [`docs/spec/`](docs/spec/) before editing code. All interfaces, register offsets, and memory maps must match [`01_hardware_interface_spec.md`](docs/spec/01_hardware_interface_spec.md).
2. **Bit-True Invariance**: Python models (`model/`), Verilog RTL (`rtl/`), and simulator (`sim/simulator/`) must maintain 100% bit-true consistency (0 error).
3. **Hard Budgets**: SRAM $\le 64\text{ KB}$ (16 KB currently), Gates $< 20\text{k}$, Standby Power $< 20\text{ }\mu\text{W}$, zero external DRAM.
4. **Zero-Regression Gatekeeper**: Before finishing any turn, always run:
   ```bash
   python3 sim/run_simulator.py --mode regression
   ```
   All 5 regression tests must report `[PASS]`.

---

## 2. Dedicated Antigravity Skills

Specialized domain skills are available in `.agents/skills/`:
- **`smartwatch-sdd-workflow`**: 6-step SOP for feature intake, impact analysis, multi-layer synchronization, and task worklog generation.
- **`smartwatch-verilog-hw`**: Synthesizable Verilog-2001 hardware design, APB3 slave contracts, FSM and register decoding.
- **`smartwatch-riscv-fw`**: PicoRV32 RV32I assembly, ABI conventions, `waitirq` instruction (`0x0000006b`), ISR flow, and assembler toolchain.
- **`smartwatch-golden-model`**: DSP algorithms (CIC decimator, VAD short-time energy), INT8 DS-CNN quantization, and golden vector generation.
- **`smartwatch-reg-test`**: Verification testbench execution, VCD waveform and dashboard generation, and systematic troubleshooting.

---

## 3. Key Quick Commands

- **Run Full Regression**: `python3 sim/run_simulator.py --mode regression`
- **Reassemble Firmware**: `python3 sw/build_firmware.py sw/app/main.s sw/firmware.hex`
- **Regenerate Golden Vectors**: `python3 sim/run_sim.py`
- **Generate Waveform & Dashboard**: `python3 sim/run_simulator.py --mode scenario --vcd sim/waves_soc.vcd --dashboard sim/simulator_dashboard.html`
