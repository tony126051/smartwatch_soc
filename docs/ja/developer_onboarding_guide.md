# 🔰 開発者オンボーディングガイド (Developer Onboarding Guide)

[繁體中文](../developer_onboarding_guide.md) | [English](../en/developer_onboarding_guide.md) | [日本語](developer_onboarding_guide.md)

**Edge AI スマートウォッチ SoC 設計プロジェクト** へようこそ！本ドキュメントは、新規参加エンジニア（アルゴリズム、デジタル IC 設計、ファームウェア技術者）向けに書かれており、**10分以内** にシステムアーキテクチャを把握し、シミュレータを起動、ファームウェア修正とハードウェア検証を行うためのガイドです。

---

## 1. コア概念速習：2段階音声起動アーキテクチャ (Two-Stage Wakeup)

スマートウォッチのバッテリー容量が極めて小さい（約 200 mAh）一方で、**24時間常時稼働（Always-on）** で音声を待受ける必要がある課題を解決するため、本チップは厳密な「2段階フィルタリング」構成を採用しています：

```
[環境音声] ──> [1.024MHz PDM マイク] ──> [3次 CIC フィルタ (R=64)] ──> 16kHz 16-bit PCM
                                                                           │
┌──────────────────────────────────────────────────────────────────────────┘
▼
【第1段：ハードウェア VAD (Always-on)】
  - アルゴリズム：160 点（10ms フレーム）短時間絶対値エネルギー（STE）累積
  - 待機電力：< 20 μW
  - 通常待機時：環境が無音の場合、CPU、NPU、画面は完全ディープスリープ（WFI）
  - 発火条件：短時間エネルギーが閾値（デフォルト 200,000）を超えると割込み `irq_vad_wakeup` を発火
        │
        ▼ (CPU 起動)
【プロセッサ協調：32-bit RISC-V CPU】
  - CPU が起床し、VAD 割込みフラグをクリア
  - 音声特徴量を NPU 特徴量 RAM（0x4000_0400）へ転送
  - NPU 演算を開始（NPU_CTRL = 1）
        │
        ▼
【第2段：KWS NPU アクセラレータ】
  - 軽量畳み込みニューラルネット：DS-CNN (Depthwise Separable CNN)、全層 INT8 固定小数点
  - 固定レイテンシ：28,688 クロックサイクル（12.288 MHz でわずか 2.33 ms、約 3.82 mW）
  - 推論完了割込み `irq_npu_done` を発火
        │
        ▼
【判定出力】
  - スコア比較：Class 1 (ターゲットキーワード) > Class 0 (背景ノイズ)
  - 一致時：LED に `0xAA` を書込み、スマートウォッチ画面を点灯し OS を起動
  - 不一致時：LED に `0x55` を書込み、CPU は直ちに `waitirq` ディープスリープへ復帰
```

---

## 2. 開発環境の確認

本プロジェクトは **巨大な外部ツールチェーン依存ゼロ** で設計されています：
- **対応 OS**：Linux / macOS / Windows (WSL)
- **必須要件**：`Python 3.8+`（標準ライブラリのみで動作し、追加パッケージのインストール不要）
- **任意ツール**：GTKWave / PulseView（`.vcd` 波形ファイルを開く場合）

環境確認コマンド：
```bash
python3 --version
```

---

## 3. 日常の開発ワークフロー (Day-to-Day Tasks)

### タスク A：視覚的 Web GUI シミュレータの起動
```bash
python3 sim/web_server.py 8080
```
- ブラウザで `http://localhost:8080` を開く。
- 上部言語メニューから日本語、英語、繁体字、簡体字をリアルタイム切り替え。
- `単歩実行`、`音声注入`、`ノイズ注入` をクリックし、画面の点灯や LED 変化、レジスタの推移を直感的に確認。

### タスク B：RISC-V ファームウェアの修正と再ビルド
ファームウェアのソースコードは [`sw/app/main.s`](../../sw/app/main.s) にあります。アセンブリを変更した後、同梱のアセンブラを実行します：
```bash
python3 sw/build_firmware.py sw/app/main.s sw/firmware.hex
```
実行後、シミュレータと RTL は更新された [`sw/firmware.hex`](../../sw/firmware.hex) を即座に読み込みます。

### タスク C：自動回帰テストの実行
コードのコミット前には、必ず自動回帰テストを実行してください：
```bash
python3 sim/run_simulator.py --mode regression --lang ja
```
5 つのテスト項目がすべて `[合格]` となることを確認します。

### タスク D：GDB スタイル対話型ターミナルデバッガ
レジスタ値の追跡や割込みベクタにブレークポイントを設定する場合：
```bash
python3 sim/run_simulator.py --mode interactive --lang ja
```
主なコマンド：
```text
[SoC @ 0x00000000 | LED 0x00] > step 5       # 5命令ステップ実行
[SoC @ 0x00000020 | LED 0x01] > regs         # 32本のレジスタを表示
[SoC @ 0x00000020 | LED 0x01] > break 0x10   # 割込みエントリにブレークポイント設定
[SoC @ 0x00000020 | LED 0x01] > feed speech  # 音声ストリームを注入
[SoC @ 0x00000020 | LED 0x01] > run          # 全速実行 (ブレークポイントかスリープで停止)
[SoC @ 0x00000010 | LED 0x08] > mem 0x10000000 16 # メモリ内容を確認
[SoC @ 0x00000010 | LED 0x08] > power        # 消費電力とバッテリー予測を表示
```

### タスク E：波形ファイルの出力とハードウェア信号確認
```bash
python3 sim/run_simulator.py --mode scenario --vcd sim/waves_soc.vcd --dashboard sim/simulator_dashboard.html --lang ja
```
GTKWave で `sim/waves_soc.vcd` を確認、またはブラウザで `sim/simulator_dashboard.html` を開きます。

---

## 4. サブシステムコード・構成ナビゲーション

- **アルゴリズムゴールデンモデル** ([`model/`](../../model/)):
  - `golden_vad.py`: 短時間エネルギー VAD のビット完全 Python リファレンス。
  - `golden_npu.py`: INT8 重みを用いた DS-CNN 固定小数点推論モデル。
  - `golden_vectors/`: ゴールデンテストベクトルと刺激入力データ。
- **合成可能 Verilog RTL** ([`rtl/`](../../rtl/)):
  - `afe/`: PDM 受信器、3次 CIC フィルタ、音声 FIFO。
  - `vad/`: 第1段 常時稼働ハードウェア VAD コア。
  - `npu/`: 第2段 KWS NPU MAC アレイおよび FSM。
  - `cpu/`: 32-bit RISC-V PicoRV32 コア。
  - `bus/`: APB スレーブアダプタ。
  - `top/`: Smartwatch SoC トップ回路。
- **シミュレータ環境** ([`sim/`](../../sim/)):
  - `simulator/`: Python サイクル正確ハードウェアシミュレータライブラリ。
  - `web_server.py`: Web GUI 向けリアルタイム HTTP サーバー。
  - `smartwatch_simulator_ui.html`: 多言語対応 HTML5 インタラクティブ画面。
- **組込みファームウェア** ([`sw/`](../../sw/)):
  - `app/main.s`: ブートローダ、周辺回路設定、ISR、スリープ制御。
  - `build_firmware.py`: 純 Python 製軽量 RISC-V アセンブラ。
