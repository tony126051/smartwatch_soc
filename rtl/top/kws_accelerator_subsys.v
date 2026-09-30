// ==============================================================================
// Module: kws_accelerator_subsys.v
// Project: Ultra-low Power Smartwatch SoC
// Description:
//   Complete KWS Hardware Accelerator Subsystem with APB Slave Interface.
//   Integrates:
//     - Audio Front-End (PDM Rx, 3rd-order CIC Decimator, 256-word FIFO)
//     - Level-1 Hardware VAD (Always-on Short-time Energy Detector)
//     - Level-2 KWS NPU (DS-CNN INT8 Matrix Accelerator)
// ==============================================================================

`timescale 1ns / 1ps

module kws_accelerator_subsys (
    input  wire        pclk,
    input  wire        presetn,
    
    // APB Bus Interface
    input  wire        psel,
    input  wire        penable,
    input  wire        pwrite,
    input  wire [11:0] paddr,
    input  wire [31:0] pwdata,
    output wire [31:0] prdata,
    output wire        pready,
    output wire        pslverr,
    
    // External Microphone Interface
    input  wire        pdm_clk_en,
    input  wire        pdm_data_in,
    
    // System Wakeup & Done Interrupts
    output wire        irq_vad_wakeup,
    output wire        irq_npu_done
);

    // -------------------------------------------------------------------------
    // APB Interface Adapter
    // -------------------------------------------------------------------------
    wire        reg_wr_en;
    wire        reg_rd_en;
    wire [11:0] reg_addr;
    wire [31:0] reg_wdata;
    reg  [31:0] reg_rdata;

    apb_slave_adapter #(
        .ADDR_WIDTH(12),
        .DATA_WIDTH(32)
    ) u_apb_if (
        .pclk      (pclk),
        .presetn   (presetn),
        .psel      (psel),
        .penable   (penable),
        .pwrite    (pwrite),
        .paddr     (paddr),
        .pwdata    (pwdata),
        .prdata    (prdata),
        .pready    (pready),
        .pslverr   (pslverr),
        .reg_wr_en (reg_wr_en),
        .reg_rd_en (reg_rd_en),
        .reg_addr  (reg_addr),
        .reg_wdata (reg_wdata),
        .reg_rdata (reg_rdata)
    );

    // -------------------------------------------------------------------------
    // Register Declarations
    // -------------------------------------------------------------------------
    // AFE Registers (0x00 - 0x0C)
    reg        afe_enable;
    
    // VAD Registers (0x10 - 0x1C)
    reg        vad_enable;
    reg [23:0] vad_threshold;
    reg [3:0]  vad_hangover;
    reg        vad_irq_pending;
    
    // NPU Registers (0x20 - 0x30)
    reg        npu_start_pulse;
    reg        npu_irq_pending;

    // -------------------------------------------------------------------------
    // Audio Front-End Instantiations
    // -------------------------------------------------------------------------
    wire pdm_bit_valid;
    wire pdm_bit_out;
    pdm_receiver u_rx (
        .clk           (pclk),
        .rst_n         (presetn),
        .pdm_clk_en    (pdm_clk_en),
        .pdm_data_in   (pdm_data_in),
        .pdm_bit_valid (pdm_bit_valid),
        .pdm_bit_out   (pdm_bit_out)
    );

    wire pcm_valid;
    wire [15:0] pcm_data;
    cic_decimator_q64 u_cic (
        .clk       (pclk),
        .rst_n     (presetn && afe_enable),
        .pdm_valid (pdm_bit_valid),
        .pdm_bit   (pdm_bit_out),
        .pcm_valid (pcm_valid),
        .pcm_data  (pcm_data)
    );

    wire fifo_empty, fifo_full;
    wire [8:0] fifo_count;
    reg  fifo_rd_en;
    wire [15:0] fifo_rd_data;
    audio_fifo #(
        .DATA_WIDTH(16),
        .ADDR_WIDTH(8)
    ) u_fifo (
        .clk     (pclk),
        .rst_n   (presetn && afe_enable),
        .wr_en   (pcm_valid),
        .wr_data (pcm_data),
        .full    (fifo_full),
        .rd_en   (fifo_rd_en),
        .rd_data (fifo_rd_data),
        .empty   (fifo_empty),
        .count   (fifo_count)
    );

    // -------------------------------------------------------------------------
    // Hardware VAD Core Instantiation
    // -------------------------------------------------------------------------
    wire [23:0] vad_energy;
    wire vad_speech_active;
    wire vad_raw_irq;

    vad_core #(
        .FRAME_SIZE(160)
    ) u_vad (
        .clk              (pclk),
        .rst_n            (presetn),
        .pcm_valid        (pcm_valid),
        .pcm_data         (pcm_data),
        .cfg_enable       (vad_enable),
        .cfg_threshold    (vad_threshold),
        .cfg_hangover_len (vad_hangover),
        .cur_frame_energy (vad_energy),
        .speech_active    (vad_speech_active),
        .irq_vad_wakeup   (vad_raw_irq)
    );

    // -------------------------------------------------------------------------
    // KWS NPU Core Instantiation
    // -------------------------------------------------------------------------
    reg        npu_feat_wr;
    reg [7:0]  npu_feat_addr;
    reg [7:0]  npu_feat_data;
    
    reg        npu_wgt_wr;
    reg [7:0]  npu_wgt_addr;
    reg [7:0]  npu_wgt_data;
    
    wire signed [31:0] npu_score_0;
    wire signed [31:0] npu_score_1;
    wire npu_keyword_det;
    wire npu_done;
    wire npu_raw_irq;

    npu_top u_npu (
        .clk               (pclk),
        .rst_n             (presetn),
        .start_inference   (npu_start_pulse),
        .inference_done    (npu_done),
        .irq_npu_done      (npu_raw_irq),
        .feat_wr_en        (npu_feat_wr),
        .feat_wr_addr      (npu_feat_addr),
        .feat_wr_data      (npu_feat_data),
        .wgt_wr_en         (npu_wgt_wr),
        .wgt_wr_addr       (npu_wgt_addr),
        .wgt_wr_data       (npu_wgt_data),
        .score_class_0     (npu_score_0),
        .score_class_1     (npu_score_1),
        .predicted_keyword (npu_keyword_det)
    );

    // -------------------------------------------------------------------------
    // Interrupt Management
    // -------------------------------------------------------------------------
    always @(posedge pclk or negedge presetn) begin
        if (!presetn) begin
            vad_irq_pending <= 1'b0;
            npu_irq_pending <= 1'b0;
        end else begin
            if (vad_raw_irq)
                vad_irq_pending <= 1'b1;
            else if (reg_wr_en && (reg_addr == 12'h010) && reg_wdata[1]) // Write 1 to clear
                vad_irq_pending <= 1'b0;

            if (npu_raw_irq)
                npu_irq_pending <= 1'b1;
            else if (reg_wr_en && (reg_addr == 12'h020) && reg_wdata[1]) // Write 1 to clear
                npu_irq_pending <= 1'b0;
        end
    end

    assign irq_vad_wakeup = vad_irq_pending;
    assign irq_npu_done   = npu_irq_pending;

    // -------------------------------------------------------------------------
    // APB Register Read & Write Decoding
    // -------------------------------------------------------------------------
    always @(posedge pclk or negedge presetn) begin
        if (!presetn) begin
            afe_enable      <= 1'b0;
            vad_enable      <= 1'b0;
            vad_threshold   <= 24'd200000;
            vad_hangover    <= 4'd3;
            npu_start_pulse <= 1'b0;
            npu_feat_wr     <= 1'b0;
            npu_wgt_wr      <= 1'b0;
            fifo_rd_en      <= 1'b0;
        end else begin
            npu_start_pulse <= 1'b0;
            npu_feat_wr     <= 1'b0;
            npu_wgt_wr      <= 1'b0;
            fifo_rd_en      <= 1'b0;

            if (reg_wr_en) begin
                case (reg_addr[11:0])
                    12'h000: afe_enable    <= reg_wdata[0];
                    12'h010: vad_enable    <= reg_wdata[0];
                    12'h014: vad_threshold <= reg_wdata[23:0];
                    12'h018: vad_hangover  <= reg_wdata[3:0];
                    12'h020: npu_start_pulse <= reg_wdata[0];
                    default: begin
                        // NPU Feature Window: 0x400 - 0x4FF
                        if (reg_addr >= 12'h400 && reg_addr < 12'h500) begin
                            npu_feat_wr   <= 1'b1;
                            npu_feat_addr <= reg_addr[7:0];
                            npu_feat_data <= reg_wdata[7:0];
                        end
                        // NPU Weight Window: 0x500 - 0x5FF
                        else if (reg_addr >= 12'h500 && reg_addr < 12'h600) begin
                            npu_wgt_wr   <= 1'b1;
                            npu_wgt_addr <= reg_addr[7:0];
                            npu_wgt_data <= reg_wdata[7:0];
                        end
                    end
                endcase
            end

            // FIFO Pop on read of 0x008
            if (reg_rd_en && (reg_addr == 12'h008)) begin
                fifo_rd_en <= 1'b1;
            end
        end
    end

    // APB Read Multiplexer
    always @(*) begin
        case (reg_addr[11:0])
            12'h000: reg_rdata = {31'd0, afe_enable};
            12'h004: reg_rdata = {15'd0, fifo_count, 6'd0, fifo_full, fifo_empty};
            12'h008: reg_rdata = {16'd0, fifo_rd_data};
            12'h010: reg_rdata = {30'd0, vad_irq_pending, vad_enable};
            12'h014: reg_rdata = {8'd0, vad_threshold};
            12'h018: reg_rdata = {28'd0, vad_hangover};
            12'h01C: reg_rdata = {7'd0, vad_speech_active, vad_energy};
            12'h020: reg_rdata = {30'd0, npu_irq_pending, 1'b0};
            12'h024: reg_rdata = {29'd0, npu_keyword_det, npu_done, (u_npu.state != 0)};
            12'h028: reg_rdata = npu_score_0;
            12'h02C: reg_rdata = npu_score_1;
            default: reg_rdata = 32'd0;
        endcase
    end

endmodule
