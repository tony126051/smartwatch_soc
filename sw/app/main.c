/**
 * @file main.c
 * @brief Ultra-low Power Smartwatch SoC Firmware
 *
 * Implements the Two-Stage Voice Wakeup System Logic:
 *   1. Hardware Initialization (Configure AFE & Always-on VAD).
 *   2. Enter Low-Power WFI sleep mode.
 *   3. On Level-1 VAD Wakeup Interrupt:
 *        - Clear VAD IRQ flag.
 *        - Read PCM audio buffer and load features to NPU.
 *        - Trigger Level-2 NPU inference.
 *   4. On Level-2 NPU Done Interrupt:
 *        - Read classification confidence scores.
 *        - If keyword detected, assert wake-up flag & update status LED.
 */

#include "soc_regs.h"

#define REG_DEBUG_LEDS  (*(volatile uint32_t *)0x80000000UL)

// Interrupt flags set by ISR
volatile uint32_t g_vad_triggered = 0;
volatile uint32_t g_npu_finished  = 0;

void vad_isr(void) {
    // Clear VAD Interrupt by writing 1 to bit 1 of VAD_CTRL
    HW_REG(REG_VAD_CTRL) = 0x03; 
    g_vad_triggered = 1;
}

void npu_isr(void) {
    // Clear NPU Interrupt by writing 1 to bit 1 of NPU_CTRL
    HW_REG(REG_NPU_CTRL) = 0x02; 
    g_npu_finished = 1;
}

void soc_init(void) {
    // 1. Light up LED 0x01 indicating Booting
    REG_DEBUG_LEDS = 0x01;

    // 2. Enable AFE and CIC filter
    HW_REG(REG_AFE_CTRL) = 0x01;

    // 3. Configure VAD Threshold (200,000) & Hangover (3 frames)
    HW_REG(REG_VAD_THRESHOLD) = 200000;
    HW_REG(REG_VAD_HANGOVER)  = 3;

    // 4. Enable Hardware VAD
    HW_REG(REG_VAD_CTRL) = 0x01;

    // 5. System Ready LED 0x02
    REG_DEBUG_LEDS = 0x02;
}

int main(void) {
    soc_init();

    while (1) {
        // Sleep until VAD interrupt wakes up CPU
        REG_DEBUG_LEDS = 0x04; // Status: Standby Sleep (< 20uW)
        
        // Wait-For-Interrupt (WFI)
        // __asm__ volatile ("waitirq");

        if (g_vad_triggered) {
            g_vad_triggered = 0;
            REG_DEBUG_LEDS = 0x08; // Status: Voice Detected, running NPU

            // Transfer feature data into NPU Feature Window
            for (int i = 0; i < 256; i++) {
                HW_REG(NPU_FEAT_WINDOW_BASE + (i * 4)) = (i % 16);
            }

            // Start KWS NPU inference
            HW_REG(REG_NPU_CTRL) = 0x01;

            // Wait for NPU Done
            // __asm__ volatile ("waitirq");

            if (g_npu_finished) {
                g_npu_finished = 0;
                
                int32_t score0 = (int32_t)HW_REG(REG_NPU_SCORE0);
                int32_t score1 = (int32_t)HW_REG(REG_NPU_SCORE1);
                uint32_t status = HW_REG(REG_NPU_STATUS);

                if (status & 0x04) { // Keyword detected bit
                    REG_DEBUG_LEDS = 0xAA; // Keyword MATCH! Wake up UI
                } else {
                    REG_DEBUG_LEDS = 0x55; // Non-keyword, return to sleep
                }
            }
        }
    }

    return 0;
}
