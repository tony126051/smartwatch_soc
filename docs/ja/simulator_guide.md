# Smartwatch SoC シミュレータ操作・アーキテクチャ詳細手引

[繁體中文](../simulator_guide.md) | [English](../en/simulator_guide.md) | [日本語](simulator_guide.md)

本シミュレータは、**Edge AI スマートウォッチ SoC 設計** のために開発されたフルシステム（Full-System）、サイクル正確（Cycle-Accurate）かつビット完全（Bit-True）なシミュレーション・ハードウェアデバッグ環境です。

---

## 1. シミュレータシステムアーキテクチャ

```
                                [ Smartwatch SoC シミュレータアーキテクチャ ]
                                                     │
          ┌──────────────────────────────────────────┴──────────────────────────────────────────┐
          ▼                                          ▼                                          ▼
    [ 音声フロントエンド (AFE) ]              [ CPU コア ]                              [ チップ内バス ]
    - 1.024MHz PDM 受信器                     - 32-bit RISC-V (PicoRV32 RV32I)          - 8KB Boot ROM (0x0000_0000)
    - 3次 CIC フィルタ (R=64)                 - 独自命令 (waitirq, retirq, maskirq)     - 8KB Data SRAM (0x1000_0000)
    - 256ワード音声リング FIFO                - 2段階割込み線 (VAD IRQ / NPU IRQ)       - APB サブシステム (0x4000_0000)
          │                                          │                                  - デバッグ LED (0x8000_0000)
          ▼                                          ▼                                          ▲
    [ 第1段：ハードウェア VAD ]               [ 第2段：KWS NPU アクセラレータ ]                  │
    - 160点短時間エネルギー累積               - 16x16 INT8 特徴量 RAM (0x400)                   │
    - 動的閾値比較 & Hangover デバウンス      - 256B 重み RAM (0x500)                           │
    - 立上がり起動割込み (irq_vad_wakeup)     - DS-CNN エンジン (28,688 cycles)                 │
                                              - 完了割込み (irq_npu_done) ──────────────────────┘
```

---

## 2. シミュレータモジュール構成 (`sim/simulator/`)

| モジュールファイル | クラス・コンポーネント | 説明 |
|---|---|---|
| [`types.py`](../../sim/simulator/types.py) | 定数・型定義 | メモリアドレスマップ、レジスタオフセット、12.288MHz クロック定数、LED 定数、32-bit 演算補助関数 |
| [`cpu.py`](../../sim/simulator/cpu.py) | `RiscvCpu` | PicoRV32 の `waitirq`, `retirq`, `maskirq` を含む完全な RV32I 37 命令シミュレータ、サイクル計測・レジスタ追跡 |
| [`bus.py`](../../sim/simulator/bus.py) | `SoCBus` | システムインターコネクト・アドレスデコーダ（ITCM、DTCM、APB、デバッグレジスタのルーティング） |
| [`afe.py`](../../sim/simulator/afe.py) | `AudioFrontEnd` | PDM 受信、3次 CIC フィルタ（$R=64$）、256 サンプル音声 FIFO |
| [`vad.py`](../../sim/simulator/vad.py) | `HardwareVad` | 160 サンプル短時間エネルギー累積、動的閾値比較、Hangover カウンタ、起動割込み生成 |
| [`npu.py`](../../sim/simulator/npu.py) | `KwsNpu` | DS-CNN（Conv1, DW, PW, GAP, FC）状態遷移、INT8 固定小数点 MAC、28,688 サイクルの精密シミュレーション |
| [`power.py`](../../sim/simulator/power.py) | `PowerProfiler` | 動的消費電力プロファイラ：待機スリープ（<20μW）、CPU 動作（1.25mW）、NPU 推論（3.82mW）、電池寿命予測 |
| [`vcd.py`](../../sim/simulator/vcd.py) | `VcdWriter` | GTKWave や PulseView で開く標準 IEEE 1364 VCD 波形ファイル出力 |
| [`soc.py`](../../sim/simulator/soc.py) | `SmartwatchSoC` | CPU、周辺 IP、割込み、音声入力、クロック歩進を統合するトップレベル SoC シミュレータ |
| [`cli.py`](../../sim/simulator/cli.py) | `InteractiveSimulatorCLI` | ブレークポイント、ステップ実行、レジスタ表示、メモリダンプ、言語切替に対応した対話型 CLI デバッガ |
| [`i18n.py`](../../sim/simulator/i18n.py) | 多言語化コア | 繁体字 (`zh-TW`)、英語 (`en`)、簡体字 (`zh-CN`)、日本語 (`ja`) の翻訳辞書と実行時言語管理 |
| [`dashboard.py`](../../sim/simulator/dashboard.py) | `generate_dashboard_html` | 多言語切替対応の単一自己完結型 HTML5 視覚化ダッシュボード生成 |

---

## 3. シミュレータ実行モード

### 3.1 自動回帰テストモード (`--mode regression`)
全 5 大コアサブシステム（CPU 命令セット、AFE CIC フィルタ、VAD エネルギー割込み、NPU ビット完全推論、SoC ファームウェア起動・ウェイクアップ）を検証：
```bash
python3 sim/run_simulator.py --mode regression --lang ja
```

### 3.2 エンドツーエンド音声起動シナリオシミュレーション (`--mode scenario`)
実際の音声ストリームを入力し、「起動 -> スタンバイ待機 -> VAD 音声検出 -> CPU 起動 -> 特徴量転送 -> NPU 推論 -> キーワード検出 -> 画面点灯」の一連の流れをシミュレートし、波形ファイルとダッシュボードを出力：
```bash
python3 sim/run_simulator.py --mode scenario --vcd sim/waves_soc.vcd --dashboard sim/simulator_dashboard.html --lang ja
```

### 3.3 対話型ターミナルデバッガ (`--mode interactive`)
GDB スタイルの対話型デバッグ環境を提供：
```bash
python3 sim/run_simulator.py --mode interactive --lang ja
```
主なコマンド：
- `step [N]`：N 個の命令を実行し、逆アセンブルとレジスタ書込みを表示。
- `run [N]`：次のブレークポイント、トラップ、またはスリープまで実行。
- `break <addr>`：指定アドレスにブレークポイントを設定。
- `delete [addr]`：ブレークポイントを解除。
- `regs`：32 本の RISC-V レジスタをダンプ。
- `mem <addr> [len]`：メモリ内容を 16 進および ASCII で表示。
- `status`：SoC 状態（AFE、VAD、NPU、LED、CPU）を表示。
- `feed [speech|tone|silence]`：マイク入力に音声を注入。
- `power`：動的消費電力とバッテリー寿命予測を表示。
- `lang [code]`：表示言語を切り替え（`ja`, `en`, `zh-TW`, `zh-CN`）。
- `reset`：SoC をリセット。
- `quit`：終了。

### 3.4 視覚的 Web GUI 画面 (`sim/smartwatch_simulator_ui.html`)
内蔵サーバーを起動：
```bash
python3 sim/web_server.py 8080
```
ブラウザで `http://localhost:8080/` にアクセスします。主な機能：
1. **多言語切替セレクタ**：日本語、英語、繁体字、簡体字をリアルタイム切り替え。
2. **コントロールツールバー**：`Run`、`Step`、`50ステップ早送り`、`Reset`。
3. **音声刺激注入**：音声、無音、ノイズの即時注入。
4. **スマートウォッチ画面モックアップ**：待機、音声認識、キーワード検出、画面点灯を視覚化。
5. **LED インジケータ**：8-bit オンボード LED（`0x01` 起動、`0x02` 準備完了、`0x04` 待機、`0x08` 音声検出、`0xAA` 一致、`0x55` 非キーワード）。
6. **サブシステムモニタ**：VAD 短時間エネルギーバー、NPU パイプライン状態、CPU レジスタ、バッテリー残量推定。

---

## 4. 主要性能およびリソース指標

- **CPU コア**：32-bit RISC-V RV32I (PicoRV32) @ 12.288 MHz
- **音声入力**：1.024 MHz PDM マイク $\to$ 16 kHz 16-bit PCM
- **第1段 VAD 遅延**：10.0 ms / フレーム（待機電力 < 20 μW）
- **第2段 NPU 推論時間**：28,688 サイクル（12.288 MHz 動作時わずか **2.33 ms**）
- **チップ内メモリ**：16 KB SRAM（8KB ITCM + 8KB DTCM、外部 DRAM ゼロ）
- **バッテリー駆動時間予測**：一般的なスマートウォッチ使用で **10 日以上**（200 mAh 電池基準）
