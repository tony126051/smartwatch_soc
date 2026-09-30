# Edge AI 智慧手錶 SoC 系統架構設計規範 (System Architecture Specification)

## 1. 概述 (Overview)
本 SoC 專為超低功耗穿戴式智慧手錶所設計，具備兩級 Always-on 語音喚醒階層架構（Two-Stage Wakeup Hierarchy），全系統記憶體與特徵緩衝區完全常駐於晶片內 SRAM（On-chip SRAM / BRAM），杜絕任何外部 DRAM 存取耗電。

---

## 2. 系統模組架構 (Subsystems)

### 2.1 音訊前端 (Audio Front-End, AFE)
- **PDM 接收器 (`pdm_receiver.v`)**：雙級正反器同步外部 1.024MHz MEMS 數位麥克風 1-bit PDM 信號，杜絕亞穩態。
- **CIC 降頻濾波器 (`cic_decimator_q64.v`)**：
  - 階數：$N=3$（3 階積分梳狀濾波器）。
  - 降採樣比：$R=64$（將 1.024MHz 降頻至 16kHz）。
  - 內部運算字長：22-bit 符號數累加器，輸出飽和截斷至 16-bit PCM。
- **音訊 FIFO (`audio_fifo.v`)**：256-word 同步環形緩衝區，支援 CPU 隨時讀取或 DMA 搬移。

### 2.2 第一級過濾：硬體 VAD (`vad_core.v`)
- **待機功耗**：$< 20\text{ }\mu\text{W}$。
- **演算法**：短時絕對值能量（Short-Time Absolute Energy, STE）。
- **音框長度**：160 個 PCM 採樣（10ms @ 16kHz）。
- **功能特性**：
  - 動態可配置能量門檻暫存器。
  - Hangover 防抖計數器（防止語音音節中斷）。
  - 上升沿硬體喚醒中斷（`irq_vad_wakeup`），在安靜無聲環境下維持零中斷、CPU 深度睡眠。

### 2.3 第二級過濾：輕量化 KWS NPU (`npu_top.v`)
- **網路架構**：深度可分離卷積神經網路（DS-CNN）：
  - **Conv2D**：$3\times3$, 1 input ch $\to$ 4 output ch, ReLU
  - **Depthwise Conv2D**：$3\times3$, 4 groups, 4 channels, ReLU
  - **Pointwise Conv2D**：$1\times1$, 4 input ch $\to$ 8 output ch, ReLU
  - **Global Average Pooling**：$16\times16 \to 1$ 空間均值池化
  - **Fully Connected**：$8 \to 2$ 輸出（Class 0: 雜音/非關鍵詞, Class 1: 目標喚醒詞）
- **量化格式**：全程 INT8 定點運算（8-bit 權重 $\times$ 8-bit 特徵 $\to$ 32-bit 累加，定點截斷縮放）。
- **推論耗時**：28,688 時脈週期（在 12.288MHz 時脈下僅需 **2.33 ms**）。

### 2.4 系統匯流排與記憶體映射 (`kws_accelerator_subsys.v`)
- 標準 AMBA APB 介面，統一管理 AFE、VAD 與 NPU。
- 支援透過 APB 窗口動態燒錄/更新神經網路權重（Weight RAM）與特徵（Feature RAM）。
