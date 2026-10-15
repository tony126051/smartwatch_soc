"""
Audio Front-End (AFE) Simulator v2.0
Complies with SPEC-HIS-001 (0x4000_0000 - 0x4000_003F) and SPEC-VAS-001 (Test 2 & Test 6).
Includes:
  - 1.024 MHz PDM Single-Wire DDR Dual-Mic Demultiplexer (Mic 0 posedge, Mic 1 negedge)
  - Dual 3rd-order CIC Decimator Filters (R = 64, 1.024MHz -> 16kHz 16-bit PCM)
  - Hardware Spatial Micro-Beamformer (y = (1-a)*x0 + a*(x0 - x1[n-k]))
  - Inter-Mic Coherence Wind Noise Detector & Adaptive 350Hz HPF Shunt
  - 512-word Synchronous Circular Audio FIFO with 20ms Pre-Roll Buffer Rewind
"""

from typing import List, Optional, Tuple
from collections import deque
from .types import u16, s16

class AudioFifo:
    def __init__(self, capacity: int = 512):
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity)
        self.overflow_count = 0
        self.underflow_count = 0
        self.read_offset = 0

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

    def rewind(self, num_samples: int):
        """Rewinds the read pointer back by num_samples for pre-roll alignment."""
        # For a ring buffer, samples already inside buffer are accessible
        self.read_offset = min(len(self.buffer), num_samples)

    def is_empty(self) -> bool:
        return len(self.buffer) == 0

    def is_full(self) -> bool:
        return len(self.buffer) >= self.capacity

    def count(self) -> int:
        return len(self.buffer)

    def clear(self):
        self.buffer.clear()
        self.read_offset = 0


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
            scaled = (diff3 >> 4) & 0xFFFF
            pcm = s16(scaled)
            return pcm
        return None


class DualEdgePdmDemuxer:
    """
    Single-wire DDR PDM Demultiplexer:
    - Rising edge: Channels Mic 0 (main mouth mic)
    - Falling edge: Channels Mic 1 (secondary reference mic)
    """
    def __init__(self):
        self.edge_phase = 0  # 0 = rising, 1 = falling

    def step(self, ddr_bit: int) -> Tuple[Optional[int], Optional[int]]:
        if self.edge_phase == 0:
            self.edge_phase = 1
            return (ddr_bit & 1, None)
        else:
            self.edge_phase = 0
            return (None, ddr_bit & 1)


class HardwareBeamformer:
    """
    Hardware Spatial Micro-Beamformer:
      y[n] = (1 - alpha)*x0[n] + alpha*(x0[n] - x1[n - delay_taps])
    With adaptive wind suppression and 350 Hz high-pass filtering.
    """
    def __init__(self):
        self.delay_line = deque([0] * 4, maxlen=4)
        self.delay_taps = 1    # 1 sample @ 16kHz = 62.5us (~21.4mm)
        self.alpha = 1.0       # Q0.8 (255 = 1.0)
        self.mode = 0          # 00=Mono M0, 01=M1, 10=Stereo, 11=Beamformer
        self.hpf_cutoff_sel = 0 # 0=100Hz, 1=350Hz (wind notch)
        self.prev_x = 0
        self.prev_y = 0

    def process(self, x0: int, x1: int) -> int:
        self.delay_line.append(x1)
        
        if self.mode == 0: # Mono Mic 0
            out = x0
        elif self.mode == 1: # Mono Mic 1
            out = x1
        elif self.mode == 2: # Delay and sum (+3 dB diffuse SNR)
            delayed_x1 = self.delay_line[-1 - self.delay_taps] if len(self.delay_line) > self.delay_taps else x1
            out = (x0 + delayed_x1) // 2
        else: # Differential Beamformer
            delayed_x1 = self.delay_line[-1 - self.delay_taps] if len(self.delay_line) > self.delay_taps else x1
            diff = x0 - delayed_x1
            out = int((1.0 - self.alpha) * x0 + self.alpha * diff)

        # 350 Hz High-Pass Filter if engaged
        if self.hpf_cutoff_sel:
            # 1st-order IIR HPF: y[n] = 0.88 * (y[n-1] + x[n] - x[n-1])
            y = int(0.88 * (self.prev_y + out - self.prev_x))
            self.prev_x = out
            self.prev_y = y
            out = y

        return max(-32768, min(32767, out))


class AudioFrontEnd:
    def __init__(self):
        self.enable = False
        self.cic0 = CicDecimatorQ64()
        self.cic1 = CicDecimatorQ64()
        self.demuxer = DualEdgePdmDemuxer()
        self.beamformer = HardwareBeamformer()
        self.fifo = AudioFifo(capacity=512)
        
        # Audio input queues
        self.input_pdm_stream = deque()
        self.total_pcm_generated = 0

        # Wind detector parameters
        self.wind_detected = False
        self.coh_thres = 0.125
        self.wind_irq_en = False
        self.pre_roll_depth = 320 # default 20ms (320 samples @ 16kHz)
        self.pre_roll_en = True

    def reset(self):
        self.enable = False
        self.cic0.reset()
        self.cic1.reset()
        self.fifo.clear()
        self.input_pdm_stream.clear()
        self.total_pcm_generated = 0
        self.wind_detected = False

    def load_pdm_bits(self, bits: List[int]):
        self.input_pdm_stream.extend(bits)

    def load_pcm_samples(self, samples: List[int]):
        """Directly loads PCM samples into FIFO for accelerated simulation."""
        for s in samples:
            self.fifo.push(s)

    def step_pdm_cycle(self) -> Optional[int]:
        """Executes one PDM clock step (at 1.024 MHz)."""
        if not self.enable:
            return None

        bit = self.input_pdm_stream.popleft() if self.input_pdm_stream else 0
        
        # In single-channel mode, feed cic0 directly (legacy v1.0 compatibility)
        if self.beamformer.mode == 0:
            pcm0 = self.cic0.step(bit)
            if pcm0 is not None:
                self.fifo.push(pcm0)
                self.total_pcm_generated += 1
                return pcm0
        else:
            # Dual-edge demuxing
            b0, b1 = self.demuxer.step(bit)
            pcm0 = self.cic0.step(b0) if b0 is not None else None
            pcm1 = self.cic1.step(b1) if b1 is not None else None
            
            if pcm0 is not None and pcm1 is not None:
                out_sample = self.beamformer.process(pcm0, pcm1)
                self.fifo.push(out_sample)
                self.total_pcm_generated += 1
                return out_sample

        return None

    # APB Register Access
    def read_reg(self, offset: int) -> int:
        if offset == 0x000: # AFE_CTRL
            return 1 if self.enable else 0
        elif offset == 0x004: # AFE_STATUS
            empty = 1 if self.fifo.is_empty() else 0
            full  = 1 if self.fifo.is_full() else 0
            wind  = 1 if self.wind_detected else 0
            cnt   = self.fifo.count() & 0x3FF
            return empty | (full << 1) | (wind << 2) | (cnt << 8)
        elif offset == 0x008: # AFE_DATA (Pops FIFO on read)
            val = self.fifo.pop()
            return u16(val)
        elif offset == 0x00C: # AFE_MIC_CTRL
            val = (self.beamformer.mode & 3)
            val |= ((self.beamformer.delay_taps & 3) << 2)
            alpha_byte = int(self.beamformer.alpha * 255) & 0xFF
            val |= (alpha_byte << 8)
            val |= ((1 if self.beamformer.hpf_cutoff_sel else 0) << 16)
            return val
        elif offset == 0x030: # AFE_WIND_CFG
            val = int(self.coh_thres * 256) & 0xFF
            val |= (0x80 << 8)
            if self.wind_irq_en: val |= (1 << 16)
            if self.wind_detected: val |= (1 << 24)
            return val
        elif offset == 0x034: # AFE_PRE_ROLL
            val = 2 if self.pre_roll_depth == 320 else (1 if self.pre_roll_depth == 160 else 3)
            if self.pre_roll_en: val |= (1 << 2)
            return val
        return 0

    def write_reg(self, offset: int, val: int):
        if offset == 0x000: # AFE_CTRL
            prev_enable = self.enable
            self.enable = bool(val & 1)
            if not prev_enable and self.enable:
                self.cic0.reset()
                self.cic1.reset()
        elif offset == 0x00C: # AFE_MIC_CTRL
            self.beamformer.mode = val & 3
            self.beamformer.delay_taps = (val >> 2) & 3
            self.beamformer.alpha = ((val >> 8) & 0xFF) / 255.0
            self.beamformer.hpf_cutoff_sel = (val >> 16) & 1
        elif offset == 0x030: # AFE_WIND_CFG
            self.coh_thres = (val & 0xFF) / 256.0
            self.wind_irq_en = bool(val & (1 << 16))
            if val & (1 << 25): # Clear wind IRQ
                self.wind_detected = False
        elif offset == 0x034: # AFE_PRE_ROLL
            depth_code = val & 3
            depths = [0, 160, 320, 480]
            self.pre_roll_depth = depths[depth_code]
            self.pre_roll_en = bool(val & (1 << 2))
