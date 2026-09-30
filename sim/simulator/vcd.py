"""
VCD (Value Change Dump) Waveform Generator
Generates standard IEEE 1364 VCD files viewable in GTKWave or PulseView.
"""

from typing import Dict, Any

class VcdWriter:
    def __init__(self, filename: str):
        self.filename = filename
        self.file = open(filename, "w")
        self.time_ns = 0
        self.signals = {}
        self.prev_values = {}
        self.header_written = False

        self._register_signals()
        self._write_header()

    def _register_signals(self):
        # (name, width, identifier)
        self.sig_defs = [
            ("clk", 1, "A"),
            ("rst_n", 1, "B"),
            ("pc", 32, "C"),
            ("debug_leds", 8, "D"),
            ("irq_vad", 1, "E"),
            ("irq_npu", 1, "F"),
            ("cpu_sleeping", 1, "G"),
            ("npu_busy", 1, "H"),
            ("vad_energy", 24, "I"),
            ("speech_active", 1, "J"),
        ]

    def _write_header(self):
        self.file.write("$date\n  Simulated SoC Execution\n$end\n")
        self.file.write("$version\n  Smartwatch SoC Simulator VCD Writer 1.0\n$end\n")
        self.file.write("$timescale 10ns $end\n")
        self.file.write("$scope module smartwatch_soc $end\n")
        for name, width, sym in self.sig_defs:
            self.file.write(f"$var wire {width} {sym} {name} $end\n")
        self.file.write("$upscope $end\n")
        self.file.write("$enddefinitions $end\n")
        self.file.write("$dumpvars\n")
        for name, width, sym in self.sig_defs:
            if width == 1:
                self.file.write(f"0{sym}\n")
            else:
                self.file.write(f"b0 {sym}\n")
        self.file.write("$end\n")
        self.header_written = True

    def dump_change(self, time_step: int, current_vals: Dict[str, int]):
        time_changed = False
        for name, width, sym in self.sig_defs:
            val = current_vals.get(name, 0)
            if self.prev_values.get(name) != val:
                if not time_changed:
                    self.file.write(f"#{time_step}\n")
                    time_changed = True
                if width == 1:
                    self.file.write(f"{1 if val else 0}{sym}\n")
                else:
                    self.file.write(f"b{bin(val)[2:]} {sym}\n")
                self.prev_values[name] = val

    def close(self):
        if self.file and not self.file.closed:
            self.file.close()
