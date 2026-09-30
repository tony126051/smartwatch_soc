# Edge AI スマートウォッチ SoC システムアーキテクチャ設計仕様書

[繁體中文](../system_architecture.md) | [English](../en/system_architecture.md) | [日本語](system_architecture.md)

## 1. 概要 (Overview)
本 SoC は超低消費電力のウェアラブルスマートウォッチ向けに特化設計されており、2段階の常時稼働音声起動階層（Two-Stage Wakeup Hierarchy）を備えています。全システムのメモリおよび特徴量バッファはすべてオンチップ SRAM（16 KB On-chip SRAM）内に常駐し、高消費電力な外部 DRAM アクセスを完全に排除しています。

---

## 2. システムモジュール構成 (Subsystems)

### 2.1 音声フロントエンド (Audio Front-End, AFE)
- **PDM 受信器 (`pdm_receiver.v`)**：外部 1.024MHz MEMS デジタルマイクの 1-bit PDM 信号を 2 段フリップフロップで同期し、メタスタビリティを防止。
- **CIC フィルタ (`cic_decimator_q64.v`)**：
  - フィルタ次数：$N=3$（3次積分型間引きフィルタ）。
  - 間引き比率：$R=64$（1.024MHz を 16kHz にダウンサンプリング）。
  - 内部語長：22-bit 符号付きアキュムレータ、16-bit PCM への飽和丸め処理。
- **音声 FIFO (`audio_fifo.v`)**：256 ワード同期リングバッファ、CPU の即時読出しや DMA 転送に対応。

### 2.2 第1段フィルタ：ハードウェア VAD (`vad_core.v`)
- **待機電力**：$< 20\text{ }\mu\text{W}$。
- **アルゴリズム**：短時間絶対値エネルギー（Short-Time Energy, STE）。
- **フレーム長**：160 PCM サンプル（10ms @ 16kHz）。
- **主要機能**：
  - 動的に設定可能なエネルギー閾値レジスタ。
  - Hangover デバウンスカウンタ（音声途切れ防止）。
  - 立上がりハードウェア割込み（`irq_vad_wakeup`）、無音時は CPU を完全ディープスリープ（WFI）に維持。

### 2.3 第2段フィルタ：軽量 KWS NPU (`npu_top.v`)
- **ネットワーク構造**：Depthwise Separable CNN (DS-CNN)：
  - **Conv2D**：$3\times3$, 1 input ch $\to$ 4 output ch, ReLU
  - **Depthwise Conv2D**：$3\times3$, 4 groups, 4 channels, ReLU
  - **Pointwise Conv2D**：$1\times1$, 4 input ch $\to$ 8 output ch, ReLU
  - **Global Average Pooling**：$16\times16 \to 1$ 空間平均プーリング
  - **Fully Connected**：$8 \to 2$ 出力（Class 0: 雑音/非キーワード, Class 1: ターゲットキーワード）
- **量子化形式**：全レイヤ INT8 固定小数点演算（8-bit 重み $\times$ 8-bit 特徴量 $\to$ 32-bit 累積・スケール処理）。
- **推論時間**：28,688 クロックサイクル（12.288MHz 動作時わずか **2.33 ms**）。

### 2.4 システムバスとメモリマップ (`kws_accelerator_subsys.v`)
- 標準 AMBA APB インターフェースにより、AFE、VAD、NPU を統一管理。
- APB ウィンドウ経由でニューラルネットワーク重み（Weight RAM）および入力特徴量（Feature RAM）を動的に書換え可能。
