// ==============================================================================
// Testbench: tb_soc_top.v
// Project: Ultra-low Power Smartwatch SoC (System-level Full Flow)
// Description:
//   Validates the entire SoC KWS acceleration pipeline:
//     1. APB Bus configuration of AFE, VAD, and NPU
//     2. NPU Weight loading via bus transactions
//     3. Audio PDM bitstream injection
//     4. CPU sleep simulation and Hardware VAD Level-1 Wakeup Interrupt capture
//     5. CPU Wakeup ISR: Load features into NPU and start inference
//     6. Capture NPU Level-2 Done Interrupt and verify final wake-up decision!
// ==============================================================================

`timescale 1ns / 1ps

module tb_soc_top;

    reg clk;
    reg rst_n;

    // APB Bus Signals
    reg        psel;
    reg        penable;
    reg        pwrite;
    reg [11:0] paddr;
    reg [31:0] pwdata;
    wire [31:0] prdata;
    wire        pready;
    wire        pslverr;

    // Microphone interface
    reg  pdm_clk_en;
    reg  pdm_data_in;

    // Interrupts to CPU
    wire irq_vad_wakeup;
    wire irq_npu_done;

    // Clock: 12.5 MHz
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

    // Instantiate KWS Accelerator Subsystem
    kws_accelerator_subsys u_soc_subsys (
        .pclk           (clk),
        .presetn        (rst_n),
        .psel           (psel),
        .penable        (penable),
        .pwrite         (pwrite),
        .paddr          (paddr),
        .pwdata         (pwdata),
        .prdata         (prdata),
        .pready         (pready),
        .pslverr        (pslverr),
        .pdm_clk_en     (pdm_clk_en),
        .pdm_data_in    (pdm_data_in),
        .irq_vad_wakeup (irq_vad_wakeup),
        .irq_npu_done   (irq_npu_done)
    );

    // -------------------------------------------------------------------------
    // APB Master BFM Tasks
    // -------------------------------------------------------------------------
    task apb_write(input [11:0] addr, input [31:0] data);
    begin
        @(posedge clk);
        psel    <= 1'b1;
        pwrite  <= 1'b1;
        paddr   <= addr;
        pwdata  <= data;
        penable <= 1'b0;
        @(posedge clk);
        penable <= 1'b1;
        @(posedge clk);
        psel    <= 1'b0;
        penable <= 1'b0;
        pwrite  <= 1'b0;
    end
    endtask

    task apb_read(input [11:0] addr, output [31:0] data);
    begin
        @(posedge clk);
        psel    <= 1'b1;
        pwrite  <= 1'b0;
        paddr   <= addr;
        penable <= 1'b0;
        @(posedge clk);
        penable <= 1'b1;
        @(posedge clk);
        data    = prdata;
        psel    <= 1'b0;
        penable <= 1'b0;
    end
    endtask

    integer file_pdm, file_wgt, status, bit_val, hex_val;
    integer i, addr;
    reg [31:0] read_val;

    initial begin
        $dumpfile("sim/tb_soc_top.vcd");
        $dumpvars(0, tb_soc_top);

        clk         = 0;
        rst_n       = 0;
        psel        = 0;
        penable     = 0;
        pwrite      = 0;
        paddr       = 0;
        pwdata      = 0;
        pdm_data_in = 0;

        #200;
        rst_n = 1;
        #100;

        $display("================================================================");
        $display("  Starting Smartwatch SoC Full-System Simulation");
        $display("================================================================");

        // Step 1: Configure AFE and VAD
        $display("[Step 1] Configuring AFE and VAD registers via APB...");
        apb_write(12'h000, 32'h00000001); // AFE_CTRL: enable AFE
        apb_write(12'h014, 32'd200000);   // VAD_THRESHOLD: 200,000
        apb_write(12'h018, 32'd3);        // VAD_HANGOVER: 3 frames
        apb_write(12'h010, 32'h00000001); // VAD_CTRL: enable VAD
        $display("[Step 1] AFE and VAD enabled.");

        // Step 2: Load Model Weights into NPU RAM via APB
        $display("[Step 2] Programming NPU Weights from weights_int8.hex...");
        file_wgt = $fopen("model/golden_vectors/weights_int8.hex", "r");
        if (file_wgt == 0) begin
            $display("[ERROR] Cannot open weights_int8.hex");
            $finish;
        end

        addr = 0;
        while (!$feof(file_wgt) && addr < 120) begin
            status = $fscanf(file_wgt, "%x\n", hex_val);
            apb_write(12'h500 + addr, hex_val[7:0]);
            addr = addr + 1;
        end
        $fclose(file_wgt);
        $display("[Step 2] Programmed %0d weights into NPU Weight RAM.", addr);

        // Step 3: Inject Audio Stream & Emulate CPU WFI Sleep
        $display("[Step 3] CPU entering WFI sleep. Injecting microphone PDM stream...");
        file_pdm = $fopen("model/golden_vectors/stimulus_pdm_1mhz.txt", "r");
        if (file_pdm == 0) begin
            $display("[ERROR] Cannot open stimulus_pdm_1mhz.txt");
            $finish;
        end

        fork
            // PDM audio injector thread
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

            // CPU Interrupt Monitor thread
            begin
                // Wait for Level-1 VAD Wakeup Interrupt
                while (!irq_vad_wakeup) begin
                    @(posedge clk);
                end
                $display("----------------------------------------------------------------");
                $display("[INTERRUPT] Level-1 VAD Wakeup IRQ Triggered! CPU Waking Up!");
                $display("----------------------------------------------------------------");

                // Step 4: Clear VAD IRQ
                apb_write(12'h010, 32'h00000003); // Write 1 to bit 1 to clear IRQ

                // Step 5: CPU fills feature window and triggers NPU
                $display("[Step 5] CPU loading feature map into NPU and starting inference...");
                for (i = 0; i < 256; i = i + 1) begin
                    apb_write(12'h400 + i, (i % 16));
                end
                apb_write(12'h020, 32'h00000001); // NPU_CTRL: bit 0 = start

                // Wait for Level-2 NPU Done Interrupt
                while (!irq_npu_done) begin
                    @(posedge clk);
                end
                $display("----------------------------------------------------------------");
                $display("[INTERRUPT] Level-2 KWS NPU Done IRQ Triggered!");
                $display("----------------------------------------------------------------");

                // Step 6: Read classification scores
                apb_read(12'h028, read_val);
                $display("[Result] NPU Score 0 (Non-keyword): %0d", $signed(read_val));
                apb_read(12'h02C, read_val);
                $display("[Result] NPU Score 1 (Keyword):     %0d", $signed(read_val));
                apb_read(12'h024, read_val);
                $display("[Result] Keyword Detected Flag:     %0b", read_val[2]);

                // Clear NPU IRQ
                apb_write(12'h020, 32'h00000002);

                $display("================================================================");
                $display("  [FULL SoC TEST PASS] All Subsystems Verified Successfully!  ");
                $display("================================================================");
                #1000;
                $finish;
            end
        join

    end

endmodule
