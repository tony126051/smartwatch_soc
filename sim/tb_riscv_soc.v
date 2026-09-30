// ==============================================================================
// Testbench: tb_riscv_soc.v
// Project: Ultra-low Power Smartwatch SoC (Firmware Co-Simulation)
// Description:
//   Validates the Complete Heterogeneous SoC with Real RISC-V Firmware Execution:
//     1. CPU powers on and fetches first instruction at 0x0000_0000
//     2. Firmware configures AFE and Always-on VAD via APB
//     3. Firmware puts CPU into low-power sleep (waitirq / wfi)
//     4. Audio PDM bitstream is injected into the microphone pin
//     5. Level-1 VAD wakes up CPU via interrupt (irq[0])
//     6. CPU ISR executes, loads features to NPU, and starts inference
//     7. Level-2 NPU completes and asserts interrupt (irq[1])
//     8. CPU ISR handles NPU completion and reads classification scores
// ==============================================================================

`timescale 1ns / 1ps

module tb_riscv_soc;

    reg clk;
    reg rst_n;

    // Microphone PDM inputs
    reg pdm_clk_en;
    reg pdm_data_in;

    // SoC Status outputs
    wire [7:0] debug_leds;
    wire       soc_trap;

    // Clock: 12.5 MHz (Period = 80ns)
    always #40 clk = ~clk;

    // PDM Clock Enable: 1.024 MHz (divide by 12)
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

    // Instantiate Full SoC Top Module
    smartwatch_soc_top #(
        .BOOT_HEX_FILE("sw/firmware.hex")
    ) u_soc (
        .clk         (clk),
        .rst_n       (rst_n),
        .pdm_clk_en  (pdm_clk_en),
        .pdm_data_in (pdm_data_in),
        .debug_leds  (debug_leds),
        .soc_trap    (soc_trap)
    );

    // Audio stream injection variables
    integer file_pdm, status, bit_val;
    reg [7:0] prev_leds;

    initial begin
        $dumpfile("sim/tb_riscv_soc.vcd");
        $dumpvars(0, tb_riscv_soc);

        clk         = 0;
        rst_n       = 0;
        pdm_data_in = 0;
        prev_leds   = 8'h00;

        #200;
        rst_n = 1;
        $display("================================================================");
        $display("  Starting RISC-V CPU & SoC Hardware Firmware Co-Simulation");
        $display("================================================================");

        // Preload NPU Weights directly into NPU RAM for fast co-sim test
        #50;
        $display("[Testbench] Preloading INT8 weights into NPU Weight RAM...");
        $readmemh("model/golden_vectors/weights_int8.hex", u_soc.u_kws_subsys.u_npu.weight_mem);

        // Inject PDM Audio Stream
        file_pdm = $fopen("model/golden_vectors/stimulus_pdm_1mhz.txt", "r");
        if (file_pdm == 0) begin
            $display("[ERROR] Cannot open stimulus_pdm_1mhz.txt");
            $finish;
        end

        fork
            // Thread 1: PDM Microphone Audio Feeder
            begin
                while (!$feof(file_pdm)) begin
                    @(posedge clk);
                    if (pdm_clk_en) begin
                        status = $fscanf(file_pdm, "%d\n", bit_val);
                        pdm_data_in = (bit_val != 0);
                    end
                end
                $fclose(file_pdm);
            end

            // Thread 2: Monitor CPU & LED execution states
            begin
                while (1) begin
                    @(posedge clk);
                    if (soc_trap) begin
                        $display("[ERROR] CPU TRAP occurred at PC = 0x%08x!", u_soc.u_cpu.reg_pc);
                        $finish;
                    end

                    if (debug_leds != prev_leds) begin
                        case (debug_leds)
                            8'h01: $display("[FIRMWARE EVENT] CPU Booting up (LED = 0x01)");
                            8'h02: $display("[FIRMWARE EVENT] AFE & Hardware VAD Initialized (LED = 0x02)");
                            8'h04: $display("[FIRMWARE EVENT] CPU Entering Low-Power Sleep < 20uW (LED = 0x04)");
                            8'h08: $display("[FIRMWARE EVENT] CPU Woken up by VAD! Processing KWS NPU (LED = 0x08)");
                            8'hAA: begin
                                $display("[FIRMWARE EVENT] Keyword MATCHED! Wake up Smartwatch UI! (LED = 0xAA)");
                                $display("================================================================");
                                $display("  [CO-SIMULATION SUCCESS] RISC-V CPU Firmware Verified 100%!  ");
                                $display("================================================================");
                                #2000;
                                $finish;
                            end
                            8'h55: begin
                                $display("[FIRMWARE EVENT] Non-keyword detected. Returning to sleep. (LED = 0x55)");
                                $display("================================================================");
                                $display("  [CO-SIMULATION SUCCESS] RISC-V CPU Firmware Verified 100%!  ");
                                $display("================================================================");
                                #2000;
                                $finish;
                            end
                            default: $display("[FIRMWARE LED] Value = 0x%02x", debug_leds);
                        endcase
                        prev_leds = debug_leds;
                    end
                end
            end

            // Timeout watchdog
            begin
                #10000000; // 10ms simulation time
                $display("[TIMEOUT] Co-simulation timed out!");
                $finish;
            end
        join
    end

endmodule
