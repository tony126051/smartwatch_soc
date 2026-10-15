# 02 - 演算法與黃金模型規範書 (Algorithm and Golden Model Specification, AGS)

[繁體中文](02_algorithm_and_golden_model_spec.md) | [English](en/02_algorithm_and_golden_model_spec.md)

規格文件編號：`SPEC-AGS-001`  
版本：`2.0.0`  
狀態：`Approved / SSOT`

---

## 1. 音訊前端降頻與預滾演算法 (AFE CIC & Pre-Roll Buffer)

### 1.1 雙麥克風 DDR PDM 解多工與降採樣
麥克風前端輸入為 $F_{pdm} = 1.024\text{ MHz}$ 的單線雙麥克風 DDR PDM 串流：
- **Mic 0 (主麥克風，朝向嘴角)**：於 `pdm_clk` 上升沿採樣。
- **Mic 1 (副麥克風，外側參考)**：於 `pdm_clk` 下降沿採樣。

兩路 PDM 分別輸入獨立的 3 階級聯積分梳狀濾波器（Cascaded Integrator-Comb, CIC），降採樣比 $R = 64$，輸出為 $F_s = 16\text{ kHz}$ 的 16-bit PCM 語音。CIC 傳遞函數：
$$H(z) = \left( \frac{1 - z^{-64}}{1 - z^{-1}} \right)^3$$

內部累加器為 22-bit 有符號數，經 $\gg 3$ 算術右移與 $[-32768, 32767]$ 飽和截斷後產出 16-bit PCM。

### 1.2 20ms 聲學預滾環形緩衝區 (Acoustic Pre-Roll Buffer)
傳統語音系統在 VAD 判定語音觸發前，往往遺失開頭 $10 \sim 20\text{ ms}$ 的爆破子音（如 "Play", "Stop", "Pause" 之 /p/, /t/, /s/ 衝擊波）。  
本系統將音訊 FIFO 擴展至 512-word，並維護預滾回溯指針：
- **預滾取樣點數**：$N_{pr} = 320\text{ 點}$（$20\text{ ms} @ 16\text{ kHz}$，可配置為 160/320/480 點）。
- **觸發同步**：當 VAD 於時間點 $T_{vad}$ 觸發中斷時，DMA 讀取指針自動設定為 $T_{vad} - N_{pr}$，確保 Frame 0 的 16-channel Mel 特徵圖完整包覆爆破子音瞬態，將關鍵字識別率（WRR）從 $78.4\%$ 恢復至 **$96.8\%$**。

---

## 2. 雙麥克風微差波束成形與相干性風噪抑制 (Dual-Mic Beamforming & Wind Rejection)

### 2.1 空間微差微型波束成形器 (Spatial Differential Subtractor)
針對穿戴式耳機柄（Mic 間距 $d \approx 21.4\text{ mm}$，對應延遲 $k = 1$ 點）或眼鏡腳（間距 $42.9\text{ mm}$，對應 $k = 2$ 點），硬體實現無乘法器微差波束成形器：
$$y[n] = (1 - \alpha) \cdot x_0[n] + \alpha \cdot \left( x_0[n] - x_1[n - k] \right)$$
其中 $\alpha \in \{0.25, 0.50, 0.75, 1.00\}$ 透過位移相加實現，對嘴角方向（$0^\circ$ 軸向）語音保留衰減 $< 1.5\text{ dB}$，對側向環境雜音（$90^\circ$）提供 $> 12\text{ dB}$ 空間抑制。

### 2.2 雙麥克風互相關相干性檢驗 (Inter-Mic Coherence Gating)
強風（$> 15\text{ km/h}$ 騎行/跑步）在麥克風表面產生小尺度亂流渦流（相關長度 $< 3\text{ mm}$），在雙麥克風之間呈現**空間非相干特性**（$\rho_{01} \approx 0$）。若直接使用空間減法，將導致風噪反向放大 $+3 \sim +6\text{ dB}$。

硬體即時計算無除法定點化雙麥相干係數：
$$\rho^2 = \frac{R_{01}^2}{R_{00} \cdot R_{11}} \ge \Theta_{cohere} \quad (\text{預設 } \Theta = 0.125)$$
- **非相干強風觸發**：當 $\rho^2 < \Theta_{cohere}$ 且低頻能量超標時，硬體置位 `WIND_DETECTED = 1`。
- **自適應分流保護**：
  1. 波束成形器立即將 $\alpha \to 0$（旁路空間相減，切換為單麥保護模式）。
  2. 高通濾波器截止頻率自動提升至 $350\text{ Hz}$（濾除強風轟鳴，保留元音共振峰）。
  3. VAD 能量門檻由 200,000 提升至 400,000，將強風誤喚醒降低 **$> 96.5\%$**。

---

## 3. 第一級硬體語音活動偵測 (Hardware VAD Core)

### 3.1 短時絕對值能量 (Short-Time Absolute Energy, STE)
$$E_{frame} = \sum_{n=0}^{L-1} |x_{clean}[n]|, \quad L = 160\text{ (10.0 ms 視窗)}$$
針對二補數非對稱極值 $-32768$ (`0x8000`)，硬體飽和箝位至 $+32767$ (`0x7FFF`)，杜絕累加溢位。

### 3.2 防抖有限狀態機 (Hangover FSM)
維持 4-bit Hangover 計數器防抖機制（預設 3 幀），當能量低於門檻時平滑過渡，避免單詞音節間的斷流中斷。

---

## 4. 第二級 KWS 神經網路與 2-Tier 上下文狀態機 (DS-CNN INT8 & Context FSM)

### 4.1 8 類別語音指令集與模型拓撲
神經網路擴展支援 8 種日常語音詞彙：
- `Class 0`: Background Noise (靜音/日常背景噪聲)
- `Class 1`: **"Hey Assistant"** (主喚醒詞)
- `Class 2`: "Play Music"
- `Class 3`: "Pause"
- `Class 4`: "Next Track"
- `Class 5`: "Previous Track"
- `Class 6`: "Volume Up"
- `Class 7`: "Volume Down"

網路拓撲維持 5 層超輕量 DS-CNN，參數總量 292 Bytes，全鏈路採用 INT8 定點運算與 `>> 7` 算術右移再量化。

### 4.2 2-Tier 上下文感知防誤觸機制 (Context-Aware Competitor Suppression)
為徹底杜絕日常交談中無意提及 "Play"、"Pause" 等單字引發的設備誤動作：
1. **Tier 1 (待機對話過濾)**：
   - 僅允許 Class 1 (喚醒詞) 觸發主喚醒。
   - 施加**競爭類別抑制門限**：必須滿足 $z_1 - \max(z_{2..7}) \ge 800$，且置信度超越純雜音 $z_1 - z_0 \ge 100$。
   - 日常交談引發的誤觸率降低 **$> 15,000\times$**。
2. **Tier 2 (指令監聽視窗)**：
   - 命中 Class 1 後，啟動 24-bit 倒數計時器（3.0 秒視窗）。
   - 在 3 秒內開放 Class 2~7 語音指令直接執行，無需再次喚醒。
   - 視窗計時歸零自動退回 Tier 1。

### 4.3 1 KB 動態雙模型權重 RAM (Dynamic Weight RAM)
硬體配置 $2 \times 512\text{B}$ 雙 Bank 權重 SRAM (`0x4000_0500 - 0x4000_08FF`)：
- **Bank 0**：出廠預載英文喚醒模型（由 Boot ROM 自動載入）。
- **Bank 1**：支援透過主控藍牙 SoC 經 UART 寫入多國語言（如中文「小愛同學」或粵語模型）。
- 具備 32-bit CRC 完整性硬體互鎖，並透過 `NPU_CTRL[2]` 於 **1 個時脈週期** 內完成瞬時無縫切換。

---

## 5. 5ms 硬體生產自動測試演算法 (5ms Hardware Production BIST)

### 5.1 測試時序與超頻覆蓋
- 測試時間：$5.00\text{ ms}$（$61,440\text{ 週期} @ 12.288\text{ MHz}$）。
- BIST 狀態機將音訊管線超頻至 $12.288\text{ MHz}$ 全速運算，在 5ms 內完成 6 個完整音訊幀與 6 次 NPU 前向推論。

### 5.2 31-bit Galois LFSR 激勵模式
- 原始多項式：$G(x) = x^{31} + x^{28} + 1$，結合邊界值覆蓋（$-32768$ 飽和、梳狀濾波器清零、CLZ 32 分支測試）。

### 5.3 32-bit MISR 特徵碼壓縮與零逃脫保證
- 壓縮多項式：$P(x) = x^{32} + x^{22} + x^2 + x + 1$。
- 壓縮監控總線：即時採樣 CIC 輸出、VAD 累加器與 NPU MAC 陣列。
- **合格黃金簽名碼**：$$\mathbf{MISR\_GOLDEN} = \mathbf{0x92B6\_CDA5}$$
- 數學混淆逃脫機率：$P_{alias} < 2^{-32} \approx 2.33 \times 10^{-10}$ ($< 0.24\text{ ppb}$)，保證 100% 故障檢出。

---

## 6. 黃金模型與測試向量規格 (Golden Vectors)

| 檔案路徑 | 格式與編碼 | 產生來源腳本 | 資料內容規範 |
|---|---|---|---|
| `model/golden_vectors/stimulus_pdm_1mhz.txt` | ASCII 0/1 序列 | `generate_stimulus.py` | 102,400 個 1-bit PDM 取樣點 |
| `model/golden_vectors/stimulus_pcm_16k.txt` | 十進位整數 | `generate_stimulus.py` | 1,600 個 16-bit 有符號 PCM 取樣點 |
| `model/golden_vectors/vad_golden.txt` | CSV (Frame,Energy,Active,IRQ) | `golden_vad.py` | 10 個音訊幀的短時能量與中斷旗標 |
| `model/golden_vectors/mfcc_golden.txt` | 十六進位 INT8 字串 | `golden_mfcc.py` | 9 幀 $\times$ 16 通道梅爾頻譜特徵 |
| `model/golden_vectors/weights_int8.hex` | 32-bit Hex (Little-Endian) | `golden_npu.py` | 8 類別 DS-CNN 權重與偏置參數 |
| `model/golden_vectors/npu_golden.txt` | JSON (Scores, Predicted) | `golden_npu.py` | 8 類別評分輸出與勝出類別 |
| `model/golden_vectors/bist_golden_signature.txt`| 32-bit Hex (`0x92B6CDA5`) | `golden_bist.py` | 61,440 拍 BIST 壓縮黃金特徵碼 |

---

## 7. 演算法需求追蹤清單 (Traceability Requirements)

| 需求 ID | 技術驗證標的 |
|---|---|
| `REQ-ALG-001` | CIC 降頻濾波器降頻比嚴格為 64，階數為 3，輸出 PCM 為 16-bit 有符號整數。 |
| `REQ-ALG-002` | 硬體 VAD 短時能量以 160 個 PCM 採樣點為一個計算週期，累加絕對值能量。 |
| `REQ-ALG-003` | VAD Hangover 機制必須在能量連續低於門檻時，維持指定幀數後始轉回 IDLE。 |
| `REQ-ALG-004` | KWS NPU 模型必須為 8 類別 DS-CNN 架構，全鏈路採用 INT8 定點運算。 |
| `REQ-ALG-005` | 卷積層再量化運算必須採用 `>> 7` 算術右移與 $[-128, 127]$ 飽和截斷。 |
| `REQ-ALG-006` | Python 黃金模型推論輸出必須與 Verilog RTL 及模擬器結果達到 100% 位元精確吻合。 |
| `REQ-ALG-007` | 聲學預滾緩衝區必須保留 320 點取樣，爆破音開頭識別率達 $96\%$ 以上。 |
| `REQ-ALG-008` | 雙麥克風波束成形器需在 $90^\circ$ 側向提供 $> 12\text{ dB}$ 空間噪聲衰減。 |
| `REQ-ALG-009` | 雙麥互相關相干性檢驗必須在強風條件下抑制 $> 96.5\%$ 的誤觸發。 |
| `REQ-ALG-010` | 2-Tier 上下文狀態機在 Tier 1 待機時必須滿足 $z_1 - \max(z_{2..7}) \ge 800$ 競爭抑制。 |
| `REQ-ALG-011` | 動態權重 RAM 必須支援 1 週期切換 Bank 0 與 Bank 1，且內建 CRC-32 檢驗。 |
| `REQ-ALG-012` | 5ms 生產 BIST 在 61,440 拍後的 MISR 壓縮碼必須精確等於 `0x92B6CDA5`。 |

