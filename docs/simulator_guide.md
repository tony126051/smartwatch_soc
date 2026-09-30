# Smartwatch SoC 模擬器使用與架構手冊 (Simulator Guide)

[繁體中文](simulator_guide.md) | [English](en/simulator_guide.md) | [日本語](ja/simulator_guide.md)

本模擬器為專為 **Edge AI 智慧手錶 SoC 晶片設計** 所開發之全系統（Full-System）、週期精確（Cycle-Accurate）暨位元精確（Bit-True）模擬與硬體除錯環境。

---

## 1. 模擬器系統架構

```
                                  [ Smartwatch SoC 模擬器架構 ]
                                                 │
      ┌──────────────────────────────────────────┴──────────────────────────────────────────┐
      ▼                                          ▼                                          ▼
[ 音訊前端 (AFE) ]                       [ 處理器核心 (CPU) ]                     [ 晶片內匯流排 (Bus) ]
- 1.024MHz PDM 接收器                    - 32-bit RISC-V (PicoRV32 RV32I)         - 8KB Boot ROM (0x0000_0000)
- 3階 CIC 降頻濾波器 (R=64)              - 支援自訂指令 (waitirq, retirq, maskirq)- 8KB Data SRAM (0x1000_0000)
- 256-word 音訊環形 FIFO                 - 雙級中斷向量控制 (VAD IRQ / NPU IRQ)   - APB 加速器映射 (0x4000_0000)
      │                                          │                                - 系統除錯 LED (0x8000_0000)
      ▼                                          ▼                                          ▲
[ 第一級：硬體 VAD ]                     [ 第二級：KWS NPU 加速器 ]                         │
- 160點短時絕對值能量累加器              - 16x16 INT8 特徵 RAM (0x400)                      │
- 動態門檻比較器與 Hangover 防抖         - 256B 權重 RAM (0x500)                            │
- 上升沿硬體喚醒中斷 (irq_vad_wakeup)    - DS-CNN 深度可分離卷積硬體引擎 (28,688 cycles)   │
                                         - 喚醒完成中斷 (irq_npu_done) ─────────────────────┘
```

---

## 2. 模擬器模組結構 (`sim/simulator/`)

| 模組檔案 | 類別名稱 | 說明 |
|---|---|---|
| [`types.py`](file:///home/tony/repo/projects/smart_watch/sim/simulator/types.py) | 定義常數與型別 | 定義位址映射、暫存器偏移量、時脈頻率（12.288MHz）、LED 狀態常數與 32-bit 符號運算輔助工具 |
| [`cpu.py`](file:///home/tony/repo/projects/smart_watch/sim/simulator/cpu.py) | `RiscvCpu` | 完整 RV32I 37 條指令模擬，實作 PicoRV32 `waitirq`, `retirq`, `maskirq`，精準週期計算與暫存器堆除錯追蹤 |
| [`bus.py`](file:///home/tony/repo/projects/smart_watch/sim/simulator/bus.py) | `SoCBus` | 系統互連與記憶體解碼器，處理 ITCM、DTCM、APB 與除錯暫存器的讀寫路由與 Byte/Word 遮罩 |
| [`afe.py`](file:///home/tony/repo/projects/smart_watch/sim/simulator/afe.py) | `AudioFrontEnd` | PDM 輸入串流接收、3 階 CIC 濾波器（降採樣比 $R=64$）及 256-sample 音訊 FIFO |
| [`vad.py`](file:///home/tony/repo/projects/smart_watch/sim/simulator/vad.py) | `HardwareVad` | 160 採樣點短時能量累加器、動態門檻比較、Hangover 計數器與上升沿喚醒中斷產生 |
| [`npu.py`](file:///home/tony/repo/projects/smart_watch/sim/simulator/npu.py) | `KwsNpu` | DS-CNN（Conv1, DW, PW, GAP, FC）神經網路運算狀態機，INT8 定點 MAC，精確模擬 28,688 週期推論 |
| [`power.py`](file:///home/tony/repo/projects/smart_watch/sim/simulator/power.py) | `PowerProfiler` | 動態功耗分析器：待機休眠（<20μW）、CPU 運行（1.25mW）、NPU 運算（3.82mW）及電池續航力估計 |
| [`vcd.py`](file:///home/tony/repo/projects/smart_watch/sim/simulator/vcd.py) | `VcdWriter` | 產生標準 IEEE 1364 VCD 波形檔，可使用 GTKWave 或 PulseView 開啟檢視 |
| [`soc.py`](file:///home/tony/repo/projects/smart_watch/sim/simulator/soc.py) | `SmartwatchSoC` | 頂層系統單晶片模擬器，協調整合 CPU、周邊 IP、中斷、音訊輸入與時鐘步進 |
| [`cli.py`](file:///home/tony/repo/projects/smart_watch/sim/simulator/cli.py) | `InteractiveSimulatorCLI` | 互動式命令列除錯介面（支援單步執行、中斷點、暫存器檢視、記憶體 Dump、多國語言切換） |
| [`i18n.py`](file:///home/tony/repo/projects/smart_watch/sim/simulator/i18n.py) | 多國語言核心模組 | 支援繁體中文 (`zh-TW`)、英文 (`en`)、簡體中文 (`zh-CN`) 與日文 (`ja`) 之命令列、測試回報與 UI 翻譯字典 |
| [`dashboard.py`](file:///home/tony/repo/projects/smart_watch/sim/simulator/dashboard.py) | `generate_dashboard_html` | 產生獨立式互動 HTML5 視覺化監控儀表板（內建多國語言切換） |

---

## 3. 執行指令與操作模式

### 3.1 完整回歸測試模式 (`--mode regression`)
驗證 5 大核心功能（CPU 指令集、AFE CIC 濾波、VAD 能量中斷、NPU 位元真實推論、全 SoC 韌體喚醒）：
```bash
python3 sim/run_simulator.py --mode regression
```

### 3.2 端到端音訊喚醒情境模擬 (`--mode scenario`)
載入真實人聲串流，模擬「開機 -> 待機微瓦休眠 -> VAD 語音中斷 -> CPU 喚醒 -> 特徵載入 -> NPU 推論 -> 命中關鍵詞 -> 點亮螢幕」完整流程，並輸出波形檔與儀表板：
```bash
python3 sim/run_simulator.py --mode scenario --vcd sim/waves_soc.vcd --dashboard sim/simulator_dashboard.html
```

### 3.4 視覺化互動圖形介面 (Interactive Web GUI)
除了終端機 CLI 外，本模擬器亦配備完整的 **HTML5 視覺化圖形介面**：
- **檔案路徑**：[`sim/smartwatch_simulator_ui.html`](file:///home/tony/repo/projects/smart_watch/sim/smartwatch_simulator_ui.html)
- **直接開啟**：可在任何瀏覽器直接開啟該 HTML 檔案，或執行本機 HTTP 伺服器：
  ```bash
  python3 -m http.server 8080 --directory sim
  # 接著在瀏覽器存取 http://localhost:8080/smartwatch_simulator_ui.html
  ```

**UI 介面特色功能：**
1. **多國語言即時切換 (i18n)**：介面頂端提供語言下拉選單，支援 **繁體中文 (Traditional Chinese)**、**English (英文)**、**简体中文 (Simplified Chinese)** 與 **日本語 (Japanese)** 即時切換，並自動保存使用者偏好。
2. **互動控制台**：提供 `Run`（連續運行）、`Step`（單步執行）、`快進 50 步` 與 `Reset` 控制按鈕。
3. **音訊串流即時注入**：可自由切換注入「🗣️ 人類語音 (Speech)」、「🤫 無聲環境 (Silence)」或「📻 雜音/非關鍵詞 (Tone)」。
4. **智慧手錶動態錶盤**：即時反應休眠模式（黑屏待機 <20μW）、語音偵測中（"Listening..."）與關鍵詞命中（螢幕全亮顯示時間與電量）。
5. **板載 8-bit LED 指示燈**：動態高亮發光顯示 `0x01`（開機）、`0x02`（就緒）、`0x04`（待機休眠）、`0x08`（語音中斷）、`0xAA`（關鍵詞命中 🎯）、`0x55`（非目標詞）。
6. **子系統儀表板**：
   - **VAD 短時能量動態計量條**：顯示當前能量與 200,000 門檻紅線。
   - **NPU DS-CNN 管線進度**：高亮顯示當前 FSM 狀態（`CONV1` $\to$ `DW` $\to$ `PW` $\to$ `GAP` $\to$ `FC` $\to$ `DONE`）與雙類別得分。
   - **RISC-V CPU 核心**：即時顯示 PC、指令數、中斷狀態與 `sp`, `s0`, `s1`, `t0` 等核心暫存器數值。
   - **動態功耗與續航儀表**：計算休眠佔空比、即時平均功耗（μW）與 200 mAh 電池續航預估天數。

**支援除錯命令：**
- `step [N]`：單步執行 N 條指令（預設 1 條），印出反彙編與暫存器寫入變化。
- `run [N]`：執行直到中斷點、休眠（WFI）或達到上限週期數。
- `break <addr>`：設定程式計數器中斷點（例如 `break 0x10`, `break 0x48`）。
- `regs`：傾印所有 32 顆 RISC-V 通用暫存器（標註 ABI 名稱）。
- `mem <addr> [len]`：檢視記憶體內容（十六進位與 ASCII）。
- `status`：檢視 SoC 總體狀態（LED、AFE、VAD、NPU 得分、功耗）。
- `feed [speech|tone|silence]`：向音訊前端注入人聲、正弦波音訊或無聲環境。
- `power`：即時評估功耗佔空比與電池預估天數。
- `lang [code]`：切換終端機語言介面（支援 `zh-TW`, `en`, `zh-CN`, `ja`）。
- `reset`：重設 SoC 至初始上電狀態。
- `quit`：結束模擬。

---

## 4. 關鍵效能與資源指標

- **CPU 核心**：32-bit RISC-V RV32I (PicoRV32)
- **主時脈頻率**：12.288 MHz
- **音訊規格**：1.024 MHz PDM 數位麥克風輸入 $\to$ 16 kHz 16-bit PCM
- **第一級 VAD 延遲**：10.0 ms（160 個採樣點，待機功耗 $< 20\text{ }\mu\text{W}$）
- **第二級 NPU 耗時**：28,688 週期（在 12.288 MHz 下僅 **2.33 ms**，遠優於 15 ms 目標）
- **晶片內記憶體**：16 KB SRAM（8KB ITCM + 8KB DTCM），零外部 DRAM 依賴
- **標準手錶續航預估 (200 mAh 電池)**：典型語音使用場景下可達 **10 天以上**
