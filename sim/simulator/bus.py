"""
SoC Interconnect Bus & Address Decoder
Matches rtl/top/smartwatch_soc_top.v address decoding logic.
"""

from typing import Optional
from .types import u32, u16, u8, ROM_BASE, ROM_SIZE, RAM_BASE, RAM_SIZE, KWS_BASE, KWS_SIZE, SYS_BASE
from .afe import AudioFrontEnd
from .vad import HardwareVad
from .npu import KwsNpu

class SoCBus:
    def __init__(self, afe: AudioFrontEnd, vad: HardwareVad, npu: KwsNpu):
        self.afe = afe
        self.vad = vad
        self.npu = npu
        
        # 8 KB Boot ROM & 8 KB Data SRAM
        self.rom = bytearray(ROM_SIZE)
        self.ram = bytearray(RAM_SIZE)
        
        # Debug LEDs
        self.debug_leds = 0x00
        
        # Access callbacks / listeners for logging & VCD tracing
        self.last_write = None # (addr, val, size)
        self.last_read = None  # (addr, val, size)

    def reset(self):
        self.ram = bytearray(RAM_SIZE)
        self.debug_leds = 0x00
        self.last_write = None
        self.last_read = None

    def load_rom_hex(self, hex_path: str):
        """Loads 32-bit hex firmware words into ROM"""
        with open(hex_path, "r") as f:
            lines = f.readlines()
        
        offset = 0
        for line in lines:
            line = line.strip()
            if not line or line.startswith("//") or line.startswith("#"):
                continue
            val = int(line, 16)
            # Store in Little Endian
            if offset + 4 <= len(self.rom):
                self.rom[offset + 0] = val & 0xFF
                self.rom[offset + 1] = (val >> 8) & 0xFF
                self.rom[offset + 2] = (val >> 16) & 0xFF
                self.rom[offset + 3] = (val >> 24) & 0xFF
                offset += 4

    def load_rom_words(self, words: list):
        offset = 0
        for val in words:
            if offset + 4 <= len(self.rom):
                self.rom[offset + 0] = val & 0xFF
                self.rom[offset + 1] = (val >> 8) & 0xFF
                self.rom[offset + 2] = (val >> 16) & 0xFF
                self.rom[offset + 3] = (val >> 24) & 0xFF
                offset += 4

    # -------------------------------------------------------------------------
    # Read Methods
    # -------------------------------------------------------------------------
    def read_u8(self, addr: int) -> int:
        return self._read(addr, 1)

    def read_u16(self, addr: int) -> int:
        return self._read(addr, 2)

    def read_u32(self, addr: int) -> int:
        return self._read(addr, 4)

    def _read(self, addr: int, size: int) -> int:
        addr = u32(addr)
        top4 = (addr >> 28) & 0xF
        val = 0

        # 0x0...: Boot ROM (8 KB)
        if top4 == 0x0:
            offset = addr & (ROM_SIZE - 1)
            for i in range(size):
                if offset + i < ROM_SIZE:
                    val |= (self.rom[offset + i] << (i * 8))

        # 0x1...: Data SRAM (8 KB)
        elif top4 == 0x1:
            offset = addr & (RAM_SIZE - 1)
            for i in range(size):
                if offset + i < RAM_SIZE:
                    val |= (self.ram[offset + i] << (i * 8))

        # 0x4...: KWS APB Subsystem
        elif top4 == 0x4:
            offset = addr & 0xFFF
            if offset < 0x010: # AFE
                word_val = self.afe.read_reg(offset & ~3)
            elif offset < 0x020: # VAD
                word_val = self.vad.read_reg(offset & ~3)
            elif offset < 0x040: # NPU control/status/score
                word_val = self.npu.read_reg(offset & ~3)
            elif 0x400 <= offset < 0x600: # NPU RAMs
                word_val = self.npu.read_reg(offset)
            else:
                word_val = 0
            
            shift = (addr & 3) * 8
            val = (word_val >> shift) & ((1 << (size * 8)) - 1)

        # 0x8...: System Status / LEDs
        elif top4 == 0x8:
            val = self.debug_leds & ((1 << (size * 8)) - 1)

        self.last_read = (addr, val, size)
        return val

    # -------------------------------------------------------------------------
    # Write Methods
    # -------------------------------------------------------------------------
    def write_u8(self, addr: int, val: int):
        self._write(addr, val & 0xFF, 1)

    def write_u16(self, addr: int, val: int):
        self._write(addr, val & 0xFFFF, 2)

    def write_u32(self, addr: int, val: int):
        self._write(addr, val & 0xFFFF_FFFF, 4)

    def _write(self, addr: int, val: int, size: int):
        addr = u32(addr)
        top4 = (addr >> 28) & 0xF

        # 0x1...: Data SRAM (8 KB)
        if top4 == 0x1:
            offset = addr & (RAM_SIZE - 1)
            for i in range(size):
                if offset + i < RAM_SIZE:
                    self.ram[offset + i] = (val >> (i * 8)) & 0xFF

        # 0x4...: KWS APB Subsystem
        elif top4 == 0x4:
            offset = addr & 0xFFF
            if offset < 0x010: # AFE
                self.afe.write_reg(offset & ~3, val)
            elif offset < 0x020: # VAD
                self.vad.write_reg(offset & ~3, val)
            elif offset < 0x040: # NPU
                self.npu.write_reg(offset & ~3, val)
            elif 0x400 <= offset < 0x600: # NPU RAMs
                self.npu.write_reg(offset, val)

        # 0x8...: System Debug LEDs
        elif top4 == 0x8:
            self.debug_leds = val & 0xFF

        self.last_write = (addr, val, size)
