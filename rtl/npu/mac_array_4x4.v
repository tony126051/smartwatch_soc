// ==============================================================================
// Module: mac_array_4x4.v
// Project: Ultra-low Power Smartwatch SoC (KWS NPU Engine)
// Description:
//   SIMD MAC Array with 4 parallel PEs.
//   Computes 4 parallel output channels with broadcast activation input.
// ==============================================================================

`timescale 1ns / 1ps

module mac_array_4x4 (
    input  wire               clk,
    input  wire               rst_n,
    
    input  wire               clr_accum,
    input  wire               load_bias,
    input  wire signed [31:0] bias_0,
    input  wire signed [31:0] bias_1,
    input  wire signed [31:0] bias_2,
    input  wire signed [31:0] bias_3,
    
    input  wire               mac_en,
    input  wire signed [7:0]  act_broadcast, // Common activation broadcasted to 4 PEs
    
    input  wire signed [7:0]  wgt_0,         // Filter 0 weight
    input  wire signed [7:0]  wgt_1,         // Filter 1 weight
    input  wire signed [7:0]  wgt_2,         // Filter 2 weight
    input  wire signed [7:0]  wgt_3,         // Filter 3 weight
    
    input  wire [4:0]         shift_right,
    input  wire               apply_relu,
    
    output wire signed [31:0] accum_0,
    output wire signed [31:0] accum_1,
    output wire signed [31:0] accum_2,
    output wire signed [31:0] accum_3,
    
    output wire signed [7:0]  act_out_0,
    output wire signed [7:0]  act_out_1,
    output wire signed [7:0]  act_out_2,
    output wire signed [7:0]  act_out_3
);

    mac_pe pe0 (
        .clk(clk), .rst_n(rst_n),
        .clr_accum(clr_accum), .load_bias(load_bias), .bias_in(bias_0),
        .mac_en(mac_en), .act_in(act_broadcast), .wgt_in(wgt_0),
        .shift_right(shift_right), .apply_relu(apply_relu),
        .accum_out(accum_0), .quant_act_out(act_out_0)
    );

    mac_pe pe1 (
        .clk(clk), .rst_n(rst_n),
        .clr_accum(clr_accum), .load_bias(load_bias), .bias_in(bias_1),
        .mac_en(mac_en), .act_in(act_broadcast), .wgt_in(wgt_1),
        .shift_right(shift_right), .apply_relu(apply_relu),
        .accum_out(accum_1), .quant_act_out(act_out_1)
    );

    mac_pe pe2 (
        .clk(clk), .rst_n(rst_n),
        .clr_accum(clr_accum), .load_bias(load_bias), .bias_in(bias_2),
        .mac_en(mac_en), .act_in(act_broadcast), .wgt_in(wgt_2),
        .shift_right(shift_right), .apply_relu(apply_relu),
        .accum_out(accum_2), .quant_act_out(act_out_2)
    );

    mac_pe pe3 (
        .clk(clk), .rst_n(rst_n),
        .clr_accum(clr_accum), .load_bias(load_bias), .bias_in(bias_3),
        .mac_en(mac_en), .act_in(act_broadcast), .wgt_in(wgt_3),
        .shift_right(shift_right), .apply_relu(apply_relu),
        .accum_out(accum_3), .quant_act_out(act_out_3)
    );

endmodule
