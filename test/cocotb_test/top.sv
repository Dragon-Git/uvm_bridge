module top ();
    import uvm_pkg::*;
    `include "uvm_macros.svh"
    import python_bridge_pkg::*;

    reg test_wire/*verilator public_flat*/;
    // uvm_hdl_force and uvm_hdl_deposit (and the SV
    // 'force' statement) drive the target signal through
    // VPI vpi_put_value. Verilator 5.x only implements
    // vpi_put_value for logic/reg vector types; on the
    // SystemVerilog 'int' type the call returns a
    // non-zero status and the value is never written,
    // which is why this had to change from 'int' to a
    // 32-bit logic vector. The public_flat and forceable
    // pragmas below are kept so the cocotb-top access
    // path and any future SV 'force' statements still
    // work.
    logic [31:0] dpi_vec_test/*verilator public_flat*/  /*verilator forceable*/ = 32'hBABABABA;

    class env_cfg extends uvm_object;
        `uvm_object_utils(env_cfg)
        function new(string name = "env_cfg");
            super.new(name);
        endfunction
    endclass

    class direct_env_cfg extends env_cfg;
        `uvm_object_utils(direct_env_cfg)
        function new(string name = "direct_env_cfg");
            super.new(name);
        endfunction
    endclass

    class random_env_cfg extends env_cfg;
        `uvm_object_utils(random_env_cfg)
        function new(string name = "random_env_cfg");
            super.new(name);
        endfunction
    endclass

    logic clk/*verilator public_flat*/ = 1'b0;
    always #5 clk = ~clk;

    
    initial begin 
        string test;
        byte test1 []; 
        test = base16_encode({8'h11,8'h22,0,3,4,0,5,6});
        test1 = base16_decode(test);
        $display("test: %s, test1: %p", test, test1);
        $monitor("dpi_vec_test: %h", dpi_vec_test);
        run_test();
        // #1000;
        // $finish;
    end
endmodule
