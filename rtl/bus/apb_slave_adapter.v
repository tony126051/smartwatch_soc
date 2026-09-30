// ==============================================================================
// Module: apb_slave_adapter.v
// Project: Ultra-low Power Smartwatch SoC (Bus Subsystem)
// Description:
//   Standard AMBA APB (Advanced Peripheral Bus) Slave Interface Wrapper.
// ==============================================================================

`timescale 1ns / 1ps

module apb_slave_adapter #(
    parameter ADDR_WIDTH = 12,
    parameter DATA_WIDTH = 32
)(
    input  wire                  pclk,
    input  wire                  presetn,
    
    // APB Bus Signals
    input  wire                  psel,
    input  wire                  penable,
    input  wire                  pwrite,
    input  wire [ADDR_WIDTH-1:0] paddr,
    input  wire [DATA_WIDTH-1:0] pwdata,
    output reg  [DATA_WIDTH-1:0] prdata,
    output wire                  pready,
    output wire                  pslverr,
    
    // Internal Register Bus Signals
    output wire                  reg_wr_en,
    output wire                  reg_rd_en,
    output wire [ADDR_WIDTH-1:0] reg_addr,
    output wire [DATA_WIDTH-1:0] reg_wdata,
    input  wire [DATA_WIDTH-1:0] reg_rdata
);

    assign pready   = 1'b1; // Zero wait-state responses for internal registers
    assign pslverr  = 1'b0;

    assign reg_wr_en = psel && penable && pwrite;
    assign reg_rd_en = psel && !penable && !pwrite;
    assign reg_addr  = paddr;
    assign reg_wdata = pwdata;

    always @(posedge pclk or negedge presetn) begin
        if (!presetn) begin
            prdata <= {DATA_WIDTH{1'b0}};
        end else if (psel && !pwrite) begin
            prdata <= reg_rdata;
        end
    end

endmodule
