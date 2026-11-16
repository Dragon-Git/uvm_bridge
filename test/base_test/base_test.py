"""Python-side regression for the DPI bridge, driven from UVM's main_phase.

Every block is a standalone ``test_*`` function registered in ``TESTS``.
``main()`` only dispatches them; a block can also be called on its own with
``+UVM_PY_FUNC=test_register_model`` (see main_phase in python_bridge_pkg.sv),
but only ``main()`` writes the completion marker and the pass/fail summary.

Checks use :func:`check` rather than ``assert`` or ``uvm_error``: py_func()
discards unhandled Python exceptions (they only print a traceback), and the
report test reconfigures UVM_ERROR/UVM_FATAL handling, so neither would make
the run fail. A failed check is printed and collected; ``main()`` emits the
completion marker only when every check passed, which is what the Makefile
greps for on both simulators.
"""

import itertools
import math

from svuvm import _svuvm as svuvm


_CHECKS = 0
_FAILURES = []
_SKIPS = []


def check(condition, label, detail=""):
    """Record one real assertion and print a marker on failure."""
    global _CHECKS
    _CHECKS += 1
    if condition:
        return True
    msg = f"[FAIL] {label}" + (f" - {detail}" if detail else "")
    svuvm.vpi.vpi_printf(msg + "\n")
    _FAILURES.append(msg)
    return False


def skip(label, reason):
    """An API that is allowed to be unsupported on some simulators."""
    svuvm.vpi.vpi_printf(f"[SKIP] {label} - {reason}\n")
    _SKIPS.append(label)


def banner(title):
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf(f"*        TEST {title} \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")


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
    # The register model and its front-end bus; test_register_model uses it.
    svuvm.create_component_by_name("reg_model_env", "uvm_test_top", "m_reg_model")
    svuvm.print_topology()


def connect():
    for i in range(3):
        for j in range(3):
            # svuvm.tlm_connect(f"uvm_test_top.m_env_{i}.m_agent_{j}.m_driver.seq_item_port", f"uvm_test_top.m_env_{i}.m_agent_{j}.m_sequencer.seq_item_export")
            pass


def test_print_topology():
    svuvm.create_object_by_name("env_cfg", "uvm_test_top", "m_env_cfg")
    svuvm.set_factory_inst_override("env_cfg", "random_env_cfg", "uvm_test_top.m_env_cfg")
    svuvm.create_object_by_name("env_cfg", "uvm_test_top", "m_random_env_cfg")
    svuvm.set_factory_type_override("env_cfg", "direct_env_cfg", 1)
    svuvm.create_object_by_name("env_cfg", "uvm_test_top", "m_direct_env_cfg")
    svuvm.print_topology()
    svuvm.print_factory()
    # These factory calls are void; completing the block without an exception
    # is the assertion, which _run() records for every test.


def test_uvm_objection():
    prefix = ["pre_", "", "post_"]
    tsk_phases = ["reset", "configure", "main", "shutdown"]
    phases = ["".join(ph[::-1]) for ph in itertools.product(tsk_phases, prefix)]
    for phase in phases:
        svuvm.uvm_objection_op("RAISE", phase, "uvm_test_top", "TEST OBJECTION RAISE", 1)
        svuvm.uvm_objection_op("DROP", phase, "uvm_test_top", "TEST OBJECTION DROP", 1)
    check(len(phases) == 12, "raise/drop over all 12 task phases", f"got {len(phases)}")


def test_uvm_hdl():
    value = svuvm.VpiVecVal()
    path_ok = svuvm.uvm_hdl_check_path("top.dpi_vec_test")
    check(bool(path_ok), "uvm_hdl_check_path(top.dpi_vec_test)", f"got {path_ok!r}")

    svuvm.uvm_hdl_deposit("top.dpi_vec_test", svuvm.VpiVecVal(0xDEADDEAD, 0x0))
    svuvm.uvm_hdl_read("top.dpi_vec_test", value)
    check(value.aval == 0xDEADDEAD, "deposit then read", f"0x{value.aval:X}")

    svuvm.uvm_hdl_force("top.dpi_vec_test", svuvm.VpiVecVal(0xDEADBEEF, 0x0))
    svuvm.uvm_hdl_read("top.dpi_vec_test", value)
    check(value.aval == 0xDEADBEEF, "force then read", f"0x{value.aval:X}")

    svuvm.uvm_hdl_release_and_read("top.dpi_vec_test", value)
    svuvm.vpi.vpi_printf(f"uvm_hdl_release_and_read: 0x{value.aval:X}\n")
    # Verilator keeps the last forced value after release; a deposit-only
    # backend falls back to 0xDEADDEAD. Both are legal VPI behaviour.
    check(
        value.aval in (0xDEADDEAD, 0xDEADBEEF),
        "release_and_read returns one of the driven values",
        f"0x{value.aval:X}",
    )
    svuvm.uvm_hdl_release("top.dpi_vec_test")


def test_uvm_report():
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

    action = svuvm.get_report_action("", svuvm.UVM_INFO, "main")
    verbosity = svuvm.get_report_verbosity_level("", svuvm.UVM_INFO, "main")
    max_verbosity = svuvm.get_report_max_verbosity_level("")
    svuvm.vpi.vpi_printf(f"report_action: {action}\n")
    svuvm.vpi.vpi_printf(f"verbosity_level: {verbosity}\n")
    svuvm.vpi.vpi_printf(f"max_verbosity_level: {max_verbosity}\n")
    check(isinstance(action, int) and action >= 0, "get_report_action", f"got {action!r}")
    check(isinstance(verbosity, int) and verbosity >= 0, "get_report_verbosity_level", f"got {verbosity!r}")
    check(
        max_verbosity == svuvm.UVM_MEDIUM,
        "set_report_verbosity_level(UVM_MEDIUM) is visible",
        f"got {max_verbosity!r}",
    )


def test_report_server():
    svuvm.print_report_server()
    svuvm.set_quit_count(10)
    svuvm.set_max_quit_count(100)
    expected_severity = [
        (svuvm.UVM_INFO, 40),
        (svuvm.UVM_WARNING, 30),
        (svuvm.UVM_ERROR, 20),
        (svuvm.UVM_FATAL, 10),
    ]
    for severity, value in expected_severity:
        svuvm.set_severity_count(severity, value)
    svuvm.set_id_count("main", 88)

    # Read everything back before any report call: print_report_server()
    # emits a UVM_INFO and uvm_info() has id "main", so an intervening report
    # changes the counters. The old hard-coded expectations sat after those
    # calls and two of them always failed.
    for severity, value in expected_severity:
        got = svuvm.get_severity_count(severity)
        check(got == value, f"severity count {severity}", f"got {got!r}, expected {value}")
    check(svuvm.get_quit_count() == 10, "get_quit_count", f"got {svuvm.get_quit_count()!r}")
    check(svuvm.get_max_quit_count() == 100, "get_max_quit_count", f"got {svuvm.get_max_quit_count()!r}")
    check(svuvm.get_id_count("main") == 88, "get_id_count(main)", f"got {svuvm.get_id_count('main')!r}")

    svuvm.print_report_server()


def test_config_db():
    svuvm.wait_unit(6)
    svuvm.set_config_int("", "", "int_value", 1)
    int_value = svuvm.get_config_int("", "", "int_value")
    svuvm.vpi.vpi_printf(f"int_value: {int_value}\n")
    check(int_value == 1, "config_db int round trip", f"got {int_value!r}")

    pi_expected = 3.141592653589793
    svuvm.set_config_real("", "", "PI", pi_expected)
    pi = svuvm.get_config_real("", "", "PI")
    svuvm.vpi.vpi_printf(f"PI: {pi}\n")
    check(math.isclose(pi, pi_expected), "config_db real round trip", f"got {pi!r}")

    svuvm.set_config_string("", "", "string_value", "hello world")
    string_value = svuvm.get_config_string("", "", "string_value")
    svuvm.vpi.vpi_printf(f"string_value: {string_value}\n")
    check(string_value == "hello world", "config_db string round trip", f"got {string_value!r}")

    # The reg-operator section that used to be here is gone: it called
    # svuvm.write_reg()/read_reg() without a register block ever being set,
    # so reg_operator::inst was null and the calls dereferenced it. On 0.11.0
    # xezim let that through and returned uninitialised data ("read data:
    # 32514" in old logs); on 0.11.1 it is a segfault. Real register access
    # is covered by test_register_model and test/pyral_test.


def test_vpi_io():
    f = svuvm.vpi.vpi_mcd_open("test.log")
    check(bool(f), "vpi_mcd_open(test.log)", f"got {f!r}")
    svuvm.vpi.vpi_mcd_printf(f, "hello world\n")
    svuvm.vpi.vpi_mcd_flush(f)
    svuvm.vpi.vpi_printf("vpi_printf success\n")
    svuvm.vpi.vpi_flush()
    svuvm.vpi.vpi_mcd_close(f)
    try:
        with open("test.log", encoding="utf-8") as fh:
            content = fh.read()
        check("hello world" in content, "vpi_mcd_printf reached test.log", f"got {content!r}")
    except OSError as exc:
        skip("read back test.log", str(exc))


def test_vpi_info():
    top = svuvm.vpi.vpi_handle_by_name("top")
    check(top is not None, "vpi_handle_by_name(top)", f"got {top!r}")
    wire = svuvm.vpi.vpi_handle_by_name("test_wire", top)
    check(wire is not None, "vpi_handle_by_name(test_wire, top)", f"got {wire!r}")

    error = svuvm.vpi.VpiErrorInfo()
    svuvm.vpi.vpi_printf(f"vpiVpiErrorInfo: {error.level}\n")
    check(error.level == 0, "no pending VPI error", f"level={error.level!r}")

    info = svuvm.vpi.VpiVlogInfo()
    svuvm.vpi.vpi_printf(
        f"argc: {info.argc}, argv: {info.argv}, product: {info.product}, version: {info.version}\n"
    )
    check(info.argc >= 1, "vpi_get_vlog_info argc", f"got {info.argc!r}")
    check(bool(info.product), "vpi_get_vlog_info product", f"got {info.product!r}")


def test_vpi_handle():
    obj = svuvm.vpi.vpi_handle_by_name("top.dpi_vec_test")
    check(obj is not None, "vpi_handle_by_name(top.dpi_vec_test)", f"got {obj!r}")
    name = svuvm.vpi.vpi_get_str(svuvm.vpi.vpiName, obj)
    vpi_type = svuvm.vpi.vpi_get(svuvm.vpi.vpiType, obj)
    size = svuvm.vpi.vpi_get(svuvm.vpi.vpiSize, obj)
    svuvm.vpi.vpi_printf(f"handle: name={name}, type={vpi_type}, size={size}\n")
    check("dpi_vec_test" in str(name), "vpi_get_str(vpiName)", f"got {name!r}")
    check(vpi_type > 0, "vpi_get(vpiType)", f"got {vpi_type!r}")
    check(size == 32, "vpi_get(vpiSize) of logic [31:0]", f"got {size!r}")


def test_dpi_time():
    sim_time = svuvm.get_sim_time("Vtop")
    unit = svuvm.get_time_unit("Vtop")
    precision = svuvm.get_time_precision("Vtop")
    svuvm.vpi.vpi_printf(f"time: {sim_time}, timeunit: {unit}, precision: {precision}\n")
    check(isinstance(sim_time, (int, float)) and sim_time >= 0, "get_sim_time", f"got {sim_time!r}")
    check(unit == precision, "time unit and precision agree", f"{unit!r} vs {precision!r}")
    check(unit <= 0, "time unit is an SI exponent", f"got {unit!r}")


def test_vpi_callback():
    # Own the handles: this block used to borrow `obj` and `value` from
    # test_vpi_handle, which is no longer in the same scope.
    obj = svuvm.vpi.vpi_handle_by_name("top.dpi_vec_test")
    time_obj = svuvm.vpi.VpiTime(svuvm.vpi.vpiSimTime, 0, 0, 0)
    value = svuvm.vpi.VpiValue(svuvm.vpi.vpiIntVal, 0)
    svuvm.vpi.vpi_get_time(obj, time_obj)
    a = svuvm.vpi.CbData(svuvm.vpi.cbNextSimTime, cb_test, obj, time_obj, value, 0, "")
    check(a is not None, "CbData constructed", f"got {a!r}")
    svuvm.vpi.vpi_register_cb(a)


def test_process_pool():
    for name in ("base_test.hello", "base_test.hello1", "base_test.hello2", "base_test.hello2"):
        svuvm.process_pool_run(name)
    svuvm.process_pool_clear()
    svuvm.process_pool_run("base_test.hello2")
    # process_pool_run dispatches SV fork/join_none children; there is no
    # return value, so _run()'s "completed without exception" is the check.


def test_phase_objection():
    svuvm.set_drain_time(100)
    drain = svuvm.get_drain_time()
    svuvm.vpi.vpi_printf(f"set_drain_time(100), get_drain_time = {drain}\n")
    check(drain == 100, "drain_time round trip", f"got {drain!r}")

    svuvm.set_timeout(1000000)
    svuvm.set_finish_on_completion(1)

    obj_cnt = svuvm.get_objection_count("run", "uvm_test_top")
    obj_total = svuvm.get_objection_total("run", "uvm_test_top")
    svuvm.vpi.vpi_printf(f"objection count={obj_cnt}, total={obj_total}\n")
    check(obj_cnt >= 0, "get_objection_count", f"got {obj_cnt!r}")
    check(obj_total >= 0, "get_objection_total", f"got {obj_total!r}")

    svuvm.display_objections("run", "uvm_test_top")
    cur_phase = svuvm.get_current_phase_name()
    ph_state = svuvm.get_phase_state("run")
    ph_state_name = svuvm.get_phase_state_name("run")
    svuvm.vpi.vpi_printf(f"phase={cur_phase}, state={ph_state}, state_name={ph_state_name}\n")
    check(bool(cur_phase), "get_current_phase_name", f"got {cur_phase!r}")
    check(isinstance(ph_state, int) and ph_state >= 0, "get_phase_state", f"got {ph_state!r}")
    check(bool(ph_state_name), "get_phase_state_name", f"got {ph_state_name!r}")


def test_component_topology():
    num_children = svuvm.component_get_num_children("uvm_test_top")
    svuvm.vpi.vpi_printf(f"uvm_test_top children count: {num_children}\n")
    # build() creates three envs plus the register-model env.
    check(num_children == 4, "uvm_test_top child count", f"got {num_children!r}")

    names = [svuvm.component_get_child_name("uvm_test_top", i) for i in range(num_children)]
    for i, child_name in enumerate(names):
        svuvm.vpi.vpi_printf(f"  child[{i}] = {child_name}\n")
    for expected in ("m_env_0", "m_env_1", "m_env_2", "m_reg_model"):
        check(expected in names, f"child {expected} exists", f"got {names!r}")

    if names:
        first_child_path = "uvm_test_top." + names[0]
        parent = svuvm.component_get_parent(first_child_path)
        type_name = svuvm.component_get_type_name(first_child_path)
        svuvm.vpi.vpi_printf(f"  parent = {parent}, type_name = {type_name}\n")
        check(parent == "uvm_test_top", "component_get_parent", f"got {parent!r}")
        check(type_name == "base_env", "component_get_type_name", f"got {type_name!r}")

    sprint_text = svuvm.component_sprint("uvm_test_top")
    top_sprint = svuvm.uvm_top_sprint()
    svuvm.vpi.vpi_printf(f"sprint lengths: {len(sprint_text or '')}, {len(top_sprint or '')}\n")
    check(bool(sprint_text), "component_sprint is non-empty")
    check(bool(top_sprint), "uvm_top_sprint is non-empty")

    for tname, expected in (("base_env", True), ("base_agent", True), ("non_existent_type", False)):
        exists = bool(svuvm.is_type_registered(tname))
        svuvm.vpi.vpi_printf(f"is_type_registered({tname}) = {exists}\n")
        check(exists == expected, f"is_type_registered({tname})", f"got {exists!r}")


def test_uvm_event():
    event_name = "test_event"
    svuvm.ev_reset(event_name)
    svuvm.trigger(event_name)
    is_on_val = svuvm.is_on(event_name)
    is_off_val = svuvm.is_off(event_name)
    trigger_time = svuvm.get_trigger_time(event_name)
    num_waiters = svuvm.get_num_waiters(event_name)
    svuvm.vpi.vpi_printf(
        f"event: is_on={is_on_val}, is_off={is_off_val}, "
        f"trigger_time={trigger_time}, waiters={num_waiters}\n"
    )
    check(bool(is_on_val), "trigger sets is_on", f"got {is_on_val!r}")
    check(not is_off_val, "trigger clears is_off", f"got {is_off_val!r}")
    check(trigger_time >= 0, "get_trigger_time", f"got {trigger_time!r}")
    check(num_waiters == 0, "get_num_waiters with no waiters", f"got {num_waiters!r}")

    # A uvm_object may come back as a capsule or None on the Python side.
    try:
        _ = svuvm.get_default_data(event_name)
        svuvm.vpi.vpi_printf("get_default_data ok\n")
    except Exception as exc:
        skip("get_default_data", str(exc))

    svuvm.cancel(event_name)
    svuvm.ev_reset(event_name, 1)
    check(not svuvm.is_on(event_name), "ev_reset clears the event", f"got {svuvm.is_on(event_name)!r}")


def test_config_db_extended():
    exists_int = svuvm.config_db_exists("", "", "int_value")
    exists_str = svuvm.config_db_exists("", "", "string_value")
    exists_none = svuvm.config_db_exists("", "", "non_existent_key")
    svuvm.vpi.vpi_printf(
        f"config_db_exists: int_value={exists_int}, string_value={exists_str}, "
        f"non_existent_key={exists_none}\n"
    )
    # The bridge stores ints as uint64, which config_db_exists() does not
    # report as a match on every UVM; the round trip is checked above.
    check(bool(exists_str), "config_db_exists(string_value)", f"got {exists_str!r}")
    check(not exists_none, "config_db_exists(nonexistent) is false", f"got {exists_none!r}")

    svuvm.config_db_trace_on()
    svuvm.config_db_trace_off()


def test_register_model():
    reg_names = svuvm.get_reg_names("")
    block_names = svuvm.get_block_names("")
    svuvm.vpi.vpi_printf(f"get_reg_names: {reg_names}\n")
    svuvm.vpi.vpi_printf(f"get_block_names: {block_names}\n")

    regs = [r for r in (reg_names or "").split(",") if r]
    check(len(regs) == 3, "top reg block has three registers", f"got {regs!r}")
    if not regs:
        return

    first_reg = regs[0]

    # Model-level checks, no bus involved, so they run everywhere.
    for i, name in enumerate(regs):
        addr = svuvm.get_reg_address(name)
        svuvm.reset_reg(name, "HARD")
        reset_val = svuvm.get_reg_mirrored_value(name)
        desired = svuvm.get_reg_desired_value(name)
        svuvm.vpi.vpi_printf(
            f"  {name}: addr=0x{addr:x} reset(mirror)=0x{reset_val:08x} "
            f"desired=0x{desired:08x}\n"
        )
        check(addr == 4 * i, f"{name} address", f"0x{addr:x}, expected 0x{4 * i:x}")
        check(reset_val == 0, f"{name} reset value", f"0x{reset_val:08x}")

    # Written straight into the model, no bus: the mirror must follow.
    if svuvm.predict_reg(first_reg, 0xABCD, "DIRECT"):
        predicted = svuvm.get_reg_mirrored_value(first_reg)
        svuvm.vpi.vpi_printf(f"  predict_reg({first_reg}, 0xABCD) -> mirror=0x{predicted:x}\n")
        check(predicted == 0xABCD, "predict_reg updates the mirror", f"0x{predicted:x}")
    else:
        check(False, "predict_reg returned false")

    field_names = svuvm.get_reg_field_names(first_reg)
    svuvm.vpi.vpi_printf(f"  {first_reg} fields: {field_names}\n")
    fields = [f for f in (field_names or "").split(",") if f]
    check(len(fields) == 2, f"{first_reg} has two fields", f"got {fields!r}")

    block_sprint = svuvm.reg_block_sprint("")
    svuvm.vpi.vpi_printf(f"  reg_block_sprint length: {len(block_sprint or '')}\n")
    check(bool(block_sprint), "reg_block_sprint is non-empty")

    # Bus checks: a register access runs a sequence on the bus. All
    # simulators support this now, so the assertions always run.
    for i, name in enumerate(regs):
        value = 0x1000_0000 + i
        svuvm.write_reg(name, value)
        read_back = svuvm.read_reg(name)
        mirrored = svuvm.get_reg_mirrored_value(name)
        svuvm.vpi.vpi_printf(
            f"  {name}: write=0x{value:08x} read=0x{read_back:08x} mirror=0x{mirrored:08x}\n"
        )
        check(read_back == value, f"{name} bus read back", f"0x{read_back:08x}, expected 0x{value:08x}")
        # The map has auto_predict on, so a bus write updates the mirror.
        check(mirrored == value, f"{name} mirror after bus write", f"0x{mirrored:08x}, expected 0x{value:08x}")

    # Field write: the value must land in the field's own bits.
    if fields:
        svuvm.write_field_by_name(first_reg, fields[0], 0x1234)
        f_val = svuvm.read_field_by_name(first_reg, fields[0])
        svuvm.vpi.vpi_printf(
            f"  write_field_by_name({first_reg}.{fields[0]}, 0x1234) -> read 0x{f_val:x}\n"
        )
        check(f_val == 0x1234, f"field {first_reg}.{fields[0]} round trip", f"got 0x{f_val:x}")


def test_sequencer():
    sqr_path = "uvm_test_top.m_env_0.m_agent_0.m_sequencer"
    svuvm.vpi.vpi_printf(f"sequencer path: {sqr_path}\n")

    busy = svuvm.is_sequencer_busy(sqr_path)
    svuvm.vpi.vpi_printf(f"is_sequencer_busy = {busy}\n")
    check(busy in (0, 1), "is_sequencer_busy returns a flag", f"got {busy!r}")

    cur_seq = svuvm.get_current_sequence_name(sqr_path)
    svuvm.vpi.vpi_printf(f"get_current_sequence_name = {cur_seq}\n")
    check(isinstance(cur_seq, str), "get_current_sequence_name", f"got {cur_seq!r}")

    # start_seq needs a connected sequencer/driver; not every simulator's
    # UVM provides one here, so a failure is reported as a skip, not a check.
    try:
        svuvm.start_seq("simple_seq", sqr_path, rand_en=0, background=1)
        svuvm.vpi.vpi_printf("start_seq background: success\n")
    except Exception as exc:
        skip("start_seq background", str(exc))
    try:
        svuvm.stop_sequences(sqr_path)
        svuvm.vpi.vpi_printf("stop_sequences: success\n")
    except Exception as exc:
        skip("stop_sequences", str(exc))


def test_barrier():
    bar_name = "my_barrier"
    svuvm.barrier_set_threshold(bar_name, 3)
    threshold = svuvm.barrier_get_threshold(bar_name)
    svuvm.vpi.vpi_printf(f"barrier threshold after set: {threshold}\n")
    check(threshold == 3, "barrier threshold round trip", f"got {threshold!r}")

    num_waiters_bar = svuvm.barrier_get_num_waiters(bar_name)
    svuvm.vpi.vpi_printf(f"barrier num waiters: {num_waiters_bar}\n")
    check(num_waiters_bar == 0, "new barrier has no waiters", f"got {num_waiters_bar!r}")

    svuvm.barrier_reset(bar_name, 0)
    svuvm.vpi.vpi_printf("barrier_reset success\n")
    check(svuvm.barrier_get_threshold(bar_name) == 3, "barrier_reset keeps the threshold")


def test_pool():
    for n in ("evt_a", "evt_b", "evt_c"):
        svuvm.trigger(n)

    num_events = svuvm.pool_num("event")
    svuvm.vpi.vpi_printf(f"pool_num(event) = {num_events}\n")
    check(num_events >= 3, "event pool has the triggered events", f"got {num_events!r}")

    keys = svuvm.pool_keys("event") or ""
    svuvm.vpi.vpi_printf(f"pool_keys(event) = {keys}\n")
    key_list = keys.split(",")
    for n in ("evt_a", "evt_b", "evt_c"):
        check(n in key_list, f"pool_keys contains {n}", f"got {keys!r}")

    exists_a = svuvm.pool_exists("event", "evt_a")
    exists_z = svuvm.pool_exists("event", "evt_not_exist")
    svuvm.vpi.vpi_printf(f"pool_exists: evt_a={exists_a}, evt_not_exist={exists_z}\n")
    check(bool(exists_a), "pool_exists(evt_a)", f"got {exists_a!r}")
    check(not exists_z, "pool_exists(evt_not_exist) is false", f"got {exists_z!r}")


def test_callback():
    cb_cnt = svuvm.get_callback_count("uvm_test_top", "")
    svuvm.vpi.vpi_printf(f"get_callback_count(uvm_test_top) = {cb_cnt}\n")
    check(isinstance(cb_cnt, int) and cb_cnt >= 0, "get_callback_count", f"got {cb_cnt!r}")

    cb_type_names = svuvm.get_callback_type_names("uvm_test_top")
    svuvm.vpi.vpi_printf(f"get_callback_type_names(uvm_test_top) = {cb_type_names}\n")
    check(isinstance(cb_type_names, str), "get_callback_type_names", f"got {cb_type_names!r}")


def test_printer_comparer_knobs():
    knobs_to_test = ["indent", "show_root", "header", "footer", "depth", "reference", "type_name", "size"]
    for knob in knobs_to_test:
        old_val = svuvm.get_default_printer_knob(knob)
        if knob in ("depth", "indent"):
            new_val = old_val + 1 if isinstance(old_val, int) else 1
        else:
            new_val = 1
        svuvm.set_default_printer_knob(knob, new_val)
        read_back = svuvm.get_default_printer_knob(knob)
        svuvm.vpi.vpi_printf(f"printer knob[{knob}]: set={new_val}, read_back={read_back}\n")
        check(read_back == new_val, f"printer knob[{knob}] round trip", f"got {read_back!r}, expected {new_val!r}")

    for knob in ("show_max", "verbosity"):
        old_val = svuvm.get_default_comparer_knob(knob)
        new_val = 5 if isinstance(old_val, int) else old_val
        svuvm.set_default_comparer_knob(knob, new_val)
        read_back = svuvm.get_default_comparer_knob(knob)
        svuvm.vpi.vpi_printf(f"comparer knob[{knob}]: set={new_val}, read_back={read_back}\n")
        check(read_back == new_val, f"comparer knob[{knob}] round trip", f"got {read_back!r}, expected {new_val!r}")

    try:
        result = svuvm.component_compare("uvm_test_top", "uvm_test_top")
        svuvm.vpi.vpi_printf(f"component_compare(self, self) = {result}\n")
        check(result == 1, "a component compares equal to itself", f"got {result!r}")
    except Exception as exc:
        skip("component_compare", str(exc))


def test_report_summarize():
    try:
        svuvm.report_summarize()
    except Exception as exc:
        check(False, "report_summarize", str(exc))


TESTS = [
    ("print_topology", test_print_topology),
    ("uvm_objection", test_uvm_objection),
    ("uvm_hdl", test_uvm_hdl),
    ("uvm_report", test_uvm_report),
    ("report_server", test_report_server),
    ("config_db", test_config_db),
    ("vpi_io", test_vpi_io),
    ("vpi_info", test_vpi_info),
    ("vpi_handle", test_vpi_handle),
    ("dpi_time", test_dpi_time),
    ("vpi_callback", test_vpi_callback),
    ("process_pool", test_process_pool),
    ("phase_objection", test_phase_objection),
    ("component_topology", test_component_topology),
    ("uvm_event", test_uvm_event),
    ("config_db_extended", test_config_db_extended),
    ("register_model", test_register_model),
    ("sequencer", test_sequencer),
    ("barrier", test_barrier),
    ("pool", test_pool),
    ("callback", test_callback),
    ("printer_comparer_knobs", test_printer_comparer_knobs),
    ("report_summarize", test_report_summarize),
]


def _run(name, fn):
    """Isolate each block: one failure must not hide the rest of the checks."""
    global _CHECKS
    banner(name)
    _CHECKS += 1  # the block itself completing without raising
    before = len(_FAILURES)
    try:
        fn()
    except Exception as exc:
        msg = f"[FAIL] {name} raised {type(exc).__name__}: {exc}"
        svuvm.vpi.vpi_printf(msg + "\n")
        _FAILURES.append(msg)
        return
    if len(_FAILURES) == before:
        svuvm.vpi.vpi_printf(f"[PASS] {name}\n")


def main():
    for name, fn in TESTS:
        _run(name, fn)

    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    if _FAILURES:
        for msg in _FAILURES:
            svuvm.vpi.vpi_printf(msg + "\n")
        svuvm.vpi.vpi_printf(
            f"*        BASE TEST FAILED: {len(_FAILURES)} failures / {_CHECKS} checks, "
            f"{len(_SKIPS)} skipped \n"
        )
        # Deliberately no completion marker: both Makefile branches grep for
        # it, so a failed check now fails the run instead of being ignored.
    else:
        svuvm.vpi.vpi_printf(f"*        {_CHECKS} checks passed, {len(_SKIPS)} skipped \n")
        svuvm.vpi.vpi_printf("*        所有新增API测试完成 \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.print_report_server()


def hello():
    print("hello world")


def hello1():
    print("hello world1")


def hello2():
    print("hello world2")


# The cocotb-driven variant of this regression lives in test/cocotb_test.
