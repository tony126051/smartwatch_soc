# 04 - Verification and Acceptance Specification (VAS)

Document ID: `SPEC-VAS-001-EN`  
Version: `1.0.0`  
Status: `Approved / SSOT`

---

## 1. Verification Pyramid & Strategy

The project employs a three-tier verification structure ensuring strict synchronization between mathematical algorithms, digital RTL, and embedded firmware:

```
       ▲
      / \     [Level 3] Full SoC System Regression Suite
     /   \    - Python cycle-accurate simulator + actual firmware binary (sim/run_simulator.py)
    /─────\
   /       \  [Level 2] Subsystem Verilog Testbenches
  /         \ - RTL simulation with test vectors (tb_afe.v, tb_vad.v, tb_npu.v, tb_soc_top.v)
 /───────────\
/             \ [Level 1] Python Algorithm Golden Models
─────────────── - Floating-to-fixed point conversion & stimulus (golden_vad.py, golden_npu.py)
```

---

## 2. The 5 Mandatory Regression Suites & Acceptance Criteria

Every code change must pass all 5 acceptance checkpoints before handover:

### Test 1: RISC-V RV32I Core & Memory Subsystem
- **Target**: `PicoRV32` core, Boot ROM, Data RAM, `waitirq` custom instruction.
- **Criteria**:
  1. General registers read/write integrity.
  2. Memory load/store little-endian alignment.
  3. `waitirq` freezes execution and resumes upon interrupt assertion.
- **Expected Output**: `[PASS] RISC-V RV32I arithmetic and custom instructions (waitirq) 100% correct`

### Test 2: Audio Front-End Decimation & FIFO Buffer
- **Target**: `pdm_receiver.v`, `cic_decimator_q64.v`, `audio_fifo.v`.
- **Criteria**:
  1. Decimates 1.024 MHz PDM test stream into 16 kHz PCM.
  2. FIFO sample count increments correctly (`FIFO_COUNT = 10`).
  3. Popped sample matches reference (`sample = -194`).
- **Expected Output**: `[PASS] CIC filter decimation -> FIFO count: 10, sample = -194`

### Test 3: Level-1 Hardware VAD Core & Wakeup IRQ
- **Target**: `vad_core.v`, Short-time absolute energy accumulator, Hangover FSM.
- **Criteria**:
  1. Accumulation across 10 frames matches [`model/golden_vectors/vad_golden.txt`](../../../model/golden_vectors/vad_golden.txt) **with 100% bit-true accuracy (zero error)**.
  2. Rising-edge wakeup IRQ `irq_vad_wakeup` asserts precisely on Frame 2.
  3. Writing `VAD_CTRL[1] = 1` clears the IRQ flag.
- **Expected Output**:
  - `[PASS] Hardware VAD short-time energy accumulation 100% bit-true!`
  - `[PASS] Rising-edge wakeup IRQ (irq_vad_wakeup) asserted on frame 2!`

### Test 4: Level-2 KWS NPU Accelerator & INT8 Inference
- **Target**: `npu_top.v`, `mac_array_4x4.v`, DS-CNN INT8 pipeline.
- **Criteria**:
  1. Total execution latency is strictly **28,688 cycles** (2.33 ms @ 12.288 MHz).
  2. Output classification scores match golden reference:
     - **Class 0 (Background / Noise)**: `58`
     - **Class 1 (Wakeup Keyword)**: `-51`
  3. Predicted classification: `Class 0` (confidence margin: 109).
- **Expected Output**:
  - `[PASS] NPU DS-CNN inference matches Python golden model 100% bit-true!`
  - `[PASS] Hardware latency: 28688 cycles (2.33 ms @ 12.288MHz)`
  - `[PASS] Classification scores: Class 0 = 58, Class 1 = -51`

### Test 5: Full SoC System Integration & Firmware Flow
- **Target**: `smartwatch_soc_top.v` executing binary [`sw/firmware.hex`](../../../sw/firmware.hex).
- **Criteria**:
  1. **Stage 1 (Boot)**: CPU initializes AFE/VAD, enters standby sleep, LED displays `0x04`.
  2. **Stage 2 (Wakeup)**: Voice stream injected, VAD IRQ triggers ISR, LED transitions to `0x55`.
  3. **Stage 3 (Inference)**: CPU transfers features and triggers NPU; non-keyword rejected, LED stays `0x55`, returns to sleep.
- **Expected Output**:
  - `[PASS] Stage 1: CPU Boot -> Configure AFE/VAD -> Enter standby sleep (LED = 0x04)`
  - `[PASS] Stage 2: Voice stream detected -> VAD Wakeup IRQ -> Execute ISR`
  - `[PASS] Stage 3: Load features -> Complete NPU inference -> LED = 0x55`

---

## 3. Automated Verification Command Matrix

| Purpose | Command Line | Execution Time | Exit Code | Artifacts |
|---|---|---|---|---|
| **Full Regression** | `python3 sim/run_simulator.py --mode regression` | $< 2\text{ s}$ | `0` | All 5 test cases PASS |
| **Golden Model Run**| `python3 sim/run_sim.py` | $< 3\text{ s}$ | `0` | Updates `model/golden_vectors/*` |
| **Rebuild Firmware**| `python3 sw/build_firmware.py sw/app/main.s sw/firmware.hex` | $< 1\text{ s}$ | `0` | Updates `sw/firmware.hex` |
| **Interactive GDB** | `python3 sim/run_simulator.py --mode interactive` | Interactive | `0` | Live PC/register debugging |
| **Waveform & Dash** | `python3 sim/run_simulator.py --mode scenario --vcd sim/waves_soc.vcd --dashboard sim/simulator_dashboard.html` | $< 3\text{ s}$ | `0` | Standard IEEE 1364 VCD & HTML5 dashboard |
| **Web GUI Server**  | `python3 sim/web_server.py 8080` | Daemon | N/A | Interactive GUI at `http://localhost:8080/` |

---

## 4. Failure Troubleshooting Matrix

| Failing Test | Root Cause Hypotheses | Primary Files to Inspect | Recommended Remedy |
|---|---|---|---|
| **Test 1 Fail** | RV32I syntax error, or `waitirq` opcode mismatch | 1. [`sw/app/main.s`](../../../sw/app/main.s)<br>2. [`sw/build_firmware.py`](../../../sw/build_firmware.py) | Verify `sw/firmware.hex` was rebuilt; ensure custom instruction opcode is `0x0000006b`. |
| **Test 2 Fail** | CIC bit growth overflow or FIFO pointer desynchronization | 1. [`rtl/afe/cic_decimator_q64.v`](../../../rtl/afe/cic_decimator_q64.v)<br>2. [`sim/simulator/afe.py`](../../../sim/simulator/afe.py) | Check clamping math: `clamp(cic_out >> 3, -32768, 32767)`. |
| **Test 3 Fail** | Energy window length $\ne 160$, or Hangover FSM bug | 1. [`rtl/vad/vad_core.v`](../../../rtl/vad/vad_core.v)<br>2. [`sim/simulator/vad.py`](../../../sim/simulator/vad.py) | Check Frame 2 energy in `vad_golden.txt`; ensure `irq_vad_wakeup` is rising-edge latched. |
| **Test 4 Fail** | DS-CNN requantization shift mismatch, or cycle stall | 1. [`rtl/npu/npu_top.v`](../../../rtl/npu/npu_top.v)<br>2. [`sim/simulator/npu.py`](../../../sim/simulator/npu.py) | Confirm activation scale is `>> 7` with ReLU; confirm latency equals 28,688 cycles. |
| **Test 5 Fail** | ISR fails to clear IRQ, or LED status codes misaligned | 1. [`sw/app/main.s`](../../../sw/app/main.s)<br>2. [`sim/simulator/soc.py`](../../../sim/simulator/soc.py) | Ensure ISR writes `VAD_CTRL[1] = 1`; verify LED register writes to `0x8000_0000`. |

---

## 5. Verification Requirements Traceability Matrix

| Requirement ID | Technical Assertion |
|---|---|
| `REQ-VERIF-001` | Regression suite must run on pure Python 3.8+ with zero third-party EDA dependencies. |
| `REQ-VERIF-002` | Regression pass rate must be 100% across all 5 test cases. |
| `REQ-VERIF-003` | Algorithm models and simulator outputs must achieve 0 error (Bit-True Exact Match). |
| `REQ-VERIF-004` | Supports exporting standard IEEE 1364 `.vcd` files for GTKWave visualization. |
| `REQ-VERIF-005` | Test CLI and reporting must support multi-language flags (`--lang en`, `zh-TW`, `zh-CN`, `ja`). |
