/**
 * @file soc_regs.h
 * @brief Memory-Mapped Registers for Smartwatch SoC KWS Accelerator v2.0
 * Complies with SPEC-HIS-001 (0x4000_0000 - 0x4000_08FF)
 */

#ifndef SMARTWATCH_SOC_REGS_H_
#define SMARTWATCH_SOC_REGS_H_

#include <stdint.h>

#define KWS_BASE_ADDR        0x40000000UL
#define SYS_BASE_ADDR        0x80000000UL

// AFE Registers (0x000 - 0x034)
#define REG_AFE_CTRL         (KWS_BASE_ADDR + 0x000)
#define REG_AFE_STATUS       (KWS_BASE_ADDR + 0x004)
#define REG_AFE_DATA         (KWS_BASE_ADDR + 0x008)
#define REG_AFE_MIC_CTRL     (KWS_BASE_ADDR + 0x00C)
#define REG_AFE_WIND_CFG     (KWS_BASE_ADDR + 0x030)
#define REG_AFE_PRE_ROLL     (KWS_BASE_ADDR + 0x034)

// VAD Registers (0x010 - 0x01C)
#define REG_VAD_CTRL         (KWS_BASE_ADDR + 0x010)
#define REG_VAD_THRESHOLD    (KWS_BASE_ADDR + 0x014)
#define REG_VAD_HANGOVER     (KWS_BASE_ADDR + 0x018)
#define REG_VAD_ENERGY       (KWS_BASE_ADDR + 0x01C)

// NPU Registers (0x020 - 0x02C)
#define REG_NPU_CTRL         (KWS_BASE_ADDR + 0x020)
#define REG_NPU_STATUS       (KWS_BASE_ADDR + 0x024)
#define REG_NPU_SCORE0       (KWS_BASE_ADDR + 0x028)
#define REG_NPU_SCORE1       (KWS_BASE_ADDR + 0x02C)

// Context-Aware FSM Registers (0x070 - 0x074)
#define REG_SYS_CONTEXT_CTRL (KWS_BASE_ADDR + 0x070)
#define REG_SYS_WINDOW_TIMER (KWS_BASE_ADDR + 0x074)

// Production BIST Registers (0x0F8 - 0x0FC)
#define REG_BIST_SIGNATURE   (KWS_BASE_ADDR + 0x0F8)
#define REG_BIST_CTRL        (KWS_BASE_ADDR + 0x0FC)

// Memory Windows
#define NPU_FEAT_WINDOW_BASE (KWS_BASE_ADDR + 0x400) // 256 bytes (16x16)
#define NPU_WGT_WINDOW_BASE  (KWS_BASE_ADDR + 0x500) // 1024 bytes Total
#define NPU_WGT_BANK0_BASE   (KWS_BASE_ADDR + 0x500) // 512 bytes (Default Model)
#define NPU_WGT_BANK1_BASE   (KWS_BASE_ADDR + 0x700) // 512 bytes (Multi-language Model)

// System Debug & LEDs
#define REG_SYS_LEDS         (SYS_BASE_ADDR + 0x000)

// Standard Debug LED Status Codes
#define LED_BOOTING          0x01
#define LED_INIT_READY       0x02
#define LED_MINI_POST        0x03
#define LED_STANDBY_SLEEP    0x04
#define LED_ATE_BIST_ACTIVE  0x05
#define LED_VOICE_DETECTED   0x08
#define LED_ISR_ENTRY        0x10
#define LED_FEATURE_LOADED   0x55
#define LED_KEYWORD_HIT      0xAA
#define LED_FAULT_SRAM       0xE1
#define LED_FAULT_AFE        0xE2
#define LED_FAULT_VAD        0xE3
#define LED_FAULT_NPU        0xE4
#define LED_FAULT_MISR       0xEF
#define LED_SYSTEM_TRAP      0xFF

// Helper macros
#define HW_REG(addr)         (*(volatile uint32_t *)(addr))

#endif // SMARTWATCH_SOC_REGS_H_
