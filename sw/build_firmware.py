#!/usr/bin/env python3
"""
Lightweight RISC-V RV32I Assembler & Firmware Hex Generator
Compiles assembly source (sw/app/main.s) directly to 32-bit hex (sw/firmware.hex)
for Verilog Boot ROM simulation without requiring external GCC toolchains.
"""

import sys
import os
import re

REG_MAP = {
    'zero': 0, 'ra': 1, 'sp': 2, 'gp': 3, 'tp': 4,
    't0': 5, 't1': 6, 't2': 7, 's0': 8, 'fp': 8, 's1': 9,
    'a0': 10, 'a1': 11, 'a2': 12, 'a3': 13, 'a4': 14, 'a5': 15, 'a6': 16, 'a7': 17,
    's2': 18, 's3': 19, 's4': 20, 's5': 21, 's6': 22, 's7': 23, 's8': 24, 's9': 25,
    's10': 26, 's11': 27, 't3': 28, 't4': 29, 't5': 30, 't6': 31
}
for i in range(32):
    REG_MAP[f'x{i}'] = i

def parse_reg(s):
    s = s.strip().lower()
    if s in REG_MAP:
        return REG_MAP[s]
    raise ValueError(f"Unknown register: {s}")

def parse_imm(s):
    s = s.strip()
    if s.startswith(('0x', '0X')):
        return int(s, 16)
    return int(s)

def assemble(lines):
    # Two-pass assembler
    # Pass 1: Collect labels and clean instructions
    labels = {}
    cleaned_code = []
    pc = 0

    for raw_line in lines:
        line = raw_line.split('#')[0].strip()
        if not line or line.startswith('.'):
            continue
        
        if ':' in line:
            parts = line.split(':')
            label = parts[0].strip()
            labels[label] = pc
            rem = ':'.join(parts[1:]).strip()
            if rem:
                cleaned_code.append((pc, rem))
                pc += 4
        else:
            cleaned_code.append((pc, line))
            pc += 4

    # Pass 2: Generate machine code
    machine_words = []

    for curr_pc, instr_str in cleaned_code:
        tokens = [t.strip() for t in re.split(r'[\s,()]+', instr_str) if t.strip()]
        op = tokens[0].lower()

        # Custom Instructions
        if op == 'nop':
            machine_words.append(0x00000013)
        elif op == 'waitirq':
            machine_words.append(0x0000400B)
        elif op == 'retirq':
            machine_words.append(0x0000500B)
        elif op == 'maskirq':
            rd = parse_reg(tokens[1])
            rs1 = parse_reg(tokens[2])
            w = (rs1 << 15) | (0b011 << 12) | (rd << 7) | 0b0001011
            machine_words.append(w)

        # U-Type: lui, auipc
        elif op in ('lui', 'auipc'):
            rd = parse_reg(tokens[1])
            imm = parse_imm(tokens[2])
            opcode = 0b0110111 if op == 'lui' else 0b0010111
            w = ((imm & 0xFFFFF) << 12) | (rd << 7) | opcode
            machine_words.append(w)

        # J-Type: jal
        elif op == 'jal':
            rd = parse_reg(tokens[1])
            target = tokens[2]
            if target in labels:
                offset = labels[target] - curr_pc
            else:
                offset = parse_imm(target)
            imm20 = (offset >> 20) & 1
            imm10_1 = (offset >> 1) & 0x3FF
            imm11 = (offset >> 11) & 1
            imm19_12 = (offset >> 12) & 0xFF
            w = (imm20 << 31) | (imm10_1 << 21) | (imm11 << 20) | (imm19_12 << 12) | (rd << 7) | 0b1101111
            machine_words.append(w)

        # I-Type ALU: addi, andi, ori, xori
        elif op in ('addi', 'andi', 'ori', 'xori'):
            rd = parse_reg(tokens[1])
            rs1 = parse_reg(tokens[2])
            imm = parse_imm(tokens[3]) & 0xFFF
            funct3 = {'addi': 0, 'xori': 4, 'ori': 6, 'andi': 7}[op]
            w = (imm << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0b0010011
            machine_words.append(w)

        # R-Type: add, sub, and, or, xor, sll, srl, sra
        elif op in ('add', 'sub', 'and', 'or', 'xor', 'sll', 'srl', 'sra'):
            rd = parse_reg(tokens[1])
            rs1 = parse_reg(tokens[2])
            rs2 = parse_reg(tokens[3])
            funct3_map = {'add': 0, 'sub': 0, 'sll': 1, 'xor': 4, 'srl': 5, 'sra': 5, 'or': 6, 'and': 7}
            funct7 = 0x20 if op in ('sub', 'sra') else 0x00
            w = (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3_map[op] << 12) | (rd << 7) | 0b0110011
            machine_words.append(w)

        # S-Type: sw, sh, sb (e.g. sw rs2, imm(rs1))
        elif op in ('sw', 'sh', 'sb'):
            rs2 = parse_reg(tokens[1])
            imm = parse_imm(tokens[2])
            rs1 = parse_reg(tokens[3])
            funct3 = {'sb': 0, 'sh': 1, 'sw': 2}[op]
            imm11_5 = (imm >> 5) & 0x7F
            imm4_0 = imm & 0x1F
            w = (imm11_5 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (imm4_0 << 7) | 0b0100011
            machine_words.append(w)

        # I-Type Load: lw, lh, lb (e.g. lw rd, imm(rs1))
        elif op in ('lw', 'lh', 'lb'):
            rd = parse_reg(tokens[1])
            imm = parse_imm(tokens[2]) & 0xFFF
            rs1 = parse_reg(tokens[3])
            funct3 = {'lb': 0, 'lh': 1, 'lw': 2}[op]
            w = (imm << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0b0000011
            machine_words.append(w)

        # B-Type: beq, bne, blt, bge
        elif op in ('beq', 'bne', 'blt', 'bge'):
            rs1 = parse_reg(tokens[1])
            rs2 = parse_reg(tokens[2])
            target = tokens[3]
            offset = (labels[target] - curr_pc) if target in labels else parse_imm(target)
            funct3 = {'beq': 0, 'bne': 1, 'blt': 4, 'bge': 5}[op]
            imm12 = (offset >> 12) & 1
            imm10_5 = (offset >> 5) & 0x3F
            imm4_1 = (offset >> 1) & 0xF
            imm11 = (offset >> 11) & 1
            w = (imm12 << 31) | (imm10_5 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (imm4_1 << 8) | (imm11 << 7) | 0b1100011
            machine_words.append(w)
        else:
            raise ValueError(f"Unsupported instruction: {op}")

    return machine_words

def build(src_path="sw/app/main.s", out_hex="sw/firmware.hex"):
    with open(src_path, "r") as f:
        lines = f.readlines()
    words = assemble(lines)
    os.makedirs(os.path.dirname(out_hex), exist_ok=True)
    with open(out_hex, "w") as f:
        for w in words:
            f.write(f"{w:08x}\n")
    print(f"[Firmware Builder] Successfully assembled {len(words)} instructions -> {out_hex}")
    return words

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "sw/app/main.s"
    out = sys.argv[2] if len(sys.argv) > 2 else "sw/firmware.hex"
    build(src, out)
