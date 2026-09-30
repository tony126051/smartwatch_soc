// ==============================================================================
// Module: smartwatch_soc_top.v
// Project: Ultra-low Power Smartwatch SoC
// Description:
//   Complete Heterogeneous SoC Top-Level Module.
//   Integrates:
//     - 32-bit RISC-V PicoRV32 CPU Core
//     - 8 KB Boot ROM / Instruction SRAM (0x0000_0000)
//     - 8 KB Data SRAM (0x1000_0000)
//     - Bus Interconnect & APB Bridge
//     - KWS Hardware Accelerator Subsystem (0x4000_0000)
//     - Dual-level Interrupts (VAD IRQ -> irq[0], NPU IRQ -> irq[1])
//     - System Status & Debug Registers
// ==============================================================================

`timescale 1ns / 1ps

module smartwatch_soc_top #(
    parameter BOOT_HEX_FILE = "sw/firmware.hex"
)(
    input  wire        clk,
    input  wire        rst_n,
    
    // External Audio Microphone Interface
    input  wire        pdm_clk_en,
    input  wire        pdm_data_in,
    
    // Status & Debug LEDs
    output reg  [7:0]  debug_leds,
    output wire        soc_trap
);

    // -------------------------------------------------------------------------
    // CPU Native Memory Bus Signals
    // -------------------------------------------------------------------------
    wire        mem_valid;
    wire        mem_instr;
    reg         mem_ready;
    wire [31:0] mem_addr;
    wire [31:0] mem_wdata;
    wire [ 3:0] mem_wstrb;
    reg  [31:0] mem_rdata;

    // CPU Interrupt lines
    wire [31:0] cpu_irq;
    wire [31:0] cpu_eoi;
    wire        irq_vad_wakeup;
    wire        irq_npu_done;

    assign cpu_irq = {30'd0, irq_npu_done, irq_vad_wakeup};

    // -------------------------------------------------------------------------
    // PicoRV32 CPU Core Instantiation
    // -------------------------------------------------------------------------
    picorv32 #(
        .ENABLE_COUNTERS     (1),
        .ENABLE_COUNTERS64   (0),
        .ENABLE_REGS_16_31   (1),
        .ENABLE_REGS_DUALPORT(1),
        .BARREL_SHIFTER      (1),
        .ENABLE_MUL          (0),
        .ENABLE_DIV          (0),
        .ENABLE_IRQ          (1),
        .ENABLE_IRQ_QREGS    (0),
        .PROGADDR_RESET      (32'h0000_0000),
        .PROGADDR_IRQ        (32'h0000_0010),
        .STACKADDR           (32'h1000_2000)
    ) u_cpu (
        .clk         (clk),
        .resetn      (rst_n),
        .trap        (soc_trap),
        .mem_valid   (mem_valid),
        .mem_instr   (mem_instr),
        .mem_ready   (mem_ready),
        .mem_addr    (mem_addr),
        .mem_wdata   (mem_wdata),
        .mem_wstrb   (mem_wstrb),
        .mem_rdata   (mem_rdata),
        .mem_la_read (),
        .mem_la_write(),
        .mem_la_addr (),
        .mem_la_wdata(),
        .mem_la_wstrb(),
        .pcpi_valid  (),
        .pcpi_insn   (),
        .pcpi_rs1    (),
        .pcpi_rs2    (),
        .pcpi_wr     (1'b0),
        .pcpi_rd     (32'd0),
        .pcpi_wait   (1'b0),
        .pcpi_ready  (1'b0),
        .irq         (cpu_irq),
        .eoi         (cpu_eoi),
        .trace_valid (),
        .trace_data  ()
    );

    // -------------------------------------------------------------------------
    // Address Decoding
    // -------------------------------------------------------------------------
    // 0x0000_0000 - 0x0000_1FFF : Boot ROM / ITCM (8 KB)
    // 0x1000_0000 - 0x1000_1FFF : Data SRAM / DTCM (8 KB)
    // 0x4000_0000 - 0x4000_0FFF : KWS Accelerator Subsystem (APB)
    // 0x8000_0000 - 0x8000_000F : SoC System Status & LEDs
    wire sel_rom  = (mem_addr[31:28] == 4'h0);
    wire sel_sram = (mem_addr[31:28] == 4'h1);
    wire sel_apb  = (mem_addr[31:28] == 4'h4);
    wire sel_sys  = (mem_addr[31:28] == 4'h8);

    // -------------------------------------------------------------------------
    // 1. Boot ROM (8 KB = 2048 words)
    // -------------------------------------------------------------------------
    reg [31:0] boot_rom [0:2047];
    reg [31:0] rom_rdata;

    initial begin
        // Initialize ROM with firmware hex if exists
        $readmemh(BOOT_HEX_FILE, boot_rom);
    end

    always @(posedge clk) begin
        if (mem_valid && sel_rom && (mem_wstrb == 0)) begin
            rom_rdata <= boot_rom[mem_addr[12:2]];
        end
    end

    // -------------------------------------------------------------------------
    // 2. Data SRAM (8 KB = 2048 words with byte write enables)
    // -------------------------------------------------------------------------
    reg [31:0] data_sram [0:2047];
    reg [31:0] sram_rdata;

    always @(posedge clk) begin
        if (mem_valid && sel_sram) begin
            if (mem_wstrb[0]) data_sram[mem_addr[12:2]][ 7: 0] <= mem_wdata[ 7: 0];
            if (mem_wstrb[1]) data_sram[mem_addr[12:2]][15: 8] <= mem_wdata[15: 8];
            if (mem_wstrb[2]) data_sram[mem_addr[12:2]][23:16] <= mem_wdata[23:16];
            if (mem_wstrb[3]) data_sram[mem_addr[12:2]][31:24] <= mem_wdata[31:24];
            sram_rdata <= data_sram[mem_addr[12:2]];
        end
    end

    // -------------------------------------------------------------------------
    // 3. APB Bridge for KWS Accelerator Subsystem
    // -------------------------------------------------------------------------
    reg        apb_psel;
    reg        apb_penable;
    reg        apb_pwrite;
    reg [11:0] apb_paddr;
    reg [31:0] apb_pwdata;
    wire [31:0] apb_prdata;
    wire        apb_pready;
    wire        apb_pslverr;

    localparam APB_IDLE   = 2'd0;
    localparam APB_SETUP  = 2'd1;
    localparam APB_ACCESS = 2'd2;
    reg [1:0] apb_state;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            apb_state   <= APB_IDLE;
            apb_psel    <= 1'b0;
            apb_penable <= 1'b0;
            apb_pwrite  <= 1'b0;
            apb_paddr   <= 12'd0;
            apb_pwdata  <= 32'd0;
        end else begin
            case (apb_state)
                APB_IDLE: begin
                    if (mem_valid && sel_apb) begin
                        apb_psel    <= 1'b1;
                        apb_pwrite  <= |mem_wstrb;
                        apb_paddr   <= mem_addr[11:0];
                        apb_pwdata  <= mem_wdata;
                        apb_penable <= 1'b0;
                        apb_state   <= APB_SETUP;
                    end
                end
                APB_SETUP: begin
                    apb_penable <= 1'b1;
                    apb_state   <= APB_ACCESS;
                end
                APB_ACCESS: begin
                    if (apb_pready) begin
                        apb_psel    <= 1'b0;
                        apb_penable <= 1'b0;
                        apb_state   <= APB_IDLE;
                    end
                end
            endcase
        end
    end

    kws_accelerator_subsys u_kws_subsys (
        .pclk           (clk),
        .presetn        (rst_n),
        .psel           (apb_psel),
        .penable        (apb_penable),
        .pwrite         (apb_pwrite),
        .paddr          (apb_paddr),
        .pwdata         (apb_pwdata),
        .prdata         (apb_prdata),
        .pready         (apb_pready),
        .pslverr        (apb_pslverr),
        .pdm_clk_en     (pdm_clk_en),
        .pdm_data_in    (pdm_data_in),
        .irq_vad_wakeup (irq_vad_wakeup),
        .irq_npu_done   (irq_npu_done)
    );

    // -------------------------------------------------------------------------
    // 4. Debug Registers & LEDs (0x8000_0000)
    // -------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            debug_leds <= 8'h00;
        end else if (mem_valid && sel_sys && (|mem_wstrb)) begin
            debug_leds <= mem_wdata[7:0];
        end
    end

    // -------------------------------------------------------------------------
    // Memory Response Mux & Ready Logic
    // -------------------------------------------------------------------------
    always @(*) begin
        mem_ready = 1'b0;
        mem_rdata = 32'd0;

        if (sel_rom) begin
            mem_ready = 1'b1;
            mem_rdata = rom_rdata;
        end else if (sel_sram) begin
            mem_ready = 1'b1;
            mem_rdata = sram_rdata;
        end else if (sel_apb) begin
            mem_ready = (apb_state == APB_ACCESS) && apb_pready;
            mem_rdata = apb_prdata;
        end else if (sel_sys) begin
            mem_ready = 1'b1;
            mem_rdata = {24'd0, debug_leds};
        end
    end

endmodule
