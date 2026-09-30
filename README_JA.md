# ⌚ Edge AI スマートウォッチ SoC 設計・シミュレーション検証プラットフォーム

[繁體中文](README.md) | [English](README_EN.md) | [日本語](README_JA.md)

本プロジェクトは、超低消費電力スマートウォッチ向けの **2段階音声起動（Two-Stage Voice Wakeup）システムオンチップ（SoC）** です。アルゴリズムのゴールデンモデル、Verilog RTL ハードウェア記述、RISC-V 組込みファームウェア、およびリアルタイム HTML5 Web GUI を備えたサイクル正確・ビット完全なシミュレータを含んでいます。

<p align="center">
  <img src="docs/assets/simulator_gui_preview.png" alt="Smartwatch SoC Interactive Simulator Web GUI" width="100%" style="border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);" />
  <br>
  <em>▲ 多言語リアルタイム切替、ハードウェア状態遷移パイプライン追跡、動的消費電力分析を備えた Web GUI シミュレータ画面</em>
</p>

---

## 🚀 30秒クイックスタート (Quick Start)

複雑な EDA ツールやクロスコンパイラのインストールは不要です。**Python 3** だけで全機能が即座に動作します：

### 1. 視覚的・対話型 Web GUI シミュレータの起動 (推奨)
```bash
python3 sim/web_server.py 8080
```
ブラウザを開いてアクセス：**`http://localhost:8080/`**
- **🌐 多言語対応 (i18n)**：画面上部に言語選択メニューを搭載し、**繁体中国語 (繁體中文)**、**英語 (English)**、**簡体中国語 (简体中文)**、**日本語** にリアルタイム切り替え可能（設定は自動保存）。
- **リアルタイム表示**：スマートウォッチの外観画面、オンボード 8-bit LED、CPU PC / レジスタ、VAD 短時間エネルギーバー、NPU 畳み込みパイプライン、動的消費電力プロファイルを視覚化。
- **インタラクティブ操作**：`単歩実行 (Step)`、`連続実行 (Run)`、`音声ストリーム (Speech)`、`無音 (Silence)`、`リセット (Reset)` をクリック操作。

### 2. 全チップ自動回帰テストの実行
```bash
python3 sim/run_simulator.py --mode regression --lang ja
# 言語オプション: --lang ja (日本語), --lang en (英語), --lang zh-TW (繁体中国語), --lang zh-CN (簡体中国語)
```
以下の5大項目を自動検証します：
1. RISC-V RV32I 命令セットおよびメモリ読み書き
2. 音声フロントエンド（PDM $\to$ 3次 CIC フィルタ $\to$ 256ワード FIFO）
3. 第1段 常時稼働（Always-on）ハードウェア VAD エネルギー計算および割込み発火
4. 第2段 KWS NPU（DS-CNN INT8）行列演算および推論スコア
5. システム起動、待機スリープ、音声起動シーケンスの完全検証

### 3. GDB スタイル対話型コマンドラインデバッガ
```bash
python3 sim/run_simulator.py --mode interactive --lang ja
```
サポートされているコマンド：
- `step [N]`：N 個の命令をステップ実行し、逆アセンブルとレジスタ変化を表示。
- `run [N]`：ブレークポイント、トラップ、またはスリープまで実行。
- `break <addr>`：指定アドレスにブレークポイントを設定（例: `break 0x10`）。
- `delete [addr]`：ブレークポイントを解除。
- `regs`：32 本の汎用レジスタ（ABI 名付き）をダンプ。
- `mem <addr> [len]`：メモリ内容を 16 進および ASCII で表示。
- `status`：SoC 周辺回路（LED、AFE、VAD、NPU、CPU）の状態を表示。
- `feed [speech|tone|silence]`：マイク入力にテスト音声を注入。
- `power`：消費電力、累積エネルギー、バッテリー駆動時間予測を表示。
- `lang [code]`：表示言語を切り替え（`ja`, `en`, `zh-TW`, `zh-CN`）。
- `reset`：全レジスタと周辺回路をリセット。
- `quit`：シミュレーションを終了。

### 4. デジタル波形ファイル (VCD) & ダッシュボードの生成
```bash
python3 sim/run_simulator.py --mode scenario --vcd sim/waves_soc.vcd --dashboard sim/simulator_dashboard.html --lang ja
```
- 標準 IEEE 1364 `.vcd` ファイルを出力し、**GTKWave** や **PulseView** でクロックごとの信号遷移を確認可能。
- 独立した対話型 HTML5 ダッシュボード [`sim/simulator_dashboard.html`](sim/simulator_dashboard.html) を出力（多言語切替対応）。

---

## 🏛️ ハードウェアアーキテクチャ概要

外部 DRAM への高消費電力アクセスを排除するため、すべての特徴バッファとメモリはオンチップ（**On-chip 16 KB SRAM**）に統合されています：

```
+-----------------------------------------------------------------------------------+
|                         Smartwatch SoC トップアーキテクチャ                       |
|                                                                                   |
|  [ 音声入力 ]             [ メモリサブシステム ]         [ コア演算ユニット ]     |
|  1.024MHz PDM マイク       0x0000_0000: 8KB Boot ROM     32-bit RISC-V CPU        |
|       │                    0x1000_0000: 8KB Data SRAM    (PicoRV32 RV32I)         |
|       ▼                                                       ▲                   |
|  [ AFE 前段回路 ]          [ システムバス & APB ]              │ (割込み信号)       |
|  - 3次 CIC 間引き (R=64)   0x4000_0000: KWS Subsystem ───────┼── irq[0]: VAD 起動 |
|  - 256ワード音声 FIFO      0x8000_0000: デバッグ LED レジスタ  └── irq[1]: NPU 完了 |
|       │                                                                           |
|       ▼ (16kHz PCM)                                                               |
|  [ 第1段：HW VAD (Always-on) ]  ────────────── 音声検出 ───────────┐              |
|  - 160点短時間エネルギー累積 (< 20μW)                               │              |
|                                                                    ▼              |
|  [ 第2段：KWS NPU 加速器 ] ◄──────────────────────────────── CPU起動・特徴読込     |
|  - 16x16 INT8 特徴 RAM (0x400)                                                    |
|  - 256B 重み RAM (0x500)                                                          |
|  - DS-CNN (Conv1 -> DW -> PW -> GAP -> FC, 28,688 サイクル, 2.33ms)               |
|  - Class 0 (背景ノイズ) と Class 1 (ウェイクワード) のスコア出力                   |
+-----------------------------------------------------------------------------------+
```

---

## 📂 プロジェクト構成一覧

```text
smart_watch/
├── docs/                       # 設計仕様書と解説マニュアル
│   ├── developer_onboarding_guide.md  # 開発者オンボーディングガイド
│   ├── simulator_guide.md             # シミュレータ操作・アーキテクチャ詳細手引
│   ├── system_architecture.md         # システムタイミング・回路設計仕様
│   └── register_map.md                # APB レジスタマップ手引
├── model/                      # Python アルゴリズムゴールデンモデル
│   ├── generate_stimulus.py           # 音声信号ジェネレータ (PDM/PCM)
│   ├── golden_vad.py                  # VAD 短時間エネルギーゴールデンモデル
│   ├── golden_mfcc.py                 # MFCC 特徴抽出モデル
│   ├── golden_npu.py                  # DS-CNN INT8 固定小数点推論モデル
│   └── golden_vectors/                # ゴールデンテストベクトルと重み
├── rtl/                        # 合成可能 Verilog HDL 回路記述
│   ├── afe/                           # PDM 受信器、CIC フィルタ、音声 FIFO
│   ├── vad/                           # 第1段 常時稼働ハードウェア VAD コア
│   ├── npu/                           # 第2段 KWS NPU MAC アレイ & FSM
│   ├── cpu/                           # 32-bit RISC-V PicoRV32 プロセッサ
│   ├── bus/                           # APB バスブリッジ & アダプタ
│   └── top/                           # SoC トップレベル統合回路
├── sim/                        # シミュレーション検証 & 視覚化スイート
│   ├── simulator/                     # サイクル正確 Python SoC シミュレータ
│   │   ├── cpu.py, bus.py, afe.py, vad.py, npu.py, power.py, vcd.py, i18n.py ...
│   ├── run_simulator.py               # 統一シミュレーション実行スクリプト (--lang 対応)
│   ├── run_sim.py                     # EDA ツール検証スクリプト (iverilog)
│   ├── web_server.py                  # リアルタイム Web サーバーバックエンド
│   ├── smartwatch_simulator_ui.html   # インタラクティブ HTML5 Web GUI (多言語対応)
│   ├── simulator_dashboard.html       # 全システムアーキテクチャダッシュボード
│   └── waves_soc.vcd                  # 出力されたデジタル波形ファイル
└── sw/                         # 組込みファームウェア & ツールチェーン
    ├── app/                           # ソースコード (main.s, main.c)
    ├── include/                       # レジスタ定義ヘッダ (soc_regs.h)
    ├── build_firmware.py              # 純 Python 軽量 RISC-V アセンブラ
    └── firmware.hex                   # コンパイル済 32-bit マシンコード
```

---

## 🛠️ 開発手順と操作ガイド

### 1. RISC-V ファームウェアの変更と再ビルド
ファームウェアのソースコードは [`sw/app/main.s`](sw/app/main.s) にあります。修正後、同梱のアセンブラを実行するだけで `sw/firmware.hex` が更新されます：
```bash
python3 sw/build_firmware.py sw/app/main.s sw/firmware.hex
```

### 2. VAD 感度閾値の調整
ソフトウェアから `0x4000_0014` (`REG_VAD_THRESHOLD`) に書き込みます（デフォルト値: `200000`）。[`sw/app/main.s`](sw/app/main.s) 内で初期値を変更することも可能です。

### 3. オンボード LED の状態コード
`0x8000_0000` の LED レジスタでハードウェア動作フェーズを確認できます：
- `0x01`：SoC 起動・初期化中 (Booting)
- `0x02`：周辺回路準備完了 (System Ready)
- `0x04`：ディープスタンバイスリープ (`WFI` 待機電力 < 20μW)
- `0x08`：人声を検出！第2段 NPU 推論を開始
- `0xAA`：キーワード一致 🎯 画面全点灯 (MATCH)
- `0x55`：非キーワード / 雑音 $\to$ スリープ状態へ復帰

### 4. 技術ドキュメント (日本語版)
- 🔰 開発者オンボーディングガイド：[`docs/ja/developer_onboarding_guide.md`](docs/ja/developer_onboarding_guide.md)
- 🕹️ シミュレータ操作・アーキテクチャ詳細手引：[`docs/ja/simulator_guide.md`](docs/ja/simulator_guide.md)
- 🏛️ システムアーキテクチャ設計仕様書：[`docs/ja/system_architecture.md`](docs/ja/system_architecture.md)
- 📋 APB レジスタマップ手引：[`docs/ja/register_map.md`](docs/ja/register_map.md)

---

## 📊 主要仕様と PPA 特性

- **CPU コア**：32-bit RISC-V RV32I (PicoRV32) @ 12.288 MHz
- **音声入力**：1.024 MHz PDM デジタルマイク $\to$ 16 kHz 16-bit PCM
- **第1段 VAD 遅延**：10.0 ms / フレーム（待機電力 < 20 μW）
- **第2段 NPU 推論時間**：28,688 サイクル（**2.33 ms** @ 12.288 MHz）
- **オンチップメモリ**：16 KB SRAM（8KB ITCM + 8KB DTCM、外部 DRAM ゼロ）
- **推定バッテリー寿命**：標準的なウェアラブル使用環境で **10 日以上**（200 mAh 電池基準）
