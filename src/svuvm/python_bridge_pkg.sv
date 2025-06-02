package python_bridge_pkg;

    import uvm_pkg::*;
    `include "uvm_macros.svh"

    function automatic uvm_component get_contxt (string contxt);

        uvm_root top = uvm_root::get();
        uvm_component comp;
        if (contxt == "") begin
            get_contxt = top;
        end else begin
            get_contxt = top.find(contxt);
        end
    endfunction

    //------------------------------------------------------------------------------
    // Group: Factory
    //
    // Provides ability to set type and instance overrides for simple classes
    // (non-parameterized).
    //------------------------------------------------------------------------------

    function automatic void print_factory (int all_types=1);
        uvm_factory factory = uvm_factory::get();
        factory.print(all_types);
    endfunction

    function automatic void set_factory_inst_override (string requested_type, string override_type, string contxt);
        uvm_factory factory = uvm_factory::get();
        factory.set_inst_override_by_name(requested_type,override_type,contxt);
    endfunction

    function automatic void set_factory_type_override (string requested_type, string override_type, bit replace=1);
        uvm_factory factory = uvm_factory::get();
        factory.set_type_override_by_name(requested_type,override_type,replace);
    endfunction

    function automatic void create_object_by_name (string requested_type, string contxt="", string name="");
        uvm_factory factory = uvm_factory::get();
        factory.create_object_by_name(requested_type,contxt,name);
    endfunction

    function automatic void create_component_by_name (string requested_type, string contxt="", string name="");
        uvm_factory factory = uvm_factory::get();
        uvm_root top = uvm_root::get();
        uvm_component 	parent;
        parent = top.find(contxt);
        if (parent == null)  begin
            top.print_topology();
            `uvm_fatal("python_bridge_pkg", $sformatf("can not find %0s uvm_component", contxt))
        end
        factory.create_component_by_name(requested_type,contxt,name,parent);
    endfunction

    function automatic void debug_factory_create (string requested_type, string contxt="");
        uvm_factory factory = uvm_factory::get();
        factory.debug_create_by_name(requested_type,contxt,"");
    endfunction

    function automatic void find_factory_override (string requested_type, string contxt, output string override_type);
        uvm_object_wrapper wrapper;
        uvm_factory factory = uvm_factory::get();
        wrapper = factory.find_override_by_name(requested_type, contxt);
        if (wrapper == null)
            override_type = requested_type;
        else
            override_type = wrapper.get_type_name();
    endfunction

    //------------------------------------------------------------------------------
    // Group: Topology
    //
    // Provides ability to wait for UVM phase transitions.
    //------------------------------------------------------------------------------

    function automatic void print_topology(string contxt="");
        uvm_root top = uvm_root::get();
        uvm_component comps[$];
        if (contxt == "")
            comps.push_back(top);
        else begin
            top.find_all(contxt,comps);
            `uvm_error("PRINT_TOPOLOGY", {"No components found at context ", contxt})
            return;
        end

        foreach (comps[i]) begin
            string name = comps[i].get_full_name();
            if (name == "")
                name = "uvm_top";
            `uvm_info("PRINT_TOPOLOGY", {"Topology for component ",name,":"},UVM_NONE)
            comps[i].print();
            $display();
        end
    endfunction

    function automatic void set_timeout(longint timeout, bit overridable=1);
        uvm_root top = uvm_root::get();
        top.set_timeout(time'(timeout), overridable);
    endfunction

    function automatic void set_finish_on_completion(bit f=1);
        uvm_root top = uvm_root::get();
        top.set_finish_on_completion(f);
    endfunction

    //------------------------------------------------------------------------------
    // Group: OBJECTIONS
    //
    // Provides ability to raise or drop objections.
    // (limited to phase objections ).
    //------------------------------------------------------------------------------
    function automatic void uvm_objection_op (string op, string name, string contxt, string description, int unsigned count);
        uvm_domain dom;
        uvm_phase ph;
        string nm;
        uvm_root top = uvm_root::get();
        uvm_component 	comp;

        comp = get_contxt(contxt);
        if (comp == null)
            comp = uvm_root::get();
        nm = comp.get_full_name();
        if ($test$plusargs("UVM_COMMAND_TRACE"))
            `uvm_info("TRACE/UVM_CMD/OBJECTION",$sformatf("op=%s name=%s contxt=%s description=%s count=%0d sv_contxt=%s",
                op,name,contxt,description,count,(nm==""?"uvm_top":nm)),UVM_NONE)
        dom = uvm_domain::get_common_domain();
        ph = dom.find_by_name(name,0);
        description = {contxt,": ",description};
        if (ph == null) begin
            `uvm_error({"UVM_",op,"_OBJECTION"}, {"Request for objection in unknown phase <",name,">"})
            return;
        end
        if (op == "RAISE")
            ph.raise_objection(comp,description,count);
        else if (op == "DROP")
            ph.drop_objection(comp,description,count);
        else
            `uvm_error("UVM_OBJECTION", {"Unknown operation ",op})
    endfunction

    //------------
    // uvm debug
    //------------
    class dbg_uvm_object#(type T=uvm_object, string name="") extends T;
        `uvm_object_registry(dbg_uvm_object#(T, name), name)

        function new(string name="dbg_uvm_object");
            super.new(name);
            uvm_config_db #(string)::set(null, "", get_full_name, this.sprint());
        endfunction

    endclass

    function void dbg_print(string name);
        string info;
        uvm_config_db #(string)::get(null, "", name, info);
        $display(info);
    endfunction

    function automatic void tlm_connect(string src, string dst);
        uvm_component src_comp = get_contxt(src);
        uvm_component dst_comp = get_contxt(dst);
        uvm_port_component#(uvm_port_base #()) src_port_comp;
        uvm_port_component#(uvm_port_base #()) dst_port_comp;
        uvm_port_base #() src_port;
        uvm_port_base #() dst_port;
        
        if (src_comp == null) begin
            `uvm_fatal("python_bridge_pkg", $sformatf("can not find %0s uvm_component", src))
        end
        if (dst_comp == null) begin
            `uvm_fatal("python_bridge_pkg", $sformatf("can not find %0s uvm_component", dst))
        end
        if (!$cast(src_port_comp, src_comp))  begin
            `uvm_fatal("python_bridge_pkg", $sformatf("cast failed - %0s is not a uvm_port_component", src))
        end
        if (!$cast(dst_port_comp, dst_comp))  begin
            `uvm_fatal("python_bridge_pkg", $sformatf("cast failed - %0s is not a uvm_port_component", dst))
        end
        if (!$cast(src_port, src_port_comp.get_port()))  begin
            `uvm_fatal("python_bridge_pkg", $sformatf("cast failed - %0s is not a uvm_port", src))
        end
        if (!$cast(dst_port, dst_port_comp.get_port()))  begin
            `uvm_fatal("python_bridge_pkg", $sformatf("cast failed - %0s is not a uvm_port", dst))
        end
        src_port.connect(dst_port);
    endfunction

    //------------
    // uvm event
    //------------

    // Wrapper for wait_on
    task automatic wait_on(string ev_name, bit delta = 0);
        uvm_event ev;
        ev = uvm_event_pool::get_global(ev_name);
        ev.wait_on(delta);
    endtask

    // Wrapper for wait_off
    task automatic wait_off(string ev_name, bit delta = 0);
        uvm_event ev = uvm_event_pool::get_global(ev_name);
        ev.wait_off(delta);
    endtask

    // Wrapper for wait_trigger
    task automatic wait_trigger(string ev_name);
        uvm_event ev = uvm_event_pool::get_global(ev_name);
        ev.wait_trigger();
    endtask

    // Wrapper for wait_ptrigger
    task automatic wait_ptrigger(string ev_name);
        uvm_event ev = uvm_event_pool::get_global(ev_name);
        ev.wait_ptrigger();
    endtask

    // Wrapper for wait_trigger_data
    task automatic wait_trigger_data(string ev_name, output uvm_object data);
        uvm_event ev = uvm_event_pool::get_global(ev_name);
        ev.wait_trigger_data(data);
    endtask

    // Wrapper for wait_ptrigger_data
    task automatic wait_ptrigger_data(string ev_name, output uvm_object data);
        uvm_event ev = uvm_event_pool::get_global(ev_name);
        ev.wait_ptrigger_data(data);
    endtask

    // Wrapper for get_trigger_time
    function automatic longint get_trigger_time(string ev_name);
        uvm_event ev = uvm_event_pool::get_global(ev_name);
        return ev.get_trigger_time();
    endfunction

    // Wrapper for is_on
    function automatic bit is_on(string ev_name);
        uvm_event ev = uvm_event_pool::get_global(ev_name);
        return ev.is_on();
    endfunction

    // Wrapper for is_off
    function automatic bit is_off(string ev_name);
        uvm_event ev = uvm_event_pool::get_global(ev_name);
        return ev.is_off();
    endfunction

    // Wrapper for reset
    function automatic void reset(string ev_name, bit wakeup = 0);
        uvm_event ev = uvm_event_pool::get_global(ev_name);
        ev.reset(wakeup);
    endfunction

    // Wrapper for cancel
    function automatic void cancel(string ev_name);
        uvm_event ev = uvm_event_pool::get_global(ev_name);
        ev.cancel();
    endfunction

    // Wrapper for get_num_waiters
    function automatic int get_num_waiters(string ev_name);
        uvm_event ev = uvm_event_pool::get_global(ev_name);
        return ev.get_num_waiters();
    endfunction

    // Wrapper for trigger
    function automatic void trigger(string ev_name);
        uvm_event ev = uvm_event_pool::get_global(ev_name);
        ev.trigger();
    endfunction
    
    // Wrapper for get_trigger_data
    function automatic uvm_object get_trigger_data(string ev_name);
        uvm_event ev = uvm_event_pool::get_global(ev_name);
        return ev.get_trigger_data();
    endfunction

    // Wrapper for get_default_data
    function automatic uvm_object get_default_data(string ev_name);
        uvm_event ev = uvm_event_pool::get_global(ev_name);
        return ev.get_default_data();
    endfunction

    // Wrapper for set_default_data
    function automatic void set_default_data(string ev_name, uvm_object data);
        uvm_event ev = uvm_event_pool::get_global(ev_name);
        ev.set_default_data(data);
    endfunction
    

    `define SET_CONFIG_FUNC(datatype) \
        function automatic void set_config_``datatype``(string contxt, string inst_name, string field_name, datatype value); \
            uvm_component comp = get_contxt(contxt); \
            uvm_config_db#(datatype)::set(comp, inst_name, field_name, value); \
        endfunction
    
    `define GET_CONFIG_FUNC(datatype) \
        function automatic datatype get_config_``datatype``(string contxt, string inst_name, string field_name); \
            uvm_component comp = get_contxt(contxt); \
            uvm_config_db#(datatype)::get(comp, inst_name, field_name, get_config_``datatype``); \
        endfunction
    
    typedef longint unsigned uint64_t;
    typedef int int_array_t[];
    typedef byte byte_array_t[];
    
    `SET_CONFIG_FUNC(uint64_t)
    `GET_CONFIG_FUNC(uint64_t)
    `SET_CONFIG_FUNC(string)
    `GET_CONFIG_FUNC(string)
    `SET_CONFIG_FUNC(int_array_t)
    `GET_CONFIG_FUNC(int_array_t)
    `SET_CONFIG_FUNC(byte_array_t)
    `GET_CONFIG_FUNC(byte_array_t)

    function automatic int get_report_verbosity_level(string contxt, int severity, string id);
        uvm_component comp = get_contxt(contxt);
        return comp.get_report_verbosity_level(uvm_severity'(severity), id);
    endfunction

    function automatic int get_report_max_verbosity_level(string contxt);
        uvm_component comp = get_contxt(contxt);
        return comp.get_report_max_verbosity_level();
    endfunction

    function automatic void set_report_verbosity_level (string contxt, int verbosity_level);
        uvm_component comp = get_contxt(contxt);
        comp.set_report_verbosity_level(verbosity_level);
    endfunction

    function automatic void set_report_id_verbosity (string contxt, string id, int verbosity);
        uvm_component comp = get_contxt(contxt);
        comp.set_report_id_verbosity(id, verbosity);
    endfunction

    function automatic void set_report_severity_id_verbosity (string contxt, int severity, string id, int verbosity);
        uvm_component comp = get_contxt(contxt);
        comp.set_report_severity_id_verbosity(uvm_severity'(severity), id, verbosity);
    endfunction

    function automatic int get_report_action(string contxt, int severity, string id);
        uvm_component comp = get_contxt(contxt);
        return comp.get_report_action(uvm_severity'(severity), id);
    endfunction

    function automatic void set_report_severity_action (string contxt, int severity, uvm_action action);
        uvm_component comp = get_contxt(contxt);
        comp.set_report_severity_action(uvm_severity'(severity), action);
    endfunction


    function automatic void set_report_id_action (string contxt, string id, uvm_action action);
        uvm_component comp = get_contxt(contxt);
        comp.set_report_id_action(id, action);
    endfunction

    function automatic void set_report_severity_id_action (string contxt, int severity, string id, uvm_action action);
        uvm_component comp = get_contxt(contxt);
        comp.set_report_severity_id_action(uvm_severity'(severity), id, action);
    endfunction

    function automatic void set_report_severity_override(string contxt, int cur_severity, int new_severity);
        uvm_component comp = get_contxt(contxt);
        comp.set_report_severity_override(uvm_severity'(cur_severity), uvm_severity'(new_severity));
    endfunction

    function automatic void set_report_severity_id_override(string contxt, int cur_severity, string id, int new_severity);
        uvm_component comp = get_contxt(contxt);
        comp.set_report_severity_id_override(uvm_severity'(cur_severity), id, uvm_severity'(new_severity));
    endfunction

    function automatic string base16_encode(input byte data_in []);
        base16_encode = "";
        foreach (data_in[i]) begin
            base16_encode = {base16_encode, $sformatf("%02h", data_in[i])};
        end
    endfunction

    function automatic byte_array_t base16_decode(input string hex_str);
        int str_len;
        static int i;
        str_len = hex_str.len();
        if (str_len % 2!= 0) begin
            $display("Invalid hexadecimal string length for conversion.");
            return base16_decode;
        end
        base16_decode = new[str_len>>1];
        for (i = 0; i < str_len; i += 2) begin
            base16_decode[i>>1] = hex_str.substr(i, i+1).atohex();
        end
        return base16_decode;
    endfunction

    task automatic start_seq(string seq_name, string sqr_name, bit rand_en=0, bit background=0);
        uvm_root top;
        uvm_factory factory;
        uvm_object obj;
        uvm_component comp;
        uvm_sequence_item item;
        uvm_sequence_base seq;
        uvm_sequencer_base sqr;
 
        top = uvm_root::get();
        factory = uvm_factory::get();
        obj = factory.create_object_by_name(seq_name, "", seq_name);
        if (obj == null)  begin
            factory.print(1);
            `uvm_fatal("python_bridge_pkg", $sformatf("can not create %0s seq", seq_name))
        end
        if (!$cast(item, obj))  begin
            `uvm_fatal("python_bridge_pkg", $sformatf("cast failed - %0s is not a uvm_sequence_item", seq_name))
        end
        comp = top.find(sqr_name);
        if (comp == null)  begin
            top.print_topology();
            `uvm_fatal("python_bridge_pkg", $sformatf("can not find %0s seq", sqr_name))
        end
        if (!$cast(sqr, comp))  begin
            `uvm_fatal("python_bridge_pkg", $sformatf("cast failed - %0s is not a uvm_sequencer", sqr_name))
        end
        if (rand_en)  begin
            item.randomize();
        end
    `ifndef VERILATOR
        if (background)  begin: bg
            fork: start_seq__bg_thread
                begin
                    if (item.is_item())  begin
                        sqr.execute_item(item);
                    end else if ($cast(seq, item))  begin
                        seq.start(sqr);
                    end
                end
            join_none: start_seq__bg_thread
        end else begin: fg
            if (item.is_item())  begin
                sqr.execute_item(item);
            end else if ($cast(seq, item))  begin
                seq.start(sqr);
            end
        end
    `endif //VERILATOR
    endtask:start_seq

    class reg_operator extends uvm_object;

        uvm_reg_block top_reg_block;
        uvm_status_e status;
        static reg_operator inst;

        `uvm_object_utils(reg_operator)

        function new(string name = "reg_operator");
            super.new(name);
        endfunction:new

        static function void set_top_reg_block(uvm_reg_block block);
            if (inst == null)  begin
                inst = reg_operator::type_id::create("reg_operator");
            end
            inst.top_reg_block = block;
        endfunction:set_top_reg_block

        function uvm_reg get_reg(string name);
            uvm_reg_block block;
            uvm_reg_block current_block;
            string blk_name;
            string reg_name;
            int start_idx = 0;
            int end_idx;

            if (top_reg_block == null)  begin
                `uvm_fatal("python_bridge_pkg", "top_reg_block is null, please set it by reg_operator::set_top_reg_block")
            end

            current_block = top_reg_block;
            for(int i = 0; i < name.len(); i++) begin
                if(name[i] == ".") begin
                    end_idx = i;
                    blk_name = name.substr(start_idx, end_idx - 1);
                    block = current_block.get_block_by_name(blk_name);
                    if (block == null)  begin
                        `uvm_fatal("python_bridge_pkg", $sformatf("can not find %0s in reg_block", blk_name))
                    end
                    current_block = block;
                    start_idx = i + 1;
                end
            end
            
            reg_name = name.substr(start_idx, name.len() - 1);
            get_reg = current_block.get_reg_by_name(reg_name);
            if (get_reg == null)  begin
                `uvm_fatal("python_bridge_pkg", $sformatf("can not find %0s in reg_block", reg_name))
            end
        endfunction:get_reg

        virtual task write_reg(input string name, input int data);
            uvm_reg rg;
            rg = get_reg(name);
            rg.write(status, data);
        endtask:write_reg

        virtual task read_reg(input string name, output int data);
            uvm_reg rg;
            rg = get_reg(name);
            rg.read(status, data);
        endtask:read_reg

        virtual task check_reg(input string name, input int data=0, input bit predict=1'b0);
            uvm_reg rg;
            rg = get_reg(name);
            if (predict)  begin
                rg.predict(data);
            end
            rg.mirror(status, UVM_CHECK);
        endtask:check_reg

    endclass:reg_operator

    task automatic write_reg(input string name, input int data);
       `ifndef VERILATOR
        reg_operator::inst.write_reg(name, data);
        `endif //VERILATOR
    endtask:write_reg

    task automatic read_reg(input string name, output int data);
        `ifndef VERILATOR
        reg_operator::inst.read_reg(name, data);
        `endif //VERILATOR
    endtask:read_reg

    task automatic check_reg(input string name, input int data=0, input bit predict=1'b0);
        `ifndef VERILATOR
        reg_operator::inst.check_reg(name, data, predict);
        `endif //VERILATOR
    endtask:check_reg

    // custom task
    task automatic wait_unit(int n);
    `ifndef VERILATOR
        #n;
    `endif //VERILATOR
        $display("=== time: %d ===", $time);
    endtask:wait_unit

    task automatic run_test_wrap(string test_name="");
    `ifndef VERILATOR
        run_test(test_name);
    `endif //VERILATOR
    endtask:run_test_wrap

    // export
    // uvm_factory
    export "DPI-C" function print_factory;
    export "DPI-C" function set_factory_inst_override;
    export "DPI-C" function set_factory_type_override;
    export "DPI-C" function create_object_by_name;
    export "DPI-C" function create_component_by_name;
    export "DPI-C" function debug_factory_create;
    export "DPI-C" function find_factory_override; // not tested

    // uvm_root
    export "DPI-C" function set_timeout;
    export "DPI-C" function set_finish_on_completion;
    export "DPI-C" function print_topology;
    export "DPI-C" function uvm_objection_op;
    export "DPI-C" function dbg_print;
    export "DPI-C" function tlm_connect;

    // uvm_event
    `ifndef VERILATOR
    export "DPI-C" task wait_on;
    export "DPI-C" task wait_off;
    export "DPI-C" task wait_trigger;
    export "DPI-C" task wait_ptrigger;
    //export "DPI-C" task wait_trigger_data;
    //export "DPI-C" task wait_ptrigger_data;
    `endif //VERILATOR

    export "DPI-C" function get_trigger_time;
    export "DPI-C" function is_on;
    export "DPI-C" function is_off;
    export "DPI-C" function reset;
    export "DPI-C" function cancel;
    export "DPI-C" function get_num_waiters;
    export "DPI-C" function trigger;
    //export "DPI-C" function get_trigger_data;
    //export "DPI-C" function get_default_data;
    //export "DPI-C" function set_default_data;

    // config db
    export "DPI-C" function set_config_uint64_t;
    export "DPI-C" function get_config_uint64_t;
    export "DPI-C" function set_config_string;
    export "DPI-C" function get_config_string;
    // export "DPI-C" function set_config_int_array_t;
    // export "DPI-C" function get_config_int_array_t;
    // export "DPI-C" function set_config_byte_array_t;
    // export "DPI-C" function get_config_byte_array_t;

    // report
    export "DPI-C" function get_report_verbosity_level;
    export "DPI-C" function get_report_max_verbosity_level;
    export "DPI-C" function set_report_verbosity_level;
    export "DPI-C" function set_report_id_verbosity;
    export "DPI-C" function set_report_severity_id_verbosity;
    export "DPI-C" function get_report_action;
    export "DPI-C" function set_report_severity_action;
    export "DPI-C" function set_report_id_action;
    export "DPI-C" function set_report_severity_id_action;
    export "DPI-C" function set_report_severity_override;
    export "DPI-C" function set_report_severity_id_override;

    // register access
    export "DPI-C" task write_reg;
    export "DPI-C" task read_reg;
    export "DPI-C" task check_reg;
    // sequence
    export "DPI-C" task start_seq;

    // utils
    export "DPI-C" task run_test_wrap;
    export "DPI-C" task wait_unit;

    import "DPI-C" pure function string dirname(string file_path);
    `ifndef VERILATOR
    import "DPI-C" function string getenv(input string name);
    `endif //VERILATOR
    import "DPI-C" context task py_func(input string mod_name, string func_name = "main", string mod_paths = "");
    task call_py_func(input string mod_name, string func_name = "main", string mod_paths = "");
        py_func(mod_name, func_name, mod_paths);
    endtask:call_py_func

endpackage