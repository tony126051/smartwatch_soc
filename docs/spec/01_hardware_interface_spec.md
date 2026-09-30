# 01 - 硬體介面與匯流排通訊規範書 (Hardware Interface Specification, HIS)

[繁體中文](01_hardware_interface_spec.md) | [English](en/01_hardware_interface_spec.md)

規格文件編號：`SPEC-HIS-001`  
版本：`1.0.0`  
狀態：`Approved / SSOT`

---

## 1. 晶片記憶體映射總覽 (Global Memory Map)

晶片採用 32-bit 扁平記憶體空間（Unified Memory Space），總體規劃如下：

| 實體位址區間 | 區域別名 | 容量 | 匯流排/協定 | 存取屬性 | 用途說明 |
|---|---|---|---|---|---|
| `0x0000_0000 - 0x0000_1FFF` | **ITCM / Boot ROM** | 8 KB | CPU Native Bus | R/X | 開機重設向量、韌體代碼段與常數 (firmware.hex) |
| `0x1000_0000 - 0x1000_1FFF` | **DTCM / Data SRAM** | 8 KB | CPU Native Bus | R/W | 堆疊區 (SP 從 0x1000_1FF0 向下增長)、全局變數 |
| `0x4000_0000 - 0x4000_003F` | **KWS Control Regs** | 64 B | AMBA APB3 | R/W | AFE、VAD、NPU 控制/狀態暫存器 |
| `0x4000_0400 - 0x4000_04FF` | **NPU Feature RAM** | 256 B | AMBA APB3 | R/W | $16\times16$ INT8 特徵輸入 RAM 窗口 |
| `0x4000_0500 - 0x4000_05FF` | **NPU Weight RAM** | 256 B | AMBA APB3 | R/W | 模型權重 INT8 寫入窗口 |
| `0x8000_0000 - 0x8000_0003` | **Debug LED Reg** | 4 B | CPU Native Bus | R/W | 8-bit 板載 LED 狀態顯示與除錯指示暫存器 |

---

## 2. AMBA 3 APB 匯流排協定規範 (APB3 Protocol)

KWS 硬體子系統 (`0x4000_0000`) 透過標準 AMBA 3 APB Slave 介面與主匯流排橋接器連接。

### 2.1 匯流排信號定義

| 信號名稱 | 方向 (對 Slave 而言) | 位元寬度 | 描述 |
|---|---|---|---|
| `PCLK` | Input | 1 | 系統同步主時脈 (12.288 MHz) |
| `PRESETn` | Input | 1 | 非同步重設信號 (低電位有效) |
| `PADDR` | Input | 12 | APB 暫存器偏移位址 (字對齊，低 2 位為 0) |
| `PSEL` | Input | 1 | Slave 模組片選信號 |
| `PENABLE` | Input | 1 | APB 傳輸致能信號 (第二週期拉高) |
| `PWRITE` | Input | 1 | 傳輸方向 (1 = 寫入 Write, 0 = 讀取 Read) |
| `PWDATA` | Input | 32 | 32-bit 寫入資料匯流排 |
| `PRDATA` | Output | 32 | 32-bit 讀取資料匯流排 |
| `PREADY` | Output | 1 | Slave 就緒信號 (本系統固定為 1'b1，單週期響應) |
| `PSLVERR` | Output | 1 | 傳輸錯誤信號 (本系統固定綁定 1'b0) |

### 2.2 APB 讀寫時序契約
1. **Setup 階段 (第 1 週期)**：Master 拉高 `PSEL`，驅動 `PADDR`、`PWRITE` 及 `PWDATA`（寫操作時）。此時 `PENABLE` 為 0。
2. **Access 階段 (第 2 週期)**：Master 拉高 `PENABLE`。Slave 在此週期採樣寫入資料，或在 `PRDATA` 驅動有效讀取資料。
3. **無等待傳輸 (Zero Wait States)**：`PREADY` 恆為 1，因此每次 APB 傳輸固定耗時 **2 個時脈週期**。

---

## 3. 暫存器詳細位元規範 (Detailed Register Map)

基底位址：`0x4000_0000`

### 3.1 AFE_CTRL - 音訊前端控制暫存器 (Offset: `0x000`)
- **重設預設值**：`0x0000_0000`
- **存取屬性**：可讀可寫 (R/W)

| 位元區間 | 欄位名稱 | 屬性 | 預設值 | 功能描述 |
|---|---|---|---|---|
| `[0]` | `AFE_EN` | R/W | 1'b0 | **音訊前端致能**：<br>`1` = 啟用 PDM 採樣與 CIC 降頻濾波器運作<br>`0` = 關閉 AFE 進入超低功耗待機 |
| `[31:1]` | `RESERVED` | RO | 31'd0 | 保留位元，讀取恆為 0 |

### 3.2 AFE_STATUS - 音訊前端狀態暫存器 (Offset: `0x004`)
- **重設預設值**：`0x0000_0001`
- **存取屬性**：唯讀 (RO)

| 位元區間 | 欄位名稱 | 屬性 | 預設值 | 功能描述 |
|---|---|---|---|---|
| `[0]` | `FIFO_EMPTY` | RO | 1'b1 | 音訊 FIFO 空標誌：`1` = FIFO 內無任何音訊取樣 |
| `[1]` | `FIFO_FULL` | RO | 1'b0 | 音訊 FIFO 滿標誌：`1` = FIFO 已滿 (256-word) |
| `[16:8]` | `FIFO_COUNT` | RO | 9'd0 | 當前 FIFO 內累積的 16-bit PCM 取樣點數量 (0 ~ 256) |
| 其他 | `RESERVED` | RO | 0 | 保留位元 |

### 3.3 AFE_DATA - 音訊 FIFO 資料讀取暫存器 (Offset: `0x008`)
- **重設預設值**：`0x0000_0000`
- **存取屬性**：唯讀 (RO)
- **副作用**：每次讀取此暫存器時，硬體 FIFO 自動 Pop 彈出一個資料。

| 位元區間 | 欄位名稱 | 屬性 | 預設值 | 功能描述 |
|---|---|---|---|---|
| `[15:0]` | `PCM_SAMPLE` | RO | 16'd0 | 當前彈出的 16-bit 有符號 (Signed) PCM 音訊資料 |
| `[31:16]` | `RESERVED` | RO | 16'd0 | 讀取恆為 0 |

---

### 3.4 VAD_CTRL - 語音活動偵測控制暫存器 (Offset: `0x010`)
- **重設預設值**：`0x0000_0000`
- **存取屬性**：可讀可寫 (R/W)

| 位元區間 | 欄位名稱 | 屬性 | 預設值 | 功能描述 |
|---|---|---|---|---|
| `[0]` | `VAD_EN` | R/W | 1'b0 | **VAD 模組致能**：`1` = 啟動短時能量計算，`0` = 關閉 |
| `[1]` | `VAD_IRQ_CLR` | WO | 1'b0 | **清除中斷**：寫入 `1` 清除 `irq_vad_wakeup` 中斷旗標（自動回清） |
| `[31:2]` | `RESERVED` | RO | 30'd0 | 保留位元 |

### 3.5 VAD_THRESHOLD - 語音能量門檻暫存器 (Offset: `0x014`)
- **重設預設值**：`200000` (`0x0003_0D40`)
- **存取屬性**：可讀可寫 (R/W)

| 位元區間 | 欄位名稱 | 屬性 | 預設值 | 功能描述 |
|---|---|---|---|---|
| `[23:0]` | `ENERGY_THRES`| R/W | 200,000 | 160 點時短絕對值能量累加比較閾值。超過此值視為潛在語音。 |
| `[31:24]` | `RESERVED` | RO | 8'd0 | 保留位元 |

### 3.6 VAD_HANGOVER - 防抖計數長度暫存器 (Offset: `0x018`)
- **重設預設值**：`3` (`0x0000_0003`)
- **存取屬性**：可讀可寫 (R/W)

| 位元區間 | 欄位名稱 | 屬性 | 預設值 | 功能描述 |
|---|---|---|---|---|
| `[3:0]` | `HANGOVER_LEN`| R/W | 4'd3 | 當能量低於閾值時，維持語音判定狀態的幀數 (避免音節停頓斷流) |
| `[31:4]` | `RESERVED` | RO | 28'd0 | 保留位元 |

### 3.7 VAD_ENERGY - 當前幀能量讀取暫存器 (Offset: `0x01C`)
- **重設預設值**：`0x0000_0000`
- **存取屬性**：唯讀 (RO)

| 位元區間 | 欄位名稱 | 屬性 | 預設值 | 功能描述 |
|---|---|---|---|---|
| `[23:0]` | `CURRENT_ENERGY`| RO | 24'd0 | 前一幀完成計算之 160 點時短絕對值能量值 |
| `[24]` | `SPEECH_ACTIVE` | RO | 1'b0 | 當前是否處於語音活躍狀態 (包含 Hangover 延伸區間) |
| `[31:25]` | `RESERVED` | RO | 7'd0 | 保留位元 |

---

### 3.8 NPU_CTRL - KWS NPU 加速器控制暫存器 (Offset: `0x020`)
- **重設預設值**：`0x0000_0000`
- **存取屬性**：可讀可寫 (R/W)

| 位元區間 | 欄位名稱 | 屬性 | 預設值 | 功能描述 |
|---|---|---|---|---|
| `[0]` | `START_INFER` | WO | 1'b0 | **啟動推論脈衝**：寫入 `1` 觸發 NPU 狀態機開始執行前向計算 |
| `[1]` | `NPU_IRQ_CLR` | WO | 1'b0 | **清除中斷**：寫入 `1` 清除 `irq_npu_done` 中斷旗標 |
| `[31:2]` | `RESERVED` | RO | 30'd0 | 保留位元 |

### 3.9 NPU_STATUS - KWS NPU 狀態暫存器 (Offset: `0x024`)
- **重設預設值**：`0x0000_0000`
- **存取屬性**：唯讀 (RO)

| 位元區間 | 欄位名稱 | 屬性 | 預設值 | 功能描述 |
|---|---|---|---|---|
| `[0]` | `NPU_BUSY` | RO | 1'b0 | NPU 忙碌標誌：`1` = 正在計算中，禁止重複寫入特徵 |
| `[1]` | `NPU_DONE` | RO | 1'b0 | 推論完成標誌：`1` = 推論完成，分類得分已就緒 |
| `[2]` | `KEYWORD_HIT` | RO | 1'b0 | 喚醒詞分類旗標：`1` = Class 1 得分大於 Class 0 |
| `[31:3]` | `RESERVED` | RO | 29'd0 | 保留位元 |

### 3.10 NPU_SCORE0 - 類別 0 得分暫存器 (Offset: `0x028`)
- **重設預設值**：`0x0000_0000`
- **存取屬性**：唯讀 (RO)
- **說明**：32-bit 有符號二補數整數，代表背景雜音/非喚醒詞之 FC 分類輸出。

### 3.11 NPU_SCORE1 - 類別 1 得分暫存器 (Offset: `0x02C`)
- **重設預設值**：`0x0000_0000`
- **存取屬性**：唯讀 (RO)
- **說明**：32-bit 有符號二補數整數，代表目標喚醒詞之 FC 分類輸出。

---

### 3.12 特徵與權重存取窗口 (SRAM Windows)
- **`0x4000_0400 - 0x4000_04FF` (NPU_FEAT_RAM)**：
  - 共 256 個位元組空間（對應 $16\times16$ 特徵圖）。
  - 支援 Byte 存取或 32-bit Word 存取（小端序 Little-Endian）。
- **`0x4000_0500 - 0x4000_05FF` (NPU_WGT_RAM)**：
  - 共 256 個位元組空間（儲存 INT8 模型參數與權重）。
  - 支援動態熱更新，開機時由 CPU 載入或模擬器預填。

---

## 4. 中斷架構與協定 (Interrupt Specification)

系統支援 2 條核心硬體中斷線，直連 PicoRV32 的 `cpu_irq` 介面：

| 中斷編號 | 信號名稱 | 觸發來源 | 觸發模式 | 優先權 | 服務與清除方法 |
|---|---|---|---|---|---|
| `cpu_irq[0]` | `irq_vad_wakeup` | VAD Core | 上升沿鎖存 (Active High) | 高 | 寫入 `VAD_CTRL[1] = 1` 清除 |
| `cpu_irq[1]` | `irq_npu_done` | NPU FSM | 上升沿鎖存 (Active High) | 次高 | 寫入 `NPU_CTRL[1] = 1` 清除 |

### 4.1 中斷服務協定 (Interrupt Handshake Flow)
1. **中斷發生**：當硬體條件滿足時，內部正反器拉高中斷信號並持續保持為高。
2. **CPU 響應**：PicoRV32 跳轉至中斷向量 `0x0000_0010`。
3. **清除旗標**：CPU ISR 必須向對應控制暫存器的 Bit[1] 寫入 `1`，清除硬體中斷鎖存器，否則返回後會重複觸發中斷。

---

## 5. 頂層引腳與實體封裝信號 (Top-Level Pinout)

| 引腳名稱 | 方向 | 寬度 | 阻抗/驅動 | 描述 |
|---|---|---|---|---|
| `clk` | Input | 1 | 外部 CMOS | 12.288 MHz 主時脈輸入 |
| `rst_n` | Input | 1 | 內建弱上拉 | 晶片主非同步重設 (低電位有效) |
| `pdm_clk_en` | Input | 1 | CMOS | 1.024 MHz PDM 取樣致能信號 |
| `pdm_data_in` | Input | 1 | 外部 PDM 麥克風 | 1-bit 數位麥克風 PDM 串流輸入 |
| `debug_leds` | Output | 8 | 4mA 驅動 | 8 顆板載狀態指示 LED 輸出 |
| `soc_trap` | Output | 1 | 4mA 驅動 | CPU 陷入非法指令/死當輸出 (高電位有效) |

---

## 6. 介面需求追蹤矩陣 (Traceability Requirements)

| 需求 ID | 技術驗證標的 |
|---|---|
| `REQ-BUS-001` | APB3 匯流排存取週期嚴格限定為 2 個時脈週期（`PREADY=1`）。 |
| `REQ-BUS-002` | `AFE_DATA` (0x008) 讀取操作必須具備自動 Pop FIFO 樣點之硬體副作用。 |
| `REQ-BUS-003` | `VAD_CTRL[1]` 與 `NPU_CTRL[1]` 寫入 1 必須在 1 拍內完成中斷旗標回清。 |
| `REQ-BUS-004` | 特徵 RAM 與權重 RAM 讀寫必須支援 Little-Endian 32-bit 字對齊與 Byte 封裝。 |
| `REQ-BUS-005` | `debug_leds` 預設值為 `0x00`，重設釋放後由韌體寫入 `0x8000_0000` 驅動。 |
