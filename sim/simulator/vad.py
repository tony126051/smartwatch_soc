"""
Hardware Voice Activity Detector (VAD) Core Simulator
Matches rtl/vad/vad_core.v and model/golden_vad.py
Always-on ultra-low power first-stage filter.
"""

from typing import Tuple

class HardwareVad:
    def __init__(self):
        self.enable = False
        self.threshold = 200_000
        self.hangover_limit = 3
        
        # Internal State
        self.sample_idx = 0
        self.accum_energy = 0
        self.current_frame_energy = 0
        self.speech_active = False
        self.hangover_cnt = 0
        self.speech_detected_prev = False
        
        # Interrupt Flag
        self.irq_vad_wakeup = False
        
        # Diagnostics
        self.total_frames = 0
        self.speech_frames = 0

    def reset(self):
        self.enable = False
        self.threshold = 200_000
        self.hangover_limit = 3
        self.sample_idx = 0
        self.accum_energy = 0
        self.current_frame_energy = 0
        self.speech_active = False
        self.hangover_cnt = 0
        self.speech_detected_prev = False
        self.irq_vad_wakeup = False
        self.total_frames = 0
        self.speech_frames = 0

    def feed_sample(self, pcm_sample: int) -> bool:
        """
        Feeds one 16-bit PCM sample (16 kHz).
        Returns True if a new frame boundary (160 samples) was reached.
        """
        if not self.enable:
            return False

        abs_val = abs(pcm_sample) & 0xFFFF
        self.accum_energy += abs_val
        self.sample_idx += 1

        if self.sample_idx >= 160:
            self.current_frame_energy = self.accum_energy
            self.total_frames += 1
            
            # Threshold decision
            raw_speech = (self.current_frame_energy >= self.threshold)
            if raw_speech:
                self.hangover_cnt = self.hangover_limit
                self.speech_active = True
                self.speech_frames += 1
            elif self.hangover_cnt > 0:
                self.hangover_cnt -= 1
                self.speech_active = True
                self.speech_frames += 1
            else:
                self.speech_active = False

            # Rising-edge detection for wakeup IRQ
            if self.speech_active and not self.speech_detected_prev:
                self.irq_vad_wakeup = True

            self.speech_detected_prev = self.speech_active
            
            # Reset accumulator for next frame
            self.accum_energy = 0
            self.sample_idx = 0
            return True

        return False

    # APB Register Interface
    def read_reg(self, offset: int) -> int:
        if offset == 0x010: # VAD_CTRL
            bit0 = 1 if self.enable else 0
            bit1 = 1 if self.irq_vad_wakeup else 0
            return bit0 | (bit1 << 1)
        elif offset == 0x014: # VAD_THRESHOLD
            return self.threshold & 0xFF_FFFF
        elif offset == 0x018: # VAD_HANGOVER
            return self.hangover_limit & 0x0F
        elif offset == 0x01C: # VAD_ENERGY
            energy = self.current_frame_energy & 0xFF_FFFF
            speech = 1 if self.speech_active else 0
            return energy | (speech << 24)
        return 0

    def write_reg(self, offset: int, val: int):
        if offset == 0x010: # VAD_CTRL
            self.enable = bool(val & 1)
            # Write 1 to bit 1 clears IRQ
            if val & 2:
                self.irq_vad_wakeup = False
        elif offset == 0x014: # VAD_THRESHOLD
            self.threshold = val & 0xFF_FFFF
        elif offset == 0x018: # VAD_HANGOVER
            self.hangover_limit = val & 0x0F
