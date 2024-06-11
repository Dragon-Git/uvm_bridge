`define FUNC_TRIGER(NAME) \
wire NAME``_s; \
uvm_object NAME``_obj; \
always @(posedge NAME``_s) begin \
    NAME``_obj = new();\
end

`FUNC_TRIGER(write_reg)
`FUNC_TRIGER(read_reg)
`FUNC_TRIGER(write_stream)
`FUNC_TRIGER(read_stream)
`FUNC_TRIGER(start_seq)
`FUNC_TRIGER(wait_time)
