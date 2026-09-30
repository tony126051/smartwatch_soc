"""
RISC-V RV32I Processor Core Emulator with PicoRV32 IRQ Extensions
"""

from typing import Tuple, Dict, Any, Optional
from .types import u32, s32, sign_extend

ABI_REG_NAMES = [
    "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
    "s0",   "s1", "a0", "a1", "a2", "a3", "a4", "a5",
    "a6",   "a7", "s2", "s3", "s4", "s5", "s6", "s7",
    "s8",   "s9", "s10", "s11", "t3", "t4", "t5", "t6"
]

class RiscvCpu:
    def __init__(self, bus, reset_pc: int = 0x0000_0000, irq_pc: int = 0x0000_0010):
        self.bus = bus
        self.reset_pc = reset_pc
        self.irq_pc = irq_pc
        
        self.regs = [0] * 32
        self.pc = reset_pc
        self.next_pc = reset_pc
        
        # PicoRV32 IRQ Support
        self.irq_mask = 0xFFFF_FFFF   # All masked by default
        self.irq_pending = 0
        self.is_sleeping = False      # Waiting for interrupt (WFI / waitirq)
        self.in_irq = False
        self.saved_pc = 0
        self.trapped = False
        
        # Statistics
        self.instruction_count = 0
        self.cycle_count = 0

    def reset(self):
        self.regs = [0] * 32
        self.pc = self.reset_pc
        self.next_pc = self.reset_pc
        self.irq_mask = 0xFFFF_FFFF
        self.irq_pending = 0
        self.is_sleeping = False
        self.in_irq = False
        self.saved_pc = 0
        self.trapped = False
        self.instruction_count = 0
        self.cycle_count = 0

    def set_irq(self, irq_bit: int, val: bool):
        if val:
            self.irq_pending |= (1 << irq_bit)
        else:
            self.irq_pending &= ~(1 << irq_bit)
            
        # Wake up if sleeping and an unmasked IRQ is active
        if self.is_sleeping and (self.irq_pending & ~self.irq_mask) != 0:
            self.is_sleeping = False

    def check_and_take_irq(self) -> bool:
        active_irqs = self.irq_pending & ~self.irq_mask
        if active_irqs != 0 and not self.in_irq:
            self.in_irq = True
            self.saved_pc = self.pc
            self.pc = self.irq_pc
            self.next_pc = self.irq_pc
            self.is_sleeping = False
            return True
        return False

    def step(self) -> Dict[str, Any]:
        """
        Executes a single instruction or handles sleep/IRQ state.
        Returns trace info dict.
        """
        self.cycle_count += 1
        
        # Check interrupts before instruction fetch
        if self.check_and_take_irq():
            return {
                "pc": self.pc,
                "disasm": f"[IRQ Triggered -> Vector 0x{self.irq_pc:08x}]",
                "cycles": 4,
                "is_irq": True,
                "sleeping": False,
                "reg_write": None
            }

        if self.is_sleeping:
            return {
                "pc": self.pc,
                "disasm": "[WFI / waitirq: CPU Sleeping in Standby]",
                "cycles": 1,
                "is_irq": False,
                "sleeping": True,
                "reg_write": None
            }

        # Instruction Fetch
        curr_pc = self.pc
        inst = self.bus.read_u32(curr_pc)
        self.next_pc = curr_pc + 4
        
        # Decode fields
        opcode = inst & 0x7F
        rd     = (inst >> 7) & 0x1F
        funct3 = (inst >> 12) & 0x07
        rs1    = (inst >> 15) & 0x1F
        rs2    = (inst >> 20) & 0x1F
        funct7 = (inst >> 25) & 0x7F
        
        reg_write = None
        cycles = 3 # Nominal PicoRV32 instruction latency
        disasm_str = ""

        def write_rd(val: int):
            nonlocal reg_write
            val = u32(val)
            if rd != 0:
                self.regs[rd] = val
                reg_write = (rd, val)

        # ---------------------------------------------------------------------
        # PicoRV32 Custom Instructions (Opcode 0b0001011 = 0x0B)
        # ---------------------------------------------------------------------
        if opcode == 0x0B:
            if funct3 == 0b100: # waitirq
                self.is_sleeping = True
                disasm_str = "waitirq"
                cycles = 2
            elif funct3 == 0b101: # retirq
                self.in_irq = False
                self.next_pc = self.saved_pc
                disasm_str = "retirq"
                cycles = 3
            elif funct3 == 0b011: # maskirq rd, rs1
                old_mask = self.irq_mask
                new_mask = self.regs[rs1]
                self.irq_mask = new_mask
                write_rd(old_mask)
                disasm_str = f"maskirq {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]} (mask=0x{new_mask:08x})"
                cycles = 3
            else:
                self.trapped = True
                disasm_str = f"unknown_custom_0b (funct3={funct3})"

        # ---------------------------------------------------------------------
        # LUI / AUIPC
        # ---------------------------------------------------------------------
        elif opcode == 0x37: # LUI
            imm = (inst >> 12) << 12
            write_rd(imm)
            disasm_str = f"lui {ABI_REG_NAMES[rd]}, 0x{imm >> 12:x}"
            cycles = 2
        elif opcode == 0x17: # AUIPC
            imm = (inst >> 12) << 12
            write_rd(curr_pc + imm)
            disasm_str = f"auipc {ABI_REG_NAMES[rd]}, 0x{imm >> 12:x}"
            cycles = 2

        # ---------------------------------------------------------------------
        # JAL / JALR
        # ---------------------------------------------------------------------
        elif opcode == 0x6F: # JAL
            imm = (((inst >> 31) & 1) << 20) | (((inst >> 12) & 0xFF) << 12) | (((inst >> 20) & 1) << 11) | (((inst >> 21) & 0x3FF) << 1)
            imm = sign_extend(imm, 21)
            write_rd(curr_pc + 4)
            self.next_pc = curr_pc + imm
            target = self.next_pc
            disasm_str = f"jal {ABI_REG_NAMES[rd]}, 0x{target:08x}"
            cycles = 3
        elif opcode == 0x67: # JALR
            imm = sign_extend(inst >> 20, 12)
            target = (self.regs[rs1] + imm) & ~1
            write_rd(curr_pc + 4)
            self.next_pc = target
            disasm_str = f"jalr {ABI_REG_NAMES[rd]}, {imm}({ABI_REG_NAMES[rs1]})"
            cycles = 3

        # ---------------------------------------------------------------------
        # Branch Instructions (Opcode 0x63)
        # ---------------------------------------------------------------------
        elif opcode == 0x63:
            imm = (((inst >> 31) & 1) << 12) | (((inst >> 7) & 1) << 11) | (((inst >> 25) & 0x3F) << 5) | (((inst >> 8) & 0xF) << 1)
            imm = sign_extend(imm, 13)
            val1 = self.regs[rs1]
            val2 = self.regs[rs2]
            take_branch = False
            
            b_names = {0: "beq", 1: "bne", 4: "blt", 5: "bge", 6: "bltu", 7: "bgeu"}
            op_name = b_names.get(funct3, "b_unk")
            
            if funct3 == 0:   take_branch = (val1 == val2)
            elif funct3 == 1: take_branch = (val1 != val2)
            elif funct3 == 4: take_branch = (s32(val1) < s32(val2))
            elif funct3 == 5: take_branch = (s32(val1) >= s32(val2))
            elif funct3 == 6: take_branch = (u32(val1) < u32(val2))
            elif funct3 == 7: take_branch = (u32(val1) >= u32(val2))
            
            if take_branch:
                self.next_pc = curr_pc + imm
                cycles = 3
            else:
                cycles = 2
                
            disasm_str = f"{op_name} {ABI_REG_NAMES[rs1]}, {ABI_REG_NAMES[rs2]}, 0x{curr_pc + imm:08x}"

        # ---------------------------------------------------------------------
        # Load Instructions (Opcode 0x03)
        # ---------------------------------------------------------------------
        elif opcode == 0x03:
            imm = sign_extend(inst >> 20, 12)
            addr = u32(self.regs[rs1] + imm)
            cycles = 5 # PicoRV32 load cycle latency
            
            if funct3 == 0:   # LB
                val = sign_extend(self.bus.read_u8(addr), 8)
                write_rd(val)
                disasm_str = f"lb {ABI_REG_NAMES[rd]}, {imm}({ABI_REG_NAMES[rs1]})"
            elif funct3 == 1: # LH
                val = sign_extend(self.bus.read_u16(addr), 16)
                write_rd(val)
                disasm_str = f"lh {ABI_REG_NAMES[rd]}, {imm}({ABI_REG_NAMES[rs1]})"
            elif funct3 == 2: # LW
                val = self.bus.read_u32(addr)
                write_rd(val)
                disasm_str = f"lw {ABI_REG_NAMES[rd]}, {imm}({ABI_REG_NAMES[rs1]})"
            elif funct3 == 4: # LBU
                val = self.bus.read_u8(addr)
                write_rd(val)
                disasm_str = f"lbu {ABI_REG_NAMES[rd]}, {imm}({ABI_REG_NAMES[rs1]})"
            elif funct3 == 5: # LHU
                val = self.bus.read_u16(addr)
                write_rd(val)
                disasm_str = f"lhu {ABI_REG_NAMES[rd]}, {imm}({ABI_REG_NAMES[rs1]})"
            else:
                self.trapped = True
                disasm_str = f"invalid_load (funct3={funct3})"

        # ---------------------------------------------------------------------
        # Store Instructions (Opcode 0x23)
        # ---------------------------------------------------------------------
        elif opcode == 0x23:
            imm = (((inst >> 25) & 0x7F) << 5) | ((inst >> 7) & 0x1F)
            imm = sign_extend(imm, 12)
            addr = u32(self.regs[rs1] + imm)
            val = self.regs[rs2]
            cycles = 4 # PicoRV32 store cycle latency
            
            if funct3 == 0:   # SB
                self.bus.write_u8(addr, val & 0xFF)
                disasm_str = f"sb {ABI_REG_NAMES[rs2]}, {imm}({ABI_REG_NAMES[rs1]})"
            elif funct3 == 1: # SH
                self.bus.write_u16(addr, val & 0xFFFF)
                disasm_str = f"sh {ABI_REG_NAMES[rs2]}, {imm}({ABI_REG_NAMES[rs1]})"
            elif funct3 == 2: # SW
                self.bus.write_u32(addr, val)
                disasm_str = f"sw {ABI_REG_NAMES[rs2]}, {imm}({ABI_REG_NAMES[rs1]})"
            else:
                self.trapped = True
                disasm_str = f"invalid_store (funct3={funct3})"

        # ---------------------------------------------------------------------
        # ALU Immediate (Opcode 0x13)
        # ---------------------------------------------------------------------
        elif opcode == 0x13:
            imm = sign_extend(inst >> 20, 12)
            shamt = (inst >> 20) & 0x1F
            v1 = self.regs[rs1]
            cycles = 2
            
            if funct3 == 0: # ADDI / NOP
                res = u32(v1 + imm)
                write_rd(res)
                if rd == 0 and rs1 == 0 and imm == 0:
                    disasm_str = "nop"
                else:
                    disasm_str = f"addi {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {imm}"
            elif funct3 == 1: # SLLI
                write_rd(u32(v1 << shamt))
                disasm_str = f"slli {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {shamt}"
            elif funct3 == 2: # SLTI
                write_rd(1 if s32(v1) < imm else 0)
                disasm_str = f"slti {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {imm}"
            elif funct3 == 3: # SLTIU
                write_rd(1 if u32(v1) < u32(imm) else 0)
                disasm_str = f"sltiu {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {imm}"
            elif funct3 == 4: # XORI
                write_rd(v1 ^ imm)
                disasm_str = f"xori {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {imm}"
            elif funct3 == 5:
                if funct7 == 0x00: # SRLI
                    write_rd(v1 >> shamt)
                    disasm_str = f"srli {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {shamt}"
                else: # SRAI
                    write_rd(u32(s32(v1) >> shamt))
                    disasm_str = f"srai {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {shamt}"
            elif funct3 == 6: # ORI
                write_rd(v1 | imm)
                disasm_str = f"ori {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {imm}"
            elif funct3 == 7: # ANDI
                write_rd(v1 & imm)
                disasm_str = f"andi {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {imm}"

        # ---------------------------------------------------------------------
        # ALU Reg-Reg (Opcode 0x33)
        # ---------------------------------------------------------------------
        elif opcode == 0x33:
            v1 = self.regs[rs1]
            v2 = self.regs[rs2]
            shamt = v2 & 0x1F
            cycles = 2
            
            if funct3 == 0:
                if funct7 == 0x00: # ADD
                    write_rd(u32(v1 + v2))
                    disasm_str = f"add {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {ABI_REG_NAMES[rs2]}"
                elif funct7 == 0x20: # SUB
                    write_rd(u32(v1 - v2))
                    disasm_str = f"sub {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {ABI_REG_NAMES[rs2]}"
            elif funct3 == 1: # SLL
                write_rd(u32(v1 << shamt))
                disasm_str = f"sll {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {ABI_REG_NAMES[rs2]}"
            elif funct3 == 2: # SLT
                write_rd(1 if s32(v1) < s32(v2) else 0)
                disasm_str = f"slt {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {ABI_REG_NAMES[rs2]}"
            elif funct3 == 3: # SLTU
                write_rd(1 if u32(v1) < u32(v2) else 0)
                disasm_str = f"sltu {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {ABI_REG_NAMES[rs2]}"
            elif funct3 == 4: # XOR
                write_rd(v1 ^ v2)
                disasm_str = f"xor {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {ABI_REG_NAMES[rs2]}"
            elif funct3 == 5:
                if funct7 == 0x00: # SRL
                    write_rd(v1 >> shamt)
                    disasm_str = f"srl {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {ABI_REG_NAMES[rs2]}"
                else: # SRA
                    write_rd(u32(s32(v1) >> shamt))
                    disasm_str = f"sra {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {ABI_REG_NAMES[rs2]}"
            elif funct3 == 6: # OR
                write_rd(v1 | v2)
                disasm_str = f"or {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {ABI_REG_NAMES[rs2]}"
            elif funct3 == 7: # AND
                write_rd(v1 & v2)
                disasm_str = f"and {ABI_REG_NAMES[rd]}, {ABI_REG_NAMES[rs1]}, {ABI_REG_NAMES[rs2]}"

        else:
            self.trapped = True
            disasm_str = f"unimplemented_opcode (0x{opcode:02x}, inst=0x{inst:08x})"
            cycles = 1

        self.regs[0] = 0 # Enforce x0 is zero
        self.pc = self.next_pc
        self.instruction_count += 1
        
        return {
            "pc": curr_pc,
            "disasm": disasm_str,
            "cycles": cycles,
            "is_irq": False,
            "sleeping": self.is_sleeping,
            "reg_write": reg_write
        }
