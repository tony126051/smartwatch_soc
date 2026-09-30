#!/usr/bin/env python3
"""
Real-Time Interactive Web Server for Smartwatch SoC Simulator
Bridges the HTML5 Web UI directly to the cycle-accurate Python SmartwatchSoC hardware engine.
"""

import sys
import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sim.simulator import SmartwatchSoC, ABI_REG_NAMES
from model.generate_stimulus import generate_pcm_scenario

# Global SoC Instance
soc = SmartwatchSoC(firmware_hex="sw/firmware.hex")

class SoCRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(PROJECT_ROOT, "sim"), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/" or parsed.path == "/index.html":
            self.path = "/smartwatch_simulator_ui.html"
            return super().do_GET()

        elif parsed.path == "/api/status":
            self.send_json_response(self.get_full_status())

        elif parsed.path == "/api/memory":
            qs = parse_qs(parsed.query)
            addr_str = qs.get("addr", ["0x10000000"])[0]
            len_str = qs.get("len", ["32"])[0]
            addr = int(addr_str, 16) if addr_str.startswith("0x") else int(addr_str)
            length = int(len_str)
            
            bytes_data = [soc.bus.read_u8(addr + i) for i in range(length)]
            self.send_json_response({"addr": hex(addr), "len": length, "bytes": bytes_data})

        else:
            return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        data = json.loads(post_body.decode("utf-8")) if post_body else {}

        if parsed.path == "/api/step":
            steps = data.get("steps", 1)
            for _ in range(steps):
                soc.step_single_cycle()
            self.send_json_response(self.get_full_status())

        elif parsed.path == "/api/run":
            max_c = data.get("max_cycles", 5000)
            target = soc.total_cycles + max_c
            while soc.total_cycles < target:
                soc.step_single_cycle()
                if soc.cpu.is_sleeping and not soc.vad.irq_vad_wakeup:
                    break
                if soc.cpu.trapped:
                    break
            self.send_json_response(self.get_full_status())

        elif parsed.path == "/api/reset":
            soc.reset()
            self.send_json_response(self.get_full_status())

        elif parsed.path == "/api/feed_audio":
            atype = data.get("type", "speech")
            if atype == "speech":
                soc.npu.force_keyword = True
                pcm = generate_pcm_scenario()
                soc.feed_pcm_samples(pcm[:160 * 10])
            elif atype == "tone":
                soc.npu.force_keyword = False
                import math
                pcm = [int(10000 * math.sin(2 * math.pi * 1000 * i / 16000)) for i in range(160 * 10)]
                soc.feed_pcm_samples(pcm)
            elif atype == "silence":
                soc.npu.force_keyword = False
                soc.feed_pcm_samples([0] * (160 * 10))
            self.send_json_response(self.get_full_status())

        else:
            self.send_error(404, "Endpoint not found")

    def get_full_status(self):
        st = soc.get_system_status()
        # Add register dump
        st["cpu"]["regs"] = {ABI_REG_NAMES[i]: f"0x{soc.cpu.regs[i]:08x}" for i in range(32)}
        st["trace"] = soc.instruction_trace[-8:]
        st["backend"] = "Real Python Cycle-Accurate SoC Hardware Engine"
        return st

    def send_json_response(self, data_dict):
        body = json.dumps(data_dict).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

def run_server(port: int = 8080):
    server = HTTPServer(("0.0.0.0", port), SoCRequestHandler)
    print(f"\n" + "=" * 70)
    print(f"  Smartwatch SoC Real-Time Web GUI Simulator Server")
    print(f"  Listening on: http://localhost:{port}")
    print(f"  Hardware Engine: Cycle-Accurate 32-bit RISC-V + AFE + VAD + NPU")
    print(f"=" * 70 + "\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        server.server_close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)
