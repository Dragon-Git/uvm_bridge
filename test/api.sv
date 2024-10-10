module top ();
    import uvm_pkg::*;
    `include "uvm_macros.svh"
    import python_bridge_pkg::*;

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
        run_test("my_test");
    end
endmodule