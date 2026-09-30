# 🔰 新進開發人員快速上手與導覽指南 (Developer Onboarding Guide)

[繁體中文](developer_onboarding_guide.md) | [English](en/developer_onboarding_guide.md) | [日本語](ja/developer_onboarding_guide.md)

歡迎加入 **Edge AI 智慧手錶 SoC 晶片設計專案**！本文件專為新進工程師（演算法、數位 IC 設計、韌體工程師）所編寫，目標讓您在 **10 分鐘內** 理解全系統架構、啟動模擬器、修改韌體並進行硬體驗證。

---

## 1. 核心觀念速成：兩級語音喚醒架構 (Two-Stage Wakeup)

為了解決智慧手錶電池容量極小（約 200 mAh）但必須 **24 小時 Always-on** 聆聽語音的挑戰，本晶片採用嚴格的「兩級過濾」架構：

```
[環境聲音] ──> [1.024MHz PDM 麥克風] ──> [3階 CIC 降頻 (R=64)] ──> 16kHz 16-bit PCM
                                                                           │
┌──────────────────────────────────────────────────────────────────────────┘
▼
【第一級：硬體 VAD (Always-on)】
  - 演算法：160 點（10ms 訊框）短時絕對值能量（Short-Time Energy, STE）累加
  - 待機功耗：< 20 μW
  - 平時狀態：環境無聲時，CPU、NPU 與螢幕全部深度休眠（WFI）
  - 觸發條件：當短時能量超過門檻（預設 200,000）時，發出硬體中斷 `irq_vad_wakeup`
        │
        ▼ (喚醒 CPU)
【處理器協調：32-bit RISC-V CPU】
  - CPU 醒來，清除 VAD 中斷旗標
  - 將音訊特徵搬移至 NPU 特徵 RAM（0x4000_0400）
  - 啟動 NPU 運算（NPU_CTRL = 1）
        │
        ▼
【第二級：KWS NPU 加速器】
  - 輕量化卷積神經網路：DS-CNN (Depthwise Separable CNN)，全程 INT8 定點運算
  - 硬體推論耗時：固定 28,688 時脈週期（在 12.288 MHz 下僅需 2.33 ms，功耗約 3.82 mW）
  - 產生推論完成中斷 `irq_npu_done`
        │
        ▼
【決策輸出】
  - 判定得分：Class 1 (目標喚醒詞) > Class 0 (背景雜音)
  - 若命中喚醒詞：LED 寫入 `0xAA`，點亮手錶主螢幕，啟動完整作業系統
  - 若為非關鍵詞：LED 寫入 `0x55`，CPU 立即返回 `waitirq` 深度待機休眠（防誤觸省電）
```

---

## 2. 開發環境確認

本專案經過精心設計，具備 **零外部龐大工具鏈依賴** 的優勢：
- **作業系統**：Linux / macOS / Windows (WSL)
- **唯一依賴**：`Python 3.8+`（系統自帶標準庫即可，無需額外安裝龐大套件）
- **選用工具**：GTKWave（若需開啟 `.vcd` 波形檔）

確認環境指令：
```bash
python3 --version
```

---

## 3. 開發者常用工作流程 (Day-to-Day Tasks)

### 任務 A：啟動可視化 Web GUI 模擬器
```bash
python3 sim/web_server.py 8080
```
- 開啟瀏覽器訪問：`http://localhost:8080`
- 可直觀點擊 `單步執行`、`注入語音`、`注入雜音`，觀察手錶螢幕亮起、LED 燈號變化與暫存器跳動。

### 任務 B：修改並重新編譯 RISC-V 韌體
韌體原始碼位於 [`sw/app/main.s`](file:///home/tony/repo/projects/smart_watch/sw/app/main.s)。當您修改了組合語言程式碼後，執行專屬組譯器：
```bash
# 組譯 main.s 產生機器碼 firmware.hex
python3 sw/build_firmware.py sw/app/main.s sw/firmware.hex
```
執行後，模擬器與 RTL 即可立即讀取新的 [`sw/firmware.hex`](file:///home/tony/repo/projects/smart_watch/sw/firmware.hex) 執行。

### 任務 C：執行自動化回歸測試
在提交任何代碼修改前，請務必執行全自動回歸測試：
```bash
python3 sim/run_simulator.py --mode regression
```
確認 5 項測試皆顯示 `[PASS]`。

### 任務 D：使用 GDB 式終端互動除錯器
當您想追蹤 CPU 內部暫存器數值或在特定中斷下斷點：
```bash
python3 sim/run_simulator.py --mode interactive
```
常用除錯指令：
```text
[SoC @ 0x00000000 | LED 0x00] > step 5       # 單步執行 5 條指令
[SoC @ 0x00000020 | LED 0x01] > regs         # 傾印 32 顆 RISC-V 暫存器
[SoC @ 0x00000020 | LED 0x01] > break 0x10   # 在中斷向量入口下中斷點
[SoC @ 0x00000020 | LED 0x01] > feed speech  # 注入語音串流
[SoC @ 0x00000020 | LED 0x01] > run          # 全速運行，會停在斷點或休眠
[SoC @ 0x00000010 | LED 0x08] > mem 0x10000000 16 # 查看記憶體內容
[SoC @ 0x00000010 | LED 0x08] > power        # 查看即時功耗與預估電池壽命
```

### 任務 E：匯出波形檢視硬體信號
```bash
python3 sim/run_simulator.py --mode scenario --vcd sim/waves_soc.vcd
```
產生之 [`sim/waves_soc.vcd`](file:///home/tony/repo/projects/smart_watch/sim/waves_soc.vcd) 可直接使用 GTKWave 開啟：
```bash
gtkwave sim/waves_soc.vcd &
```

---

## 4. 關鍵暫存器與記憶體空間速查 (Cheat Sheet)

基底位址與記憶體佈局：
- `0x0000_0000 - 0x0000_1FFF`：**8 KB Boot ROM** (ITCM，存放開機程式)
- `0x1000_0000 - 0x1000_1FFF`：**8 KB Data SRAM** (DTCM，堆疊與變數，`sp = 0x1000_2000`)
- `0x4000_0000 - 0x4000_0FFF`：**KWS 加速器 APB 暫存器空間**
- `0x8000_0000`：**系統除錯 LED 暫存器**

| 暫存器位址 | 暫存器名稱 | 讀/寫 | 關鍵欄位說明 |
|---|---|---|---|
| `0x4000_0000` | **AFE_CTRL** | R/W | bit[0]: 啟用 AFE 與 CIC 濾波器 |
| `0x4000_0004` | **AFE_STATUS** | RO | bit[0]: FIFO 空, bit[1]: FIFO 滿, bit[16:8]: 樣本數 |
| `0x4000_0008` | **AFE_DATA** | RO | 讀取 16-bit PCM 樣本（讀取後自動 Pop FIFO） |
| `0x4000_0010` | **VAD_CTRL** | R/W | bit[0]: 啟用 VAD, bit[1]: 寫 1 清除喚醒中斷旗標 |
| `0x4000_0014` | **VAD_THRESHOLD** | R/W | 短時能量門檻（預設 `200,000`） |
| `0x4000_0018` | **VAD_HANGOVER** | R/W | Hangover 訊框防抖計數（預設 3 訊框） |
| `0x4000_001C` | **VAD_ENERGY** | RO | bit[23:0]: 當前累積能量, bit[24]: 語音活動旗標 |
| `0x4000_0020` | **NPU_CTRL** | R/W | bit[0]: 啟動推論脈衝, bit[1]: 寫 1 清除完成中斷 |
| `0x4000_0024` | **NPU_STATUS** | RO | bit[0]: 忙碌中, bit[1]: 推論完成, bit[2]: 喚醒詞命中 |
| `0x4000_0028` | **NPU_SCORE0** | RO | Class 0 (背景非關鍵詞) 32-bit INT8 分類得分 |
| `0x4000_002C` | **NPU_SCORE1** | RO | Class 1 (目標喚醒詞) 32-bit INT8 分類得分 |
| `0x4000_0400` | **NPU_FEAT_RAM** | R/W | 256 Bytes 輸入特徵 RAM ($16\times16$ INT8) |
| `0x4000_0500` | **NPU_WGT_RAM** | R/W | 256 Bytes 神經網路權重 RAM |
| `0x8000_0000` | **DEBUG_LEDS** | R/W | [7:0]: 除錯燈號 (`0x01`開機, `0x04`休眠, `0xAA`命中, `0x55`雜音) |

---

## 5. 常見問題與除錯秘訣 (FAQ)

### Q1: 啟動 `web_server.py` 時提示 Address already in use？
若預設埠號 8080 被佔用，可指定其他任意埠號：
```bash
python3 sim/web_server.py 8888
# 瀏覽器打開 http://localhost:8888
```

### Q2: 為什麼手錶有時不會全亮（維持黑屏休眠）？
這正是兩級過濾的核心機制！若點擊「📻 雜音/非關鍵詞」或背景噪音，雖然能量衝破 VAD 門檻，但 NPU 矩陣推論後發現非目標關鍵詞，會自動退回休眠模式（LED `0x55`），防止誤喚醒造成耗電。只有注入「🗣️ 語音串流 (Speech)」時才會判定命中喚醒詞（LED `0xAA`）並全亮螢幕。

### Q3: 如何將我訓練好的自訂神經網路權重換上？
1. 在 [`model/golden_npu.py`](file:///home/tony/repo/projects/smart_watch/model/golden_npu.py) 中調整模型權重陣列。
2. 執行 `python3 model/golden_npu.py`，會自動導出十六進位權重檔至 `model/golden_vectors/weights_int8.hex`。
3. 模擬器與 RTL 重新載入該檔案即可進行測試。

---

祝您開發順利！若有任何硬體規格疑義，可隨時參閱 [`docs/spec/README.md`](spec/README.md)（規格驅動開發與 AI Agent 規範體系）、[`docs/system_architecture.md`](file:///home/tony/repo/projects/smart_watch/docs/system_architecture.md) 與 [`docs/simulator_guide.md`](file:///home/tony/repo/projects/smart_watch/docs/simulator_guide.md)。
