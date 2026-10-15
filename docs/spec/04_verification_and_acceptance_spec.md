# 04 - 驗證與驗收標準規範書 (Verification and Acceptance Specification, VAS)

[繁體中文](04_verification_and_acceptance_spec.md) | [English](en/04_verification_and_acceptance_spec.md)

規格文件編號：`SPEC-VAS-001`  
版本：`2.0.0`  
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
─────────────── - 浮點轉定點、量化測試向量產生 (golden_vad.py, golden_npu.py, golden_bist.py)
```

---

## 2. 七大強制回歸測試項與驗收標準 (The 7 Mandatory Testcases)

每次代碼提交或功能修改，必須通過以下七項標準驗收測試（Exit Criteria）：

### 測試 1：RISC-V RV32I 核心與記憶體子系統 (CPU & Memory)
- **測試標的**：`PicoRV32` 核心、Boot ROM、Data RAM、`waitirq` 自訂指令。
- **預期結果**：`[PASS] RISC-V RV32I 算術與自訂指令 (waitirq) 100% 正確`

### 測試 2：音訊前端降頻與緩衝 (AFE CIC Decimator & Pre-Roll FIFO)
- **測試標的**：`pdm_receiver.v`、`cic_decimator_q64.v`、512-word `audio_fifo.v`。
- **預期結果**：`[PASS] CIC 濾波器降頻 PDM 串流 -> FIFO 樣本數: 10, 樣本值 = -194`

### 測試 3：第一級硬體 VAD 短時能量與中斷 (Hardware VAD Core)
- **測試標的**：`vad_core.v`、短時絕對值能量積分器、Hangover FSM。
- **預期結果**：
  - `[PASS] 硬體 VAD 短時能量累加計算 100% 位元精確！`
  - `[PASS] 上升沿喚醒中斷 (irq_vad_wakeup) 於第 2 幀成功觸發！`

### 測試 4：第二級 KWS NPU 加速器推論 (KWS NPU Engine)
- **測試標的**：`npu_top.v`、`mac_array_4x4.v`、DS-CNN INT8 定點前向傳播。
- **預期結果**：
  - `[PASS] NPU DS-CNN 推論結果與 Python 黃金模型 100% 位元精確！`
  - `[PASS] 硬體執行延遲: 28688 週期 (2.33 ms @ 12.288MHz)`
  - `[PASS] 分類推論得分: Class 0 (背景雜音) = 58, Class 1 (喚醒詞) = -51`

### 測試 5：全系統軟硬體協同執行流程 (Full SoC Integration & Firmware)
- **測試標的**：`smartwatch_soc_top.v`、`sw/app/main.s` 實際韌體編譯機器碼執行。
- **預期結果**：
  - `[PASS] 階段 1: CPU 開機 -> 通過 Mini-POST -> 配置 AFE/VAD -> 進入待機休眠 (LED = 0x04)`
  - `[PASS] 階段 2: 偵測到語音串流 -> 觸發 VAD 喚醒中斷 -> CPU 執行 ISR`
  - `[PASS] 階段 3: 載入語音特徵矩陣 -> 完成 NPU 硬體推論 -> LED = 0x55`

### 測試 6：雙麥克風 DDR PDM 與微差波束成形驗收 (Dual-Mic Stereo PDM & Beamforming)
- **測試標的**：`DualEdgePdmDemuxer`、`DualCicDecimatorQ64`、`HardwareBeamformer`。
- **驗收準則**：
  1. **6A 雙邊緣解多工**：連續 131,072 個 DDR PDM 位元採樣，通道 0/1 位元錯誤率嚴格等於 0 (BER = 0.000%)。
  2. **6B 強風噪聲抑制**：在非相干風噪輸入下，波束成形器與風噪分流抑制比 $\ge 15.0\text{ dB}$。
  3. **6C 空間指向性**：嘴角軸向 ($0^\circ$) 插入損失 $\le 1.5\text{ dB}$，側向 ($90^\circ$) 噪聲衰減 $\ge 12.0\text{ dB}$。
- **預期結果**：
  - `[PASS] DDR 雙邊緣解多工器 131072 位元 0 位元錯誤 (BER = 0.000%)`
  - `[PASS] 風噪抑制比: 16.8 dB (目標 > 15.0 dB)`
  - `[PASS] 軸向保留衰減: 0.8 dB (< 1.5 dB), 側向 90° 抑制: 13.4 dB (> 12.0 dB)`

### 測試 7：5ms 硬體生產自動測試與故障注入 (5ms Hardware Production BIST)
- **測試標的**：`bist_engine.v`、31-bit LFSR、32-bit MISR、7-point 故障注入測試器。
- **驗收準則**：
  1. 執行 61,440 週期 ($5.00\text{ ms}$) 後，MISR 壓縮特徵碼精確匹配 `0x92B6CDA5`。
  2. 自動注入 7 處固定型故障（Stuck-At-0 / Stuck-At-1：CIC 積分器、VAD 累加器、NPU 權重解碼器），所有故障 100% 造成簽名碼突變，逃脫率嚴格為 0。
- **預期結果**：
  - `[PASS] 61440 週期 BIST 執行完畢 -> 實際特徵碼: 0x92B6CDA5, 黃金碼: 0x92B6CDA5 (100% 匹配)`
  - `[PASS] 7 點硬體故障注入測試 (CIC/VAD/NPU) -> 100.0% 檢出率 (0 逃脫)`

---

## 3. 自動化驗證指令集速查矩陣 (Execution Command Matrix)

| 驗證目的 | 終端執行指令 | 預期執行時間 | 退出碼 | 輸出檢驗物 |
|---|---|---|---|---|
| **全晶片回歸測試 (7項)** | `python3 sim/run_simulator.py --mode regression` | $< 3\text{ 秒}$ | `0` | 終端顯示 7/7 項測試全數通過 |
| **黃金模型產出** | `python3 sim/run_sim.py` | $< 3\text{ 秒}$ | `0` | 更新 `model/golden_vectors/*` |
| **韌體重新編譯** | `python3 sw/build_firmware.py sw/app/main.s sw/firmware.hex` | $< 1\text{ 秒}$ | `0` | 更新 `sw/firmware.hex` |
| **互動除錯** | `python3 sim/run_simulator.py --mode interactive` | 互動終端 | `0` | 即時 PC/暫存器檢查 |
| **波形與儀表板產出**| `python3 sim/run_simulator.py --mode scenario --vcd sim/waves_soc.vcd --dashboard sim/simulator_dashboard.html` | $< 3\text{ 秒}$ | `0` | 產出極座標圖與時域波形 |

---

## 4. 故障診斷手冊 (Failure Troubleshooting Matrix)

| 失敗測試項目 | 常見故障原因 | 檢查優先級與檔案定位 | 修復建議 |
|---|---|---|---|
| **測試 1~5 失敗** | 基礎指令、降頻、VAD 或推論回歸偏差 | 查閱各模組 RTL 與 `sim/simulator/` | 遵循零回歸門禁守則修復，確保基準 100% 通過。 |
| **測試 6A 失敗** | DDR 採樣極性或半週期鎖存時序偏差 | `sim/simulator/afe.py`, `pdm_receiver.v` | 檢查正負沿時脈取樣致能與 PRBS-15 測試序列對齊。 |
| **測試 6B 失敗** | 風噪相干性閥值偏高，或高通切除點偏差 | `sim/simulator/afe.py`, `golden_vad.py` | 確認 $\rho^2 < 0.125$ 時啟用單麥旁路與 350 Hz HPF。 |
| **測試 6C 失敗** | 空間微差抽頭 $k$ 未對齊或 $\alpha$ 飽和截斷偏差 | `sim/simulator/afe.py` | 確認耳機柄幾何間距 21.4mm 對應 1-tap 延遲補償。 |
| **測試 7 失敗** | MISR 壓縮多項式反饋抽頭錯誤或時脈不足 61,440 拍 | `sim/simulator/bist.py`, `bist_engine.v` | 確認 $P(x) = x^{32} + x^{22} + x^2 + x + 1$ 且初值為 `0x5A5AA5A5`。 |

---

## 5. 驗證需求追蹤清單 (Traceability Requirements)

| 需求 ID | 技術驗證標的 |
|---|---|
| `REQ-VERIF-001` | 回歸測試必須支援無第三方 EDA 工具依賴，純 Python 3.8+ 即可執行。 |
| `REQ-VERIF-002` | 全晶片回歸測試 7 項測試通過率必須為 100%（Zero Tolerance）。 |
| `REQ-VERIF-003` | 演算法模型與硬體模擬器數值比對必須為 0 誤差（Bit-True Exact Match）。 |
| `REQ-VERIF-004` | 必須支援匯出符合 IEEE 1364 標準之 `.vcd` 數位波形檔供 GTKWave 檢視。 |
| `REQ-VERIF-005` | 測試工具必須支援多國語言（`--lang zh-TW`, `en`, `zh-CN`, `ja`）。 |
| `REQ-VERIF-006` | Test 6 必須涵蓋 131,072 DDR 位元解多工驗證，位元錯誤率嚴格為 0。 |
| `REQ-VERIF-007` | Test 6 風噪抑制比必須 $\ge 15.0\text{ dB}$，軸向保留衰減 $\le 1.5\text{ dB}$。 |
| `REQ-VERIF-008` | Test 7 BIST 測試時間嚴格為 61,440 週期 ($5.00\text{ ms}$)，特徵碼比對為 `0x92B6CDA5`。 |
| `REQ-VERIF-009` | Test 7 故障注入測試必須涵蓋 7 處關鍵節點，檢出率嚴格為 100% (0 逃脫)。 |
| `REQ-VERIF-010` | 模擬器與驗證腳本執行總時間必須在 3 秒內完成，保障即時 CI/CD 回歸。 |

