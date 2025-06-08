import itertools

from svuvm import svuvm
def cb_test(data):
    print("hello cb")
    return 1

def build():
    svuvm.print_factory()
    svuvm.print_topology()
    svuvm.debug_factory_create("base_env", "uvm_test_top")
    for i in range(3):
        svuvm.create_component_by_name("base_env", "uvm_test_top", f"m_env_{i}")
        for j in range(3):
            svuvm.create_component_by_name("base_agent", f"uvm_test_top.m_env_{i}", f"m_agent_{j}")
            svuvm.create_component_by_name("base_driver", f"uvm_test_top.m_env_{i}.m_agent_{j}", "m_driver")
            svuvm.create_component_by_name("base_monitor", f"uvm_test_top.m_env_{i}.m_agent_{j}", "m_monitor")
            svuvm.create_component_by_name("base_sequencer", f"uvm_test_top.m_env_{i}.m_agent_{j}", "m_sequencer")
    svuvm.print_topology()

def connect():
    for i in range(3):
        for j in range(3):
            # svuvm.tlm_connect(f"uvm_test_top.m_env_{i}.m_agent_{j}.m_driver.seq_item_port", f"uvm_test_top.m_env_{i}.m_agent_{j}.m_sequencer.seq_item_export")
            pass
def main():
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST print_topology \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    svuvm.create_object_by_name("env_cfg", "uvm_test_top", "m_env_cfg")
    svuvm.set_factory_inst_override("env_cfg", "random_env_cfg", "uvm_test_top.m_env_cfg")
    svuvm.create_object_by_name("env_cfg", "uvm_test_top", "m_random_env_cfg")
    svuvm.set_factory_type_override("env_cfg", "direct_env_cfg", 1)
    svuvm.create_object_by_name("env_cfg", "uvm_test_top", "m_direct_env_cfg")
    svuvm.print_topology()
    svuvm.print_factory()

    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST uvm_objection \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    prefix = ["pre_", "", "post_"]
    tsk_phases = ["reset", "configure", "main", "shutdown"]
    phases = ["".join(ph[::-1]) for ph in itertools.product(tsk_phases, prefix)]
    for phase in phases:
        svuvm.uvm_objection_op("RAISE", phase, "uvm_test_top", "TEST OBJECTION RAISE", 1)
        svuvm.uvm_objection_op("DROP", phase, "uvm_test_top", "TEST OBJECTION DROP", 1)

    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST uvm_hdl \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    value = svuvm.VpiVecVal()
    p = svuvm.uvm_hdl_check_path("top.dpi_vec_test")
    svuvm.uvm_info(f"uvm_hdl_check_path: <top.dpi_vec_test> {p}", svuvm.UVM_LOW)
    svuvm.uvm_hdl_deposit("top.dpi_vec_test", svuvm.VpiVecVal(0xDEADDEAD, 0x0))
    svuvm.uvm_hdl_read("top.dpi_vec_test", value)
    svuvm.uvm_info(f"uvm_hdl_read: <top.dpi_vec_test> 0x{value.aval:X}", svuvm.UVM_LOW)
    svuvm.uvm_hdl_force("top.dpi_vec_test", svuvm.VpiVecVal(0xDEADBEEF, 0x0))
    svuvm.uvm_hdl_read("top.dpi_vec_test", value)
    svuvm.uvm_info(f"uvm_hdl_read: <top.dpi_vec_test> 0x{value.aval:X}", svuvm.UVM_LOW)
    svuvm.uvm_hdl_release_and_read("top.dpi_vec_test", value)
    svuvm.uvm_info(f"uvm_hdl_release_and_read: <top.dpi_vec_test> 0x{value.aval:X}", svuvm.UVM_LOW)
    svuvm.uvm_hdl_release("top.dpi_vec_test")

    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST uvm_report \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    action_list = [
        svuvm.UVM_NO_ACTION,
        svuvm.UVM_DISPLAY,
        svuvm.UVM_LOG,
        svuvm.UVM_COUNT,
        svuvm.UVM_CALL_HOOK,
        svuvm.UVM_RM_RECORD,
        # svuvm.UVM_STOP,
        # svuvm.UVM_EXIT,
    ]
    for action in action_list:
        svuvm.set_report_id_action("", "uvm_report_test", action)
        for verbosity in range(0, 600, 100):
            svuvm.uvm_report(svuvm.UVM_INFO, "uvm_report_test", "UVM_INFO TEST SUCCESS!", verbosity, "run.py", 1)
        svuvm.uvm_report(svuvm.UVM_WARNING, "uvm_report_test", "UVM_WARNING TEST SUCCESS!", svuvm.UVM_NONE, "run.py", 1)
        svuvm.uvm_report(svuvm.UVM_ERROR, "uvm_report_test", "UVM_ERROR TEST SUCCESS!", svuvm.UVM_NONE, "run.py", 1)
    svuvm.set_report_severity_action("", svuvm.UVM_FATAL, svuvm.UVM_DISPLAY)
    svuvm.set_report_severity_override("", svuvm.UVM_FATAL, svuvm.UVM_INFO)
    svuvm.set_report_severity_id_verbosity("", svuvm.UVM_INFO, "main", svuvm.UVM_DEBUG)
    svuvm.set_report_severity_id_action("", svuvm.UVM_ERROR, "main", svuvm.UVM_NO_ACTION)
    svuvm.set_report_severity_id_override("", svuvm.UVM_ERROR, "main", svuvm.UVM_INFO)
    svuvm.uvm_info("UVM_INFO TEST SUCCESS!", svuvm.UVM_MEDIUM)
    svuvm.uvm_warning("UVM_WARNING TEST SUCCESS!")
    svuvm.uvm_error("UVM_ERROR TEST SUCCESS!")
    svuvm.uvm_fatal("UVM_FATAL TEST SUCCESS!")

    svuvm.set_report_id_verbosity("", "main", svuvm.UVM_LOW)
    svuvm.uvm_info("set_report_id_verbosity TEST SUCCESS!", svuvm.UVM_DEBUG)
    svuvm.set_report_verbosity_level("", svuvm.UVM_DEBUG)
    svuvm.uvm_info("UVM_DEBUG TEST SUCCESS!", svuvm.UVM_DEBUG)
    svuvm.set_report_verbosity_level("", svuvm.UVM_MEDIUM)

    svuvm.vpi.vpi_printf(f"report_action: {svuvm.get_report_action('', svuvm.UVM_INFO, 'main')}\n")
    svuvm.vpi.vpi_printf(f"verbosity_level: {svuvm.get_report_verbosity_level('', svuvm.UVM_INFO, 'main')}\n")
    svuvm.vpi.vpi_printf(f"max_verbosity_level: {svuvm.get_report_max_verbosity_level('')}\n")

    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST report server \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.print_report_server()
    svuvm.set_quit_count(10)
    svuvm.set_max_quit_count(100)
    svuvm.set_severity_count(svuvm.UVM_INFO, 40)
    svuvm.set_severity_count(svuvm.UVM_WARNING, 30)
    svuvm.set_severity_count(svuvm.UVM_ERROR, 20)
    svuvm.set_severity_count(svuvm.UVM_FATAL, 10)
    svuvm.set_id_count("main", 88)
    svuvm.print_report_server()
    svuvm.get_quit_count()
    
    msg_cnt = svuvm.get_max_quit_count()
    if msg_cnt == 100:
        svuvm.uvm_info("get_max_quit_count success", svuvm.UVM_LOW)
    else:
        svuvm.uvm_error("get_max_quit_count failed")
    msg_cnt = svuvm.get_quit_count()
    if msg_cnt == 10:
        svuvm.uvm_info("get_quit_count success", svuvm.UVM_LOW)
    else:
        svuvm.uvm_error("get_quit_count failed")
    msg_cnt = svuvm.get_severity_count(svuvm.UVM_INFO)
    if msg_cnt == 40:
        svuvm.uvm_info("get_severity_count success", svuvm.UVM_LOW)
    else:
        svuvm.uvm_error("get_severity_count failed")
    msg_cnt = svuvm.get_severity_count(svuvm.UVM_WARNING)
    if msg_cnt == 30:
        svuvm.uvm_info("get_severity_count success", svuvm.UVM_LOW)
    else:
        svuvm.uvm_error("get_severity_count failed")
    msg_cnt = svuvm.get_severity_count(svuvm.UVM_ERROR)
    if msg_cnt == 20:
        svuvm.uvm_info("get_severity_count success", svuvm.UVM_LOW)
    else:
        svuvm.uvm_error("get_severity_count failed")
    msg_cnt = svuvm.get_severity_count(svuvm.UVM_FATAL)
    if msg_cnt == 10:
        svuvm.uvm_info("get_severity_count success", svuvm.UVM_LOW)
    else:
        svuvm.uvm_error("get_severity_count failed")
    msg_cnt = svuvm.get_id_count("main")
    if msg_cnt == 88:
        svuvm.uvm_info("get_id_count success", svuvm.UVM_LOW)
    else:
        svuvm.uvm_error("get_id_count failed")

    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST config_db \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    svuvm.wait_unit(6)
    svuvm.set_config_int("", "", "int_value", 1)
    int_value = svuvm.get_config_int("", "", "int_value")
    svuvm.vpi.vpi_printf("int_value: {}\n", int_value)
    svuvm.set_config_string("", "", "string_value", "hello world")
    string_value = svuvm.get_config_string("", "", "string_value")
    svuvm.vpi.vpi_printf("string_value: {}\n", string_value)

    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST reg opretor \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    data = 0xDEADBEEF
    for i in range(3):
        svuvm.write_reg(str(i), i)
        data = svuvm.read_reg(str(i))
        svuvm.vpi.vpi_printf(f"read data: {data}\n")

    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST vpi io \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    f = svuvm.vpi.vpi_mcd_open("test.log")
    svuvm.vpi.vpi_mcd_printf(f, "hello world\n")
    svuvm.vpi.vpi_mcd_flush(f)
    svuvm.vpi.vpi_printf("vpi_printf success\n")
    svuvm.vpi.vpi_flush()
    svuvm.vpi.vpi_mcd_close(f)

    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST vpi info \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    obj = svuvm.vpi.vpi_handle_by_name("top")
    obj = svuvm.vpi.vpi_handle_by_name("test_wire", obj)
    error = svuvm.vpi.VpiErrorInfo()
    svuvm.vpi.vpi_printf("vpiVpiErrorInfo: {}\n", error.level)
    print(obj)
    info = svuvm.vpi.VpiVlogInfo()
    print(info.argc, info.argv, info.product, info.version)

    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST handle \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    obj = svuvm.vpi.vpi_handle_by_name("top.dpi_vec_test")
    name = svuvm.vpi.vpi_get_str(svuvm.vpi.vpiName, obj)
    type = svuvm.vpi.vpi_get(svuvm.vpi.vpiType, obj)
    size = svuvm.vpi.vpi_get(svuvm.vpi.vpiSize, obj)
    value = svuvm.vpi.VpiValue(svuvm.vpi.vpiIntVal, 0) # value can not read
    # v = svuvm.vpi.vpi_get_value(obj, svuvm.vpi.vpiIntVal)
    print(name, type, size)
    # obj1 = svuvm.vpi.vpi_handle_by_name("top.clk")
    # result = svuvm.vpi.vpi_compare_objects(obj, obj)
    # print(result)


    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST dpi time \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    time_obj = svuvm.get_sim_time("Vtop")
    svuvm.vpi.vpi_printf("time: {}\n", time_obj)
    time_obj = svuvm.get_timeunit("Vtop")
    svuvm.vpi.vpi_printf("timeunit: {}\n", time_obj)
    time_obj = svuvm.get_precision("Vtop")
    svuvm.vpi.vpi_printf("precision: {}\n", time_obj)

    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST vpi callback \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    time_obj = svuvm.vpi.VpiTime(svuvm.vpi.vpiSimTime, 0, 0, 0)
    svuvm.vpi.vpi_get_time(obj, time_obj)

    a = svuvm.vpi.CbData(svuvm.vpi.cbNextSimTime, cb_test, obj, time_obj, svuvm.vpi.VpiValue(), 0, "")
    print(a)
    svuvm.vpi.vpi_register_cb(a)

    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST cocotb \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    # breakpoint()
#     print(cocotb.simulator.get_sim_time())
#     cocotb.log.info("hello cocotb")
#     cocotb.top.dpi_vec_test.value = 0xDEADBEEF
#     cocotb.log.info(hex(cocotb.top.dpi_vec_test.value.to_unsigned()))
#     # cocotb._regression_manager = cocotb.regression.RegressionManager()
#     # cocotb._scheduler_inst = cocotb._scheduler.Scheduler()
#     svuvm.set_finish_on_completion(False)
#     cocotb._init.run_regression(None)
#     cocotb.top.dpi_vec_test.value = 0xBABABABA
#     cocotb.log.info(hex(cocotb.top.dpi_vec_test.value.to_unsigned()))

#     # svuvm.vpi.vpi_control(svuvm.vpi.vpiReset)
#     # svuvm.vpi.vpi_control(svuvm.vpi.vpiFinish)

    svuvm.process_pool_run("base_test.hello")
    svuvm.process_pool_run("base_test.hello1")
    svuvm.process_pool_run("base_test.hello2")
    svuvm.process_pool_run("base_test.hello2")
    svuvm.process_pool_clear()
    svuvm.process_pool_run("base_test.hello2")
def hello():
    print("hello world")

def hello1():
    print("hello world1")

def hello2():
    print("hello world2")

# @cocotb.test()
# async def test_main(dut):
#     cocotb.log.info("hello cocotb")
#     await Timer(100, unit='ns')
#     cocotb.log.info("hello cocotb")
#     svuvm.print_report_server()
#     cnt = svuvm.get_severity_count(svuvm.UVM_ERROR)
#     svuvm.report_summarize()
#     assert cnt == 20, f"UVM_ERROR count is {cnt}, expected 0"
