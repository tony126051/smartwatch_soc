# 06 - Task Worklog Template (TMP)

Document ID: `SPEC-TMP-001-EN`  
Version: `1.0.0`  
Status: `Approved / SSOT`

---

## Template Instructions
When an AI Agent completes a development task or bug fix, it is recommended to document the changes using this structured markdown template in the pull request description or conversation response.

---

```markdown
# 🛠️ [Task Title / Feature Summary]

- **Executor**: AI Agent (Model Name / Role)
- **Date**: YYYY-MM-DD
- **Associated Requirement ID**: `REQ-xxx-yyy` (Refer to docs/spec/en/)
- **Change Category**: [Feature Extension / Bug Fix / Optimization / Refactoring / Spec Update]

---

## 1. Objective & Context
[Briefly describe the task, context, and spec requirement being satisfied]

---

## 2. Scope & Touched Files
- **Specifications**:
  - [Spec File](file:///home/tony/repo/projects/smart_watch/docs/spec/en/...)
- **Algorithm Models**:
  - [Algorithm Script](file:///home/tony/repo/projects/smart_watch/model/...)
- **Digital RTL**:
  - [Verilog Module](file:///home/tony/repo/projects/smart_watch/rtl/...)
- **Firmware & Headers**:
  - [Assembly / C Source](file:///home/tony/repo/projects/smart_watch/sw/...)
- **Simulator & Tests**:
  - [Simulator Component](file:///home/tony/repo/projects/smart_watch/sim/...)

---

## 3. Implementation Highlights
### 3.1 Interface & Register Modifications
[Detail any register additions, bitfield adjustments, reset values, or side-effects]

### 3.2 Logic & Computational Adjustments
[Explain key changes in Verilog RTL, Python simulator, or assembly instructions]

---

## 4. Verification Evidence
### 4.1 Commands Executed
```bash
# 1. Rebuild firmware (if assembly modified)
python3 sw/build_firmware.py sw/app/main.s sw/firmware.hex

# 2. Run full regression suite
python3 sim/run_simulator.py --mode regression
```

### 4.2 Test Output Log
```text
===========================================================================
  [Regression Suite] Smartwatch SoC Subsystems & Full Chip Verification
===========================================================================
[Test 1/5] Verifying RISC-V RV32I CPU core and memory subsystem... [PASS]
[Test 2/5] Verifying Audio Front-End (3-stage CIC decimator & FIFO)... [PASS]
[Test 3/5] Verifying Level-1 Hardware Voice Activity Detector (VAD Core)... [PASS]
[Test 4/5] Verifying Level-2 KWS NPU Accelerator & INT8 inference... [PASS]
[Test 5/5] Verifying Full SoC Integration & RISC-V firmware execution... [PASS]
>>> ALL 5 REGRESSION TESTS PASSED (100% BIT-TRUE VERIFIED) <<<
```

---

## 5. Self-Audit Checklist
- [x] Zero external DRAM dependencies; total SRAM strictly within 64 KB
- [x] Register definitions 100% synchronized between `01_hardware_interface_spec.md` and `soc_regs.h`
- [x] Verilog RTL conforms to Verilog-2001 synthesizability standards (no latches)
- [x] Python simulator maintains zero-dependency standard library compliance
- [x] All 5 regression tests PASS with zero regressions
```
