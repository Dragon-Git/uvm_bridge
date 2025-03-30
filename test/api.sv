module top ();
    import uvm_pkg::*;
    `include "uvm_macros.svh"
    import python_bridge_pkg::*;

    reg test_wire/*verilator public_flat*/;

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

    class base_driver extends uvm_driver;
        `uvm_component_utils(base_driver)
        `uvm_new_func
    endclass

    class base_monitor extends uvm_monitor;
        `uvm_component_utils(base_monitor)
        `uvm_new_func
    endclass

    class base_sequencer extends uvm_sequencer;
        `uvm_component_utils(base_sequencer)
        `uvm_new_func
    endclass

    class base_agent extends uvm_agent;
        `uvm_component_utils(base_agent)
        `uvm_new_func
    endclass

    class base_env extends uvm_env;
        `uvm_component_utils(base_env)
        `uvm_new_func
    endclass

    class base_test extends uvm_test;
        `uvm_component_utils(base_test)
        `uvm_new_func
        
        virtual function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            call_py_func("run", "build", dirname(`__FILE__));
        endfunction

        virtual function void connect_phase(uvm_phase phase);
            super.connect_phase(phase);
        endfunction

        virtual task run_phase(uvm_phase phase);
            string test;
            byte test1 []; 
            test = base16_encode({8'h11,8'h22,0,3,4,0,5,6});
            test1 = base16_decode(test);
            $display("test: %s, test1: %p", test, test1);
            `uvm_info(get_name(), $sformatf("num_children: %d", this.get_num_children()), UVM_MEDIUM);
            call_py_func("run", "main", dirname(`__FILE__));
            #10;
        endtask
    endclass
    
    initial begin 
        run_test("base_test");
    end
endmodule
