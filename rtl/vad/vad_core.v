// ==============================================================================
// Module: vad_core.v
// Project: Ultra-low Power Smartwatch SoC (Level-1 Always-on Wakeup)
// Description:
//   Hardware Voice Activity Detector (VAD).
//   Calculates Short-Time Absolute Energy over 160-sample (10ms) frames.
//   Asserts interrupt to wake up CPU/NPU when speech activity is detected.
// ==============================================================================

`timescale 1ns / 1ps

module vad_core #(
    parameter FRAME_SIZE = 160
)(
    input  wire        clk,
    input  wire        rst_n,
    
    // Audio PCM stream input
    input  wire        pcm_valid,
    input  wire [15:0] pcm_data,
    
    // Configuration registers
    input  wire        cfg_enable,
    input  wire [23:0] cfg_threshold,    // Energy threshold
    input  wire [3:0]  cfg_hangover_len, // Hangover frames to prevent speech cutoff
    
    // Outputs & Interrupts
    output reg  [23:0] cur_frame_energy,
    output reg         speech_active,
    output reg         irq_vad_wakeup
);

    // Frame sample counter (0 to 159)
    reg [7:0]  sample_cnt;
    reg [23:0] energy_accum;
    reg [3:0]  hangover_cnt;
    reg        speech_active_prev;

    // Absolute value of 16-bit signed PCM
    wire [15:0] abs_val;
    assign abs_val = pcm_data[15] ? (-pcm_data) : pcm_data;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sample_cnt         <= 8'd0;
            energy_accum       <= 24'd0;
            cur_frame_energy   <= 24'd0;
            hangover_cnt       <= 4'd0;
            speech_active      <= 1'b0;
            speech_active_prev <= 1'b0;
            irq_vad_wakeup     <= 1'b0;
        end else if (cfg_enable) begin
            irq_vad_wakeup <= 1'b0; // Default de-assert (pulse)

            if (pcm_valid) begin
                // Accumulate energy
                energy_accum <= energy_accum + {8'd0, abs_val};

                if (sample_cnt == (FRAME_SIZE - 1)) begin
                    // Frame completed
                    sample_cnt <= 8'd0;
                    cur_frame_energy <= energy_accum + {8'd0, abs_val};
                    energy_accum <= 24'd0;

                    // Compare with threshold
                    if ((energy_accum + {8'd0, abs_val}) >= cfg_threshold) begin
                        speech_active <= 1'b1;
                        hangover_cnt  <= cfg_hangover_len;
                    end else if (hangover_cnt > 0) begin
                        speech_active <= 1'b1;
                        hangover_cnt  <= hangover_cnt - 1'b1;
                    end else begin
                        speech_active <= 1'b0;
                    end

                    // Rising-edge interrupt generation
                    if (((energy_accum + {8'd0, abs_val}) >= cfg_threshold) && !speech_active_prev) begin
                        irq_vad_wakeup <= 1'b1;
                    end
                    speech_active_prev <= ((energy_accum + {8'd0, abs_val}) >= cfg_threshold) || (hangover_cnt > 0);
                end else begin
                    sample_cnt <= sample_cnt + 1'b1;
                end
            end
        end else begin
            // Disabled
            sample_cnt     <= 8'd0;
            energy_accum   <= 24'd0;
            speech_active  <= 1'b0;
            irq_vad_wakeup <= 1'b0;
        end
    end

endmodule
