// ==============================================================================
// Module: cic_decimator_q64.v
// Project: Ultra-low Power Smartwatch SoC (Audio Front-End)
// Description:
//   3rd-order Cascaded Integrator-Comb (CIC) Decimation Filter.
//   Downsamples 1.024MHz 1-bit PDM stream to 16kHz 16-bit signed PCM audio.
//   Decimation factor R = 64, Differential delay M = 1, Order N = 3.
// ==============================================================================

`timescale 1ns / 1ps

module cic_decimator_q64 (
    input  wire        clk,            // System clock
    input  wire        rst_n,          // Active-low asynchronous reset
    input  wire        pdm_valid,      // Valid strobe at 1.024MHz
    input  wire        pdm_bit,        // PDM input bit (0 -> -1, 1 -> +1)
    output reg         pcm_valid,      // Strobe at 16kHz when new sample is ready
    output reg  [15:0] pcm_data        // 16-bit signed PCM audio sample
);

    localparam WIDTH = 22; // Sufficient for 3 stages with R=64

    // Convert 1-bit PDM {0, 1} to 2's complement signed: 1 -> +1, 0 -> -1
    wire signed [WIDTH-1:0] x_in;
    assign x_in = pdm_bit ? 22'sd1 : -22'sd1;

    // -------------------------------------------------------------------------
    // Stage 1: Integrators (Running at 1.024MHz PDM rate)
    // -------------------------------------------------------------------------
    reg signed [WIDTH-1:0] itg_1;
    reg signed [WIDTH-1:0] itg_2;
    reg signed [WIDTH-1:0] itg_3;

    // Rate decimation counter (0 to 63)
    reg [5:0] decim_cnt;
    wire      sample_strobe;
    assign sample_strobe = pdm_valid && (decim_cnt == 6'd63);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            itg_1     <= {WIDTH{1'b0}};
            itg_2     <= {WIDTH{1'b0}};
            itg_3     <= {WIDTH{1'b0}};
            decim_cnt <= 6'd0;
        end else if (pdm_valid) begin
            itg_1 <= itg_1 + x_in;
            itg_2 <= itg_2 + itg_1 + x_in;
            itg_3 <= itg_3 + itg_2 + itg_1 + x_in;
            
            if (decim_cnt == 6'd63)
                decim_cnt <= 6'd0;
            else
                decim_cnt <= decim_cnt + 1'b1;
        end
    end

    // -------------------------------------------------------------------------
    // Stage 2: Combs (Running at 16kHz decimated PCM rate)
    // -------------------------------------------------------------------------
    reg signed [WIDTH-1:0] comb_in;
    reg signed [WIDTH-1:0] comb_d1, comb_diff1;
    reg signed [WIDTH-1:0] comb_d2, comb_diff2;
    reg signed [WIDTH-1:0] comb_d3, comb_diff3;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            comb_in    <= {WIDTH{1'b0}};
            comb_d1    <= {WIDTH{1'b0}};
            comb_diff1 <= {WIDTH{1'b0}};
            comb_d2    <= {WIDTH{1'b0}};
            comb_diff2 <= {WIDTH{1'b0}};
            comb_d3    <= {WIDTH{1'b0}};
            comb_diff3 <= {WIDTH{1'b0}};
            pcm_valid  <= 1'b0;
            pcm_data   <= 16'd0;
        end else if (sample_strobe) begin
            // Latched integrator output
            comb_in    <= itg_3;
            // Comb 1
            comb_diff1 <= itg_3 - comb_d1;
            comb_d1    <= itg_3;
            // Comb 2
            comb_diff2 <= (itg_3 - comb_d1) - comb_d2;
            comb_d2    <= (itg_3 - comb_d1);
            // Comb 3
            comb_diff3 <= ((itg_3 - comb_d1) - comb_d2) - comb_d3;
            comb_d3    <= ((itg_3 - comb_d1) - comb_d2);

            // Scale and truncate from 22-bit to 16-bit PCM
            // Gain of 3-stage CIC with R=64 is R^3 = 64^3 = 262144 (shift right 18)
            // Scale appropriately to fit [-32768, 32767]
            pcm_data   <= comb_diff3[19:4];
            pcm_valid  <= 1'b1;
        end else begin
            pcm_valid  <= 1'b0;
        end
    end

endmodule
