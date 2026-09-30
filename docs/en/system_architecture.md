# Edge AI Smartwatch SoC System Architecture Specification

[繁體中文](../system_architecture.md) | [English](system_architecture.md) | [日本語](../ja/system_architecture.md)

## 1. Overview
This SoC is tailored for ultra-low-power wearable smartwatches, featuring a Two-Stage Always-on Wakeup Hierarchy. All memory and feature buffers reside entirely inside on-chip SRAM (16 KB On-chip SRAM), eliminating power-hungry external DRAM access.

---

## 2. Hardware Subsystems

### 2.1 Audio Front-End (AFE)
- **PDM Receiver (`pdm_receiver.v`)**: Dual-stage flip-flop synchronizer interfacing with an external 1.024 MHz MEMS digital microphone 1-bit PDM stream, eliminating metastability.
- **CIC Decimator Filter (`cic_decimator_q64.v`)**:
  - Filter Order: $N=3$ (3rd-order Cascaded Integrator-Comb filter).
  - Decimation Ratio: $R=64$ (decimates 1.024 MHz down to 16 kHz).
  - Internal wordlength: 22-bit signed accumulator with saturation rounding to 16-bit PCM.
- **Audio FIFO (`audio_fifo.v`)**: 256-word synchronous circular buffer supporting CPU reads and DMA transfers.

### 2.2 Stage 1 Filter: Hardware VAD (`vad_core.v`)
- **Standby Power**: $< 20\text{ }\mu\text{W}$.
- **Algorithm**: Short-Time Absolute Energy (STE).
- **Frame Length**: 160 PCM samples (10 ms @ 16 kHz).
- **Key Features**:
  - Dynamically configurable energy threshold register.
  - Hangover debounce counter (prevents voice syllable cut-offs).
  - Rising-edge hardware wakeup interrupt (`irq_vad_wakeup`), ensuring zero interrupts and deep CPU sleep during quiet periods.

### 2.3 Stage 2 Filter: Lightweight KWS NPU (`npu_top.v`)
- **Neural Network Architecture**: Depthwise Separable CNN (DS-CNN):
  - **Conv2D**: $3\times3$, 1 input ch $\to$ 4 output ch, ReLU
  - **Depthwise Conv2D**: $3\times3$, 4 groups, 4 channels, ReLU
  - **Pointwise Conv2D**: $1\times1$, 4 input ch $\to$ 8 output ch, ReLU
  - **Global Average Pooling**: $16\times16 \to 1$ spatial average pooling
  - **Fully Connected**: $8 \to 2$ outputs (Class 0: Noise/Non-keyword, Class 1: Target Keyword)
- **Quantization**: End-to-end INT8 fixed-point arithmetic (8-bit weights $\times$ 8-bit activations $\to$ 32-bit accumulation with scaling).
- **Inference Latency**: Fixed 28,688 clock cycles (**2.33 ms** @ 12.288 MHz).

### 2.4 System Bus & Interconnect (`kws_accelerator_subsys.v`)
- Standard AMBA APB interface for managing AFE, VAD, and NPU.
- Supports dynamically writing and updating neural network weights (Weight RAM) and feature maps (Feature RAM) via APB memory windows.
