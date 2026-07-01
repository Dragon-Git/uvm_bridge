module top ();
    import uvm_pkg::*;
    `include "uvm_macros.svh"
    import python_bridge_pkg::*;

    reg test_wire/*verilator public_flat*/  /*verilator forceable*/;
    int dpi_vec_test/*verilator public_flat*/  /*verilator forceable*/ = 32'hBABABABA;

    // --- 基础配置类 (用于 factory override 测试) ---
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

    // --- 序列 item 和 sequence (用于 sequencer 测试) ---
    class simple_item extends uvm_sequence_item;
        `uvm_object_utils(simple_item)
        rand int data;
        function new(string name = "simple_item");
            super.new(name);
        endfunction
    endclass

    class simple_seq extends uvm_sequence #(simple_item);
        `uvm_object_utils(simple_seq)
        function new(string name = "simple_seq");
            super.new(name);
        endfunction
        virtual task body();
            simple_item req;
            `uvm_do(req)
        endtask
    endclass

    // --- 寄存器模型 (用于 register API 测试) ---
    class test_reg_field extends uvm_reg_field;
        `uvm_object_utils(test_reg_field)
        function new(string name = "test_reg_field");
            super.new(name);
        endfunction
    endclass

    class test_reg extends uvm_reg;
        `uvm_object_utils(test_reg)
        test_reg_field field_0;
        test_reg_field field_1;
        function new(string name = "test_reg");
            super.new(name, 32, UVM_NO_COVERAGE);
        endfunction
        virtual function void build();
            field_0 = test_reg_field::type_id::create("field_0");
            field_0.configure(this, 16, 0, "RW", 0, 16'h0, 1, 1, 1);
            field_1 = test_reg_field::type_id::create("field_1");
            field_1.configure(this, 16, 16, "RW", 0, 16'h0, 1, 1, 1);
        endfunction
    endclass

    class test_reg_block extends uvm_reg_block;
        `uvm_object_utils(test_reg_block)
        test_reg reg_0;
        test_reg reg_1;
        test_reg reg_2;
        function new(string name = "test_reg_block");
            super.new(name, UVM_NO_COVERAGE);
        endfunction
        virtual function void build();
            default_map = create_map("default_map", 'h0, 4, UVM_LITTLE_ENDIAN);
            reg_0 = test_reg::type_id::create("reg_0");
            reg_0.configure(this, null);
            reg_0.build();
            default_map.add_reg(reg_0, 'h0000, "RW");
            reg_1 = test_reg::type_id::create("reg_1");
            reg_1.configure(this, null);
            reg_1.build();
            default_map.add_reg(reg_1, 'h0004, "RW");
            reg_2 = test_reg::type_id::create("reg_2");
            reg_2.configure(this, null);
            reg_2.build();
            default_map.add_reg(reg_2, 'h0008, "RW");
            lock_model();
        endfunction
    endclass

    // --- 自定义组件 (用于 component topology 测试) ---
    class custom_component extends uvm_component;
        `uvm_component_utils(custom_component)
        function new(string name = "custom_component", uvm_component parent = null);
            super.new(name, parent);
        endfunction
    endclass

    // --- 自定义 callback (用于 callback 测试) ---
    class test_callback extends uvm_callback;
        `uvm_object_utils(test_callback)
        function new(string name = "test_callback");
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
