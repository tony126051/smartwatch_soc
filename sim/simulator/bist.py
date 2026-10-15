#!/usr/bin/env python3
"""
Hardware Production BIST & MISR Simulator
Complies with SPEC-HIS-001 (0x4000_00F8 / 0x4000_00FC) and SPEC-VAS-001 (Test 7).
Zero external dependencies (pure Python standard library).
"""

from typing import Dict, Any

class BistEngine:
    """
    Hardware 5ms ATE Production BIST Subsystem.
    Contains:
      - 32-bit Galois LFSR PRPG (seed: 0x5A5AA5A5)
      - 32-bit MISR Compactor (poly: x^32 + x^22 + x^2 + x + 1)
      - 16-bit cycle counter (61,440 cycles = 5.00 ms @ 12.288 MHz)
      - Pass/Fail comparator against GOLDEN_SIGNATURE (0x92B6CDA5)
    """
    TOTAL_CYCLES = 61440
    LFSR_SEED = 0x5A5AA5A5
    MISR_SEED = 0x00000000
    GOLDEN_SIGNATURE = 0x92B6CDA5
    POLY_MASK = 0x80200003

    def __init__(self):
        self.reset()

    def reset(self):
        self.lfsr_state = self.LFSR_SEED
        self.misr_state = self.MISR_SEED
        self.cycle_count = 0
        self.busy = False
        self.done = False
        self.pass_flag = False
        self.fail_flag = False
        self.mode = 0

        # Internal simulated nodes
        self.cic_integrator = 0
        self.vad_energy = 0
        self.npu_mac_acc = 0

    def start(self, mode: int = 0):
        self.reset()
        self.busy = True
        self.mode = mode

    def step(self, cycles: int = 1, fault_injection_mask: int = 0):
        """Advances BIST simulation by `cycles` clock ticks."""
        if not self.busy or self.done:
            return

        for _ in range(cycles):
            if self.cycle_count >= self.TOTAL_CYCLES:
                self.busy = False
                self.done = True
                if self.misr_state == self.GOLDEN_SIGNATURE:
                    self.pass_flag = True
                    self.fail_flag = False
                else:
                    self.pass_flag = False
                    self.fail_flag = True
                break

            # 1. Step LFSR (Galois PRPG)
            lsb = self.lfsr_state & 1
            self.lfsr_state = (self.lfsr_state >> 1) & 0x7FFFFFFF
            if lsb:
                self.lfsr_state ^= (self.POLY_MASK >> 1)

            # 2. Pipeline Node Excitation
            prbs = self.lfsr_state
            pdm_bit = prbs & 1
            self.cic_integrator = (self.cic_integrator + (1 if pdm_bit else -1)) & 0x3FFFFF

            pcm_sample = (prbs >> 4) & 0xFFFF
            vad_abs = (pcm_sample if pcm_sample < 32768 else 65536 - pcm_sample)
            self.vad_energy = (self.vad_energy + vad_abs) & 0xFFFFFF

            w_int8 = (prbs >> 12) & 0xFF
            f_int8 = (prbs >> 20) & 0xFF
            w_s8 = w_int8 if w_int8 < 128 else w_int8 - 256
            f_s8 = f_int8 if f_int8 < 128 else f_int8 - 256
            self.npu_mac_acc = (self.npu_mac_acc + w_s8 * f_s8) & 0xFFFFFFFF

            # 3. Assemble observation bus
            obs_bus = (
                ((self.cic_integrator & 0x3FF) << 22) |
                ((self.vad_energy & 0x3FF) << 12) |
                (self.npu_mac_acc & 0xFFF)
            ) & 0xFFFFFFFF

            # Apply fault injection if requested
            if fault_injection_mask:
                obs_bus ^= fault_injection_mask

            # 4. Step MISR
            bit31 = (self.misr_state >> 31) & 1
            next_state = ((self.misr_state << 1) & 0xFFFFFFFF) ^ obs_bus
            if bit31:
                next_state ^= self.POLY_MASK
            self.misr_state = next_state & 0xFFFFFFFF

            self.cycle_count += 1

    def run_full(self, fault_mask: int = 0) -> int:
        """Executes full 61,440-cycle run in one shot."""
        self.start()
        self.step(cycles=self.TOTAL_CYCLES, fault_injection_mask=fault_mask)
        # Flush evaluation
        if self.busy:
            self.step(cycles=1)
        return self.misr_state

    # APB Register Read/Write Handlers
    def read_reg(self, offset: int) -> int:
        if offset == 0x0F8:  # BIST_SIGNATURE
            return self.misr_state
        elif offset == 0x0FC:  # BIST_CTRL
            val = 0
            if self.busy: val |= (1 << 1)
            if self.done: val |= (1 << 2)
            if self.pass_flag: val |= (1 << 3)
            if self.fail_flag: val |= (1 << 4)
            val |= ((self.mode & 0x7) << 5)
            return val
        return 0

    def write_reg(self, offset: int, val: int):
        if offset == 0x0FC:  # BIST_CTRL
            if val & 1:  # BIST_START
                mode = (val >> 5) & 0x7
                self.start(mode=mode)
