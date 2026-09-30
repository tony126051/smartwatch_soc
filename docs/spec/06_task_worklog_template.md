# 06 - AI Agent 任務工作日誌範本 (Task Worklog Template)

[繁體中文](06_task_worklog_template.md) | [English](en/06_task_worklog_template.md)

規格文件編號：`SPEC-TMP-001`  
版本：`1.0.0`  
狀態：`Approved / SSOT`

---

## 範本使用說明
當 AI Agent 完成特定需求開發或 Bug 修復時，建議依照本範本格式於回應中提供結構化摘要，或記錄於開發工作日誌中。

---

```markdown
# 🛠️ [任務名稱 / 功能修復摘要]

- **執行者**：AI Agent (模型名稱 / 角色)
- **執行日期**：YYYY-MM-DD
- **關聯需求 ID**：`REQ-xxx-yyy` (參照 docs/spec/ 目錄各規格書)
- **變更類型**：[功能擴充 / Bug 修復 / 效能優化 / 重構 / 規格更新]

---

## 1. 任務背景與目標 (Objective)
[簡述此任務解決的問題或達成的規格要求，並連結相關規格條款]

---

## 2. 影響範圍與檔案清單 (Touched Files)
- **規格文件**：
  - [規格名稱](file:///home/tony/repo/projects/smart_watch/docs/spec/...)
- **演算法模型**：
  - [演算法腳本](file:///home/tony/repo/projects/smart_watch/model/...)
- **數位硬體 RTL**：
  - [Verilog 模組](file:///home/tony/repo/projects/smart_watch/rtl/...)
- **韌體與軟體**：
  - [組合語言或標頭檔](file:///home/tony/repo/projects/smart_watch/sw/...)
- **模擬器與測試驗證**：
  - [模擬器組件](file:///home/tony/repo/projects/smart_watch/sim/...)

---

## 3. 核心變更細節 (Implementation Details)
### 3.1 介面與暫存器變更
[說明是否有修改或新增暫存器、位元欄位、預設值]

### 3.2 邏輯與運算調整
[說明 Verilog / Python / Assembly 的核心改動點，例如公式、狀態機或移位量]

---

## 4. 驗證與驗收佐證 (Verification Evidence)
### 4.1 執行的驗收指令
```bash
# 1. 韌體重新組譯 (若有更動組合語言)
python3 sw/build_firmware.py sw/app/main.s sw/firmware.hex

# 2. 全晶片回歸測試
python3 sim/run_simulator.py --mode regression
```

### 4.2 回歸測試輸出日誌
```text
===========================================================================
  [回歸測試套件] Smartwatch SoC 子系統與全晶片功能驗證
===========================================================================
[測試 1/5] 驗證 RISC-V RV32I 處理器核心與記憶體子系統... [通過]
[測試 2/5] 驗證音訊前端 (3 階 CIC 降頻濾波器與 FIFO)... [通過]
[測試 3/5] 驗證第一級硬體語音活動偵測器 (Hardware VAD Core)... [通過]
[測試 4/5] 驗證第二級 KWS NPU 加速器與 INT8 量化推論... [通過]
[測試 5/5] 驗證全系統整合與實際 RISC-V 韌體執行流程... [通過]
>>> 全數 5 項回歸測試通過 (100% 位元精確驗證成功) <<<
```

---

## 5. 自我審查清單 (Self-Audit Checklist)
- [x] 未引入外部 DRAM 依賴，SRAM 總預算保持在 64 KB 內
- [x] 暫存器定義與 `docs/spec/01_hardware_interface_spec.md` 及 `sw/include/soc_regs.h` 嚴格同步
- [x] Verilog RTL 遵循 Verilog-2001 可合成標準，無 Latch 與非同步風險
- [x] Python 模擬器維持純標準庫實現，無額外套件依賴
- [x] 回歸測試 100% PASS，無功能退化
```
