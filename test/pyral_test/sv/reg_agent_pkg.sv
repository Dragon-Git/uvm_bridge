// UVM agent for driving the PeakRDL-generated register block over APB3.
//
// One sequence item == one register operation (per the design decision), so
// a Python-driven test issues one start_seq() call per read or write and
// the sequencer is drained synchronously before the next one. The driver
// owns the APB slave-side transactions and reads the result back into the
// item so the sequence can assert on it.
//
// The agent is registered with the UVM factory so Python can instantiate it
// by name via create_component_by_name(), and the sequencer is findable by
// its hierarchical path for start_seq().

package reg_agent_pkg;

    // Needed for the #() delays in reg_driver; the top-level testbench
    // clock runs at 10ns per cycle.
    timeunit 1ns;
    timeprecision 1ps;

    import uvm_pkg::*;
    `include "uvm_macros.svh"

    // One register operation. is_write selects write vs read; rdata is
    // only meaningful for reads. err is set when the APB slave asserted
    // PSLVERR.
    class reg_item extends uvm_sequence_item;
        rand bit          is_write;
        rand bit [31:0]   addr;
        rand bit [31:0]   wdata;
        bit [31:0]        rdata;
        bit               err;
        string            label;

        `uvm_object_utils_begin(reg_item)
            `uvm_field_int(is_write, UVM_ALL_ON)
            `uvm_field_int(addr,    UVM_ALL_ON)
            `uvm_field_int(wdata,   UVM_ALL_ON)
            `uvm_field_int(rdata,   UVM_ALL_ON)
            `uvm_field_int(err,     UVM_ALL_ON)
        `uvm_object_utils_end

        function new(string name = "reg_item");
            super.new(name);
        endfunction
    endclass

    // Driver: pulls one reg_item at a time and performs the APB transfer
    // through the apb3_intf_driver bridge. The bridge serialises with a
    // semaphore, but the sequencer is drained synchronously so there is
    // never more than one outstanding transfer; the driver still routes
    // every item through the bridge so the APB timing stays correct.
    class reg_driver extends uvm_driver #(reg_item);
        apb3_intf_driver       m_apb_drv;
        virtual apb3_intf      m_apb;

        `uvm_component_utils(reg_driver)

        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            if (m_apb == null)
                `uvm_fatal("REG_DRV", "m_apb not connected before build")
            m_apb_drv = new("m_apb_drv", .clk(m_apb.clk), .rst(m_apb.rst), .m_apb(m_apb));
        endfunction

        task run_phase(uvm_phase phase);
            `uvm_info("REG_DRV", "run_phase entered", UVM_LOW)
            forever begin
                `uvm_info("REG_DRV", "waiting on get_next_item", UVM_LOW)
                seq_item_port.get_next_item(req);
                `uvm_info("REG_DRV", $sformatf("got item addr=0x%0x wr=%0b", req.addr, req.is_write), UVM_LOW)
                if (req.is_write) begin
                    m_apb_drv.write(req.addr, req.wdata, req.err);
                end else begin
                    m_apb_drv.read(req.addr, req.rdata, req.err);
                end
                `uvm_info("REG_DRV", $sformatf("APB done rdata=0x%0x err=%0b", req.rdata, req.err), UVM_LOW)
                // Let the simulation advance between transfers. Without
                // this the sequence can be torn down before the driver has
                // had a chance to run at all.
                #(100ns);
                `uvm_info("REG_DRV", "calling item_done", UVM_LOW)
                seq_item_port.item_done();
            end
        endtask
    endclass

    class reg_sequencer extends uvm_sequencer #(reg_item);
        `uvm_component_utils(reg_sequencer)
        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction

        // Instrumentation for the handshake. The driver entering
        // get_next_item and the sequence entering start_item are both
        // visible in the log, but neither returns, so log the exit of each
        // to see which side is actually blocked. wait_for_grant is where
        // the sequence parks until the sequencer arbitrates.
        virtual task get_next_item(output reg_item t);
            `uvm_info("REG_SQR", "get_next_item: enter", UVM_LOW)
            super.get_next_item(t);
            `uvm_info("REG_SQR", "get_next_item: item delivered", UVM_LOW)
        endtask

        virtual task wait_for_grant(uvm_sequence_base sequence_ptr,
                                    int item_priority = -1,
                                    bit lock_request = 0);
            `uvm_info("REG_SQR", $sformatf("wait_for_grant: enter (%s)",
                                           sequence_ptr.get_full_name()), UVM_LOW)
            super.wait_for_grant(sequence_ptr, item_priority, lock_request);
            `uvm_info("REG_SQR", "wait_for_grant: granted", UVM_LOW)
        endtask
    endclass

    // Agent owns the driver + sequencer and wires them together. The APB
    // interface is handed in by Python via config_db (m_apb) because the
    // agent is created dynamically and cannot reach the testbench directly.
    class reg_agent extends uvm_agent;
        reg_driver      m_drv;
        reg_sequencer   m_sqr;
        apb3_intf       m_apb;

        `uvm_component_utils(reg_agent)

        function new(string name, uvm_component parent);
            super.new(name, parent);
        endfunction

        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            if (!uvm_config_db#(apb3_intf)::get(this, "", "m_apb", m_apb))
                `uvm_fatal("REG_AGENT", "m_apb not set in config_db")
            m_drv = reg_driver::type_id::create("m_drv", this);
            // The driver drives the bus, so hand it the interface handle
            // before its build_phase runs - the agent cannot reach the
            // testbench hierarchy itself, hence the config_db hop above.
            m_drv.m_apb = m_apb;
            m_sqr = reg_sequencer::type_id::create("m_sqr", this);
        endfunction

        function void connect_phase(uvm_phase phase);
            super.connect_phase(phase);
            m_drv.seq_item_port.connect(m_sqr.seq_item_export);
        endfunction
    endclass

endpackage
