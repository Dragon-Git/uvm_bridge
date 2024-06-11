package uvm_debug_pkg;

    class debug_test extends base_test;

        event_pool = uvm_event_pool::get_global_pool();
        uvm_event start_seq_event = event_pool.get("start_seq_event");

        `uvm_new_func

        virtual task main_phase(uvm_phase phase);
            uvm_object      obj;
            super.main_phase(phase);
            phase.raise_objection(this);
            fork
                while(1) begin
                    start_seq_event.wait_triger_data(obj);
                    start_seq(obj.seq_name);
                end
                #100;
            join_any
            phase.drop_objection(this);
        endtask: main_phase

        // create a sequence by name and return the handle of uvm_sequence
        function automatic start_seq(string seq_name);
            uvm_object      obj;
            uvm_factory     factory = uvm_factory::get();
            uvm_sequence    seq;

            obj = factory.create_object_by_name(seq_name, "", seq_name);
            if (obj == null) begin
              // print factory overrides to help debug
              factory.print(1);
              `uvm_fatal(msg_id, $sformatf("could not create %0s seq", seq_name))
            end
            if (!$cast(seq, obj)) begin
              `uvm_fatal(msg_id, $sformatf("cast failed - %0s is not a uvm_sequence", seq_name))
            end
            seq.start(null);
        endfunction

    endclass: debug_test
    
endpackage: uvm_debug_pkg