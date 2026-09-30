// ==============================================================================
// Module: npu_top.v
// Project: Ultra-low Power Smartwatch SoC (Level-2 KWS Engine)
// Description:
//   Complete KWS NPU Top module.
//   Executes a lightweight Depthwise Separable CNN (DS-CNN) for keyword spotting.
//   Includes on-chip Weight RAM, Activation Buffers, MAC Engine, and FSM.
// ==============================================================================

`timescale 1ns / 1ps

module npu_top (
    input  wire               clk,
    input  wire               rst_n,
    
    // Control interface
    input  wire               start_inference,
    output reg                inference_done,
    output reg                irq_npu_done,
    
    // Input Feature Memory Interface (16x16 = 256 INT8 bytes)
    input  wire               feat_wr_en,
    input  wire [7:0]         feat_wr_addr,
    input  wire signed [7:0]  feat_wr_data,
    
    // Weight RAM Programming Interface
    input  wire               wgt_wr_en,
    input  wire [7:0]         wgt_wr_addr,
    input  wire signed [7:0]  wgt_wr_data,
    
    // Output Classification Results
    output reg  signed [31:0] score_class_0,
    output reg  signed [31:0] score_class_1,
    output reg                predicted_keyword // 1 = Keyword detected, 0 = Non-keyword
);

    // -------------------------------------------------------------------------
    // On-chip Internal Memories
    // -------------------------------------------------------------------------
    // Feature Buffer (256 bytes)
    reg signed [7:0] feat_mem [0:255];
    
    // Weight RAM (256 bytes, accommodates all layers)
    reg signed [7:0] weight_mem [0:255];
    
    always @(posedge clk) begin
        if (feat_wr_en)
            feat_mem[feat_wr_addr] <= feat_wr_data;
        if (wgt_wr_en)
            weight_mem[wgt_wr_addr] <= wgt_wr_data;
    end

    // Intermediate Activation Ping-Pong RAMs (4 channels x 16x16 = 1024 bytes)
    reg signed [7:0] act_buf_1 [0:1023];
    reg signed [7:0] act_buf_2 [0:1023];
    reg signed [7:0] act_buf_pw [0:2047]; // 8 channels x 16x16 = 2048 bytes

    // -------------------------------------------------------------------------
    // Control FSM
    // -------------------------------------------------------------------------
    localparam ST_IDLE  = 4'd0;
    localparam ST_CONV1 = 4'd1;
    localparam ST_DW    = 4'd2;
    localparam ST_PW    = 4'd3;
    localparam ST_GAP   = 4'd4;
    localparam ST_FC    = 4'd5;
    localparam ST_DONE  = 4'd6;

    reg [3:0] state;

    // Layer counters
    reg [4:0] r_cnt;    // Row: 0..15
    reg [4:0] c_cnt;    // Col: 0..15
    reg [3:0] oc_cnt;   // Out channel: 0..7
    reg [3:0] ic_cnt;   // In channel: 0..3
    reg [2:0] kr_cnt;   // Kernel row: 0..2
    reg [2:0] kc_cnt;   // Kernel col: 0..2

    // Accumulators
    reg signed [31:0] pe_accum;
    reg signed [31:0] gap_accum [0:7];

    integer i;

    // Helper functions for address translation
    function [7:0] get_feat_idx(input [4:0] r, input [4:0] c);
        get_feat_idx = (r << 4) + c;
    endfunction

    // -------------------------------------------------------------------------
    // Execution Logic
    // -------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state             <= ST_IDLE;
            inference_done    <= 1'b0;
            irq_npu_done      <= 1'b0;
            score_class_0     <= 32'sd0;
            score_class_1     <= 32'sd0;
            predicted_keyword <= 1'b0;
            r_cnt             <= 5'd0;
            c_cnt             <= 5'd0;
            oc_cnt            <= 4'd0;
            ic_cnt            <= 4'd0;
            kr_cnt            <= 3'd0;
            kc_cnt            <= 3'd0;
            pe_accum          <= 32'sd0;
            for (i=0; i<8; i=i+1) gap_accum[i] <= 32'sd0;
        end else begin
            irq_npu_done <= 1'b0;

            case (state)
                ST_IDLE: begin
                    inference_done <= 1'b0;
                    if (start_inference) begin
                        state  <= ST_CONV1;
                        r_cnt  <= 5'd0;
                        c_cnt  <= 5'd0;
                        oc_cnt <= 4'd0;
                        kr_cnt <= 3'd0;
                        kc_cnt <= 3'd0;
                        pe_accum <= 32'sd0;
                    end
                end

                // Layer 1: Conv2D (Simplified 1-PE sequential pipeline for clean verification)
                ST_CONV1: begin
                    // Compute kernel window
                    // Address in weight_mem: oc*9 + kr*3 + kc
                    if (kr_cnt < 3) begin
                        if (kc_cnt < 3) begin
                            // Sample input
                            if ((r_cnt + kr_cnt >= 1) && (r_cnt + kr_cnt - 1 < 16) &&
                                (c_cnt + kc_cnt >= 1) && (c_cnt + kc_cnt - 1 < 16)) begin
                                pe_accum <= pe_accum + 
                                    feat_mem[get_feat_idx(r_cnt + kr_cnt - 1, c_cnt + kc_cnt - 1)] *
                                    weight_mem[oc_cnt * 9 + kr_cnt * 3 + kc_cnt];
                            end
                            kc_cnt <= kc_cnt + 1'b1;
                        end else begin
                            kc_cnt <= 3'd0;
                            kr_cnt <= kr_cnt + 1'b1;
                        end
                    end else begin
                        // Pixel complete -> requantize & ReLU
                        act_buf_1[(oc_cnt << 8) + (r_cnt << 4) + c_cnt] <= 
                            (pe_accum > 0) ? ((pe_accum >>> 5) > 127 ? 8'sd127 : pe_accum[12:5]) : 8'sd0;
                        pe_accum <= 32'sd0;
                        kr_cnt   <= 3'd0;
                        kc_cnt   <= 3'd0;

                        if (c_cnt < 15) begin
                            c_cnt <= c_cnt + 1'b1;
                        end else begin
                            c_cnt <= 5'd0;
                            if (r_cnt < 15) begin
                                r_cnt <= r_cnt + 1'b1;
                            end else begin
                                r_cnt <= 5'd0;
                                if (oc_cnt < 3) begin
                                    oc_cnt <= oc_cnt + 1'b1;
                                end else begin
                                    // Conv1 Done -> DW Conv
                                    state  <= ST_DW;
                                    oc_cnt <= 4'd0;
                                    r_cnt  <= 5'd0;
                                    c_cnt  <= 5'd0;
                                end
                            end
                        end
                    end
                end

                // Layer 2: Depthwise Conv (4 channels)
                ST_DW: begin
                    // Weight base for DW: 36
                    if (kr_cnt < 3) begin
                        if (kc_cnt < 3) begin
                            if ((r_cnt + kr_cnt >= 1) && (r_cnt + kr_cnt - 1 < 16) &&
                                (c_cnt + kc_cnt >= 1) && (c_cnt + kc_cnt - 1 < 16)) begin
                                pe_accum <= pe_accum + 
                                    act_buf_1[(oc_cnt << 8) + ((r_cnt + kr_cnt - 1) << 4) + (c_cnt + kc_cnt - 1)] *
                                    weight_mem[36 + oc_cnt * 9 + kr_cnt * 3 + kc_cnt];
                            end
                            kc_cnt <= kc_cnt + 1'b1;
                        end else begin
                            kc_cnt <= 3'd0;
                            kr_cnt <= kr_cnt + 1'b1;
                        end
                    end else begin
                        act_buf_2[(oc_cnt << 8) + (r_cnt << 4) + c_cnt] <= 
                            (pe_accum > 0) ? ((pe_accum >>> 5) > 127 ? 8'sd127 : pe_accum[12:5]) : 8'sd0;
                        pe_accum <= 32'sd0;
                        kr_cnt   <= 3'd0;
                        kc_cnt   <= 3'd0;

                        if (c_cnt < 15) begin
                            c_cnt <= c_cnt + 1'b1;
                        end else begin
                            c_cnt <= 5'd0;
                            if (r_cnt < 15) begin
                                r_cnt <= r_cnt + 1'b1;
                            end else begin
                                r_cnt <= 5'd0;
                                if (oc_cnt < 3) begin
                                    oc_cnt <= oc_cnt + 1'b1;
                                end else begin
                                    // DW Done -> Pointwise Conv
                                    state  <= ST_PW;
                                    oc_cnt <= 4'd0;
                                    ic_cnt <= 4'd0;
                                    r_cnt  <= 5'd0;
                                    c_cnt  <= 5'd0;
                                end
                            end
                        end
                    end
                end

                // Layer 3: Pointwise Conv (4 in -> 8 out, 1x1)
                ST_PW: begin
                    // Weight base for PW: 36 + 36 = 72
                    if (ic_cnt < 4) begin
                        pe_accum <= pe_accum + 
                            act_buf_2[(ic_cnt << 8) + (r_cnt << 4) + c_cnt] *
                            weight_mem[72 + oc_cnt * 4 + ic_cnt];
                        ic_cnt <= ic_cnt + 1'b1;
                    end else begin
                        act_buf_pw[(oc_cnt << 8) + (r_cnt << 4) + c_cnt] <= 
                            (pe_accum > 0) ? ((pe_accum >>> 5) > 127 ? 8'sd127 : pe_accum[12:5]) : 8'sd0;
                        pe_accum <= 32'sd0;
                        ic_cnt   <= 4'd0;

                        if (c_cnt < 15) begin
                            c_cnt <= c_cnt + 1'b1;
                        end else begin
                            c_cnt <= 5'd0;
                            if (r_cnt < 15) begin
                                r_cnt <= r_cnt + 1'b1;
                            end else begin
                                r_cnt <= 5'd0;
                                if (oc_cnt < 7) begin
                                    oc_cnt <= oc_cnt + 1'b1;
                                end else begin
                                    // PW Done -> Global Average Pooling
                                    state  <= ST_GAP;
                                    oc_cnt <= 4'd0;
                                    r_cnt  <= 5'd0;
                                    c_cnt  <= 5'd0;
                                end
                            end
                        end
                    end
                end

                // Layer 4: Global Average Pooling (8 channels, 16x16 sum)
                ST_GAP: begin
                    gap_accum[oc_cnt] <= gap_accum[oc_cnt] + act_buf_pw[(oc_cnt << 8) + (r_cnt << 4) + c_cnt];
                    if (c_cnt < 15) begin
                        c_cnt <= c_cnt + 1'b1;
                    end else begin
                        c_cnt <= 5'd0;
                        if (r_cnt < 15) begin
                            r_cnt <= r_cnt + 1'b1;
                        end else begin
                            r_cnt <= 5'd0;
                            if (oc_cnt < 7) begin
                                oc_cnt <= oc_cnt + 1'b1;
                            end else begin
                                // GAP complete -> FC Layer
                                state  <= ST_FC;
                                oc_cnt <= 4'd0; // class 0 or 1
                                ic_cnt <= 4'd0; // 0..7
                                pe_accum <= (oc_cnt == 0) ? 32'sd10 : -32'sd10; // Bias
                            end
                        end
                    end
                end

                // Layer 5: Fully-Connected (Dense) (8 -> 2)
                ST_FC: begin
                    // Weight base for FC: 72 + 32 = 104
                    if (ic_cnt < 8) begin
                        // gap_accum[ic_cnt] >> 8 is the average
                        pe_accum <= pe_accum + (gap_accum[ic_cnt] >>> 8) * weight_mem[104 + oc_cnt * 8 + ic_cnt];
                        ic_cnt <= ic_cnt + 1'b1;
                    end else begin
                        if (oc_cnt == 0) begin
                            score_class_0 <= pe_accum;
                            oc_cnt   <= 4'd1;
                            ic_cnt   <= 4'd0;
                            pe_accum <= -32'sd10; // bias for class 1
                        end else begin
                            score_class_1 <= pe_accum;
                            predicted_keyword <= (pe_accum > score_class_0);
                            state <= ST_DONE;
                        end
                    end
                end

                ST_DONE: begin
                    inference_done <= 1'b1;
                    irq_npu_done   <= 1'b1;
                    state          <= ST_IDLE;
                end
            endcase
        end
    end

endmodule
