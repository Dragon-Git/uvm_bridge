import cocotb
from cocotb.triggers import Timer

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

    svuvm.uvm_info("UVM_INFO TEST SUCCESS!", svuvm.UVM_MEDIUM)
    svuvm.uvm_warning("UVM_WARNING TEST SUCCESS!")


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
    time_obj = svuvm.get_time_unit("Vtop")
    svuvm.vpi.vpi_printf("timeunit: {}\n", time_obj)
    time_obj = svuvm.get_time_precision("Vtop")
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
    print(cocotb.simulator.get_sim_time())
    cocotb.log.info("hello cocotb")
    cocotb.top.dpi_vec_test.value = 0xDEADBEEF
    cocotb.log.info(hex(cocotb.top.dpi_vec_test.value.to_unsigned()))
    # cocotb._regression_manager = cocotb.regression.RegressionManager()
    # cocotb._scheduler_inst = cocotb._scheduler.Scheduler()
    svuvm.set_finish_on_completion(False)
    cocotb._init.run_regression(None)
    cocotb.top.dpi_vec_test.value = 0xBABABABA
    cocotb.log.info(hex(cocotb.top.dpi_vec_test.value.to_unsigned()))

    # svuvm.vpi.vpi_control(svuvm.vpi.vpiReset)
    # svuvm.vpi.vpi_control(svuvm.vpi.vpiFinish)

@cocotb.test()
async def test_main(dut):
    cocotb.log.info("hello cocotb")
    await Timer(100, unit='ns')
    cocotb.log.info("hello cocotb")
    svuvm.print_report_server()
    cnt = svuvm.get_severity_count(svuvm.UVM_ERROR)
    svuvm.report_summarize()
    assert cnt == 0, f"UVM_ERROR count is {cnt}, expected 0"
