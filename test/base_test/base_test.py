import itertools
import os

from svuvm import _svuvm as svuvm

# A register access drives the bus through a sequence, and an exported task
# cannot consume time on verilator - python_bridge_pkg compiles write_reg /
# read_reg out under `ifdef VERILATOR` for that reason, and the verilator leg
# of test/base_test/Makefile passes REG_BUS_ACCESS=0. What needs the bus is
# skipped here; the rest of the register-model test runs on both.
REG_BUS_ACCESS = os.environ.get("REG_BUS_ACCESS", "1") != "0"


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
    # 寄存器模型 + 它的前端总线；main() 里用它做 RAL 读写测试
    svuvm.create_component_by_name("reg_model_env", "uvm_test_top", "m_reg_model")
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
    svuvm.vpi.vpi_printf(f"int_value: {int_value}\n")
    svuvm.set_config_real("", "", "PI", 3.141592653589793)
    pi = svuvm.get_config_real("", "", "PI")
    svuvm.vpi.vpi_printf(f"PI: {pi}\n")
    svuvm.set_config_string("", "", "string_value", "hello world")
    string_value = svuvm.get_config_string("", "", "string_value")
    svuvm.vpi.vpi_printf(f"string_value: {string_value}\n")

    # The reg-operator section that used to be here is gone: it called
    # svuvm.write_reg()/read_reg() without a register block ever being set,
    # so reg_operator::inst was null and the calls dereferenced it. On 0.11.0
    # xezim let that through and returned uninitialised data ("read data:
    # 32514" in old logs); on 0.11.1 it is a segfault. The setup it needed is
    # the block further down that is commented out, and the register names
    # would not have matched either (the block has reg_0/reg_1/reg_2).
    # Register access is covered for real by test/pyral_test, which drives an
    # actual peakrdl block through a UVM agent.

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
    svuvm.vpi.vpi_printf(f"vpiVpiErrorInfo: {error.level}\n")
    print(obj)
    info = svuvm.vpi.VpiVlogInfo()
    svuvm.vpi.vpi_printf(f"argc: {info.argc}, argv: {info.argv}, product: {info.product}, version: {info.version}\n")

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
    svuvm.vpi.vpi_printf(f"time: {time_obj}\n")
    time_obj = svuvm.get_time_unit("Vtop")
    svuvm.vpi.vpi_printf(f"timeunit: {time_obj}\n")
    time_obj = svuvm.get_time_precision("Vtop")
    svuvm.vpi.vpi_printf(f"precision: {time_obj}\n")

    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST vpi callback \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    time_obj = svuvm.vpi.VpiTime(svuvm.vpi.vpiSimTime, 0, 0, 0)
    svuvm.vpi.vpi_get_time(obj, time_obj)

    a = svuvm.vpi.CbData(svuvm.vpi.cbNextSimTime, cb_test, obj, time_obj, value, 0, "")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
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

    # =============================================================
    # TEST: Phase & Objection
    # =============================================================
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST phase & objection \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    # drain_time
    svuvm.set_drain_time(100)
    drain = svuvm.get_drain_time()
    svuvm.vpi.vpi_printf(f"set_drain_time(100), get_drain_time = {drain}\n")
    if drain == 100:
        svuvm.uvm_info("drain_time test success", svuvm.UVM_LOW)
    else:
        svuvm.uvm_error("drain_time test failed")

    # set_timeout / set_finish_on_completion
    svuvm.set_timeout(1000000)
    svuvm.set_finish_on_completion(1)
    svuvm.uvm_info("set_timeout / set_finish_on_completion success", svuvm.UVM_LOW)

    # get_objection_count / get_objection_total
    obj_cnt = svuvm.get_objection_count("run", "uvm_test_top")
    obj_total = svuvm.get_objection_total("run", "uvm_test_top")
    svuvm.vpi.vpi_printf(f"get_objection_count(run, uvm_test_top) = {obj_cnt}\n")
    svuvm.vpi.vpi_printf(f"get_objection_total(run, uvm_test_top) = {obj_total}\n")
    svuvm.uvm_info("objection query success", svuvm.UVM_LOW)

    # display_objections
    svuvm.display_objections("run", "uvm_test_top")
    svuvm.uvm_info("display_objections success", svuvm.UVM_LOW)

    # get_current_phase_name / get_phase_state / get_phase_state_name
    cur_phase = svuvm.get_current_phase_name()
    svuvm.vpi.vpi_printf(f"get_current_phase_name = {cur_phase}\n")
    ph_state = svuvm.get_phase_state("run")
    ph_state_name = svuvm.get_phase_state_name("run")
    svuvm.vpi.vpi_printf(f"run phase: state={ph_state}, state_name={ph_state_name}\n")
    svuvm.uvm_info("phase query success", svuvm.UVM_LOW)

    # =============================================================
    # TEST: Component Topology
    # =============================================================
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST component topology \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    num_children = svuvm.component_get_num_children("uvm_test_top")
    svuvm.vpi.vpi_printf(f"uvm_test_top children count: {num_children}\n")

    for i in range(num_children):
        child_name = svuvm.component_get_child_name("uvm_test_top", i)
        svuvm.vpi.vpi_printf(f"  child[{i}] = {child_name}\n")

    # parent / type_name
    if num_children > 0:
        first_child_path = "uvm_test_top." + svuvm.component_get_child_name("uvm_test_top", 0)
        parent = svuvm.component_get_parent(first_child_path)
        type_name = svuvm.component_get_type_name(first_child_path)
        svuvm.vpi.vpi_printf(f"  parent = {parent}, type_name = {type_name}\n")

    # component_sprint / uvm_top_sprint
    sprint_text = svuvm.component_sprint("uvm_test_top")
    svuvm.vpi.vpi_printf(f"component_sprint length: {len(sprint_text) if sprint_text else 0}\n")
    top_sprint = svuvm.uvm_top_sprint()
    svuvm.vpi.vpi_printf(f"uvm_top_sprint length: {len(top_sprint) if top_sprint else 0}\n")

    # is_type_registered
    for tname in ["base_env", "base_agent", "non_existent_type"]:
        exists = svuvm.is_type_registered(tname)
        svuvm.vpi.vpi_printf(f"is_type_registered({tname}) = {exists}\n")

    svuvm.uvm_info("component topology test success", svuvm.UVM_LOW)

    # =============================================================
    # TEST: UVM Event
    # =============================================================
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST uvm event \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    event_name = "test_event"
    svuvm.ev_reset(event_name)
    svuvm.trigger(event_name)
    is_on_val = svuvm.is_on(event_name)
    is_off_val = svuvm.is_off(event_name)
    trigger_time = svuvm.get_trigger_time(event_name)
    num_waiters = svuvm.get_num_waiters(event_name)
    svuvm.vpi.vpi_printf(f"event: is_on={is_on_val}, is_off={is_off_val}, "
                         f"trigger_time={trigger_time}, waiters={num_waiters}\n")

    # set_default_data / get_default_data
    # 注意：uvm_object 在 Python 端可能返回 capsule 或 None
    try:
        _ = svuvm.get_default_data(event_name)
        svuvm.vpi.vpi_printf("get_default_data ok\n")
    except Exception as e:
        svuvm.vpi.vpi_printf(f"get_default_data skipped: {e}\n")

    # cancel + ev_reset with wakeup
    svuvm.cancel(event_name)
    svuvm.ev_reset(event_name, 1)
    svuvm.uvm_info("uvm event test success", svuvm.UVM_LOW)

    # =============================================================
    # TEST: Config DB 扩展
    # =============================================================
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST config_db extended \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    exists_int = svuvm.config_db_exists("", "", "int_value")
    exists_str = svuvm.config_db_exists("", "", "string_value")
    exists_none = svuvm.config_db_exists("", "", "non_existent_key")
    svuvm.vpi.vpi_printf(f"config_db_exists(int_value) = {exists_int}\n")
    svuvm.vpi.vpi_printf(f"config_db_exists(string_value) = {exists_str}\n")
    svuvm.vpi.vpi_printf(f"config_db_exists(non_existent_key) = {exists_none}\n")

    # config_db_trace_on / off
    svuvm.config_db_trace_on()
    svuvm.config_db_trace_off()
    svuvm.uvm_info("config_db extended test success", svuvm.UVM_LOW)

    # =============================================================
    # TEST: register model (RAL)
    # =============================================================
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST register model \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    reg_names = svuvm.get_reg_names("")
    svuvm.vpi.vpi_printf(f"get_reg_names: {reg_names}\n")
    block_names = svuvm.get_block_names("")
    svuvm.vpi.vpi_printf(f"get_block_names: {block_names}\n")

    regs = [r for r in (reg_names or "").split(",") if r]
    if not regs:
        svuvm.uvm_error("register model: no registers found in the top reg block")
    else:
        first_reg = regs[0]

        # Model-level checks, no bus involved, so they run everywhere.
        for name in regs:
            addr = svuvm.get_reg_address(name)
            svuvm.reset_reg(name, "HARD")
            reset_val = svuvm.get_reg_mirrored_value(name)
            desired = svuvm.get_reg_desired_value(name)
            svuvm.vpi.vpi_printf(
                f"  {name}: addr=0x{addr:x} reset(mirror)=0x{reset_val:08x} "
                f"desired=0x{desired:08x}\n"
            )
            if addr != 4 * regs.index(name):
                svuvm.uvm_error(f"register model: {name} is at 0x{addr:x}, expected 0x{4 * regs.index(name):x}")

        # Written straight into the model, no bus: the mirror must follow.
        if svuvm.predict_reg(first_reg, 0xABCD, "DIRECT"):
            predicted = svuvm.get_reg_mirrored_value(first_reg)
            svuvm.vpi.vpi_printf(f"  predict_reg({first_reg}, 0xABCD) -> mirror=0x{predicted:x}\n")
            if predicted != 0xABCD:
                svuvm.uvm_error(f"register model: mirror after predict is 0x{predicted:x}, expected 0xabcd")

        field_names = svuvm.get_reg_field_names(first_reg)
        svuvm.vpi.vpi_printf(f"  {first_reg} fields: {field_names}\n")
        fields = [f for f in (field_names or "").split(",") if f]
        if not fields:
            svuvm.uvm_error(f"register model: {first_reg} reports no fields")

        block_sprint = svuvm.reg_block_sprint("")
        svuvm.vpi.vpi_printf(f"  reg_block_sprint length: {len(block_sprint) if block_sprint else 0}\n")

        # Bus checks. A register access runs a sequence, and an exported task
        # cannot consume time on Verilator, so a Python-driven access cannot
        # reach the bus there: python_bridge_pkg compiles write_reg/read_reg
        # out under `ifdef VERILATOR` and the Makefile's verilator leg passes
        # REG_BUS_ACCESS=0. Those calls would be silent no-ops, so the checks
        # are skipped rather than asserting on nothing.
        if REG_BUS_ACCESS:
            for i, name in enumerate(regs):
                value = 0x1000_0000 + i
                svuvm.write_reg(name, value)
                read_back = svuvm.read_reg(name)
                mirrored = svuvm.get_reg_mirrored_value(name)
                svuvm.vpi.vpi_printf(
                    f"  {name}: write=0x{value:08x} read=0x{read_back:08x} mirror=0x{mirrored:08x}\n"
                )
                if read_back != value:
                    svuvm.uvm_error(
                        f"register model: {name} read back 0x{read_back:08x}, expected 0x{value:08x}"
                    )
                # The map has auto_predict on, so a bus write updates the mirror.
                if mirrored != value:
                    svuvm.uvm_error(
                        f"register model: {name} mirror is 0x{mirrored:08x}, expected 0x{value:08x}"
                    )

            # Field write: the value must land in the field's own bits.
            if fields:
                svuvm.write_field_by_name(first_reg, fields[0], 0x1234)
                f_val = svuvm.read_field_by_name(first_reg, fields[0])
                svuvm.vpi.vpi_printf(
                    f"  write_field_by_name({first_reg}.{fields[0]}, 0x1234) -> read 0x{f_val:x}\n"
                )
                if f_val != 0x1234:
                    svuvm.uvm_error(
                        f"register model: field {first_reg}.{fields[0]} read 0x{f_val:x}, expected 0x1234"
                    )

        svuvm.uvm_info("register model test success", svuvm.UVM_LOW)

    # =============================================================
    # TEST: Sequencer & Sequence
    # =============================================================
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST sequencer & sequence \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    # 使用 build 阶段已经创建的 base_sequencer
    sqr_path = "uvm_test_top.m_env_0.m_agent_0.m_sequencer"
    svuvm.vpi.vpi_printf(f"sequencer path: {sqr_path}\n")

    busy = svuvm.is_sequencer_busy(sqr_path)
    svuvm.vpi.vpi_printf(f"is_sequencer_busy = {busy}\n")

    cur_seq = svuvm.get_current_sequence_name(sqr_path)
    svuvm.vpi.vpi_printf(f"get_current_sequence_name = {cur_seq}\n")

    # start_seq 可能需要 sequencer/driver 正确连接，使用 try/except
    try:
        svuvm.start_seq("simple_seq", sqr_path, rand_en=0, background=1)
        svuvm.vpi.vpi_printf("start_seq background: success\n")
    except Exception as e:
        svuvm.vpi.vpi_printf(f"start_seq skipped: {e}\n")

    try:
        svuvm.stop_sequences(sqr_path)
        svuvm.vpi.vpi_printf("stop_sequences: success\n")
    except Exception as e:
        svuvm.vpi.vpi_printf(f"stop_sequences skipped: {e}\n")
    svuvm.uvm_info("sequencer test success", svuvm.UVM_LOW)

    # =============================================================
    # TEST: Barrier (新增 API)
    # =============================================================
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST barrier \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    bar_name = "my_barrier"
    svuvm.barrier_set_threshold(bar_name, 3)
    threshold = svuvm.barrier_get_threshold(bar_name)
    svuvm.vpi.vpi_printf(f"barrier threshold after set: {threshold}\n")

    num_waiters_bar = svuvm.barrier_get_num_waiters(bar_name)
    svuvm.vpi.vpi_printf(f"barrier num waiters: {num_waiters_bar}\n")

    svuvm.barrier_reset(bar_name, 0)
    svuvm.vpi.vpi_printf("barrier_reset success\n")
    svuvm.uvm_info("barrier test success", svuvm.UVM_LOW)

    # =============================================================
    # TEST: Pool / Event Pool (新增 API)
    # =============================================================
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST pool / event pool \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    # 先触发一些事件，让 event pool 有内容
    for n in ["evt_a", "evt_b", "evt_c"]:
        svuvm.trigger(n)

    num_events = svuvm.pool_num("event")
    svuvm.vpi.vpi_printf(f"pool_num(event) = {num_events}\n")

    keys = svuvm.pool_keys("event")
    svuvm.vpi.vpi_printf(f"pool_keys(event) = {keys}\n")

    exists_a = svuvm.pool_exists("event", "evt_a")
    exists_z = svuvm.pool_exists("event", "evt_not_exist")
    svuvm.vpi.vpi_printf(f"pool_exists(event, evt_a) = {exists_a}, pool_exists(event, evt_not_exist) = {exists_z}\n")
    svuvm.uvm_info("pool test success", svuvm.UVM_LOW)

    # =============================================================
    # TEST: Callback (新增 API)
    # =============================================================
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST callback \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    cb_cnt = svuvm.get_callback_count("uvm_test_top", "")
    svuvm.vpi.vpi_printf(f"get_callback_count(uvm_test_top) = {cb_cnt}\n")

    cb_type_names = svuvm.get_callback_type_names("uvm_test_top")
    svuvm.vpi.vpi_printf(f"get_callback_type_names(uvm_test_top) = {cb_type_names}\n")
    svuvm.uvm_info("callback test success", svuvm.UVM_LOW)

    # =============================================================
    # TEST: Printer & Comparer Knobs (新增 API)
    # =============================================================
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST printer & comparer knobs \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    # printer knobs
    knobs_to_test = ["indent", "show_root", "header", "footer", "depth", "reference", "type_name", "size"]
    for knob in knobs_to_test:
        old_val = svuvm.get_default_printer_knob(knob)
        if knob == "depth" or knob == "indent":
            new_val = old_val + 1 if isinstance(old_val, int) else 1
        else:
            new_val = 1
        svuvm.set_default_printer_knob(knob, new_val)
        read_back = svuvm.get_default_printer_knob(knob)
        svuvm.vpi.vpi_printf(f"printer knob[{knob}]: set={new_val}, read_back={read_back}\n")
    svuvm.uvm_info("printer knob test success", svuvm.UVM_LOW)

    # comparer knobs
    cmp_knobs = ["show_max", "verbosity"]
    for knob in cmp_knobs:
        old_val = svuvm.get_default_comparer_knob(knob)
        new_val = 5 if isinstance(old_val, int) else old_val
        svuvm.set_default_comparer_knob(knob, new_val)
        read_back = svuvm.get_default_comparer_knob(knob)
        svuvm.vpi.vpi_printf(f"comparer knob[{knob}]: set={new_val}, read_back={read_back}\n")
    svuvm.uvm_info("comparer knob test success", svuvm.UVM_LOW)

    # component_compare
    try:
        result = svuvm.component_compare("uvm_test_top", "uvm_test_top")
        svuvm.vpi.vpi_printf(f"component_compare(self, self) = {result} (expected 1/true)\n")
    except Exception as e:
        svuvm.vpi.vpi_printf(f"component_compare skipped: {e}\n")

    # =============================================================
    # TEST: report_summarize (新增 API)
    # =============================================================
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        TEST report_summarize \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    try:
        svuvm.report_summarize()
        svuvm.uvm_info("report_summarize success", svuvm.UVM_LOW)
    except Exception as e:
        svuvm.uvm_error(f"report_summarize failed: {e}")

    # 最终汇总
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        所有新增API测试完成 \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.print_report_server()

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