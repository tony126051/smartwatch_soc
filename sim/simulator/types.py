"""
Smartwatch SoC Simulator Common Types & Constants
"""

# System Clock and Timing Specifications
SYS_CLK_FREQ = 12_288_000    # 12.288 MHz System Main Clock
PDM_CLK_FREQ = 1_024_000     # 1.024 MHz Microphone PDM Clock
PCM_SAMPLE_RATE = 16_000     # 16 kHz Audio Sample Rate (Decimation factor R = 64)
SYS_TO_PDM_RATIO = SYS_CLK_FREQ // PDM_CLK_FREQ  # 12 cycles per PDM clock

# Memory Map Base Addresses & Sizes
ROM_BASE = 0x0000_0000
ROM_SIZE = 8192              # 8 KB Boot ROM / ITCM
RAM_BASE = 0x1000_0000
RAM_SIZE = 8192              # 8 KB Data SRAM / DTCM
KWS_BASE = 0x4000_0000
KWS_SIZE = 4096              # 4 KB APB Peripheral Space
SYS_BASE = 0x8000_0000
SYS_SIZE = 16                # System Debug / LED Registers

# KWS APB Register Offsets
OFFSET_AFE_CTRL      = 0x000
OFFSET_AFE_STATUS    = 0x004
OFFSET_AFE_DATA      = 0x008
OFFSET_VAD_CTRL      = 0x010
OFFSET_VAD_THRESHOLD = 0x014
OFFSET_VAD_HANGOVER  = 0x018
OFFSET_VAD_ENERGY    = 0x01C
OFFSET_NPU_CTRL      = 0x020
OFFSET_NPU_STATUS    = 0x024
OFFSET_NPU_SCORE0    = 0x028
OFFSET_NPU_SCORE1    = 0x02C
OFFSET_NPU_FEAT_BASE = 0x400
OFFSET_NPU_WGT_BASE  = 0x500

# Full Peripheral Addresses
ADDR_AFE_CTRL      = KWS_BASE + OFFSET_AFE_CTRL
ADDR_AFE_STATUS    = KWS_BASE + OFFSET_AFE_STATUS
ADDR_AFE_DATA      = KWS_BASE + OFFSET_AFE_DATA
ADDR_VAD_CTRL      = KWS_BASE + OFFSET_VAD_CTRL
ADDR_VAD_THRESHOLD = KWS_BASE + OFFSET_VAD_THRESHOLD
ADDR_VAD_HANGOVER  = KWS_BASE + OFFSET_VAD_HANGOVER
ADDR_VAD_ENERGY    = KWS_BASE + OFFSET_VAD_ENERGY
ADDR_NPU_CTRL      = KWS_BASE + OFFSET_NPU_CTRL
ADDR_NPU_STATUS    = KWS_BASE + OFFSET_NPU_STATUS
ADDR_NPU_SCORE0    = KWS_BASE + OFFSET_NPU_SCORE0
ADDR_NPU_SCORE1    = KWS_BASE + OFFSET_NPU_SCORE1
ADDR_NPU_FEAT_BASE = KWS_BASE + OFFSET_NPU_FEAT_BASE
ADDR_NPU_WGT_BASE  = KWS_BASE + OFFSET_NPU_WGT_BASE
ADDR_DEBUG_LEDS    = SYS_BASE

# Status LED Bit Definitions
LED_BOOTING         = 0x01
LED_SYS_READY       = 0x02
LED_STANDBY_SLEEP   = 0x04
LED_VOICE_DETECTED  = 0x08
LED_KEYWORD_MATCH   = 0xAA
LED_KEYWORD_MISMATCH= 0x55

# ABI Register Names (x0 - x31)
ABI_REG_NAMES = [
    "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
    "s0",   "s1", "a0", "a1", "a2", "a3", "a4", "a5",
    "a6",   "a7", "s2", "s3", "s4", "s5", "s6", "s7",
    "s8",   "s9", "s10", "s11", "t3", "t4", "t5", "t6"
]

# Integer helper functions
def u32(val: int) -> int:
    """Mask to unsigned 32-bit integer."""
    return val & 0xFFFF_FFFF

def s32(val: int) -> int:
    """Convert unsigned 32-bit integer to signed 32-bit integer."""
    v = val & 0xFFFF_FFFF
    return v - 0x1_0000_0000 if v >= 0x8000_0000 else v

def u16(val: int) -> int:
    return val & 0xFFFF

def s16(val: int) -> int:
    v = val & 0xFFFF
    return v - 0x1_0000 if v >= 0x8000 else v

def u8(val: int) -> int:
    return val & 0xFF

def s8(val: int) -> int:
    v = val & 0xFF
    return v - 0x100 if v >= 0x80 else v

def sign_extend(val: int, bits: int) -> int:
    sign_bit = 1 << (bits - 1)
    return (val & (sign_bit - 1)) - (val & sign_bit)
