"""
Smartwatch SoC Top-Level System Simulator
Integrates CPU, Memory, Bus, AFE, VAD, NPU, Power Profiler, and VCD.
"""

from typing import Optional, List, Dict, Any, Callable
from .types import (
    SYS_CLK_FREQ, PDM_CLK_FREQ, SYS_TO_PDM_RATIO,
    LED_BOOTING, LED_SYS_READY, LED_STANDBY_SLEEP,
    LED_VOICE_DETECTED, LED_KEYWORD_MATCH, LED_KEYWORD_MISMATCH
)
from .cpu import RiscvCpu
from .bus import SoCBus
from .afe import AudioFrontEnd
from .vad import HardwareVad
from .npu import KwsNpu
from .power import PowerProfiler
from .vcd import VcdWriter

class SmartwatchSoC:
    def __init__(self, firmware_hex: Optional[str] = "sw/firmware.hex", vcd_output: Optional[str] = None):
        self.afe = AudioFrontEnd()
        self.vad = HardwareVad()
        self.npu = KwsNpu()
        self.bus = SoCBus(self.afe, self.vad, self.npu)
        self.cpu = RiscvCpu(self.bus)
        self.power = PowerProfiler(SYS_CLK_FREQ)
        
        self.vcd: Optional[VcdWriter] = None
        if vcd_output:
            self.vcd = VcdWriter(vcd_output)
            
        self.total_cycles = 0
        self.pdm_clock_divider = 0
        self.instruction_trace: List[Dict[str, Any]] = []
        self.max_trace_history = 200
        
        # Audio stream feeder queue
        self.pending_pcm_samples: List[int] = []
        self.pending_pdm_bits: List[int] = []

        if firmware_hex:
            self.load_firmware(firmware_hex)
        self.reset()

    def reset(self):
        self.afe.reset()
        self.vad.reset()
        self.npu.reset()
        self.bus.reset()
        self.cpu.reset()
        self.power.reset()
        self.total_cycles = 0
        self.pdm_clock_divider = 0
        self.instruction_trace.clear()

    def load_firmware(self, hex_path: str):
        self.bus.load_rom_hex(hex_path)

    def load_firmware_words(self, words: list):
        self.bus.load_rom_words(words)

    def feed_pdm_bits(self, bits: List[int]):
        self.pending_pdm_bits.extend(bits)

    def feed_pcm_samples(self, samples: List[int]):
        self.pending_pcm_samples.extend(samples)

    def step_single_cycle(self):
        """
        Advance full SoC by 1 system clock cycle (81.38 ns @ 12.288 MHz).
        """
        # 1. Update Microphone & Audio Front-End every 12 clock cycles
        self.pdm_clock_divider += 1
        if self.pdm_clock_divider >= SYS_TO_PDM_RATIO:
            self.pdm_clock_divider = 0
            
            # Feed next PDM bit if available
            if self.pending_pdm_bits:
                bit = self.pending_pdm_bits.pop(0)
                pcm = self.afe.cic.step(bit)
                if pcm is not None:
                    self.afe.fifo.push(pcm)
                    # Feed sample directly into Hardware VAD
                    self.vad.feed_sample(pcm)
            elif self.pending_pcm_samples:
                # Fast PCM simulation bypass
                pcm = self.pending_pcm_samples.pop(0)
                self.afe.fifo.push(pcm)
                self.vad.feed_sample(pcm)

        # 2. Synchronize Interrupt Signals to CPU
        # IRQ 0: VAD Wakeup Interrupt
        # IRQ 1: NPU Done Interrupt
        self.cpu.set_irq(0, self.vad.irq_vad_wakeup)
        self.cpu.set_irq(1, self.npu.irq_npu_done)

        # 3. Step NPU FSM
        self.npu.step(cycles=1)

        # 4. Step CPU
        trace_info = self.cpu.step()
        if len(self.instruction_trace) >= self.max_trace_history:
            self.instruction_trace.pop(0)
        self.instruction_trace.append(trace_info)

        cycles = trace_info.get("cycles", 1)
        self.total_cycles += cycles

        # 5. Record Power Profile
        self.power.step(
            is_cpu_sleeping=self.cpu.is_sleeping,
            is_npu_active=self.npu.busy,
            cycles=cycles
        )

        # 6. Record Waveform Changes
        if self.vcd:
            self.vcd.dump_change(
                time_step=self.total_cycles,
                current_vals={
                    "clk": 1,
                    "rst_n": 1,
                    "pc": self.cpu.pc,
                    "debug_leds": self.bus.debug_leds,
                    "irq_vad": 1 if self.vad.irq_vad_wakeup else 0,
                    "irq_npu": 1 if self.npu.irq_npu_done else 0,
                    "cpu_sleeping": 1 if self.cpu.is_sleeping else 0,
                    "npu_busy": 1 if self.npu.busy else 0,
                    "vad_energy": self.vad.current_frame_energy,
                    "speech_active": 1 if self.vad.speech_active else 0,
                }
            )

        return trace_info

    def step_instruction(self) -> Dict[str, Any]:
        """
        Steps until one CPU instruction completes or state updates.
        """
        return self.step_single_cycle()

    def run_cycles(self, num_cycles: int) -> int:
        target_cycle = self.total_cycles + num_cycles
        steps = 0
        while self.total_cycles < target_cycle:
            self.step_single_cycle()
            steps += 1
            if self.cpu.trapped:
                break
        return steps

    def run_until(self, condition_fn: Callable[['SmartwatchSoC'], bool], max_cycles: int = 500_000) -> bool:
        start_cycle = self.total_cycles
        while (self.total_cycles - start_cycle) < max_cycles:
            if condition_fn(self):
                return True
            self.step_single_cycle()
            if self.cpu.trapped:
                return False
        return False

    def close(self):
        if self.vcd:
            self.vcd.close()

    def get_system_status(self) -> Dict[str, Any]:
        leds = self.bus.debug_leds
        led_desc = "Unknown"
        if leds == LED_BOOTING: led_desc = "Booting (0x01)"
        elif leds == LED_SYS_READY: led_desc = "System Ready (0x02)"
        elif leds == LED_STANDBY_SLEEP: led_desc = "Standby Sleep <20uW (0x04)"
        elif leds == LED_VOICE_DETECTED: led_desc = "Voice Detected -> Processing NPU (0x08)"
        elif leds == LED_KEYWORD_MATCH: led_desc = "Keyword MATCHED! Display Wakeup (0xAA)"
        elif leds == LED_KEYWORD_MISMATCH: led_desc = "Non-keyword -> Return to Sleep (0x55)"

        return {
            "total_cycles": self.total_cycles,
            "sim_time_ms": (self.total_cycles / SYS_CLK_FREQ) * 1000.0,
            "cpu": {
                "pc": f"0x{self.cpu.pc:08x}",
                "sleeping": self.cpu.is_sleeping,
                "in_irq": self.cpu.in_irq,
                "trapped": self.cpu.trapped,
                "instruction_count": self.cpu.instruction_count,
                "irq_mask": f"0x{self.cpu.irq_mask:08x}",
                "irq_pending": f"0x{self.cpu.irq_pending:08x}",
            },
            "leds": {
                "val": f"0x{leds:02x}",
                "desc": led_desc
            },
            "afe": {
                "enabled": self.afe.enable,
                "fifo_count": self.afe.fifo.count(),
                "fifo_empty": self.afe.fifo.is_empty(),
                "fifo_full": self.afe.fifo.is_full()
            },
            "vad": {
                "enabled": self.vad.enable,
                "threshold": self.vad.threshold,
                "current_energy": self.vad.current_frame_energy,
                "speech_active": self.vad.speech_active,
                "irq_pending": self.vad.irq_vad_wakeup
            },
            "npu": {
                "state": KwsNpu.STATE_NAMES.get(self.npu.state, "UNKNOWN"),
                "busy": self.npu.busy,
                "done": self.npu.done,
                "keyword_detected": self.npu.keyword_detected,
                "score_0": self.npu.score_0,
                "score_1": self.npu.score_1,
                "irq_pending": self.npu.irq_npu_done
            },
            "power": self.power.get_summary()
        }
