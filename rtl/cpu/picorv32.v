// ==============================================================================
// Module: picorv32.v
// Project: Ultra-low Power Smartwatch SoC
// Description:
//   PicoRV32 is a CPU core that implements the RISC-V RV32I Instruction Set.
//   Optimized for low area, high efficiency, and easy SoC integration.
//   Includes interrupt handling, native memory bus, and WFI-compatible sleep.
// ==============================================================================

`timescale 1ns / 1ps

module picorv32 #(
    parameter [ 0:0] ENABLE_COUNTERS = 1,
    parameter [ 0:0] ENABLE_COUNTERS64 = 1,
    parameter [ 0:0] ENABLE_REGS_16_31 = 1,
    parameter [ 0:0] ENABLE_REGS_DUALPORT = 1,
    parameter [ 0:0] LATCHED_MEM_RDATA = 0,
    parameter [ 0:0] TWO_STAGE_SHIFT = 1,
    parameter [ 0:0] BARREL_SHIFTER = 0,
    parameter [ 0:0] TWO_CYCLE_COMPARE = 0,
    parameter [ 0:0] TWO_CYCLE_ALU = 0,
    parameter [ 0:0] COMPRESSED_ISA = 0,
    parameter [ 0:0] CATCH_MISALIGN = 1,
    parameter [ 0:0] CATCH_ILLINSN = 1,
    parameter [ 0:0] ENABLE_PCPI = 0,
    parameter [ 0:0] ENABLE_MUL = 0,
    parameter [ 0:0] ENABLE_FAST_MUL = 0,
    parameter [ 0:0] ENABLE_DIV = 0,
    parameter [ 0:0] ENABLE_IRQ = 1,
    parameter [ 0:0] ENABLE_IRQ_QREGS = 1,
    parameter [ 0:0] ENABLE_IRQ_TIMER = 1,
    parameter [ 0:0] ENABLE_TRACE = 0,
    parameter [ 0:0] REGS_INIT_ZERO = 1,
    parameter [31:0] MASKED_IRQ = 32'h 0000_0000,
    parameter [31:0] LATCHED_IRQ = 32'h ffff_ffff,
    parameter [31:0] PROGADDR_RESET = 32'h 0000_0000,
    parameter [31:0] PROGADDR_IRQ = 32'h 0000_0010,
    parameter [31:0] STACKADDR = 32'h 1000_2000
) (
    input clk, resetn,
    output reg trap,

    output reg        mem_valid,
    output reg        mem_instr,
    input             mem_ready,

    output reg [31:0] mem_addr,
    output reg [31:0] mem_wdata,
    output reg [ 3:0] mem_wstrb,
    input      [31:0] mem_rdata,

    // Look-Ahead Interface
    output            mem_la_read,
    output            mem_la_write,
    output     [31:0] mem_la_addr,
    output reg [31:0] mem_la_wdata,
    output reg [ 3:0] mem_la_wstrb,

    // Pico Co-Processor Interface (PCPI)
    output reg        pcpi_valid,
    output reg [31:0] pcpi_insn,
    output     [31:0] pcpi_rs1,
    output     [31:0] pcpi_rs2,
    input             pcpi_wr,
    input      [31:0] pcpi_rd,
    input             pcpi_wait,
    input             pcpi_ready,

    // IRQ Interface
    input      [31:0] irq,
    output reg [31:0] eoi,

    output reg        trace_valid,
    output reg [35:0] trace_data
);
    localparam integer regfile_size = ENABLE_REGS_16_31 ? 32 : 16;
    localparam integer regindex_bits = ENABLE_REGS_16_31 ? 5 : 4;

    reg [63:0] count_cycle, count_instr;
    reg [31:0] reg_pc, reg_next_pc, reg_op1, reg_op2, reg_out;
    reg [4:0] reg_sh;

    reg [31:0] next_insn_opcode;
    reg [31:0] dbg_insn_opcode;
    reg [31:0] dbg_insn_addr;

    wire dbg_mem_valid = mem_valid;
    wire dbg_mem_instr = mem_instr;
    wire dbg_mem_ready = mem_ready;
    wire [31:0] dbg_mem_addr  = mem_addr;
    wire [31:0] dbg_mem_wdata = mem_wdata;
    wire [ 3:0] dbg_mem_wstrb = mem_wstrb;
    wire [31:0] dbg_mem_rdata = mem_rdata;

    assign pcpi_rs1 = reg_op1;
    assign pcpi_rs2 = reg_op2;

    wire [31:0] next_pc;

    reg [31:0] irq_delay;
    reg [31:0] irq_active;
    reg [31:0] irq_mask;
    reg [31:0] irq_pending;
    reg [31:0] timer;

    // Regfile implementation
    reg [31:0] cpuregs [0:regfile_size-1];
    integer i;
    initial begin
        if (REGS_INIT_ZERO) begin
            for (i = 0; i < regfile_size; i = i + 1)
                cpuregs[i] = 0;
        end
    end

    // Instruction Decode & ALU
    localparam cpu_state_trap   = 8'b10000000;
    localparam cpu_state_fetch  = 8'b01000000;
    localparam cpu_state_ld_rs1 = 8'b00100000;
    localparam cpu_state_ld_rs2 = 8'b00010000;
    localparam cpu_state_exec   = 8'b00001000;
    localparam cpu_state_shift  = 8'b00000100;
    localparam cpu_state_stmem  = 8'b00000010;
    localparam cpu_state_ldmem  = 8'b00000001;

    reg [7:0] cpu_state;

    // ALU operations
    wire [31:0] alu_add_sub = instr_sub ? (reg_op1 - reg_op2) : (reg_op1 + reg_op2);
    wire [31:0] alu_shl     = reg_op1 << reg_op2[4:0];
    wire [31:0] alu_shr     = $signed({instr_sra ? reg_op1[31] : 1'b0, reg_op1}) >>> reg_op2[4:0];
    wire [31:0] alu_slt     = ($signed(reg_op1) < $signed(reg_op2)) ? 32'd1 : 32'd0;
    wire [31:0] alu_sltu    = (reg_op1 < reg_op2) ? 32'd1 : 32'd0;
    wire [31:0] alu_xor     = reg_op1 ^ reg_op2;
    wire [31:0] alu_or      = reg_op1 | reg_op2;
    wire [31:0] alu_and     = reg_op1 & reg_op2;

    reg instr_lui, instr_auipc, instr_jal, instr_jalr;
    reg instr_beq, instr_bne, instr_blt, instr_bge, instr_bltu, instr_bgeu;
    reg instr_lb, instr_lh, instr_lw, instr_lbu, instr_lhu, instr_sb, instr_sh, instr_sw;
    reg instr_addi, instr_slti, instr_sltiu, instr_xori, instr_ori, instr_andi, instr_slli, instr_srli, instr_srai;
    reg instr_add, instr_sub, instr_sll, instr_slt, instr_sltu, instr_xor, instr_srl, instr_sra, instr_or, instr_and;
    reg instr_rdcycle, instr_rdcycleh, instr_rdinstr, instr_rdinstrh, instr_ecall_ebreak;
    reg instr_getq, instr_setq, instr_retirq, instr_maskirq, instr_waitirq, instr_timer;

    wire [31:0] decoded_imm = 
        instr_lui | instr_auipc ? {mem_rdata[31:12], 12'b0} :
        instr_jal ? {{12{mem_rdata[31]}}, mem_rdata[19:12], mem_rdata[20], mem_rdata[30:21], 1'b0} :
        instr_jalr | instr_lb | instr_lh | instr_lw | instr_lbu | instr_lhu |
        instr_addi | instr_slti | instr_sltiu | instr_xori | instr_ori | instr_andi | instr_slli | instr_srli | instr_srai ?
            {{21{mem_rdata[31]}}, mem_rdata[30:20]} :
        instr_sb | instr_sh | instr_sw ?
            {{21{mem_rdata[31]}}, mem_rdata[30:25], mem_rdata[11:7]} :
        instr_beq | instr_bne | instr_blt | instr_bge | instr_bltu | instr_bgeu ?
            {{20{mem_rdata[31]}}, mem_rdata[7], mem_rdata[30:25], mem_rdata[11:8], 1'b0} : 32'b0;

    reg [4:0] decoded_rd, decoded_rs1, decoded_rs2;

    always @(*) begin
        instr_lui      = (mem_rdata[6:0] == 7'b0110111);
        instr_auipc    = (mem_rdata[6:0] == 7'b0010111);
        instr_jal      = (mem_rdata[6:0] == 7'b1101111);
        instr_jalr     = (mem_rdata[6:0] == 7'b1100111);
        instr_beq      = (mem_rdata[6:0] == 7'b1100011) && (mem_rdata[14:12] == 3'b000);
        instr_bne      = (mem_rdata[6:0] == 7'b1100011) && (mem_rdata[14:12] == 3'b001);
        instr_blt      = (mem_rdata[6:0] == 7'b1100011) && (mem_rdata[14:12] == 3'b100);
        instr_bge      = (mem_rdata[6:0] == 7'b1100011) && (mem_rdata[14:12] == 3'b101);
        instr_bltu     = (mem_rdata[6:0] == 7'b1100011) && (mem_rdata[14:12] == 3'b110);
        instr_bgeu     = (mem_rdata[6:0] == 7'b1100011) && (mem_rdata[14:12] == 3'b111);

        instr_lb       = (mem_rdata[6:0] == 7'b0000011) && (mem_rdata[14:12] == 3'b000);
        instr_lh       = (mem_rdata[6:0] == 7'b0000011) && (mem_rdata[14:12] == 3'b001);
        instr_lw       = (mem_rdata[6:0] == 7'b0000011) && (mem_rdata[14:12] == 3'b010);
        instr_lbu      = (mem_rdata[6:0] == 7'b0000011) && (mem_rdata[14:12] == 3'b100);
        instr_lhu      = (mem_rdata[6:0] == 7'b0000011) && (mem_rdata[14:12] == 3'b101);

        instr_sb       = (mem_rdata[6:0] == 7'b0100011) && (mem_rdata[14:12] == 3'b000);
        instr_sh       = (mem_rdata[6:0] == 7'b0100011) && (mem_rdata[14:12] == 3'b001);
        instr_sw       = (mem_rdata[6:0] == 7'b0100011) && (mem_rdata[14:12] == 3'b010);

        instr_addi     = (mem_rdata[6:0] == 7'b0010011) && (mem_rdata[14:12] == 3'b000);
        instr_slti     = (mem_rdata[6:0] == 7'b0010011) && (mem_rdata[14:12] == 3'b010);
        instr_sltiu    = (mem_rdata[6:0] == 7'b0010011) && (mem_rdata[14:12] == 3'b011);
        instr_xori     = (mem_rdata[6:0] == 7'b0010011) && (mem_rdata[14:12] == 3'b100);
        instr_ori      = (mem_rdata[6:0] == 7'b0010011) && (mem_rdata[14:12] == 3'b110);
        instr_andi     = (mem_rdata[6:0] == 7'b0010011) && (mem_rdata[14:12] == 3'b111);
        instr_slli     = (mem_rdata[6:0] == 7'b0010011) && (mem_rdata[14:12] == 3'b001) && (mem_rdata[31:25] == 7'b0000000);
        instr_srli     = (mem_rdata[6:0] == 7'b0010011) && (mem_rdata[14:12] == 3'b101) && (mem_rdata[31:25] == 7'b0000000);
        instr_srai     = (mem_rdata[6:0] == 7'b0010011) && (mem_rdata[14:12] == 3'b101) && (mem_rdata[31:25] == 7'b0100000);

        instr_add      = (mem_rdata[6:0] == 7'b0110011) && (mem_rdata[14:12] == 3'b000) && (mem_rdata[31:25] == 7'b0000000);
        instr_sub      = (mem_rdata[6:0] == 7'b0110011) && (mem_rdata[14:12] == 3'b000) && (mem_rdata[31:25] == 7'b0100000);
        instr_sll      = (mem_rdata[6:0] == 7'b0110011) && (mem_rdata[14:12] == 3'b001) && (mem_rdata[31:25] == 7'b0000000);
        instr_slt      = (mem_rdata[6:0] == 7'b0110011) && (mem_rdata[14:12] == 3'b010) && (mem_rdata[31:25] == 7'b0000000);
        instr_sltu     = (mem_rdata[6:0] == 7'b0110011) && (mem_rdata[14:12] == 3'b011) && (mem_rdata[31:25] == 7'b0000000);
        instr_xor      = (mem_rdata[6:0] == 7'b0110011) && (mem_rdata[14:12] == 3'b100) && (mem_rdata[31:25] == 7'b0000000);
        instr_srl      = (mem_rdata[6:0] == 7'b0110011) && (mem_rdata[14:12] == 3'b101) && (mem_rdata[31:25] == 7'b0000000);
        instr_sra      = (mem_rdata[6:0] == 7'b0110011) && (mem_rdata[14:12] == 3'b101) && (mem_rdata[31:25] == 7'b0100000);
        instr_or       = (mem_rdata[6:0] == 7'b0110011) && (mem_rdata[14:12] == 3'b110) && (mem_rdata[31:25] == 7'b0000000);
        instr_and      = (mem_rdata[6:0] == 7'b0110011) && (mem_rdata[14:12] == 3'b111) && (mem_rdata[31:25] == 7'b0000000);

        instr_waitirq  = (mem_rdata[6:0] == 7'b0001011) && (mem_rdata[14:12] == 3'b100); // WFI custom
        instr_retirq   = (mem_rdata[6:0] == 7'b0001011) && (mem_rdata[14:12] == 3'b101); // MRET/RETI
        instr_maskirq  = (mem_rdata[6:0] == 7'b0001011) && (mem_rdata[14:12] == 3'b011); // IRQ MASK
    end

    // Sequential Execution
    always @(posedge clk or negedge resetn) begin
        if (!resetn) begin
            reg_pc      <= PROGADDR_RESET;
            reg_next_pc <= PROGADDR_RESET;
            cpu_state   <= cpu_state_fetch;
            mem_valid   <= 1'b0;
            mem_instr   <= 1'b0;
            mem_wstrb   <= 4'b0;
            irq_mask    <= 32'h0;
            irq_active  <= 32'h0;
            eoi         <= 32'h0;
            trap        <= 1'b0;
        end else begin
            eoi <= 32'h0;

            case (cpu_state)
                cpu_state_fetch: begin
                    mem_valid <= 1'b1;
                    mem_instr <= 1'b1;
                    mem_addr  <= reg_next_pc;
                    mem_wstrb <= 4'b0;
                    reg_pc    <= reg_next_pc;
                    
                    // Check pending unmasked interrupts
                    if (ENABLE_IRQ && (| (irq & ~irq_mask)) && !(|irq_active)) begin
                        // Take interrupt
                        irq_active <= irq & ~irq_mask;
                        reg_next_pc <= PROGADDR_IRQ;
                        mem_valid   <= 1'b0;
                        cpu_state   <= cpu_state_fetch;
                    end else if (mem_ready) begin
                        mem_valid <= 1'b0;
                        decoded_rd  <= mem_rdata[11:7];
                        decoded_rs1 <= mem_rdata[19:15];
                        decoded_rs2 <= mem_rdata[24:20];
                        cpu_state   <= cpu_state_ld_rs1;
                    end
                end

                cpu_state_ld_rs1: begin
                    reg_op1 <= (decoded_rs1 == 5'd0) ? 32'd0 : cpuregs[decoded_rs1];
                    reg_op2 <= (decoded_rs2 == 5'd0) ? 32'd0 : cpuregs[decoded_rs2];
                    cpu_state <= cpu_state_exec;
                end

                cpu_state_exec: begin
                    if (instr_lui) begin
                        if (decoded_rd != 0) cpuregs[decoded_rd] <= decoded_imm;
                        reg_next_pc <= reg_pc + 4;
                        cpu_state <= cpu_state_fetch;
                    end else if (instr_auipc) begin
                        if (decoded_rd != 0) cpuregs[decoded_rd] <= reg_pc + decoded_imm;
                        reg_next_pc <= reg_pc + 4;
                        cpu_state <= cpu_state_fetch;
                    end else if (instr_jal) begin
                        if (decoded_rd != 0) cpuregs[decoded_rd] <= reg_pc + 4;
                        reg_next_pc <= reg_pc + decoded_imm;
                        cpu_state <= cpu_state_fetch;
                    end else if (instr_jalr) begin
                        if (decoded_rd != 0) cpuregs[decoded_rd] <= reg_pc + 4;
                        reg_next_pc <= (reg_op1 + decoded_imm) & ~32'd1;
                        cpu_state <= cpu_state_fetch;
                    end else if (instr_beq || instr_bne || instr_blt || instr_bge || instr_bltu || instr_bgeu) begin
                        reg branch_taken;
                        branch_taken = (instr_beq  && (reg_op1 == reg_op2)) ||
                                       (instr_bne  && (reg_op1 != reg_op2)) ||
                                       (instr_blt  && ($signed(reg_op1) < $signed(reg_op2))) ||
                                       (instr_bge  && ($signed(reg_op1) >= $signed(reg_op2))) ||
                                       (instr_bltu && (reg_op1 < reg_op2)) ||
                                       (instr_bgeu && (reg_op1 >= reg_op2));
                        reg_next_pc <= branch_taken ? (reg_pc + decoded_imm) : (reg_pc + 4);
                        cpu_state <= cpu_state_fetch;
                    end else if (instr_addi || instr_add || instr_sub || instr_slt || instr_slti ||
                                 instr_sltu || instr_sltiu || instr_xor || instr_xori ||
                                 instr_or || instr_ori || instr_and || instr_andi ||
                                 instr_sll || instr_slli || instr_srl || instr_srli || instr_sra || instr_srai) begin
                        wire [31:0] op2_eff = (instr_addi || instr_slti || instr_sltiu || instr_xori ||
                                               instr_ori  || instr_andi || instr_slli || instr_srli || instr_srai) ?
                                               decoded_imm : reg_op2;
                        wire [31:0] alu_res = 
                            (instr_add || instr_addi) ? (reg_op1 + op2_eff) :
                            (instr_sub) ? (reg_op1 - op2_eff) :
                            (instr_slt || instr_slti) ? (($signed(reg_op1) < $signed(op2_eff)) ? 32'd1 : 32'd0) :
                            (instr_sltu || instr_sltiu) ? ((reg_op1 < op2_eff) ? 32'd1 : 32'd0) :
                            (instr_xor || instr_xori) ? (reg_op1 ^ op2_eff) :
                            (instr_or || instr_ori) ? (reg_op1 | op2_eff) :
                            (instr_and || instr_andi) ? (reg_op1 & op2_eff) :
                            (instr_sll || instr_slli) ? (reg_op1 << op2_eff[4:0]) :
                            (instr_sra || instr_srai) ? ($signed(reg_op1) >>> op2_eff[4:0]) :
                            (reg_op1 >> op2_eff[4:0]);
                        if (decoded_rd != 0) cpuregs[decoded_rd] <= alu_res;
                        reg_next_pc <= reg_pc + 4;
                        cpu_state <= cpu_state_fetch;
                    end else if (instr_lb || instr_lh || instr_lw || instr_lbu || instr_lhu) begin
                        mem_addr  <= reg_op1 + decoded_imm;
                        mem_valid <= 1'b1;
                        mem_instr <= 1'b0;
                        mem_wstrb <= 4'b0;
                        cpu_state <= cpu_state_ldmem;
                    end else if (instr_sb || instr_sh || instr_sw) begin
                        mem_addr  <= reg_op1 + decoded_imm;
                        mem_valid <= 1'b1;
                        mem_instr <= 1'b0;
                        if (instr_sb) begin
                            mem_wdata <= {4{reg_op2[7:0]}};
                            mem_wstrb <= 4'b0001 << (reg_op1[1:0] + decoded_imm[1:0]);
                        end else if (instr_sh) begin
                            mem_wdata <= {2{reg_op2[15:0]}};
                            mem_wstrb <= 4'b0011 << (reg_op1[1:0] + decoded_imm[1:0]);
                        end else begin
                            mem_wdata <= reg_op2;
                            mem_wstrb <= 4'b1111;
                        end
                        cpu_state <= cpu_state_stmem;
                    end else if (instr_waitirq) begin
                        // WFI instruction - Wait until unmasked IRQ arrives
                        if (| (irq & ~irq_mask)) begin
                            reg_next_pc <= reg_pc + 4;
                            cpu_state <= cpu_state_fetch;
                        end
                    end else if (instr_retirq) begin
                        eoi <= irq_active;
                        irq_active <= 32'd0;
                        reg_next_pc <= cpuregs[1]; // Return address in x1/ra
                        cpu_state <= cpu_state_fetch;
                    end else if (instr_maskirq) begin
                        if (decoded_rd != 0) cpuregs[decoded_rd] <= irq_mask;
                        irq_mask <= reg_op1;
                        reg_next_pc <= reg_pc + 4;
                        cpu_state <= cpu_state_fetch;
                    end else begin
                        // NOP or unrecognized instruction, advance PC
                        reg_next_pc <= reg_pc + 4;
                        cpu_state <= cpu_state_fetch;
                    end
                end

                cpu_state_ldmem: begin
                    if (mem_ready) begin
                        mem_valid <= 1'b0;
                        if (decoded_rd != 0) begin
                            if (instr_lw) cpuregs[decoded_rd] <= mem_rdata;
                            else if (instr_lb) cpuregs[decoded_rd] <= {{24{mem_rdata[7]}}, mem_rdata[7:0]};
                            else if (instr_lbu) cpuregs[decoded_rd] <= {24'd0, mem_rdata[7:0]};
                            else if (instr_lh) cpuregs[decoded_rd] <= {{16{mem_rdata[15]}}, mem_rdata[15:0]};
                            else if (instr_lhu) cpuregs[decoded_rd] <= {16'd0, mem_rdata[15:0]};
                        end
                        reg_next_pc <= reg_pc + 4;
                        cpu_state <= cpu_state_fetch;
                    end
                end

                cpu_state_stmem: begin
                    if (mem_ready) begin
                        mem_valid <= 1'b0;
                        mem_wstrb <= 4'b0;
                        reg_next_pc <= reg_pc + 4;
                        cpu_state <= cpu_state_fetch;
                    end
                end

                default: cpu_state <= cpu_state_fetch;
            endcase
        end
    end

endmodule
