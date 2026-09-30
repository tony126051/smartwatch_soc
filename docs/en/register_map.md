# Smartwatch SoC KWS Accelerator Register Map

[繁體中文](../register_map.md) | [English](register_map.md) | [日本語](../ja/register_map.md)

Base Address: `0x4000_0000`  
Bus Protocol: AMBA APB (32-bit Data Bus)

| Offset | Register Name | Access | Reset Value | Description |
|---|---|---|---|---|
| `0x000` | **AFE_CTRL** | R/W | `0x0000_0000` | **[0]**: Audio Front-End & CIC decimator enable (1 = Enable, 0 = Disable) |
| `0x004` | **AFE_STATUS** | RO | `0x0000_0001` | **[0]**: FIFO empty flag (`empty`)<br>**[1]**: FIFO full flag (`full`)<br>**[16:8]**: FIFO current sample count (`count`) |
| `0x008` | **AFE_DATA** | RO | `0x0000_0000` | **[15:0]**: Read 16-bit PCM audio sample (automatically pops FIFO on read) |
| `0x010` | **VAD_CTRL** | R/W | `0x0000_0000` | **[0]**: VAD module enable<br>**[1]**: Write 1 to clear VAD wakeup interrupt flag (`irq_vad_wakeup`) |
| `0x014` | **VAD_THRESHOLD** | R/W | `200000` | **[23:0]**: Time-domain Short-Time Energy (STE) threshold |
| `0x018` | **VAD_HANGOVER** | R/W | `3` | **[3:0]**: Hangover debounce frame count (prevents syllable dropouts) |
| `0x01C` | **VAD_ENERGY** | RO | `0x0000_0000` | **[23:0]**: Current frame accumulated short-time energy<br>**[24]**: Voice activity flag (`speech_active`) |
| `0x020` | **NPU_CTRL** | R/W | `0x0000_0000` | **[0]**: Start inference pulse (`start_inference`)<br>**[1]**: Write 1 to clear NPU done interrupt flag (`irq_npu_done`) |
| `0x024` | **NPU_STATUS** | RO | `0x0000_0000` | **[0]**: NPU busy flag (`busy`)<br>**[1]**: Inference completed flag (`done`)<br>**[2]**: Target keyword detected (`keyword_detected`) |
| `0x028` | **NPU_SCORE0** | RO | `0x0000_0000` | **[31:0]**: Class 0 (non-keyword / background noise) score (signed 32-bit integer) |
| `0x02C` | **NPU_SCORE1** | RO | `0x0000_0000` | **[31:0]**: Class 1 (target keyword) score (signed 32-bit integer) |
| `0x400 - 0x4FF` | **NPU_FEAT_RAM** | R/W | `0x00` | 256 INT8 bytes input feature map window ($16\times16$) |
| `0x500 - 0x5FF` | **NPU_WGT_RAM** | R/W | `0x00` | 256 INT8 bytes neural network weights window |
