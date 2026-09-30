/**
 * @file soc_regs.h
 * @brief Memory-Mapped Registers for Smartwatch SoC KWS Accelerator
 */

#ifndef SMARTWATCH_SOC_REGS_H_
#define SMARTWATCH_SOC_REGS_H_

#include <stdint.h>

#define KWS_BASE_ADDR        0x40000000UL

// Register Offsets
#define REG_AFE_CTRL         (KWS_BASE_ADDR + 0x000)
#define REG_AFE_STATUS       (KWS_BASE_ADDR + 0x004)
#define REG_AFE_DATA         (KWS_BASE_ADDR + 0x008)

#define REG_VAD_CTRL         (KWS_BASE_ADDR + 0x010)
#define REG_VAD_THRESHOLD    (KWS_BASE_ADDR + 0x014)
#define REG_VAD_HANGOVER     (KWS_BASE_ADDR + 0x018)
#define REG_VAD_ENERGY       (KWS_BASE_ADDR + 0x01C)

#define REG_NPU_CTRL         (KWS_BASE_ADDR + 0x020)
#define REG_NPU_STATUS       (KWS_BASE_ADDR + 0x024)
#define REG_NPU_SCORE0       (KWS_BASE_ADDR + 0x028)
#define REG_NPU_SCORE1       (KWS_BASE_ADDR + 0x02C)

#define NPU_FEAT_WINDOW_BASE (KWS_BASE_ADDR + 0x400) // 256 bytes
#define NPU_WGT_WINDOW_BASE  (KWS_BASE_ADDR + 0x500) // 256 bytes

// Helper macros
#define HW_REG(addr)         (*(volatile uint32_t *)(addr))

#endif // SMARTWATCH_SOC_REGS_H_
