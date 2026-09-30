"""
Smartwatch SoC Simulator Package
"""

from .types import *
from .cpu import RiscvCpu
from .bus import SoCBus
from .afe import AudioFrontEnd, AudioFifo, CicDecimatorQ64
from .vad import HardwareVad
from .npu import KwsNpu
from .power import PowerProfiler
from .vcd import VcdWriter
from .soc import SmartwatchSoC
from .cli import InteractiveSimulatorCLI
from .dashboard import generate_dashboard_html
from .i18n import LANGUAGES, set_language, get_current_language, tr

__all__ = [
    "SmartwatchSoC",
    "RiscvCpu",
    "SoCBus",
    "AudioFrontEnd",
    "AudioFifo",
    "CicDecimatorQ64",
    "HardwareVad",
    "KwsNpu",
    "PowerProfiler",
    "VcdWriter",
    "InteractiveSimulatorCLI",
    "generate_dashboard_html",
    "LANGUAGES",
    "set_language",
    "get_current_language",
    "tr"
]
