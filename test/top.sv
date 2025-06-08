module top ();
    import uvm_pkg::*;
    `include "uvm_macros.svh"
    import python_bridge_pkg::*;

    reg test_wire/*verilator public_flat*/;
    int dpi_vec_test/*verilator public_flat*/ = 32'hBABABABA;

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
