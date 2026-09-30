#!/usr/bin/env python3
"""
Hardware Voice Activity Detector (VAD) Golden Model
Bit-True Fixed-point Model for Short-Time Energy (STE) and Voice Triggering.
Frame size: 160 samples (10ms @ 16kHz).
"""

import os

FRAME_SIZE = 160
INITIAL_THRESHOLD = 200000  # Frame cumulative absolute energy threshold
HANGOVER_FRAMES = 3         # Hangover timer to prevent premature speech cutoff

def simulate_vad(pcm_samples, threshold=INITIAL_THRESHOLD):
    """
    Simulates the Hardware VAD logic on PCM audio stream.
    Returns:
        frame_energies: list of uint32 cumulative energy per frame
        vad_decisions: list of bool (True = speech, False = silence)
        irq_events: list of frame indices where interrupt is asserted
    """
    num_frames = len(pcm_samples) // FRAME_SIZE
    frame_energies = []
    vad_decisions = []
    irq_events = []
    
    hangover_cnt = 0
    speech_detected_prev = False
    
    for f in range(num_frames):
        start_idx = f * FRAME_SIZE
        frame_data = pcm_samples[start_idx : start_idx + FRAME_SIZE]
        
        # Hardware: Short-Time Absolute Energy Accumulator
        # 16-bit abs value sum over 160 points fits in 24-bit accumulator
        frame_energy = sum(abs(x) for x in frame_data)
        frame_energies.append(frame_energy)
        
        # Threshold comparison
        raw_speech = (frame_energy >= threshold)
        
        if raw_speech:
            hangover_cnt = HANGOVER_FRAMES
            speech_active = True
        elif hangover_cnt > 0:
            hangover_cnt -= 1
            speech_active = True
        else:
            speech_active = False
            
        vad_decisions.append(speech_active)
        
        # Edge-triggered interrupt on rising edge (Silence -> Speech)
        if speech_active and not speech_detected_prev:
            irq_events.append(f)
            
        speech_detected_prev = speech_active
        
    return frame_energies, vad_decisions, irq_events

def export_vad_golden(pcm_samples, output_dir="model/golden_vectors"):
    os.makedirs(output_dir, exist_ok=True)
    energies, decisions, irqs = simulate_vad(pcm_samples)
    out_path = os.path.join(output_dir, "vad_golden.txt")
    with open(out_path, "w") as f:
        f.write("# Frame_Index Energy Speech_Active IRQ_Trigger\n")
        for i in range(len(energies)):
            is_irq = 1 if (i in irqs) else 0
            f.write(f"{i} {energies[i]} {int(decisions[i])} {is_irq}\n")
    print(f"[Golden VAD] Exported {len(energies)} frames VAD decisions -> {out_path}")
    print(f"[Golden VAD] IRQ asserted at frames: {irqs}")
    return energies, decisions, irqs

if __name__ == "__main__":
    from generate_stimulus import generate_pcm_scenario
    pcm = generate_pcm_scenario()
    export_vad_golden(pcm)
