// ==============================================================================
// Module: pdm_receiver.v
// Project: Ultra-low Power Smartwatch SoC (Audio Front-End)
// Description:
//   Synchronizes external 1-bit PDM microphone data to the internal SoC clock
//   and generates PDM clock enable strobes.
// ==============================================================================

`timescale 1ns / 1ps

module pdm_receiver (
    input  wire        clk,          // System clock (e.g., 12.288MHz or 12MHz)
    input  wire        rst_n,        // Active-low asynchronous reset
    input  wire        pdm_clk_en,   // Strobe enabled at 1.024MHz
    input  wire        pdm_data_in,  // Async PDM data from MEMS microphone
    output reg         pdm_bit_valid,// Strobe when new synchronized PDM bit is ready
    output reg         pdm_bit_out   // Synchronized 1-bit PDM sample
);

    // 2-stage synchronizer to prevent metastability
    reg pdm_meta;
    reg pdm_sync;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pdm_meta      <= 1'b0;
            pdm_sync      <= 1'b0;
            pdm_bit_out   <= 1'b0;
            pdm_bit_valid <= 1'b0;
        end else begin
            pdm_meta <= pdm_data_in;
            pdm_sync <= pdm_meta;
            
            if (pdm_clk_en) begin
                pdm_bit_out   <= pdm_sync;
                pdm_bit_valid <= 1'b1;
            end else begin
                pdm_bit_valid <= 1'b0;
            end
        end
    end

endmodule
