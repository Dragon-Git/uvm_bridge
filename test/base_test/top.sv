module top ();
    import uvm_pkg::*;
    `include "uvm_macros.svh"
    import python_bridge_pkg::*;

    reg test_wire/*verilator public_flat*/  /*verilator forceable*/;
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

    // --- 寄存器模型的前端总线 ---
    //
    // RAL 的 reg.write()/read() 要经过一个 map：adapter 把 uvm_reg_bus_op
    // 翻成总线 item，driver 负责响应。缺了这一套，模型就只能做 predict，
    // 不能真的读写。这里给出最小的一套，接到 test_reg_block 上。

    class reg_bus_item extends uvm_sequence_item;
        `uvm_object_utils(reg_bus_item)
        rand bit [31:0] addr;
        rand bit [31:0] data;
        rand bit        is_write;
        function new(string name = "reg_bus_item");
            super.new(name);
        endfunction
    endclass

    class reg_bus_adapter extends uvm_reg_adapter;
        `uvm_object_utils(reg_bus_adapter)
        function new(string name = "reg_bus_adapter");
            super.new(name);
            supports_byte_enable = 0;
            // driver 原地改 item 再 item_done()，所以不需要 response item。
            provides_responses   = 0;
        endfunction

        virtual function uvm_sequence_item reg2bus(const ref uvm_reg_bus_op rw);
            reg_bus_item tr = reg_bus_item::type_id::create("tr");
            tr.addr     = rw.addr[31:0];
            tr.data     = rw.data[31:0];
            tr.is_write = (rw.kind == UVM_WRITE);
            return tr;
        endfunction

        virtual function void bus2reg(uvm_sequence_item bus_item, ref uvm_reg_bus_op rw);
            reg_bus_item tr;
            if (!$cast(tr, bus_item)) begin
                `uvm_fatal("REG_BUS", "bus2reg got something that is not a reg_bus_item")
                return;
            end
            rw.kind   = tr.is_write ? UVM_WRITE : UVM_READ;
            rw.addr   = tr.addr;
            rw.data   = tr.data;
            rw.status = UVM_IS_OK;
        endfunction
    endclass

    // 一个最小的寄存器堆：写进去存起来，读回最后写的值，没写过的读 0。
    // 用存储而不是 RTL，是为了让读写的结果可预期、可直接断言。
    class reg_bus_driver extends uvm_driver #(reg_bus_item);
        `uvm_component_utils(reg_bus_driver)
        bit [31:0] mem[int unsigned];
        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction
        task run_phase(uvm_phase phase);
            forever begin
                seq_item_port.get_next_item(req);
                if (req.is_write) mem[req.addr] = req.data;
                else              req.data = mem.exists(req.addr) ? mem[req.addr] : 32'h0;
                seq_item_port.item_done();
            end
        endtask
    endclass

    class reg_bus_agent extends uvm_agent;
        `uvm_component_utils(reg_bus_agent)
        reg_bus_driver                m_drv;
        uvm_sequencer #(reg_bus_item) m_sqr;
        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            m_drv = reg_bus_driver::type_id::create("m_drv", this);
            m_sqr = uvm_sequencer#(reg_bus_item)::type_id::create("m_sqr", this);
        endfunction
        function void connect_phase(uvm_phase phase);
            super.connect_phase(phase);
            m_drv.seq_item_port.connect(m_sqr.seq_item_export);
        endfunction
    endclass

    // 把寄存器模型接到总线上，并注册成 python_bridge 的 top reg block，
    // 这样 Python 侧的 write_reg()/read_reg()/get_reg_names() 才找得到它。
    //
    // 注册只能在这里做：uvm_reg_block 是 uvm_object，不是 uvm_component，
    // 而桥接的 set_top_reg_block_by_path() 走的是 top.find()——找不到对象。
    class reg_model_env extends uvm_component;
        `uvm_component_utils(reg_model_env)
        test_reg_block  m_block;
        reg_bus_agent   m_bus;
        uvm_reg_adapter m_adapter;

        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            m_bus     = reg_bus_agent::type_id::create("m_bus", this);
            m_adapter = reg_bus_adapter::type_id::create("m_adapter");
            m_block   = test_reg_block::type_id::create("m_block");
            m_block.build();
        endfunction

        function void end_of_elaboration_phase(uvm_phase phase);
            super.end_of_elaboration_phase(phase);
            m_block.default_map.set_sequencer(m_bus.m_sqr, m_adapter);
            // 默认 auto_predict 是关的：总线写不会碰镜像值，那要靠 monitor +
            // uvm_reg_predictor。这个测试没有 monitor，所以打开它——这样每次
            // 读写之后 get_mirrored_value() 的断言才有意义。
            m_block.default_map.set_auto_predict(1);
            reg_operator::set_top_reg_block(m_block);
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
