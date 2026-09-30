#!/usr/bin/env python3
"""
DS-CNN (Depthwise Separable CNN) INT8 Inference Golden Model
Designed for KWS (Keyword Spotting) on Resource-Constrained Smartwatch SoC.
Input: 16 (Freq bins) x 16 (Time frames) INT8 feature map.
Output: 2 classes (0: Unknown/Silence, 1: Wake-up Keyword).
"""

import os
import random

# Fixed deterministic weights for bit-true hardware testing
def get_model_parameters():
    # Seed for deterministic generation
    rng = random.Random(42)
    
    # Layer 1: Standard Conv2D (3x3, in_ch=1, out_ch=4)
    # Weights: 4 filters of 3x3
    w_conv1 = [[[rng.randint(-16, 16) for _ in range(3)] for _ in range(3)] for _ in range(4)]
    b_conv1 = [rng.randint(-5, 5) for _ in range(4)]
    
    # Layer 2: Depthwise Conv2D (3x3, ch=4)
    w_dw = [[[rng.randint(-16, 16) for _ in range(3)] for _ in range(3)] for _ in range(4)]
    b_dw = [rng.randint(-5, 5) for _ in range(4)]
    
    # Layer 3: Pointwise Conv2D (1x1, in_ch=4, out_ch=8)
    w_pw = [[rng.randint(-16, 16) for _ in range(4)] for _ in range(8)]
    b_pw = [rng.randint(-5, 5) for _ in range(8)]
    
    # Layer 4: Fully Connected (in=8, out=2)
    w_fc = [[rng.randint(-30, 30) for _ in range(8)] for _ in range(2)]
    b_fc = [10, -10]
    
    return {
        "conv1_w": w_conv1, "conv1_b": b_conv1,
        "dw_w": w_dw, "dw_b": b_dw,
        "pw_w": w_pw, "pw_b": b_pw,
        "fc_w": w_fc, "fc_b": b_fc
    }

def clip_int8(val):
    return max(-128, min(127, val))

def relu_int8(val):
    return max(0, min(127, val))

def run_ds_cnn_inference(input_feature_map, params):
    """
    Simulates INT8 inference:
    input_feature_map: 16x16 2D array of INT8
    """
    H, W = 16, 16
    
    # 1. Standard Conv2D: 1x16x16 -> 4x16x16
    conv1_out = [[[0 for _ in range(W)] for _ in range(H)] for _ in range(4)]
    for oc in range(4):
        for r in range(H):
            for c in range(W):
                accum = params["conv1_b"][oc] << 4
                for kr in range(3):
                    for kc in range(3):
                        in_r = r + kr - 1
                        in_c = c + kc - 1
                        val = input_feature_map[in_r][in_c] if (0 <= in_r < H and 0 <= in_c < W) else 0
                        accum += val * params["conv1_w"][oc][kr][kc]
                # Requantize (shift right 5) and ReLU
                conv1_out[oc][r][c] = relu_int8(accum >> 5)
                
    # 2. Depthwise Conv2D: 4x16x16 -> 4x16x16
    dw_out = [[[0 for _ in range(W)] for _ in range(H)] for _ in range(4)]
    for ch in range(4):
        for r in range(H):
            for c in range(W):
                accum = params["dw_b"][ch] << 4
                for kr in range(3):
                    for kc in range(3):
                        in_r = r + kr - 1
                        in_c = c + kc - 1
                        val = conv1_out[ch][in_r][in_c] if (0 <= in_r < H and 0 <= in_c < W) else 0
                        accum += val * params["dw_w"][ch][kr][kc]
                dw_out[ch][r][c] = relu_int8(accum >> 5)
                
    # 3. Pointwise Conv2D: 4x16x16 -> 8x16x16
    pw_out = [[[0 for _ in range(W)] for _ in range(H)] for _ in range(8)]
    for oc in range(8):
        for r in range(H):
            for c in range(W):
                accum = params["pw_b"][oc] << 4
                for ic in range(4):
                    accum += dw_out[ic][r][c] * params["pw_w"][oc][ic]
                pw_out[oc][r][c] = relu_int8(accum >> 5)
                
    # 4. Global Average Pooling: 8x16x16 -> 8
    gap_out = [0] * 8
    for ch in range(8):
        s = sum(pw_out[ch][r][c] for r in range(H) for c in range(W))
        gap_out[ch] = s // (H * W)
        
    # 5. Fully-Connected (Dense): 8 -> 2
    fc_out = [0] * 2
    for cls in range(2):
        accum = params["fc_b"][cls]
        for ic in range(8):
            accum += gap_out[ic] * params["fc_w"][cls][ic]
        fc_out[cls] = accum
        
    predicted_class = 1 if fc_out[1] > fc_out[0] else 0
    return {
        "gap": gap_out,
        "fc_out": fc_out,
        "class": predicted_class
    }

def export_npu_golden(mfcc_features, output_dir="model/golden_vectors"):
    os.makedirs(output_dir, exist_ok=True)
    params = get_model_parameters()
    
    # Pack 16 consecutive frames to form a 16x16 input map
    # If less than 16 frames, pad with zeros
    input_map = [[0 for _ in range(16)] for _ in range(16)]
    for f in range(min(16, len(mfcc_features))):
        for b in range(16):
            input_map[b][f] = mfcc_features[f][b]
            
    res = run_ds_cnn_inference(input_map, params)
    
    # Export weights in HEX format for RTL memory init
    hex_path = os.path.join(output_dir, "weights_int8.hex")
    with open(hex_path, "w") as f:
        # Layer 1
        for oc in range(4):
            for kr in range(3):
                for kc in range(3):
                    w = params["conv1_w"][oc][kr][kc] & 0xFF
                    f.write(f"{w:02x}\n")
        # Layer 2 DW
        for ch in range(4):
            for kr in range(3):
                for kc in range(3):
                    w = params["dw_w"][ch][kr][kc] & 0xFF
                    f.write(f"{w:02x}\n")
        # Layer 3 PW
        for oc in range(8):
            for ic in range(4):
                w = params["pw_w"][oc][ic] & 0xFF
                f.write(f"{w:02x}\n")
        # Layer 4 FC
        for cls in range(2):
            for ic in range(8):
                w = params["fc_w"][cls][ic] & 0xFF
                f.write(f"{w:02x}\n")
                
    # Export Golden output
    gold_path = os.path.join(output_dir, "npu_golden.txt")
    with open(gold_path, "w") as f:
        f.write(f"# Predicted_Class Score_0 Score_1\n")
        f.write(f"{res['class']} {res['fc_out'][0]} {res['fc_out'][1]}\n")
        f.write(f"# GAP Outputs (8 channels):\n")
        f.write(" ".join(str(v) for v in res["gap"]) + "\n")
        
    print(f"[Golden NPU] Inferred Class: {res['class']}, Scores: {res['fc_out']}")
    print(f"[Golden NPU] Weights exported to -> {hex_path}")
    print(f"[Golden NPU] Golden result exported to -> {gold_path}")
    return res

if __name__ == "__main__":
    from generate_stimulus import generate_pcm_scenario
    from golden_mfcc import extract_mfcc_golden
    pcm = generate_pcm_scenario()
    feats = extract_mfcc_golden(pcm)
    export_npu_golden(feats)
