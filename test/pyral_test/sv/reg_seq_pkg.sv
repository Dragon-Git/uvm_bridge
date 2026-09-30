// A single register operation as a sequence.
//
// start_seq() creates the sequence by name with no constructor arguments
// and calls seq.start(sqr), so the operation cannot ride in on the
// constructor. The Python side stages the operation with set_config_int /
// set_config_string and this sequence picks it up in pre_start().
//
// config_db is keyed by type as well as by scope, so the types here must
// match what python_bridge_pkg's SET_CONFIG_FUNC macros actually use:
// set_config_int is bound to set_config_uint64_t, i.e. the value lives in
// the database as uint64_t. Using int here would silently miss.

package reg_seq_pkg;

    // Needed for the #10 in the wait(var) probe below.
    timeunit 1ns;
    timeprecision 1ps;

    import uvm_pkg::*;
    import reg_agent_pkg::*;
    `include "uvm_macros.svh"

    class reg_seq extends uvm_sequence #(reg_item);
        // Staged by Python before start_seq().
        uint64_t          op_addr;
        uint64_t          op_wdata;
        uint64_t          op_is_write;
        string            op_label;

        // Published by this sequence for Python to read back afterwards.
        uint64_t          res_rdata;
        uint64_t          res_err;

        // Counter for the pre-flight wait(var) probe below. Static so the
        // forked increment and the wait see the same variable.
        static int        probe_counter = 0;

        `uvm_object_utils(reg_seq)

        function new(string name = "reg_seq");
            super.new(name);
        endfunction

        virtual task pre_start();
            // Python stages these with contxt="" (which get_contxt maps to
            // uvm_root) and inst_name="*". Looking them up with "this" would
            // search from the sequence instance up through its ancestors and
            // not reach the root, so every lookup would silently return the
            // default - use the same null-context / wildcard form instead.
            void'(uvm_config_db#(uint64_t)::get(null, "*", "op_addr",     op_addr));
            void'(uvm_config_db#(uint64_t)::get(null, "*", "op_wdata",    op_wdata));
            void'(uvm_config_db#(uint64_t)::get(null, "*", "op_is_write", op_is_write));
            void'(uvm_config_db#(string)::get(null,   "*", "op_label",    op_label));
            `uvm_info("REG_SEQ", $sformatf("pre_start done (addr=0x%0x)", op_addr), UVM_LOW)
        endtask

        virtual task body();
            uint64_t snapshot;
            reg_item it;
            `uvm_info("REG_SEQ", $sformatf("body: start_item (addr=0x%0x wr=%0b)", op_addr, op_is_write[0]), UVM_LOW)

            // Pre-flight check of the primitive the sequencer handshake is
            // built on. uvm_sequencer_base drives everything through
            // "wait (a != b)" where b is written by another process: the
            // driver waits for m_lock_arb_size to change, the sequence waits
            // for the driver to set arb_completed. Test the same pattern
            // here, in the sequence's own process, before relying on it.
            snapshot = probe_counter;
            fork
                begin
                    #10;
                    probe_counter++;
                end
            join_none
            wait (snapshot != probe_counter);
            `uvm_info("REG_SEQ", "body: wait(var) across processes works", UVM_LOW)

            it = reg_item::type_id::create("it");
            start_item(it);
            `uvm_info("REG_SEQ", "body: start_item returned (item granted)", UVM_LOW)
            // start_seq is called with rand_en=0, so the item is filled
            // explicitly rather than randomized.
            it.is_write = op_is_write[0];
            it.addr     = op_addr[31:0];
            it.wdata    = op_wdata[31:0];
            it.label    = op_label;
            finish_item(it);

            // finish_item() blocks until the driver calls item_done(), so
            // the read data and error status are final by this point.
            res_rdata = it.rdata;
            res_err   = it.err;
            `uvm_info("REG_SEQ", $sformatf("body: done (rdata=0x%0x err=%0b)", res_rdata, res_err), UVM_LOW)
            uvm_config_db#(uint64_t)::set(null, "*", "res_rdata", res_rdata);
            uvm_config_db#(uint64_t)::set(null, "*", "res_err",   res_err);
        endtask
    endclass

endpackage
