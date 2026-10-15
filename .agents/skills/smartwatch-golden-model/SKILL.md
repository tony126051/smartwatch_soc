---
name: smartwatch-golden-model
description: >-
  Guides audio DSP algorithm design, INT8 neural network quantization, and golden vector
  generation for the Smartwatch SoC. Use when modifying or validating the CIC decimator,
  VAD short-time energy calculation, DS-CNN neural network quantization in model/, or
  updating golden test vectors in model/golden_vectors/.
---

# Smartwatch SoC Algorithm DSP, INT8 Quantization & Golden Model Skill

This skill governs the mathematical algorithm models and bit-true golden vector generation in `model/` and `sim/simulator/`, adhering to [02_algorithm_and_golden_model_spec.md](../../../docs/spec/02_algorithm_and_golden_model_spec.md).

---

## 1. Algorithm Mathematical Specifications

### 1.1 Audio Front-End (AFE) CIC Decimator
- **PDM Sampling Rate**: $1.024\text{ MHz}$
- **Decimation Ratio**: $R = 64$ ($N = 3$ stages)
- **Output PCM Sampling Rate**: $16\text{ kHz}$
- **Internal Accumulator**: 22-bit signed two's complement integer
- **Scaling and Clamping**:
  ```python
  # Downscale 3 bits and clamp to 16-bit signed integer [-32768, 32767]
  scaled = cic_out >> 3
  pcm_sample = max(-32768, min(32767, scaled))
  ```

### 1.2 First-Stage Hardware VAD (Voice Activity Detection)
- **Frame Size**: 160 samples ($10.0\text{ ms}$ at $16\text{ kHz}$)
- **Short-Time Absolute Energy (STE)**:
  $$E = \sum_{n=0}^{159} |x[n]|$$
- **Default Energy Threshold**: `200,000`
- **Hangover Counter**: Default `4` frames. Transition from `IDLE` to `SPEECH` triggers a rising-edge interrupt `irq_vad_wakeup` on Frame 2 of the test stimulus.

### 1.3 Second-Stage KWS NPU (DS-CNN INT8 Quantization)
- **Topology**: Standard Conv2D $\to$ Depthwise Conv2D $\to$ Pointwise Conv2D $\to$ Global Average Pooling (GAP) $\to$ Fully Connected (FC).
- **Quantization Standard**: Symmetric INT8.
- **Requantization Shift & Activation**:
  ```python
  # Intermediate layer: Requantize by shifting right 7 bits and clip to [0, 127]
  act = max(0, min(127, (acc + 64) >> 7))
  ```
- **Final Layer**: Output Score 0 (Noise) and Score 1 (Keyword) without ReLU.

---

## 2. Python Simulator Implementation Constraints

When writing or editing Python behavioral models in `sim/simulator/`:

1. **Zero External Dependencies**:
   - 🚫 **NEVER** import `numpy`, `scipy`, `torch`, `sklearn`, or other third-party packages in `sim/simulator/`.
   - Use standard library modules only (`sys`, `os`, `struct`, `typing`, `math`).
2. **Bit-True Integer Simulation**:
   - Python integers do not overflow naturally. Always enforce 32-bit truncation and signed two's complement conversion:
     ```python
     # 32-bit Unsigned Truncation
     val_u32 = (a + b) & 0xFFFFFFFF

     # 32-bit Signed Conversion
     val_s32 = val_u32 if val_u32 < 0x80000000 else val_u32 - 0x100000000
     ```

---

## 3. Golden Vector Generation & Verification Workflow

When algorithms, coefficients, or quantization parameters change:

### Step 1: Run Golden Simulation Pipeline
Execute the full golden vector generator:
```bash
python3 sim/run_sim.py
```
This updates:
- `model/golden_vectors/stimulus_pcm_16k.txt`
- `model/golden_vectors/stimulus_pdm_1mhz.txt`
- `model/golden_vectors/vad_golden.txt`
- `model/golden_vectors/mfcc_golden.txt`
- `model/golden_vectors/weights_int8.hex`
- `model/golden_vectors/npu_golden.txt`

### Step 2: Validate Bit-True Invariance
Run the regression suite to ensure RTL and simulator match the golden vectors with **0 bit error**:
```bash
python3 sim/run_simulator.py --mode regression
```
Both Test 3 (VAD) and Test 4 (NPU) must report `100% 位元精確！`.
