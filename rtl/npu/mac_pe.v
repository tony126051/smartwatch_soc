// ==============================================================================
// Module: mac_pe.v
// Project: Ultra-low Power Smartwatch SoC (KWS NPU Engine)
// Description:
//   INT8 Multiply-Accumulate Processing Element (PE).
//   8-bit signed weight * 8-bit signed activation -> 32-bit signed accumulator.
//   Supports bias loading, dynamic shift requantization, and ReLU activation.
// ==============================================================================

`timescale 1ns / 1ps

module mac_pe (
    input  wire               clk,
    input  wire               rst_n,
    
    // Control strobes
    input  wire               clr_accum,    // Clear / initialize accumulator
    input  wire               load_bias,    // Load initial 32-bit bias
    input  wire signed [31:0] bias_in,
    input  wire               mac_en,       // Perform MAC: accum += act * weight
    input  wire signed [7:0]  act_in,       // 8-bit signed activation
    input  wire signed [7:0]  wgt_in,       // 8-bit signed weight
    
    // Post-processing configuration
    input  wire [4:0]         shift_right,  // Fixed-point scaling factor
    input  wire               apply_relu,   // Apply ReLU (clip negative to 0)
    
    // Outputs
    output reg  signed [31:0] accum_out,
    output wire signed [7:0]  quant_act_out // Quantized 8-bit output activation
);

    // Multiplier: 8x8 signed -> 16-bit signed
    wire signed [15:0] prod;
    assign prod = act_in * wgt_in;

    // Accumulator logic
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            accum_out <= 32'sd0;
        end else if (clr_accum) begin
            accum_out <= load_bias ? bias_in : 32'sd0;
        end else if (mac_en) begin
            accum_out <= accum_out + {{16{prod[15]}}, prod};
        end
    end

    // Requantization: shift and saturate to INT8
    wire signed [31:0] shifted;
    assign shifted = accum_out >>> shift_right;

    // ReLU and saturation
    reg signed [7:0] final_val;
    always @(*) begin
        if (apply_relu && shifted < 0) begin
            final_val = 8'sd0;
        end else if (shifted > 32'sd127) begin
            final_val = 8'sd127;
        end else if (shifted < -32'sd128) begin
            final_val = -8'sd128;
        end else begin
            final_val = shifted[7:0];
        end
    end

    assign quant_act_out = final_val;

endmodule
