# 02 - 演算法與黃金模型規範書 (Algorithm and Golden Model Specification, AGS)

[繁體中文](02_algorithm_and_golden_model_spec.md) | [English](en/02_algorithm_and_golden_model_spec.md)

規格文件編號：`SPEC-AGS-001`  
版本：`1.0.0`  
狀態：`Approved / SSOT`

---

## 1. 音訊前端降頻演算法 (AFE CIC Decimator)

### 1.1 數學模型與傳遞函數
麥克風前端輸入為 $F_{pdm} = 1.024\text{ MHz}$ 的 1-bit PDM 串流，透過 3 階級聯積分梳狀濾波器（Cascaded Integrator-Comb, CIC）進行降採樣，降採樣比 $R = 64$，輸出為 $F_s = 16\text{ kHz}$ 的 16-bit PCM 語音。

CIC 濾波器的 $Z$ 域傳遞函數定義為：
$$H(z) = \left( \sum_{k=0}^{R-1} z^{-k} \right)^N = \left( \frac{1 - z^{-R}}{1 - z^{-1}} \right)^N, \quad N=3, R=64$$

### 1.2 位元擴展與定點字長規格
根據 Hogenauer 理論，CIC 濾波器的最大位元增長（Bit Growth）為：
$$B_{max} = B_{in} + N \cdot \log_2(R) = 1 + 3 \times \log_2(64) = 1 + 3 \times 6 = 19\text{ 位元}$$

為了保留溢位餘裕並配合 32-bit APB 匯流排架構：
- **內部累加器字長**：定為 **22-bit 有符號二補數整數**。
- **降頻截斷與飽和規則**：
  $$x_{pcm}[n] = \text{clamp}\left( \text{CIC}_{out}[n] \gg 3, -32768, 32767 \right)$$
- 輸出結果推入長度為 256 個取樣點的環形音訊 FIFO (`audio_fifo.v`)。

---

## 2. 第一級硬體語音活動偵測 (Hardware VAD Core)

### 2.1 短時絕對值能量 (Short-Time Absolute Energy, STE)
為了避免乘法器消耗過多面積與動態功耗，第一級 VAD 採用 **L1 範數短時絕對值能量累加**：
$$E_{frame} = \sum_{n=0}^{L-1} |x_{pcm}[n]|, \quad L = 160\text{ (10.0 ms 視窗)}$$

### 2.2 防抖有限狀態機 (Hangover FSM)
自然語言的單詞與音節之間存在 $10 \sim 30\text{ ms}$ 的短暫停頓（如爆破音、摩擦音閉音期）。若單憑瞬時幀能量進行判定，會導致喚醒中斷頻繁斷續。因此設計 4-bit Hangover 計數器防抖機制：

```mermaid
stateDiagram-v2
    [*] --> VAD_IDLE
    
    state VAD_IDLE {
        description: 靜音待機狀態 (speech_active = 0)
    }
    state VAD_ACTIVE {
        description: 語音活動狀態 (speech_active = 1)
    }
    state VAD_HANGOVER {
        description: 尾部防抖延伸狀態 (speech_active = 1)
    }
    
    VAD_IDLE --> VAD_ACTIVE: E_frame >= VAD_THRESHOLD<br>(觸發 irq_vad_wakeup)
    VAD_ACTIVE --> VAD_ACTIVE: E_frame >= VAD_THRESHOLD
    VAD_ACTIVE --> VAD_HANGOVER: E_frame < VAD_THRESHOLD<br>(計數器 cnt = HANGOVER_LEN)
    VAD_HANGOVER --> VAD_ACTIVE: E_frame >= VAD_THRESHOLD
    VAD_HANGOVER --> VAD_HANGOVER: E_frame < VAD_THRESHOLD 且 cnt > 1<br>(cnt = cnt - 1)
    VAD_HANGOVER --> VAD_IDLE: E_frame < VAD_THRESHOLD 且 cnt == 1<br>(speech_active = 0)
```

### 2.3 中斷觸發條件
- 當系統從 `VAD_IDLE` 狀態躍遷至 `VAD_ACTIVE` 時（**上升沿觸發**），硬體立即向 CPU 發出 `irq_vad_wakeup` 中斷。
- 在 `VAD_ACTIVE` 或 `VAD_HANGOVER` 維持期間，不再重複發送中斷，避免中斷淹沒（Interrupt Flooding）。

---

## 3. 第二級 KWS 輕量化神經網路 (DS-CNN INT8)

### 3.1 模型架構拓撲 (Network Topology)
本模型為超輕量深度可分離卷積網路（Depthwise Separable CNN, DS-CNN），專門針對晶片內 SRAM 限制設計：
- **輸入特徵規格**：$16 \times 16$ 單通道 INT8 二維矩陣（共 256 位元組）。

| 層次編號 | 層次類型 | 輸入尺寸 ($C_{in} \times H \times W$) | 核心/群組參數 | 輸出尺寸 ($C_{out} \times H \times W$) | 激活函數 | 備註說明 |
|---|---|---|---|---|---|---|
| **Layer 1** | Standard Conv2D | $1 \times 16 \times 16$ | Kernel $3\times3$, Stride 1, Pad 1 | $4 \times 16 \times 16$ | ReLU | 擷取基本頻譜紋理 |
| **Layer 2** | Depthwise Conv2D | $4 \times 16 \times 16$ | Kernel $3\times3$, Groups 4, Pad 1 | $4 \times 16 \times 16$ | ReLU | 通道獨立空間卷積 |
| **Layer 3** | Pointwise Conv2D | $4 \times 16 \times 16$ | Kernel $1\times1$, Stride 1 | $8 \times 16 \times 16$ | ReLU | 跨通道特徵融合 |
| **Layer 4** | Global Avg Pool | $8 \times 16 \times 16$ | $16\times16$ 空間平均 | $8 \times 1 \times 1$ | None | 降維消除空間平移敏感度 |
| **Layer 5** | Fully Connected | $8 \times 1 \times 1$ | $8 \to 2$ 矩陣向量乘法 | $2 \times 1 \times 1$ | None | 輸出 Class 0 與 Class 1 得分 |

### 3.2 對稱 INT8 定點量化規範
為了在硬體中僅使用整數加減乘與移位器，量化規則定義如下：
1. **輸入與權重格式**：有符號 8-bit 整數（INT8，區間 $[-128, 127]$）。
2. **乘加累加器**：有符號 32-bit 整數（INT32），防止累加溢位。
3. **層間再量化 (Requantization / Scale-down)**：
   卷積層輸出經過 Bias 累加後，採用 **算術右移 7 位元 (`>> 7`)** 與飽和截斷（Clamping）轉換回 INT8：
   $$y_{act} = \text{ReLU}\left( \text{clamp}\left( ( \text{Acc}_{32} + \text{Bias}_{32} ) \gg 7, -128, 127 \right) \right)$$
   其中 $\text{ReLU}(v) = \max(0, v)$。
4. **全連接層 (FC)**：
   最終輸出保留 32-bit 有符號數直接寫入 `NPU_SCORE0` 與 `NPU_SCORE1`，保留最大分類動態範圍。

---

## 4. 黃金模型與測試向量規格 (Golden Vectors)

所有演算法皆有對應的 Python 黃金模型腳本，並儲存標準測試向量於 `model/golden_vectors/`：

| 檔案路徑 | 格式與編碼 | 產生來源腳本 | 資料內容規範 |
|---|---|---|---|
| `model/golden_vectors/stimulus_pdm_1mhz.txt` | ASCII 0/1 序列 | `generate_stimulus.py` | 102,400 個 1-bit PDM 取樣點 |
| `model/golden_vectors/stimulus_pcm_16k.txt` | 十進位整數 | `generate_stimulus.py` | 1,600 個 16-bit 有符號 PCM 取樣點 |
| `model/golden_vectors/vad_golden.txt` | CSV (Frame,Energy,Active,IRQ) | `golden_vad.py` | 10 個音訊幀的短時能量與中斷旗標 |
| `model/golden_vectors/mfcc_golden.txt` | 十六進位 INT8 字串 | `golden_mfcc.py` | 9 幀 $\times$ 16 通道梅爾頻譜特徵 |
| `model/golden_vectors/weights_int8.hex` | 32-bit Hex (Little-Endian) | `golden_npu.py` | DS-CNN 權重與偏置參數二進位二補數 |
| `model/golden_vectors/npu_golden.txt` | JSON (Scores, Predicted) | `golden_npu.py` | Class 0=58, Class 1=-51 (預測類別 0) |

---

## 5. 演算法需求追蹤清單 (Traceability Requirements)

| 需求 ID | 技術驗證標的 |
|---|---|
| `REQ-ALG-001` | CIC 降頻濾波器降頻比嚴格為 64，階數為 3，輸出 PCM 為 16-bit 有符號整數。 |
| `REQ-ALG-002` | 硬體 VAD 短時能量以 160 個 PCM 採樣點為一個計算週期，累加絕對值能量。 |
| `REQ-ALG-003` | VAD Hangover 機制必須在能量連續低於門檻時，維持指定幀數後始轉回 IDLE。 |
| `REQ-ALG-004` | KWS NPU 模型必須為 5 層 DS-CNN 架構，輸入固定為 $16\times16$ INT8 矩陣。 |
| `REQ-ALG-005` | 卷積層再量化運算必須採用 `>> 7` 算術右移與 $[-128, 127]$ 飽和截斷。 |
| `REQ-ALG-006` | Python 黃金模型推論輸出必須與 Verilog RTL 及模擬器結果達到 100% 位元精確吻合。 |
