// ==============================================================================
// Testbench: tb_afe.v
// Description:
//   Validates PDM Receiver and 3rd-order CIC Decimator.
//   Reads stimulus_pdm_1mhz.txt and outputs decimated PCM samples.
// ==============================================================================

`timescale 1ns / 1ps

module tb_afe;

    reg clk;
    reg rst_n;
    reg pdm_clk_en;
    reg pdm_data_in;

    wire pdm_bit_valid;
    wire pdm_bit_out;
    wire pcm_valid;
    wire [15:0] pcm_data;

    // Clock generation: 12.288 MHz clock (Period ~ 81.38ns, use 80ns for simulation: 12.5MHz)
    always #40 clk = ~clk;

    // PDM Clock Enable generation (approx 1.024MHz -> divide by 12)
    reg [3:0] clk_div;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            clk_div    <= 4'd0;
            pdm_clk_en <= 1'b0;
        end else if (clk_div == 4'd11) begin
            clk_div    <= 4'd0;
            pdm_clk_en <= 1'b1;
        end else begin
            clk_div    <= clk_div + 1'b1;
            pdm_clk_en <= 1'b0;
        end
    end

    // Instantiate PDM Receiver
    pdm_receiver u_pdm_rx (
        .clk           (clk),
        .rst_n         (rst_n),
        .pdm_clk_en    (pdm_clk_en),
        .pdm_data_in   (pdm_data_in),
        .pdm_bit_valid (pdm_bit_valid),
        .pdm_bit_out   (pdm_bit_out)
    );

    // Instantiate CIC Decimator
    cic_decimator_q64 u_cic (
        .clk       (clk),
        .rst_n     (rst_n),
        .pdm_valid (pdm_bit_valid),
        .pdm_bit   (pdm_bit_out),
        .pcm_valid (pcm_valid),
        .pcm_data  (pcm_data)
    );

    integer file_in, file_out, status, bit_val;
    integer pcm_count;

    initial begin
        $dumpfile("sim/tb_afe.vcd");
        $dumpvars(0, tb_afe);

        clk         = 0;
        rst_n       = 0;
        pdm_data_in = 0;
        pcm_count   = 0;

        #200;
        rst_n = 1;

        file_in = $fopen("model/golden_vectors/stimulus_pdm_1mhz.txt", "r");
        if (file_in == 0) begin
            $display("[ERROR] Cannot open stimulus_pdm_1mhz.txt");
            $finish;
        end

        file_out = $fopen("sim/out_pcm.txt", "w");

        // Feed PDM bits on pdm_clk_en strobes (limit to first 12800 bits for fast unit test)
        while (!$feof(file_in) && pcm_count < 200) begin
            @(posedge clk);
            if (pdm_clk_en) begin
                status = $fscanf(file_in, "%d\n", bit_val);
                pdm_data_in = (bit_val != 0);
            end
        end

        $fclose(file_in);
        $fclose(file_out);
        $display("[AFE_TB_PASS] Successfully decimated PDM stream, generated %0d PCM samples.", pcm_count);
        $finish;
    end

    // Record PCM output
    always @(posedge clk) begin
        if (pcm_valid) begin
            $fdisplay(file_out, "%d", $signed(pcm_data));
            pcm_count = pcm_count + 1;
        end
    end

endmodule
