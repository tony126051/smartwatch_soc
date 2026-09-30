// ==============================================================================
// Module: audio_fifo.v
// Project: Ultra-low Power Smartwatch SoC (Audio Front-End)
// Description:
//   Synchronous circular FIFO buffer for 16-bit PCM audio samples.
//   Depth: 256 words (covers >15ms buffer at 16kHz).
// ==============================================================================

`timescale 1ns / 1ps

module audio_fifo #(
    parameter DATA_WIDTH = 16,
    parameter ADDR_WIDTH = 8   // 256 entries
)(
    input  wire                  clk,
    input  wire                  rst_n,
    
    // Write interface (from CIC Decimator)
    input  wire                  wr_en,
    input  wire [DATA_WIDTH-1:0] wr_data,
    output wire                  full,
    
    // Read interface (to VAD / MFCC / Bus)
    input  wire                  rd_en,
    output reg  [DATA_WIDTH-1:0] rd_data,
    output wire                  empty,
    output wire [ADDR_WIDTH:0]   count
);

    localparam DEPTH = 1 << ADDR_WIDTH;

    reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];
    reg [ADDR_WIDTH:0]   wr_ptr;
    reg [ADDR_WIDTH:0]   rd_ptr;

    assign empty = (wr_ptr == rd_ptr);
    assign full  = (wr_ptr[ADDR_WIDTH-1:0] == rd_ptr[ADDR_WIDTH-1:0]) && 
                   (wr_ptr[ADDR_WIDTH] != rd_ptr[ADDR_WIDTH]);
    assign count = wr_ptr - rd_ptr;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr  <= {(ADDR_WIDTH+1){1'b0}};
            rd_ptr  <= {(ADDR_WIDTH+1){1'b0}};
            rd_data <= {DATA_WIDTH{1'b0}};
        end else begin
            if (wr_en && !full) begin
                mem[wr_ptr[ADDR_WIDTH-1:0]] <= wr_data;
                wr_ptr <= wr_ptr + 1'b1;
            end
            if (rd_en && !empty) begin
                rd_data <= mem[rd_ptr[ADDR_WIDTH-1:0]];
                rd_ptr  <= rd_ptr + 1'b1;
            end
        end
    end

endmodule
