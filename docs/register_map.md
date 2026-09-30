# Smartwatch SoC KWS 加速器暫存器手冊 (Register Map)

[繁體中文](register_map.md) | [English](en/register_map.md) | [日本語](ja/register_map.md)

基底位址：`0x4000_0000`  
匯流排協議：AMBA APB (32-bit 資料匯流排)

| 偏移位址 (Offset) | 暫存器名稱 | 讀/寫 | 預設值 | 欄位說明 |
|---|---|---|---|---|
| `0x000` | **AFE_CTRL** | R/W | `0x0000_0000` | **[0]**: AFE 與 CIC 濾波器使能 (1 = 啟用, 0 = 關閉) |
| `0x004` | **AFE_STATUS** | RO | `0x0000_0001` | **[0]**: FIFO 空標誌 (`empty`)<br>**[1]**: FIFO 滿標誌 (`full`)<br>**[16:8]**: FIFO 當前樣本數 (`count`) |
| `0x008` | **AFE_DATA** | RO | `0x0000_0000` | **[15:0]**: 讀取 16-bit PCM 音訊資料 (讀取後自動 Pop) |
| `0x010` | **VAD_CTRL** | R/W | `0x0000_0000` | **[0]**: VAD 模組使能<br>**[1]**: 寫 1 清除 VAD 喚醒中斷旗標 (`irq_vad_wakeup`) |
| `0x014` | **VAD_THRESHOLD** | R/W | `200000` | **[23:0]**: 時域短時能量比較閾值 |
| `0x018` | **VAD_HANGOVER** | R/W | `3` | **[3:0]**: Hangover 幀數長度 (防止語音音節中斷) |
| `0x01C` | **VAD_ENERGY** | RO | `0x0000_0000` | **[23:0]**: 當前幀累計短時能量<br>**[24]**: 語音活動狀態 (`speech_active`) |
| `0x020` | **NPU_CTRL** | R/W | `0x0000_0000` | **[0]**: 啟動推論脈衝 (`start_inference`)<br>**[1]**: 寫 1 清除 NPU 完成中斷旗標 (`irq_npu_done`) |
| `0x024` | **NPU_STATUS** | RO | `0x0000_0000` | **[0]**: NPU 忙碌中 (`busy`)<br>**[1]**: 推論完成 (`done`)<br>**[2]**: 喚醒詞偵測成功 (`keyword_detected`) |
| `0x028` | **NPU_SCORE0** | RO | `0x0000_0000` | **[31:0]**: 類別 0 (非關鍵字) 分類得分 (有符號 32-bit 整數) |
| `0x02C` | **NPU_SCORE1** | RO | `0x0000_0000` | **[31:0]**: 類別 1 (目標喚醒詞) 分類得分 (有符號 32-bit 整數) |
| `0x400 - 0x4FF` | **NPU_FEAT_RAM** | R/W | `0x00` | 256 個 INT8 位元組之輸入特徵圖存取窗口 ($16\times16$) |
| `0x500 - 0x5FF` | **NPU_WGT_RAM** | R/W | `0x00` | 256 個 INT8 位元組之神經網絡權重存取窗口 |
