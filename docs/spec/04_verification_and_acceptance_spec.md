# 04 - 驗證與驗收標準規範書 (Verification and Acceptance Specification, VAS)

[繁體中文](04_verification_and_acceptance_spec.md) | [English](en/04_verification_and_acceptance_spec.md)

規格文件編號：`SPEC-VAS-001`  
版本：`1.0.0`  
狀態：`Approved / SSOT`

---

## 1. 驗證金字塔與策略 (Verification Hierarchy)

本專案採用三層驗證架構，確保演算法、硬體電路與嵌入式韌體之間的絕對一致性：

```
       ▲
      / \     [Level 3] 全晶片系統層級回歸驗證 (Full SoC Regression)
     /   \    - Python 週期精確模擬器 + RISC-V 實體韌體執行 (sim/run_simulator.py)
    /─────\
   /       \  [Level 2] RTL 子模組硬體級模擬 (RTL Subsystem Testbenches)
  /         \ - Verilog Testbench 前仿真 (tb_afe.v, tb_vad.v, tb_npu.v, tb_soc_top.v)
 /───────────\
/             \ [Level 1] 演算法數學黃金模型單元驗證 (Python Golden Models)
─────────────── - 浮點轉定點、量化測試向量產生 (golden_vad.py, golden_npu.py)
```

---

## 2. 五大強制回歸測試項與驗收標準 (The 5 Mandatory Testcases)

每次代碼提交或功能修改，必須通過以下五項標準驗收測試（Exit Criteria）：

### 測試 1：RISC-V RV32I 核心與記憶體子系統 (CPU & Memory)
- **測試標的**：`PicoRV32` 核心、Boot ROM、Data RAM、`waitirq` 自訂指令。
- **驗收準則**：
  1. 通用暫存器寫入/讀取無衝突。
  2. 記憶體載入（LW）與儲存（SW）小端序對齊正確。
  3. `waitirq` 指令能正確凍結 PC，並於中斷信號觸發時喚醒跳轉。
- **預期結果**：`[PASS] RISC-V RV32I 算術與自訂指令 (waitirq) 100% 正確`

### 測試 2：音訊前端降頻與緩衝 (AFE CIC Decimator & FIFO)
- **測試標的**：`pdm_receiver.v`、`cic_decimator_q64.v`、`audio_fifo.v`。
- **驗收準則**：
  1. 輸入 1.024 MHz PDM 測試串流，成功降採樣產出 16 kHz PCM。
  2. 樣本輸出進入 FIFO，狀態計數 `FIFO_COUNT` 正確遞增。
  3. 讀取 `AFE_DATA` 後自動 Pop，樣點數值與數學計算一致。
- **預期結果**：`[PASS] CIC 濾波器降頻 PDM 串流 -> FIFO 樣本數: 10, 樣本值 = -194`

### 測試 3：第一級硬體 VAD 短時能量與中斷 (Hardware VAD Core)
- **測試標的**：`vad_core.v`、短時絕對值能量積分器、Hangover FSM。
- **驗收準則**：
  1. 連續 10 個音訊幀的能量計算值與 [`model/golden_vectors/vad_golden.txt`](../../model/golden_vectors/vad_golden.txt) **100% 位元精確相同（0 誤差）**。
  2. 上升沿喚醒中斷 `irq_vad_wakeup` 於第 2 幀精確拉高。
  3. 寫入 `VAD_CTRL[1] = 1` 成功清除中斷。
- **預期結果**：
  - `[PASS] 硬體 VAD 短時能量累加計算 100% 位元精確！`
  - `[PASS] 上升沿喚醒中斷 (irq_vad_wakeup) 於第 2 幀成功觸發！`

### 測試 4：第二級 KWS NPU 加速器推論 (KWS NPU Engine)
- **測試標的**：`npu_top.v`、`mac_array_4x4.v`、DS-CNN INT8 定點前向傳播。
- **驗收準則**：
  1. 推論總時脈週期嚴格等於 **28,688 週期**（@ 12.288MHz 等於 **2.33 ms**）。
  2. 輸出得分精確吻合：
     - **Class 0 (背景雜音)**：`58`
     - **Class 1 (目標喚醒詞)**：`-51`
  3. 預測分類類別：`Class 0`（置信度差距 109）。
- **預期結果**：
  - `[PASS] NPU DS-CNN 推論結果與 Python 黃金模型 100% 位元精確！`
  - `[PASS] 硬體執行延遲: 28688 週期 (2.33 ms @ 12.288MHz)`
  - `[PASS] 分類推論得分: Class 0 (背景雜音) = 58, Class 1 (喚醒詞) = -51`

### 測試 5：全系統軟硬體協同執行流程 (Full SoC Integration & Firmware)
- **測試標的**：`smartwatch_soc_top.v`、`sw/app/main.s` 實際韌體編譯機器碼執行。
- **驗收準則**：
  1. **階段 1 (Boot)**：CPU 啟動並初始化 AFE/VAD，進入待機休眠，LED 顯示 `0x04`。
  2. **階段 2 (Wakeup)**：注入語音串流，VAD 中斷觸發，CPU 喚醒執行 ISR，LED 切換為 `0x55`。
  3. **階段 3 (Infer & Decision)**：CPU 搬移特徵並啟動 NPU，推論完成，判定非喚醒詞，LED 保持 `0x55` 並返回休眠。
- **預期結果**：
  - `[PASS] 階段 1: CPU 開機 -> 配置 AFE/VAD -> 進入待機休眠 (LED = 0x04)`
  - `[PASS] 階段 2: 偵測到語音串流 -> 觸發 VAD 喚醒中斷 -> CPU 執行 ISR`
  - `[PASS] 階段 3: 載入語音特徵矩陣 -> 完成 NPU 硬體推論 -> LED = 0x55`

---

## 3. 自動化驗證指令集速查矩陣 (Execution Command Matrix)

| 驗證目的 | 終端執行指令 | 預期執行時間 | 退出碼 (Exit Code) | 輸出檢驗物 |
|---|---|---|---|---|
| **全晶片回歸測試** | `python3 sim/run_simulator.py --mode regression` | $< 2\text{ 秒}$ | `0` | 終端顯示 5/5 項測試全數通過 |
| **黃金模型產出** | `python3 sim/run_sim.py` | $< 3\text{ 秒}$ | `0` | 更新 `model/golden_vectors/*` |
| **韌體重新編譯** | `python3 sw/build_firmware.py sw/app/main.s sw/firmware.hex` | $< 1\text{ 秒}$ | `0` | 更新 `sw/firmware.hex` |
| **互動除錯** | `python3 sim/run_simulator.py --mode interactive` | 互動終端 | `0` | 即時 PC/暫存器檢查 |
| **波形與儀表板產出**| `python3 sim/run_simulator.py --mode scenario --vcd sim/waves_soc.vcd --dashboard sim/simulator_dashboard.html` | $< 3\text{ 秒}$ | `0` | 產出標準 IEEE 1364 VCD 與 HTML5 儀表板 |
| **Web 伺服器啟動** | `python3 sim/web_server.py 8080` | 常駐程序 | N/A | 瀏覽器訪問 `http://localhost:8080/` |

---

## 4. 故障診斷手冊 (Failure Troubleshooting Matrix)

若在執行 `run_simulator.py --mode regression` 時發生測試失敗，請依照下表定位：

| 失敗測試項目 | 常見故障原因 | 檢查優先級與檔案定位 | 修復建議 |
|---|---|---|---|
| **測試 1 失敗** | RV32I 組合語言語法錯誤，或 `waitirq` 機器碼不匹配 | 1. [`sw/app/main.s`](../../sw/app/main.s)<br>2. [`sw/build_firmware.py`](../../sw/build_firmware.py) | 檢查 `sw/firmware.hex` 是否已重新編譯；確認自訂指令機器碼為 `0x0000006b`。 |
| **測試 2 失敗** | CIC 累加器位元寬度溢位或 FIFO 讀寫指針同步失效 | 1. [`rtl/afe/cic_decimator_q64.v`](../../rtl/afe/cic_decimator_q64.v)<br>2. [`sim/simulator/afe.py`](../../sim/simulator/afe.py) | 檢查 22-bit 符號數飽和截斷算式 `clamp(cic_out >> 3, -32768, 32767)`。 |
| **測試 3 失敗** | VAD 能量累加視窗長度非 160，或 Hangover 狀態轉換錯誤 | 1. [`rtl/vad/vad_core.v`](../../rtl/vad/vad_core.v)<br>2. [`sim/simulator/vad.py`](../../sim/simulator/vad.py) | 檢查 `vad_golden.txt` 中的 Frame 2 能量值；確認 `irq_vad_wakeup` 是否為上升沿鎖存。 |
| **測試 4 失敗** | NPU INT8 卷積再量化移位量錯誤，或週期計算有停頓 | 1. [`rtl/npu/npu_top.v`](../../rtl/npu/npu_top.v)<br>2. [`sim/simulator/npu.py`](../../sim/simulator/npu.py) | 確認層間縮放為 `>> 7` 並經 ReLU；確認推論週期嚴格等於 28,688 週期。 |
| **測試 5 失敗** | 韌體中斷服務常式未清除旗標，或 LED 狀態碼定義偏差 | 1. [`sw/app/main.s`](../../sw/app/main.s)<br>2. [`sim/simulator/soc.py`](../../sim/simulator/soc.py) | 確認 ISR 中有執行 `VAD_CTRL[1] = 1`；確認 LED 寫入 `0x8000_0000` 數值符合規格。 |

---

## 5. 驗證需求追蹤清單 (Traceability Requirements)

| 需求 ID | 技術驗證標的 |
|---|---|
| `REQ-VERIF-001` | 回歸測試必須支援無第三方 EDA 工具依賴，純 Python 3.8+ 即可執行。 |
| `REQ-VERIF-002` | 全晶片回歸測試 5 項測試通過率必須為 100%（Zero Tolerance）。 |
| `REQ-VERIF-003` | 演算法模型與硬體模擬器數值比對必須為 0 誤差（Bit-True Exact Match）。 |
| `REQ-VERIF-004` | 必須支援匯出符合 IEEE 1364 標準之 `.vcd` 數位波形檔供 GTKWave 檢視。 |
| `REQ-VERIF-005` | 測試工具必須支援多國語言（`--lang zh-TW`, `en`, `zh-CN`, `ja`）。 |
