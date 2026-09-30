"""
Audio Front-End (AFE) Simulator
Includes:
  - 1.024 MHz PDM bit receiver
  - 3rd-order CIC Decimator Filter (R = 64, 1.024MHz -> 16kHz 16-bit PCM)
  - 256-word Synchronous Circular Audio FIFO
"""

from typing import List, Optional
from collections import deque
from .types import u16, s16

class AudioFifo:
    def __init__(self, capacity: int = 256):
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity)
        self.overflow_count = 0
        self.underflow_count = 0

    def push(self, sample: int) -> bool:
        if len(self.buffer) >= self.capacity:
            self.overflow_count += 1
            return False
        self.buffer.append(s16(sample))
        return True

    def pop(self) -> int:
        if len(self.buffer) == 0:
            self.underflow_count += 1
            return 0
        return self.buffer.popleft()

    def is_empty(self) -> bool:
        return len(self.buffer) == 0

    def is_full(self) -> bool:
        return len(self.buffer) >= self.capacity

    def count(self) -> int:
        return len(self.buffer)

    def clear(self):
        self.buffer.clear()

class CicDecimatorQ64:
    """
    3rd-order CIC Decimator filter matching rtl/afe/cic_decimator_q64.v
    R = 64, N = 3
    """
    def __init__(self):
        self.reset()

    def reset(self):
        # Integrator accumulators (signed 22-bit)
        self.itg1 = 0
        self.itg2 = 0
        self.itg3 = 0
        # Comb delay registers
        self.d1 = 0
        self.d2 = 0
        self.d3 = 0
        self.decim_cnt = 0

    def step(self, pdm_bit: int) -> Optional[int]:
        """
        Step one 1.024 MHz PDM bit (0 or 1).
        Returns 16-bit signed PCM sample every 64 bits.
        """
        # Mapping 1 -> +1, 0 -> -1
        x_in = 1 if (pdm_bit & 1) else -1
        
        # 3 Integrator stages
        self.itg1 += x_in
        self.itg2 += self.itg1
        self.itg3 += self.itg2
        
        self.decim_cnt += 1
        if self.decim_cnt >= 64:
            self.decim_cnt = 0
            
            # 3 Comb differentiator stages
            diff1 = self.itg3 - self.d1
            self.d1 = self.itg3
            
            diff2 = diff1 - self.d2
            self.d2 = diff1
            
            diff3 = diff2 - self.d3
            self.d3 = diff2
            
            # Scale down and saturate to 16-bit signed PCM
            # Bit-true RTL truncation: (diff3 >> 4)
            scaled = (diff3 >> 4) & 0xFFFF
            pcm = s16(scaled)
            return pcm
        return None

class AudioFrontEnd:
    def __init__(self):
        self.enable = False
        self.cic = CicDecimatorQ64()
        self.fifo = AudioFifo(capacity=256)
        
        # Audio playback buffer (stream to feed)
        self.input_pdm_stream = deque()
        self.total_pcm_generated = 0

    def reset(self):
        self.enable = False
        self.cic.reset()
        self.fifo.clear()
        self.input_pdm_stream.clear()
        self.total_pcm_generated = 0

    def load_pdm_bits(self, bits: List[int]):
        self.input_pdm_stream.extend(bits)

    def load_pcm_samples(self, samples: List[int]):
        """
        Directly loads PCM samples into FIFO (useful for fast verification)
        """
        for s in samples:
            self.fifo.push(s)

    def step_pdm_cycle(self) -> Optional[int]:
        """
        Executes one PDM clock step (at 1.024 MHz).
        """
        if not self.enable:
            return None

        bit = self.input_pdm_stream.popleft() if self.input_pdm_stream else 0
        pcm = self.cic.step(bit)
        if pcm is not None:
            self.fifo.push(pcm)
            self.total_pcm_generated += 1
            return pcm
        return None

    # APB Register Access
    def read_reg(self, offset: int) -> int:
        if offset == 0x000: # AFE_CTRL
            return 1 if self.enable else 0
        elif offset == 0x004: # AFE_STATUS
            empty = 1 if self.fifo.is_empty() else 0
            full  = 1 if self.fifo.is_full() else 0
            cnt   = self.fifo.count() & 0x1FF
            return empty | (full << 1) | (cnt << 8)
        elif offset == 0x008: # AFE_DATA (Pops FIFO on read)
            val = self.fifo.pop()
            return u16(val)
        return 0

    def write_reg(self, offset: int, val: int):
        if offset == 0x000: # AFE_CTRL
            prev_enable = self.enable
            self.enable = bool(val & 1)
            if not prev_enable and self.enable:
                self.cic.reset()
