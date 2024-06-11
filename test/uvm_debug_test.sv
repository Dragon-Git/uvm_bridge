
module tb();
    class uvm_object;
    endclass
    `include "uvm_debug.svh"
    initial begin
        #100;
        $finish;
    end

endmodule : tb
