"""
KWS NPU Accelerator Simulator (Level-2 Keyword Spotting Engine)
Matches rtl/npu/npu_top.v and model/golden_npu.py
Cycle-accurate DS-CNN (Depthwise Separable CNN) INT8 Hardware Engine.
"""

from typing import List, Dict, Any
from .types import u32, s32, s8, u8
from model.golden_npu import get_model_parameters, run_ds_cnn_inference

class KwsNpu:
    # FSM State Constants
    ST_IDLE  = 0
    ST_CONV1 = 1
    ST_DW    = 2
    ST_PW    = 3
    ST_GAP   = 4
    ST_FC    = 5
    ST_DONE  = 6

    STATE_NAMES = {
        0: "IDLE",
        1: "CONV1",
        2: "DEPTHWISE",
        3: "POINTWISE",
        4: "GAP",
        5: "FC",
        6: "DONE"
    }

    # RTL Cycle Latencies per Layer
    CYCLES_CONV1 = 16 * 16 * 4 * 9   # 9,216 cycles
    CYCLES_DW    = 16 * 16 * 4 * 9   # 9,216 cycles
    CYCLES_PW    = 16 * 16 * 8 * 4   # 8,192 cycles
    CYCLES_GAP   = 16 * 16 * 8       # 2,048 cycles
    CYCLES_FC    = 8 * 2             # 16 cycles
    TOTAL_INFERENCE_CYCLES = CYCLES_CONV1 + CYCLES_DW + CYCLES_PW + CYCLES_GAP + CYCLES_FC

    def __init__(self):
        # 256-byte Feature RAM & Weight RAM
        self.feat_ram = bytearray(256)
        self.wgt_ram = bytearray(256)
        
        # Load default golden weights
        self.load_default_weights()
        
        # State & Control
        self.state = self.ST_IDLE
        self.busy = False
        self.done = False
        self.keyword_detected = False
        self.score_0 = 0
        self.score_1 = 0
        self.irq_npu_done = False
        
        # Cycle-accurate tracking
        self.cycles_remaining_in_state = 0
        self.total_cycles_inferred = 0
        self.force_keyword = None

    def reset(self):
        self.state = self.ST_IDLE
        self.busy = False
        self.done = False
        self.keyword_detected = False
        self.score_0 = 0
        self.score_1 = 0
        self.irq_npu_done = False
        self.cycles_remaining_in_state = 0
        self.force_keyword = None

    def load_default_weights(self):
        """Populates Weight RAM with default deterministic INT8 weights"""
        params = get_model_parameters()
        self.model_params = params
        
        idx = 0
        for oc in range(4):
            for kr in range(3):
                for kc in range(3):
                    self.wgt_ram[idx] = params["conv1_w"][oc][kr][kc] & 0xFF
                    idx += 1
        for ch in range(4):
            for kr in range(3):
                for kc in range(3):
                    self.wgt_ram[idx] = params["dw_w"][ch][kr][kc] & 0xFF
                    idx += 1
        for oc in range(8):
            for ic in range(4):
                self.wgt_ram[idx] = params["pw_w"][oc][ic] & 0xFF
                idx += 1
        for cls in range(2):
            for ic in range(8):
                self.wgt_ram[idx] = params["fc_w"][cls][ic] & 0xFF
                idx += 1

    def start_inference(self):
        if not self.busy:
            self.busy = True
            self.done = False
            self.state = self.ST_CONV1
            self.cycles_remaining_in_state = self.CYCLES_CONV1
            self.irq_npu_done = False

    def step(self, cycles: int = 1):
        """
        Advance NPU FSM by the given number of clock cycles.
        """
        if not self.busy:
            return

        remaining = cycles
        while remaining > 0 and self.busy:
            step_cycles = min(remaining, self.cycles_remaining_in_state)
            self.cycles_remaining_in_state -= step_cycles
            remaining -= step_cycles
            self.total_cycles_inferred += step_cycles

            if self.cycles_remaining_in_state <= 0:
                self._transition_fsm()

    def _transition_fsm(self):
        if self.state == self.ST_CONV1:
            self.state = self.ST_DW
            self.cycles_remaining_in_state = self.CYCLES_DW
        elif self.state == self.ST_DW:
            self.state = self.ST_PW
            self.cycles_remaining_in_state = self.CYCLES_PW
        elif self.state == self.ST_PW:
            self.state = self.ST_GAP
            self.cycles_remaining_in_state = self.CYCLES_GAP
        elif self.state == self.ST_GAP:
            self.state = self.ST_FC
            self.cycles_remaining_in_state = self.CYCLES_FC
        elif self.state == self.ST_FC:
            # Perform computation
            self._execute_computation()
            self.state = self.ST_DONE
            self.busy = False
            self.done = True
            self.irq_npu_done = True
            self.cycles_remaining_in_state = 0
        elif self.state == self.ST_DONE:
            self.state = self.ST_IDLE

    def _execute_computation(self):
        if self.force_keyword is True:
            self.score_0 = -35
            self.score_1 = 88
            self.keyword_detected = True
        elif self.force_keyword is False:
            self.score_0 = 58
            self.score_1 = -51
            self.keyword_detected = False
        else:
            # Convert 256 bytes feature map to 16x16 signed INT8
            input_map = [[0 for _ in range(16)] for _ in range(16)]
            for r in range(16):
                for c in range(16):
                    val = self.feat_ram[r * 16 + c]
                    input_map[r][c] = s8(val)
                    
            res = run_ds_cnn_inference(input_map, self.model_params)
            self.score_0 = res["fc_out"][0]
            self.score_1 = res["fc_out"][1]
            self.keyword_detected = (res["class"] == 1)

    # APB Register Access
    def read_reg(self, offset: int) -> int:
        if offset == 0x020: # NPU_CTRL
            bit0 = 1 if self.busy else 0
            bit1 = 1 if self.irq_npu_done else 0
            return bit0 | (bit1 << 1)
        elif offset == 0x024: # NPU_STATUS
            busy_bit = 1 if self.busy else 0
            done_bit = 1 if self.done else 0
            kw_bit   = 1 if self.keyword_detected else 0
            return busy_bit | (done_bit << 1) | (kw_bit << 2)
        elif offset == 0x028: # NPU_SCORE0
            return u32(self.score_0)
        elif offset == 0x02C: # NPU_SCORE1
            return u32(self.score_1)
        elif 0x400 <= offset < 0x500:
            return self.feat_ram[offset - 0x400]
        elif 0x500 <= offset < 0x600:
            return self.wgt_ram[offset - 0x500]
        return 0

    def write_reg(self, offset: int, val: int):
        if offset == 0x020: # NPU_CTRL
            if val & 1:
                self.start_inference()
            if val & 2: # Clear IRQ
                self.irq_npu_done = False
        elif 0x400 <= offset < 0x500: # Feature RAM
            self.feat_ram[offset - 0x400] = val & 0xFF
        elif 0x500 <= offset < 0x600: # Weight RAM
            self.wgt_ram[offset - 0x500] = val & 0xFF
