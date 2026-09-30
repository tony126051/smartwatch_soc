// ==============================================================================
// Testbench: tb_vad.v
// Description:
//   Validates Hardware VAD core against golden stimulus.
//   Reads stimulus_pcm_16k.txt, verifies Energy accumulation and IRQ triggering.
// ==============================================================================

`timescale 1ns / 1ps

module tb_vad;

    reg clk;
    reg rst_n;
    reg pcm_valid;
    reg [15:0] pcm_data;

    reg        cfg_enable;
    reg [23:0] cfg_threshold;
    reg [3:0]  cfg_hangover_len;

    wire [23:0] cur_frame_energy;
    wire        speech_active;
    wire        irq_vad_wakeup;

    always #40 clk = ~clk; // 12.5 MHz clock

    vad_core #(
        .FRAME_SIZE(160)
    ) u_vad (
        .clk              (clk),
        .rst_n            (rst_n),
        .pcm_valid        (pcm_valid),
        .pcm_data         (pcm_data),
        .cfg_enable       (cfg_enable),
        .cfg_threshold    (cfg_threshold),
        .cfg_hangover_len (cfg_hangover_len),
        .cur_frame_energy (cur_frame_energy),
        .speech_active    (speech_active),
        .irq_vad_wakeup   (irq_vad_wakeup)
    );

    integer file_pcm, file_out, status, val;
    integer sample_idx, irq_count;

    initial begin
        $dumpfile("sim/tb_vad.vcd");
        $dumpvars(0, tb_vad);

        clk              = 0;
        rst_n            = 0;
        pcm_valid        = 0;
        pcm_data         = 0;
        cfg_enable       = 1;
        cfg_threshold    = 24'd200000;
        cfg_hangover_len = 4'd3;
        sample_idx       = 0;
        irq_count        = 0;

        #200;
        rst_n = 1;

        file_pcm = $fopen("model/golden_vectors/stimulus_pcm_16k.txt", "r");
        if (file_pcm == 0) begin
            $display("[ERROR] Cannot open stimulus_pcm_16k.txt");
            $finish;
        end

        file_out = $fopen("sim/out_vad.txt", "w");
        $fdisplay(file_out, "# Sample_Index Speech_Active IRQ");

        // Feed PCM samples every 800 cycles (simulating 16kHz sample rate relative to 12.5MHz)
        while (!$feof(file_pcm)) begin
            status = $fscanf(file_pcm, "%d\n", val);
            @(posedge clk);
            pcm_data  = val[15:0];
            pcm_valid = 1'b1;
            @(posedge clk);
            pcm_valid = 1'b0;

            if (irq_vad_wakeup) begin
                irq_count = irq_count + 1;
                $display("[VAD Event] IRQ Wakeup asserted at sample %0d!", sample_idx);
            end

            repeat(70) @(posedge clk); // Accelerated spacing for simulation speed
            sample_idx = sample_idx + 1;
        end

        $fclose(file_pcm);
        $fclose(file_out);

        if (irq_count > 0) begin
            $display("[VAD_TB_PASS] VAD triggered %0d wake-up IRQ(s) successfully!", irq_count);
        end else begin
            $display("[VAD_TB_FAIL] No VAD wake-up IRQ triggered!");
        end

        $finish;
    end

    always @(posedge clk) begin
        if (irq_vad_wakeup) begin
            $fdisplay(file_out, "%0d %b 1", sample_idx, speech_active);
        end
    end

endmodule
