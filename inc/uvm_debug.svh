`define FUNC_TRIGER(NAME) \
wire NAME``_s; \
uvm_object NAME``_obj; \
event_pool = uvm_event_pool::get_global_pool(); \
uvm_event NAME``_event = event_pool.get("NAME``_event"); \
always @(posedge NAME``_s) begin \
    NAME``_obj = new();\
    NAME``_event.trigger(NAME``_obj); \
end

`FUNC_TRIGER(write_reg)
`FUNC_TRIGER(read_reg)
`FUNC_TRIGER(write_stream)
`FUNC_TRIGER(read_stream)
`FUNC_TRIGER(start_seq)
`FUNC_TRIGER(wait_time)
`FUNC_TRIGER(finish)

