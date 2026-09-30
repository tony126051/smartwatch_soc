# 02 - Algorithm and Golden Model Specification (AGS)

Document ID: `SPEC-AGS-001-EN`  
Version: `1.0.0`  
Status: `Approved / SSOT`

---

## 1. Audio Front-End Decimation Algorithm (AFE CIC Filter)

### 1.1 Mathematical Model & Transfer Function
The microphone input is a 1-bit PDM stream running at $F_{pdm} = 1.024\text{ MHz}$. It is decimated down to $F_s = 16\text{ kHz}$ PCM using a 3rd-order Cascaded Integrator-Comb (CIC) filter with decimation factor $R = 64$.

The $Z$-domain transfer function is defined as:
$$H(z) = \left( \sum_{k=0}^{R-1} z^{-k} \right)^N = \left( \frac{1 - z^{-R}}{1 - z^{-1}} \right)^N, \quad N=3, R=64$$

### 1.2 Bit Growth & Wordlength Specification
According to Hogenauer's bit growth formulation:
$$B_{max} = B_{in} + N \cdot \log_2(R) = 1 + 3 \times \log_2(64) = 1 + 3 \times 6 = 19\text{ bits}$$

To provide headroom and conform to 32-bit register architectures:
- **Internal Accumulator Wordlength**: **22-bit signed two's complement integer**.
- **Scaling and Clamping**:
  $$x_{pcm}[n] = \text{clamp}\left( \text{CIC}_{out}[n] \gg 3, -32768, 32767 \right)$$
- Output samples are pushed into a 256-word circular audio FIFO (`audio_fifo.v`).

---

## 2. Level-1 Hardware Voice Activity Detection (VAD Core)

### 2.1 Short-Time Absolute Energy (STE)
To minimize logic gate count and dynamic power, the VAD implements **L1-norm short-time absolute energy accumulation**:
$$E_{frame} = \sum_{n=0}^{L-1} |x_{pcm}[n]|, \quad L = 160\text{ (10.0 ms window @ 16 kHz)}$$

### 2.2 Hangover Counter State Machine
Natural speech contains brief pauses ($10 \sim 30\text{ ms}$) between consonants and vowels. To prevent choppy wakeups, a 4-bit Hangover counter FSM extends the active window:

```mermaid
stateDiagram-v2
    [*] --> VAD_IDLE
    
    state VAD_IDLE {
        description: Standby silence (speech_active = 0)
    }
    state VAD_ACTIVE {
        description: Speech active (speech_active = 1)
    }
    state VAD_HANGOVER {
        description: Hangover hold (speech_active = 1)
    }
    
    VAD_IDLE --> VAD_ACTIVE: E_frame >= VAD_THRESHOLD<br>(Asserts irq_vad_wakeup)
    VAD_ACTIVE --> VAD_ACTIVE: E_frame >= VAD_THRESHOLD
    VAD_ACTIVE --> VAD_HANGOVER: E_frame < VAD_THRESHOLD<br>(cnt = HANGOVER_LEN)
    VAD_HANGOVER --> VAD_ACTIVE: E_frame >= VAD_THRESHOLD
    VAD_HANGOVER --> VAD_HANGOVER: E_frame < VAD_THRESHOLD and cnt > 1<br>(cnt = cnt - 1)
    VAD_HANGOVER --> VAD_IDLE: E_frame < VAD_THRESHOLD and cnt == 1<br>(speech_active = 0)
```

### 2.3 Interrupt Triggering Condition
- The `irq_vad_wakeup` interrupt is asserted **only on the rising edge** transition from `VAD_IDLE` to `VAD_ACTIVE`.
- No repetitive interrupts are sent while in `VAD_ACTIVE` or `VAD_HANGOVER`, preventing CPU interrupt flooding.

---

## 3. Level-2 KWS Neural Network Model (DS-CNN INT8)

### 3.1 Network Topology
The model is an ultra-lightweight Depthwise Separable Convolutional Neural Network (DS-CNN):
- **Input Feature Size**: $16 \times 16$ single-channel INT8 matrix (256 bytes).

| Layer | Type | Input Dim ($C_{in} \times H \times W$) | Kernel / Groups | Output Dim ($C_{out} \times H \times W$) | Activation | Purpose |
|---|---|---|---|---|---|---|
| **Layer 1** | Standard Conv2D | $1 \times 16 \times 16$ | Kernel $3\times3$, Stride 1, Pad 1 | $4 \times 16 \times 16$ | ReLU | Low-level acoustic features |
| **Layer 2** | Depthwise Conv2D | $4 \times 16 \times 16$ | Kernel $3\times3$, Groups 4, Pad 1 | $4 \times 16 \times 16$ | ReLU | Spatial channel-wise filtering |
| **Layer 3** | Pointwise Conv2D | $4 \times 16 \times 16$ | Kernel $1\times1$, Stride 1 | $8 \times 16 \times 16$ | ReLU | Cross-channel feature projection |
| **Layer 4** | Global Avg Pool | $8 \times 16 \times 16$ | $16\times16$ Spatial Mean | $8 \times 1 \times 1$ | None | Spatial reduction / translation invariance |
| **Layer 5** | Fully Connected | $8 \times 1 \times 1$ | $8 \to 2$ Matrix Multiply | $2 \times 1 \times 1$ | None | Class 0 & Class 1 score generation |

### 3.2 Symmetric INT8 Fixed-Point Quantization
To eliminate floating-point hardware overhead:
1. **Inputs & Weights**: Signed 8-bit integers (INT8, range $[-128, 127]$).
2. **Accumulators**: Signed 32-bit integers (INT32).
3. **Requantization & Scale-down**:
   Following bias accumulation, convolution activations are scaled down via an **arithmetic right shift by 7 bits (`>> 7`)** and clamped back to INT8:
   $$y_{act} = \text{ReLU}\left( \text{clamp}\left( ( \text{Acc}_{32} + \text{Bias}_{32} ) \gg 7, -128, 127 \right) \right)$$
   where $\text{ReLU}(v) = \max(0, v)$.
4. **Fully Connected Layer**:
   Final output scores preserve the full 32-bit signed dynamic range and are directly stored in `NPU_SCORE0` and `NPU_SCORE1`.

---

## 4. Golden Vectors & Standard Datasets

Golden models in `model/` generate deterministic verification vectors stored in `model/golden_vectors/`:

| File Path | Format | Generator Script | Contents Specification |
|---|---|---|---|
| `model/golden_vectors/stimulus_pdm_1mhz.txt` | ASCII 0/1 bits | `generate_stimulus.py` | 102,400 bits PDM test stream |
| `model/golden_vectors/stimulus_pcm_16k.txt` | Decimal integers | `generate_stimulus.py` | 1,600 samples 16-bit signed PCM audio |
| `model/golden_vectors/vad_golden.txt` | CSV (Frame,Energy,Active,IRQ) | `golden_vad.py` | 10 audio frames energy & IRQ states |
| `model/golden_vectors/mfcc_golden.txt` | Hex INT8 values | `golden_mfcc.py` | 9 frames $\times$ 16 channels MFCC features |
| `model/golden_vectors/weights_int8.hex` | 32-bit Hex words | `golden_npu.py` | Quantized network weights and biases |
| `model/golden_vectors/npu_golden.txt` | JSON (Scores, Predicted) | `golden_npu.py` | Golden scores: Class 0=58, Class 1=-51 |

---

## 5. Algorithm Requirements Traceability Matrix

| Requirement ID | Technical Assertion |
|---|---|
| `REQ-ALG-001` | CIC filter decimation factor is strictly 64, order 3, yielding 16-bit signed PCM. |
| `REQ-ALG-002` | Hardware VAD short-time energy window is exactly 160 PCM samples (10 ms). |
| `REQ-ALG-003` | VAD Hangover mechanism must maintain active status until the countdown expires. |
| `REQ-ALG-004` | KWS NPU model must follow the 5-layer DS-CNN architecture with $16\times16$ INT8 input. |
| `REQ-ALG-005` | Convolution requantization must use arithmetic right shift `>> 7` and $[-128, 127]$ clamp. |
| `REQ-ALG-006` | Algorithm outputs must achieve 100% bit-accurate equivalence across Python, RTL, and sim. |
