module top ();
    import uvm_pkg::*;
    `include "uvm_macros.svh"
    import python_bridge_pkg::*;

    logic test_wire;

    class my_test extends uvm_test;
        `uvm_component_utils(my_test)
        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction
        virtual function void build_phase(uvm_phase phase);
            super.build_phase(phase);
        endfunction
        virtual task run_phase(uvm_phase phase);
            call_py_func("run", "main", dirname(`__FILE__));
        endtask
    endclass
    
    initial begin 
        string test;
        byte test1 []; 
        test = base16_encode({8'h11,8'h22,0,3,4,0,5,6});
        test1 = base16_decode(test);
        $display("test: %s, test1: %p", test, test1);
        call_py_func("run", "main", dirname(`__FILE__));
        #10;
        // run_test("my_test");
    end
endmodule
