"""
Power Consumption & Energy Profiler
Estimates real-time power dissipation, energy usage, and battery life
based on the Smartwatch SoC specification:
  - Always-on Standby (AFE + VAD, CPU sleeping): < 20 uW (typical 18.5 uW)
  - CPU Active (12.288 MHz PicoRV32): ~1.25 mW
  - NPU Active (Level-2 DS-CNN inference): ~3.82 mW
"""

from typing import Dict, Any
from .types import SYS_CLK_FREQ

class PowerProfiler:
    P_STANDBY_UW = 18.5       # Micro-watts in deep sleep with VAD active
    P_CPU_ACTIVE_UW = 1250.0  # 1.25 mW when CPU is executing
    P_NPU_ACTIVE_UW = 3820.0  # 3.82 mW when NPU MAC array is running
    
    # Typical wearable battery: 200 mAh @ 3.7V nominal = 740 mWh
    DEFAULT_BATTERY_MAH = 200.0
    DEFAULT_VOLTAGE_V   = 3.7

    def __init__(self, clk_freq: int = SYS_CLK_FREQ):
        self.clk_freq = clk_freq
        self.reset()

    def reset(self):
        self.cycles_sleep = 0
        self.cycles_cpu_active = 0
        self.cycles_npu_active = 0
        self.total_cycles = 0

    def step(self, is_cpu_sleeping: bool, is_npu_active: bool, cycles: int = 1):
        self.total_cycles += cycles
        
        if is_npu_active:
            self.cycles_npu_active += cycles
        elif not is_cpu_sleeping:
            self.cycles_cpu_active += cycles
        else:
            self.cycles_sleep += cycles

    @property
    def total_time_sec(self) -> float:
        return self.total_cycles / self.clk_freq if self.clk_freq > 0 else 0.0

    @property
    def total_energy_uj(self) -> float:
        """Total energy consumed in micro-Joules (uJ)"""
        t_sleep = self.cycles_sleep / self.clk_freq
        t_cpu   = self.cycles_cpu_active / self.clk_freq
        t_npu   = self.cycles_npu_active / self.clk_freq
        
        e_sleep = t_sleep * self.P_STANDBY_UW
        e_cpu   = t_cpu   * self.P_CPU_ACTIVE_UW
        e_npu   = t_npu   * self.P_NPU_ACTIVE_UW
        return e_sleep + e_cpu + e_npu

    @property
    def average_power_uw(self) -> float:
        """Average power dissipation in micro-watts (uW)"""
        t = self.total_time_sec
        return (self.total_energy_uj / t) if t > 0 else self.P_STANDBY_UW

    def estimate_battery_life_days(self, battery_mah: float = DEFAULT_BATTERY_MAH, voltage_v: float = DEFAULT_VOLTAGE_V) -> float:
        """
        Projects battery lifetime in days.
        """
        battery_energy_uwh = battery_mah * 1000.0 * voltage_v  # uWh
        avg_power = self.average_power_uw
        if avg_power <= 0:
            return 9999.0
        hours = battery_energy_uwh / avg_power
        return hours / 24.0

    def get_summary(self) -> Dict[str, Any]:
        tot_c = max(1, self.total_cycles)
        return {
            "total_time_ms": self.total_time_sec * 1000.0,
            "total_cycles": self.total_cycles,
            "sleep_pct": (self.cycles_sleep / tot_c) * 100.0,
            "cpu_active_pct": (self.cycles_cpu_active / tot_c) * 100.0,
            "npu_active_pct": (self.cycles_npu_active / tot_c) * 100.0,
            "total_energy_uj": self.total_energy_uj,
            "average_power_uw": self.average_power_uw,
            "battery_life_days": self.estimate_battery_life_days()
        }
