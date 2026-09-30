# ==============================================================================
# Smartwatch SoC RV32I Firmware (Startup & Voice Wakeup Application)
# ==============================================================================

.text
.globl _start

# 0x00: Reset Vector
_start:
    jal zero, reset_handler
    nop
    nop
    nop

# 0x10: IRQ Vector Entry Point
irq_entry:
    jal zero, irq_handler
    nop
    nop
    nop

# ------------------------------------------------------------------------------
# Reset Handler: Hardware Initialization & Weight Programming
# ------------------------------------------------------------------------------
reset_handler:
    # 1. Initialize Stack Pointer (sp = x2 = 0x10002000)
    lui sp, 0x10002
    
    # 2. Write LED = 0x01 (Booting)
    lui s0, 0x80000
    addi t0, zero, 1
    sw t0, 0(s0)

    # 3. Base address of KWS Subsystem: 0x40000000
    lui s1, 0x40000

    # 4. Enable AFE (AFE_CTRL = 0x00 = 1)
    addi t0, zero, 1
    sw t0, 0(s1)

    # 5. Set VAD Threshold (0x14 = 200,000 = 0x30D40)
    lui t0, 0x31
    addi t0, t0, -704   # 0x31000 - 704 = 200000
    sw t0, 20(s1)

    # 6. Set VAD Hangover (0x18 = 3)
    addi t0, zero, 3
    sw t0, 24(s1)

    # 7. Enable VAD (VAD_CTRL = 0x10 = 1)
    addi t0, zero, 1
    sw t0, 16(s1)

    # 8. Unmask IRQ 0 (VAD) and IRQ 1 (NPU) -> Mask = ~0x03
    addi t0, zero, -4
    maskirq zero, t0

    # 9. Write LED = 0x02 (Initialized & Ready for Voice)
    addi t0, zero, 2
    sw t0, 0(s0)

# ------------------------------------------------------------------------------
# Main Loop: Standby Sleep & Wakeup Polling
# ------------------------------------------------------------------------------
main_loop:
    # Set LED = 0x04 (Standby Micro-watt Sleep)
    addi t0, zero, 4
    sw t0, 0(s0)

    # Low-Power Wait For Interrupt (wfi / waitirq)
    waitirq

    # Woken up! Check if VAD IRQ was handled
    lui s2, 0x10000
    lw t1, 0(s2)       # Read g_vad_flag
    beq t1, zero, main_loop

    # Clear g_vad_flag
    sw zero, 0(s2)

    # Set LED = 0x08 (Voice Detected, Processing NPU)
    addi t0, zero, 8
    sw t0, 0(s0)

    # Fill Feature Window (0x400 .. 0x4FF) with test ramp
    addi t2, zero, 0   # loop index i = 0
    addi t3, zero, 256 # limit = 256
feat_loop:
    andi t4, t2, 15    # (i % 16)
    add t5, s1, t2     # 0x40000000 + i
    sw t4, 1024(t5)    # 0x40000400 + i
    addi t2, t2, 1
    bne t2, t3, feat_loop

    # Trigger NPU Inference (NPU_CTRL = 0x20 = 1)
    addi t0, zero, 1
    sw t0, 32(s1)

    # Wait for NPU Done Interrupt
    waitirq

    # Check NPU Status (0x24)
    lw t6, 36(s1)
    andi t6, t6, 4     # Check bit 2: keyword_detected
    beq t6, zero, not_keyword

keyword_matched:
    # Set LED = 0xAA (Keyword MATCHED! Full Wakeup)
    addi t0, zero, 170 # 0xAA
    sw t0, 0(s0)
    jal zero, main_loop

not_keyword:
    # Set LED = 0x55 (False alarm / other word)
    addi t0, zero, 85  # 0x55
    sw t0, 0(s0)
    jal zero, main_loop

# ------------------------------------------------------------------------------
# Interrupt Service Routine (ISR)
# ------------------------------------------------------------------------------
irq_handler:
    # Read VAD Status (0x10) to see if VAD triggered
    lw t0, 16(s1)
    andi t1, t0, 2     # Check bit 1: VAD irq pending
    beq t1, zero, check_npu

    # Clear VAD IRQ (Write 1 to bit 1)
    addi t0, zero, 3
    sw t0, 16(s1)
    
    # Set g_vad_flag = 1 in Data SRAM (0x10000000)
    lui s2, 0x10000
    addi t0, zero, 1
    sw t0, 0(s2)

check_npu:
    # Read NPU Status (0x20) to see if NPU triggered
    lw t0, 32(s1)
    andi t1, t0, 2     # Check bit 1: NPU irq pending
    beq t1, zero, irq_exit

    # Clear NPU IRQ (Write 1 to bit 1)
    addi t0, zero, 2
    sw t0, 32(s1)

irq_exit:
    retirq
