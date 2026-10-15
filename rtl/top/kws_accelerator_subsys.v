// ==============================================================================
// Module: kws_accelerator_subsys.v
// Project: Ultra-low Power Smartwatch SoC (v2.0)
// Description:
//   Complete KWS Hardware Accelerator Subsystem with APB3 Slave Interface.
//   Integrates:
//     - Dual-Mic Audio Front-End (DDR PDM Rx, Dual 3rd-order CIC, Micro-Beamformer)
//     - 512-word Circular Audio FIFO with Acoustic Pre-Roll Rewind
//     - Level-1 Hardware VAD (Short-time Absolute Energy & Hangover FSM)
//     - Level-2 KWS NPU (DS-CNN INT8 Matrix Engine with 1024B Dual-Bank Weight RAM)
//     - 2-Tier Context-Aware State Machine & 24-bit Countdown Timer
//     - 5ms Production BIST & MISR Signature Verification Engine
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
    // AFE Control & Tuning Registers (0x000 - 0x00C, 0x030 - 0x034)
    reg        afe_enable;
    reg [1:0]  mic_mode;
    reg [1:0]  mic_delay_taps;
    reg [7:0]  mic_alpha;
    reg        mic_hpf_cutoff_sel;
    reg [7:0]  wind_coh_thres;
    reg        wind_irq_en;
    reg        wind_detected_r;
    reg [1:0]  pre_roll_depth;
    reg        pre_roll_en;
    reg        rewind_req_pulse;
    
    // VAD Registers (0x010 - 0x01C)
    reg        vad_enable;
    reg [23:0] vad_threshold;
    reg [3:0]  vad_hangover;
    reg        vad_irq_pending;
    
    // NPU Registers (0x020 - 0x02C)
    reg        npu_start_pulse;
    reg        npu_irq_pending;
    reg        weight_bank_sel;

    // Context FSM Registers (0x070 - 0x074)
    reg [1:0]  context_state;
    reg        context_gating_en;
    reg        window_active;
    reg        window_timeout;
    reg [23:0] context_window_timer;

    // BIST Registers (0x0F8 - 0x0FC)
    reg        bist_start_pulse;
    reg [2:0]  bist_mode;

    // -------------------------------------------------------------------------
    // 1. Audio Front-End Instantiations
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

    // Primary CIC Decimator (Channel 0)
    wire pcm0_valid;
    wire [15:0] pcm0_data;
    cic_decimator_q64 u_cic0 (
        .clk       (pclk),
        .rst_n     (presetn && afe_enable),
        .pdm_valid (pdm_bit_valid),
        .pdm_bit   (pdm_bit_out),
        .pcm_valid (pcm0_valid),
        .pcm_data  (pcm0_data)
    );

    // Secondary CIC Decimator (Channel 1, for DDR dual-mic mode)
    wire pcm1_valid;
    wire [15:0] pcm1_data;
    cic_decimator_q64 u_cic1 (
        .clk       (pclk),
        .rst_n     (presetn && afe_enable),
        .pdm_valid (pdm_bit_valid),
        .pdm_bit   (~pdm_bit_out), // Inverted/phase-alternated for secondary channel
        .pcm_valid (pcm1_valid),
        .pcm_data  (pcm1_data)
    );

    // Spatial Micro-Beamformer & 350Hz HPF
    wire bf_pcm_valid;
    wire signed [15:0] bf_pcm_out;
    micro_beamformer u_beamformer (
        .clk            (pclk),
        .rst_n          (presetn && afe_enable),
        .pcm_valid      (pcm0_valid),
        .pcm_ch0        (pcm0_data),
        .pcm_ch1        (pcm1_data),
        .mode           (mic_mode),
        .delay_taps     (mic_delay_taps),
        .alpha          (mic_alpha),
        .hpf_cutoff_sel (mic_hpf_cutoff_sel),
        .out_valid      (bf_pcm_valid),
        .out_pcm        (bf_pcm_out)
    );

    // Active Audio Stream Selection (Single-mic bypass vs Beamformer)
    wire active_pcm_valid = (mic_mode == 2'b00) ? pcm0_valid : bf_pcm_valid;
    wire [15:0] active_pcm_data  = (mic_mode == 2'b00) ? pcm0_data  : bf_pcm_out;

    // 512-word Audio FIFO with Pre-Roll Rewind
    wire fifo_empty, fifo_full;
    wire [9:0] fifo_count;
    reg  fifo_rd_en;
    wire [15:0] fifo_rd_data;
    wire [8:0] rewind_samples = (pre_roll_depth == 2'd1) ? 9'd160 :
                                (pre_roll_depth == 2'd2) ? 9'd320 :
                                (pre_roll_depth == 2'd3) ? 9'd480 : 9'd0;

    audio_fifo #(
        .DATA_WIDTH(16),
        .ADDR_WIDTH(9)   // 512 words (v2.0)
    ) u_fifo (
        .clk           (pclk),
        .rst_n         (presetn && afe_enable),
        .wr_en         (active_pcm_valid),
        .wr_data       (active_pcm_data),
        .full          (fifo_full),
        .rd_en         (fifo_rd_en),
        .rd_data       (fifo_rd_data),
        .empty         (fifo_empty),
        .count         (fifo_count),
        .rewind_en     ((vad_raw_irq && pre_roll_en) || rewind_req_pulse),
        .rewind_offset (rewind_samples)
    );

    // -------------------------------------------------------------------------
    // 2. Hardware VAD Core Instantiation
    // -------------------------------------------------------------------------
    wire [23:0] vad_energy;
    wire vad_speech_active;
    wire vad_raw_irq;

    vad_core #(
        .FRAME_SIZE(160)
    ) u_vad (
        .clk              (pclk),
        .rst_n            (presetn),
        .pcm_valid        (active_pcm_valid),
        .pcm_data         (active_pcm_data),
        .cfg_enable       (vad_enable),
        .cfg_threshold    (vad_threshold),
        .cfg_hangover_len (vad_hangover),
        .cur_frame_energy (vad_energy),
        .speech_active    (vad_speech_active),
        .irq_vad_wakeup   (vad_raw_irq)
    );

    // -------------------------------------------------------------------------
    // 3. KWS NPU Core Instantiation (with 1024B Dual-Bank Weight RAM)
    // -------------------------------------------------------------------------
    reg        npu_feat_wr;
    reg [7:0]  npu_feat_addr;
    reg [7:0]  npu_feat_data;
    
    reg        npu_wgt_wr;
    reg [9:0]  npu_wgt_addr;
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
        .weight_bank_sel   (weight_bank_sel),
        .score_class_0     (npu_score_0),
        .score_class_1     (npu_score_1),
        .predicted_keyword (npu_keyword_det)
    );

    // -------------------------------------------------------------------------
    // 4. Production BIST Engine Instantiation
    // -------------------------------------------------------------------------
    wire        bist_busy;
    wire        bist_done;
    wire        bist_pass;
    wire        bist_fail;
    wire [31:0] bist_sig;

    bist_engine u_bist (
        .clk            (pclk),
        .rst_n          (presetn),
        .start_pulse    (bist_start_pulse),
        .test_mode      (bist_mode),
        .bist_busy      (bist_busy),
        .bist_done      (bist_done),
        .bist_pass      (bist_pass),
        .bist_fail      (bist_fail),
        .bist_signature (bist_sig)
    );

    // -------------------------------------------------------------------------
    // 5. 2-Tier Context Countdown Timer (Decrements every 16 kHz sample)
    // -------------------------------------------------------------------------
    always @(posedge pclk or negedge presetn) begin
        if (!presetn) begin
            context_window_timer <= 24'd0;
            window_active        <= 1'b0;
            window_timeout       <= 1'b0;
            context_state        <= 2'b00; // Tier 1 Idle
        end else begin
            if (reg_wr_en && (reg_addr == 12'h074)) begin
                context_window_timer <= reg_wdata[23:0];
                window_active        <= (reg_wdata[23:0] != 24'd0);
                window_timeout       <= 1'b0;
            end else if (active_pcm_valid && window_active) begin
                if (context_window_timer > 24'd1) begin
                    context_window_timer <= context_window_timer - 1'b1;
                end else begin
                    context_window_timer <= 24'd0;
                    window_active        <= 1'b0;
                    window_timeout       <= 1'b1;
                    context_state        <= 2'b00; // Auto-revert to Tier 1 Idle
                end
            end

            // Clear timeout flag on write
            if (reg_wr_en && (reg_addr == 12'h070) && reg_wdata[4]) begin
                window_timeout <= 1'b0;
            end
        end
    end

    // -------------------------------------------------------------------------
    // 6. Interrupt Management
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
    // 7. APB Register Read & Write Decoding
    // -------------------------------------------------------------------------
    always @(posedge pclk or negedge presetn) begin
        if (!presetn) begin
            afe_enable         <= 1'b0;
            mic_mode           <= 2'b00;
            mic_delay_taps     <= 2'b01;
            mic_alpha          <= 8'd255;
            mic_hpf_cutoff_sel <= 1'b0;
            wind_coh_thres     <= 8'd32;  // 0.125 * 256
            wind_irq_en        <= 1'b0;
            wind_detected_r    <= 1'b0;
            pre_roll_depth     <= 2'd2;   // Default 20ms (320 samples)
            pre_roll_en        <= 1'b1;
            rewind_req_pulse   <= 1'b0;
            vad_enable         <= 1'b0;
            vad_threshold      <= 24'd200000;
            vad_hangover       <= 4'd3;
            npu_start_pulse    <= 1'b0;
            weight_bank_sel    <= 1'b0;
            context_gating_en  <= 1'b1;
            bist_start_pulse   <= 1'b0;
            bist_mode          <= 3'b000;
            npu_feat_wr        <= 1'b0;
            npu_wgt_wr         <= 1'b0;
            fifo_rd_en         <= 1'b0;
        end else begin
            npu_start_pulse  <= 1'b0;
            bist_start_pulse <= 1'b0;
            rewind_req_pulse <= 1'b0;
            npu_feat_wr      <= 1'b0;
            npu_wgt_wr       <= 1'b0;
            fifo_rd_en       <= 1'b0;

            if (reg_wr_en) begin
                case (reg_addr[11:0])
                    12'h000: afe_enable         <= reg_wdata[0];
                    12'h00C: begin // AFE_MIC_CTRL
                        mic_mode           <= reg_wdata[1:0];
                        mic_delay_taps     <= reg_wdata[3:2];
                        mic_alpha          <= reg_wdata[15:8];
                        mic_hpf_cutoff_sel <= reg_wdata[16];
                    end
                    12'h010: vad_enable         <= reg_wdata[0];
                    12'h014: vad_threshold      <= reg_wdata[23:0];
                    12'h018: vad_hangover       <= reg_wdata[3:0];
                    12'h020: begin // NPU_CTRL
                        npu_start_pulse <= reg_wdata[0];
                        weight_bank_sel <= reg_wdata[2];
                    end
                    12'h030: begin // AFE_WIND_CFG
                        wind_coh_thres  <= reg_wdata[7:0];
                        wind_irq_en     <= reg_wdata[16];
                        if (reg_wdata[25]) wind_detected_r <= 1'b0; // Clear wind latch
                    end
                    12'h034: begin // AFE_PRE_ROLL
                        pre_roll_depth   <= reg_wdata[1:0];
                        pre_roll_en      <= reg_wdata[2];
                        rewind_req_pulse <= reg_wdata[3];
                    end
                    12'h070: begin // SYS_CONTEXT_CTRL
                        context_state     <= reg_wdata[1:0];
                        context_gating_en <= reg_wdata[2];
                    end
                    12'h0FC: begin // BIST_CTRL
                        bist_start_pulse <= reg_wdata[0];
                        bist_mode        <= reg_wdata[7:5];
                    end
                    default: begin
                        // NPU Feature Window: 0x400 - 0x4FF (256B)
                        if (reg_addr >= 12'h400 && reg_addr < 12'h500) begin
                            npu_feat_wr   <= 1'b1;
                            npu_feat_addr <= reg_addr[7:0];
                            npu_feat_data <= reg_wdata[7:0];
                        end
                        // NPU Weight Window: 0x500 - 0x8FF (1024B Dual Bank)
                        else if (reg_addr >= 12'h500 && reg_addr < 12'h900) begin
                            npu_wgt_wr   <= 1'b1;
                            npu_wgt_addr <= reg_addr[9:0] - 10'h100;
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
            12'h004: reg_rdata = {14'd0, fifo_count, 5'd0, wind_detected_r, fifo_full, fifo_empty};
            12'h008: reg_rdata = {16'd0, fifo_rd_data};
            12'h00C: reg_rdata = {15'd0, mic_hpf_cutoff_sel, mic_alpha, 4'd0, mic_delay_taps, mic_mode};
            12'h010: reg_rdata = {30'd0, vad_irq_pending, vad_enable};
            12'h014: reg_rdata = {8'd0, vad_threshold};
            12'h018: reg_rdata = {28'd0, vad_hangover};
            12'h01C: reg_rdata = {7'd0, vad_speech_active, vad_energy};
            12'h020: reg_rdata = {29'd0, weight_bank_sel, npu_irq_pending, 1'b0};
            12'h024: reg_rdata = {25'd0, 3'd0, npu_keyword_det, npu_done, (u_npu.state != 0)};
            12'h028: reg_rdata = npu_score_0;
            12'h02C: reg_rdata = npu_score_1;
            12'h030: reg_rdata = {7'd0, wind_detected_r, 7'd0, wind_irq_en, 8'h80, wind_coh_thres};
            12'h034: reg_rdata = {29'd0, pre_roll_en, pre_roll_depth};
            12'h070: reg_rdata = {27'd0, window_timeout, window_active, context_gating_en, context_state};
            12'h074: reg_rdata = {8'd0, context_window_timer};
            12'h0F8: reg_rdata = bist_sig;
            12'h0FC: reg_rdata = {24'd0, bist_mode, bist_fail, bist_pass, bist_done, bist_busy, 1'b0};
            default: reg_rdata = 32'd0;
        endcase
    end

endmodule
