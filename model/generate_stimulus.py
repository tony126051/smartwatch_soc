#!/usr/bin/env python3
"""
Audio Stimulus Generator for Smartwatch SoC Simulation
Generates 16kHz PCM audio scenarios (Silence, Noise, Tone, Keyword Pulse)
and encodes them into 1.024MHz PDM (Pulse Density Modulation) Bitstream
using a First-order Delta-Sigma Modulator.
"""

import math
import struct
import os

SAMPLE_RATE_PCM = 16000     # 16 kHz
DECIMATION_RATIO = 64       # 64x oversampling
SAMPLE_RATE_PDM = SAMPLE_RATE_PCM * DECIMATION_RATIO  # 1.024 MHz

def generate_pcm_scenario(duration_sec=0.1):
    """
    Generates a 16-bit signed PCM test scenario:
    - 0.00s ~ 0.02s: Silence (low background noise)
    - 0.02s ~ 0.07s: Voice Burst (composed of 400Hz and 800Hz harmonics)
    - 0.07s ~ 0.10s: Silence decay
    """
    total_samples = int(SAMPLE_RATE_PCM * duration_sec)
    pcm_samples = []

    for i in range(total_samples):
        t = i / SAMPLE_RATE_PCM
        if 0.02 <= t <= 0.07:
            # Voice burst with envelope
            env = math.sin((t - 0.02) / 0.05 * math.pi)
            val = (0.6 * math.sin(2 * math.pi * 400 * t) + 
                   0.4 * math.sin(2 * math.pi * 800 * t)) * env
            amp = int(val * 24000) # Amplitude around +/- 24000 (16-bit)
        else:
            # Silence / low noise
            amp = int(150 * math.sin(2 * math.pi * 60 * t))
        # Clip to 16-bit signed
        amp = max(-32768, min(32767, amp))
        pcm_samples.append(amp)
    return pcm_samples

def pcm_to_pdm_bitstream(pcm_samples):
    """
    Simulates a 1st-order Sigma-Delta Modulator (SDM)
    converting 16kHz PCM to 1.024MHz 1-bit PDM stream.
    Each PCM sample is held for 64 PDM clocks (zero-order hold with interpolation).
    """
    pdm_bits = []
    integrator = 0.0
    
    # Linear interpolation between PCM samples across 64 steps
    num_pcm = len(pcm_samples)
    for i in range(num_pcm):
        curr_val = pcm_samples[i] / 32768.0
        next_val = pcm_samples[i + 1] / 32768.0 if (i + 1 < num_pcm) else curr_val
        
        for k in range(DECIMATION_RATIO):
            # Interpolated sample in [-1.0, 1.0]
            alpha = k / float(DECIMATION_RATIO)
            interp_val = curr_val * (1.0 - alpha) + next_val * alpha
            
            # Sigma-Delta Modulation loop
            integrator += interp_val
            if integrator >= 0:
                bit = 1
                feedback = 1.0
            else:
                bit = 0
                feedback = -1.0
            integrator -= feedback
            pdm_bits.append(bit)
            
    return pdm_bits

def export_vectors(output_dir="model/golden_vectors"):
    os.makedirs(output_dir, exist_ok=True)
    pcm = generate_pcm_scenario(duration_sec=0.1)
    pdm = pcm_to_pdm_bitstream(pcm)
    
    pcm_path = os.path.join(output_dir, "stimulus_pcm_16k.txt")
    pdm_path = os.path.join(output_dir, "stimulus_pdm_1mhz.txt")
    
    with open(pcm_path, "w") as f:
        for val in pcm:
            f.write(f"{val}\n")
            
    with open(pdm_path, "w") as f:
        for b in pdm:
            f.write(f"{b}\n")
            
    print(f"[Generate Stimulus] Generated {len(pcm)} PCM samples -> {pcm_path}")
    print(f"[Generate Stimulus] Generated {len(pdm)} PDM bits -> {pdm_path}")
    return pcm, pdm

if __name__ == "__main__":
    export_vectors()
