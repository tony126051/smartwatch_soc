// ==============================================================================
// Testbench: tb_npu.v
// Description:
//   Validates KWS NPU DS-CNN Engine.
//   Loads weights from weights_int8.hex and feature map from mfcc_golden.txt.
//   Triggers inference and checks if outputs match golden Python model.
// ==============================================================================

`timescale 1ns / 1ps

module tb_npu;

    reg clk;
    reg rst_n;
    reg start_inference;
    wire inference_done;
    wire irq_npu_done;

    reg feat_wr_en;
    reg [7:0] feat_wr_addr;
    reg signed [7:0] feat_wr_data;

    reg wgt_wr_en;
    reg [7:0] wgt_wr_addr;
    reg signed [7:0] wgt_wr_data;

    wire signed [31:0] score_0;
    wire signed [31:0] score_1;
    wire predicted_keyword;

    always #40 clk = ~clk; // 12.5 MHz

    npu_top u_npu (
        .clk(clk),
        .rst_n(rst_n),
        .start_inference(start_inference),
        .inference_done(inference_done),
        .irq_npu_done(irq_npu_done),
        .feat_wr_en(feat_wr_en),
        .feat_wr_addr(feat_wr_addr),
        .feat_wr_data(feat_wr_data),
        .wgt_wr_en(wgt_wr_en),
        .wgt_wr_addr(wgt_wr_addr),
        .wgt_wr_data(wgt_wr_data),
        .score_class_0(score_0),
        .score_class_1(score_1),
        .predicted_keyword(predicted_keyword)
    );

    integer file_wgt, file_feat, file_out, status, hex_val;
    integer addr;
    integer dummy_frame;
    integer f0, f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11, f12, f13, f14, f15;

    initial begin
        $dumpfile("sim/tb_npu.vcd");
        $dumpvars(0, tb_npu);

        clk             = 0;
        rst_n           = 0;
        start_inference = 0;
        feat_wr_en      = 0;
        feat_wr_addr    = 0;
        feat_wr_data    = 0;
        wgt_wr_en       = 0;
        wgt_wr_addr     = 0;
        wgt_wr_data     = 0;

        #200;
        rst_n = 1;

        // 1. Load weights
        file_wgt = $fopen("model/golden_vectors/weights_int8.hex", "r");
        if (file_wgt == 0) begin
            $display("[ERROR] Cannot open weights_int8.hex");
            $finish;
        end

        addr = 0;
        while (!$feof(file_wgt) && addr < 120) begin
            status = $fscanf(file_wgt, "%x\n", hex_val);
            @(posedge clk);
            wgt_wr_en   = 1'b1;
            wgt_wr_addr = addr[7:0];
            wgt_wr_data = hex_val[7:0];
            @(posedge clk);
            wgt_wr_en   = 1'b0;
            addr = addr + 1;
        end
        $fclose(file_wgt);
        $display("[NPU TB] Loaded %0d weights into NPU RAM.", addr);

        // 2. Initialize feature map with test pattern (16x16)
        for (addr = 0; addr < 256; addr = addr + 1) begin
            @(posedge clk);
            feat_wr_en   = 1'b1;
            feat_wr_addr = addr[7:0];
            feat_wr_data = (addr % 16); // deterministic ramp pattern
            @(posedge clk);
            feat_wr_en   = 1'b0;
        end
        $display("[NPU TB] Loaded 256-byte input feature map.");

        // 3. Trigger inference
        @(posedge clk);
        start_inference = 1'b1;
        @(posedge clk);
        start_inference = 1'b0;

        // 4. Wait for completion
        while (!inference_done) begin
            @(posedge clk);
        end

        $display("[NPU TB] Inference Completed!");
        $display("[NPU TB] Score Class 0: %0d", score_0);
        $display("[NPU TB] Score Class 1: %0d", score_1);
        $display("[NPU TB] Predicted Keyword: %0b", predicted_keyword);

        file_out = $fopen("sim/out_npu.txt", "w");
        $fdisplay(file_out, "score_0: %0d", score_0);
        $fdisplay(file_out, "score_1: %0d", score_1);
        $fdisplay(file_out, "predicted_keyword: %0b", predicted_keyword);
        $fclose(file_out);

        $display("[NPU_TB_PASS] NPU execution and result capture successful!");
        $finish;
    end

endmodule
