"""
Interactive Command-Line Debugger & Simulator Interface for Smartwatch SoC
With Multi-Language (i18n) Support
"""

import sys
import os
from typing import Optional, Set
from .soc import SmartwatchSoC
from .types import ABI_REG_NAMES, s32
from .i18n import tr, set_language, get_current_language, LANGUAGES
from model.generate_stimulus import generate_pcm_scenario

class InteractiveSimulatorCLI:
    def __init__(self, firmware_hex: str = "sw/firmware.hex", vcd_output: Optional[str] = None, lang: str = "zh-TW"):
        self.firmware_hex = firmware_hex
        self.vcd_output = vcd_output
        self.soc = SmartwatchSoC(firmware_hex, vcd_output=vcd_output)
        self.breakpoints: Set[int] = set()
        self.lang = set_language(lang)

    def print_banner(self):
        print("=" * 72)
        print("  " + tr("banner_title", self.lang))
        print("  " + tr("banner_arch", self.lang))
        print("  " + tr("banner_specs", self.lang))
        print("=" * 72)
        print(tr("banner_prompt", self.lang))

    def run_cli(self):
        self.print_banner()
        while True:
            try:
                line = input(f"[SoC @ 0x{self.soc.cpu.pc:08x} | LED 0x{self.soc.bus.debug_leds:02x}] > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n" + tr("exiting", self.lang))
                break

            if not line:
                continue

            parts = line.split()
            cmd = parts[0].lower()
            args = parts[1:]

            if cmd in ("q", "quit", "exit"):
                print(tr("exiting", self.lang))
                break
            elif cmd in ("h", "help"):
                self.cmd_help()
            elif cmd in ("s", "step"):
                count = int(args[0]) if args else 1
                self.cmd_step(count)
            elif cmd in ("r", "run"):
                max_c = int(args[0]) if args else 100_000
                self.cmd_run(max_c)
            elif cmd in ("b", "break"):
                if args:
                    addr = int(args[0], 16) if args[0].startswith("0x") else int(args[0])
                    self.breakpoints.add(addr)
                    print(tr("bp_set", self.lang, addr=addr))
                else:
                    print(tr("bp_list", self.lang), [f"0x{b:08x}" for b in sorted(self.breakpoints)])
            elif cmd in ("del", "delete"):
                if args:
                    addr = int(args[0], 16) if args[0].startswith("0x") else int(args[0])
                    self.breakpoints.discard(addr)
                    print(tr("bp_removed", self.lang, addr=addr))
                else:
                    self.breakpoints.clear()
                    print(tr("bp_cleared", self.lang))
            elif cmd in ("regs", "reg"):
                self.cmd_regs()
            elif cmd in ("m", "mem"):
                self.cmd_mem(args)
            elif cmd in ("status", "stat"):
                self.cmd_status()
            elif cmd == "power":
                self.cmd_power()
            elif cmd == "feed":
                self.cmd_feed(args)
            elif cmd in ("lang", "language"):
                self.cmd_lang(args)
            elif cmd == "reset":
                self.soc.reset()
                print(tr("reset_done", self.lang))
            else:
                print(tr("unknown_cmd", self.lang, cmd=cmd))

    def cmd_help(self):
        print(f"\n{tr('help_title', self.lang)}")
        print(f"  step [N]                   : {tr('cmd_step_desc', self.lang)}")
        print(f"  run [max_cycles]           : {tr('cmd_run_desc', self.lang)}")
        print(f"  break <addr>               : {tr('cmd_break_desc', self.lang)}")
        print(f"  delete [addr]              : {tr('cmd_delete_desc', self.lang)}")
        print(f"  regs                       : {tr('cmd_regs_desc', self.lang)}")
        print(f"  mem <addr> [len]           : {tr('cmd_mem_desc', self.lang)}")
        print(f"  status                     : {tr('cmd_status_desc', self.lang)}")
        print(f"  feed [speech|tone|silence] : {tr('cmd_feed_desc', self.lang)}")
        print(f"  power                      : {tr('cmd_power_desc', self.lang)}")
        print(f"  lang [code]                : {tr('cmd_lang_desc', self.lang)}")
        print(f"  reset                      : {tr('cmd_reset_desc', self.lang)}")
        print(f"  quit                       : {tr('cmd_quit_desc', self.lang)}\n")

    def cmd_lang(self, args):
        if not args:
            print(f"Current language: {LANGUAGES.get(self.lang, self.lang)} ({self.lang})")
            print(tr("lang_list", self.lang))
            return
        code = args[0]
        new_lang = set_language(code)
        self.lang = new_lang
        print(tr("lang_switched", self.lang, name=LANGUAGES.get(self.lang, self.lang), code=self.lang))

    def cmd_step(self, count: int):
        for _ in range(count):
            trace = self.soc.step_single_cycle()
            pc = trace.get("pc", 0)
            disasm = trace.get("disasm", "")
            reg_wr = trace.get("reg_write")
            wr_str = f" -> {ABI_REG_NAMES[reg_wr[0]]} = 0x{reg_wr[1]:08x}" if reg_wr else ""
            print(f"  [PC 0x{pc:08x}] {disasm:<36}{wr_str}")
            if self.soc.cpu.pc in self.breakpoints:
                print(f"  *** " + tr("bp_hit", self.lang, steps=1, addr=self.soc.cpu.pc) + " ***")
                break
            if self.soc.cpu.trapped:
                print("  *** " + tr("trapped", self.lang, addr=self.soc.cpu.pc) + " ***")
                break

    def cmd_run(self, max_cycles: int):
        steps = 0
        hit_bp = False
        hit_sleep = False
        while steps < max_cycles:
            self.soc.step_single_cycle()
            steps += 1
            if self.soc.cpu.pc in self.breakpoints:
                hit_bp = True
                break
            if self.soc.cpu.is_sleeping and not self.soc.vad.irq_vad_wakeup:
                hit_sleep = True
                break
            if self.soc.cpu.trapped:
                break
                
        if hit_bp:
            print(tr("bp_hit", self.lang, steps=steps, addr=self.soc.cpu.pc))
        elif hit_sleep:
            print(tr("sleep_hit", self.lang, steps=steps, led=self.soc.bus.debug_leds))
        elif self.soc.cpu.trapped:
            print(tr("trapped", self.lang, steps=steps, addr=self.soc.cpu.pc))
        else:
            print(tr("run_done", self.lang, steps=steps, addr=self.soc.cpu.pc))

    def cmd_regs(self):
        print("-" * 65)
        print("  RISC-V RV32I Register File Dump")
        print("-" * 65)
        for i in range(0, 32, 4):
            line = ""
            for j in range(4):
                reg_idx = i + j
                name = ABI_REG_NAMES[reg_idx]
                val = self.soc.cpu.regs[reg_idx]
                line += f"  {name:>4}(x{reg_idx:<2}): 0x{val:08x}  "
            print(line)
        print(f"  PC : 0x{self.soc.cpu.pc:08x} | IRQ Mask: 0x{self.soc.cpu.irq_mask:08x} | Pending: 0x{self.soc.cpu.irq_pending:08x}")
        print("-" * 65)

    def cmd_mem(self, args):
        if not args:
            print("Usage: mem <addr_hex> [len_bytes]")
            return
        addr = int(args[0], 16) if args[0].startswith("0x") else int(args[0])
        length = int(args[1]) if len(args) > 1 else 16
        
        print(f"Memory dump @ 0x{addr:08x} ({length} bytes):")
        for i in range(0, length, 16):
            chunk_addr = addr + i
            bytes_hex = []
            ascii_chars = []
            for j in range(16):
                if i + j < length:
                    b = self.soc.bus.read_u8(chunk_addr + j)
                    bytes_hex.append(f"{b:02x}")
                    ascii_chars.append(chr(b) if 32 <= b <= 126 else ".")
                else:
                    bytes_hex.append("  ")
            hex_str = " ".join(bytes_hex[:8]) + "  " + " ".join(bytes_hex[8:])
            asc_str = "".join(ascii_chars)
            print(f"  0x{chunk_addr:08x}:  {hex_str}  |{asc_str}|")

    def cmd_status(self):
        st = self.soc.get_system_status()
        print("\n" + "=" * 60)
        print("  Smartwatch SoC Subsystem Status")
        print("=" * 60)
        print(f"  Simulation Time : {st['sim_time_ms']:.2f} ms ({st['total_cycles']} Clock Cycles)")
        print(f"  Debug Status LED: {st['leds']['val']} -> {st['leds']['desc']}")
        print(f"  CPU Core State  : PC = {st['cpu']['pc']}, Sleeping = {st['cpu']['sleeping']}, IRQ = {st['cpu']['in_irq']}")
        print(f"  Audio Front-End : Enabled = {st['afe']['enabled']}, FIFO Samples = {st['afe']['fifo_count']}/256")
        print(f"  Hardware VAD    : Enabled = {st['vad']['enabled']}, Energy = {st['vad']['current_energy']}, Voice Active = {st['vad']['speech_active']}")
        print(f"  KWS NPU Engine  : State = {st['npu']['state']}, Busy = {st['npu']['busy']}, Detected = {st['npu']['keyword_detected']}")
        print(f"  Classification  : Score Class 0 = {st['npu']['score_0']}, Score Class 1 = {st['npu']['score_1']}")
        print("=" * 60 + "\n")

    def cmd_power(self):
        p = self.soc.power.get_summary()
        days_label = "天" if self.lang.startswith("zh") else ("日" if self.lang == "ja" else "Days")
        months_label = "個月" if self.lang.startswith("zh") else ("ヶ月" if self.lang == "ja" else "Months")
        print("\n" + "-" * 55)
        print("  Real-time Power & Battery Life Analysis")
        print("-" * 55)
        print(f"  Simulated Duration   : {p['total_time_ms']:.2f} ms")
        print(f"  Deep Sleep Duty Ratio: {p['sleep_pct']:.1f} %")
        print(f"  CPU Active Ratio     : {p['cpu_active_pct']:.1f} %")
        print(f"  NPU Active Ratio     : {p['npu_active_pct']:.1f} %")
        print(f"  Total Energy Drawn   : {p['total_energy_uj']:.2f} uJ")
        print(f"  Average Power        : {p['average_power_uw']:.2f} uW")
        print(f"  Projected Battery Life (200mAh): {p['battery_life_days']:.1f} {days_label} ({p['battery_life_days'] / 30.4:.1f} {months_label})")
        print("-" * 55 + "\n")

    def cmd_feed(self, args):
        mode = args[0].lower() if args else "speech"
        if mode == "speech":
            pcm = generate_pcm_scenario()
            self.soc.feed_pcm_samples(pcm)
            print(tr("feed_done", self.lang, type=f"Speech ({len(pcm)} PCM samples)"))
        elif mode == "silence":
            pcm = [0] * (160 * 10)
            self.soc.feed_pcm_samples(pcm)
            print(tr("feed_done", self.lang, type=f"Silence ({len(pcm)} samples)"))
        elif mode == "tone":
            import math
            pcm = [int(10000 * math.sin(2 * math.pi * 1000 * i / 16000)) for i in range(160 * 10)]
            self.soc.feed_pcm_samples(pcm)
            print(tr("feed_done", self.lang, type=f"1000Hz Tone ({len(pcm)} samples)"))
        else:
            print(f"Unknown audio type: {mode}. Choices: speech, tone, silence.")
