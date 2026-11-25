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

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bt_common
import bt_uvm
import bt_vpi_behavior
import bt_vpi_value

from svuvm import _svuvm as svuvm
from bt_common import (MIN_CHECKS, _product, _SKIPPED, banner, build, check,
                       connect, fail, finalize, hello, hello1, hello2, run_case,
                       skip, try_api, try_api_ex, write_results)
from bt_uvm import (
    test_print_topology,
    test_uvm_objection,
    test_uvm_hdl,
    test_uvm_report,
    test_report_server,
    test_config_db,
    test_process_pool,
    test_phase_objection,
    test_component_topology,
    test_uvm_event,
    test_config_db_extended,
    test_register_model,
    test_sequencer,
    test_barrier,
    test_pool,
    test_callback,
    test_printer_comparer_knobs,
    test_report_summarize,
)
from bt_vpi_value import (
    test_vpi_io,
    test_vpi_info,
    test_vpi_handle,
    test_vpi_value_ctors,
    test_vpi_scalar_structs,
    test_vpi_array_value_ctors,
    test_vpi_get_value_formats,
    test_vpi_put_value_flags,
    test_vpi_error_info_fields,
    test_vpi_get_properties,
    test_vpi_get_value,
    test_vpi_put_value,
    test_vpi_get64_compare,
    test_vpi_hierarchy,
    test_vpi_handle_management,
    test_vpi_property_matrix,
    test_vpi_value_array_control,
    test_vpi_handle_by_multi_index,
    test_vpi_mcd_multichannel,
)
from bt_vpi_behavior import (
    test_dpi_time,
    test_vpi_callback,
    test_vpi_delays,
    test_vpi_cb_info_and_systf,
    test_vpi_control_operations,
    test_vpi_get_time_formats,
    test_vpi_callback_reasons,
    test_vpi_data_control,
    test_vpi_callbackinfo_lifecycle,
    test_vpi_userdata_keepalive,
    test_vpi_delay_variants,
    test_vpi_assertion_control,
    test_vpi_coverage_get,
    test_vpi_coverage_control,
    test_vpi_assertion_callback_reasons,
    test_vpi_assert_cover_object_types,
)

__all__ = [
    "MIN_CHECKS",
    "TESTS",
    "_SKIPPED",
    "_product",
    "banner",
    "build",
    "check",
    "connect",
    "fail",
    "finalize",
    "hello",
    "hello1",
    "hello2",
    "main",
    "run_case",
    "skip",
    "svuvm",
    "test_barrier",
    "test_callback",
    "test_component_topology",
    "test_config_db",
    "test_config_db_extended",
    "test_dpi_time",
    "test_phase_objection",
    "test_pool",
    "test_print_topology",
    "test_printer_comparer_knobs",
    "test_process_pool",
    "test_register_model",
    "test_report_server",
    "test_report_summarize",
    "test_sequencer",
    "test_uvm_event",
    "test_uvm_hdl",
    "test_uvm_objection",
    "test_uvm_report",
    "test_vpi_array_value_ctors",
    "test_vpi_assert_cover_object_types",
    "test_vpi_assertion_callback_reasons",
    "test_vpi_assertion_control",
    "test_vpi_callback",
    "test_vpi_callback_reasons",
    "test_vpi_callbackinfo_lifecycle",
    "test_vpi_cb_info_and_systf",
    "test_vpi_control_operations",
    "test_vpi_coverage_control",
    "test_vpi_coverage_get",
    "test_vpi_data_control",
    "test_vpi_delay_variants",
    "test_vpi_delays",
    "test_vpi_error_info_fields",
    "test_vpi_get64_compare",
    "test_vpi_get_properties",
    "test_vpi_get_time_formats",
    "test_vpi_get_value",
    "test_vpi_get_value_formats",
    "test_vpi_handle",
    "test_vpi_handle_by_multi_index",
    "test_vpi_handle_management",
    "test_vpi_hierarchy",
    "test_vpi_info",
    "test_vpi_io",
    "test_vpi_mcd_multichannel",
    "test_vpi_property_matrix",
    "test_vpi_put_value",
    "test_vpi_put_value_flags",
    "test_vpi_scalar_structs",
    "test_vpi_userdata_keepalive",
    "test_vpi_value_array_control",
    "test_vpi_value_ctors",
    "try_api",
    "try_api_ex",
    "write_results",
]

TESTS = [
    ("print_topology", bt_uvm.test_print_topology),
    ("uvm_objection", bt_uvm.test_uvm_objection),
    ("uvm_hdl", bt_uvm.test_uvm_hdl),
    ("uvm_report", bt_uvm.test_uvm_report),
    ("report_server", bt_uvm.test_report_server),
    ("config_db", bt_uvm.test_config_db),
    ("vpi_io", bt_vpi_value.test_vpi_io),
    ("vpi_info", bt_vpi_value.test_vpi_info),
    ("vpi_handle", bt_vpi_value.test_vpi_handle),
    ("dpi_time", bt_vpi_behavior.test_dpi_time),
    ("vpi_callback", bt_vpi_behavior.test_vpi_callback),
    ("vpi_value_ctors", bt_vpi_value.test_vpi_value_ctors),
    ("vpi_scalar_structs", bt_vpi_value.test_vpi_scalar_structs),
    ("vpi_array_value_ctors", bt_vpi_value.test_vpi_array_value_ctors),
    ("vpi_get_value_formats", bt_vpi_value.test_vpi_get_value_formats),
    ("vpi_put_value_flags", bt_vpi_value.test_vpi_put_value_flags),
    ("vpi_error_info_fields", bt_vpi_value.test_vpi_error_info_fields),
    ("vpi_get_properties", bt_vpi_value.test_vpi_get_properties),
    ("vpi_get_value", bt_vpi_value.test_vpi_get_value),
    ("vpi_put_value", bt_vpi_value.test_vpi_put_value),
    ("vpi_get64_compare", bt_vpi_value.test_vpi_get64_compare),
    ("vpi_hierarchy", bt_vpi_value.test_vpi_hierarchy),
    ("vpi_handle_management", bt_vpi_value.test_vpi_handle_management),
    ("vpi_delays", bt_vpi_behavior.test_vpi_delays),
    ("vpi_cb_info_and_systf", bt_vpi_behavior.test_vpi_cb_info_and_systf),
    ("vpi_control_operations", bt_vpi_behavior.test_vpi_control_operations),
    ("vpi_get_time_formats", bt_vpi_behavior.test_vpi_get_time_formats),
    ("vpi_callback_reasons", bt_vpi_behavior.test_vpi_callback_reasons),
    ("vpi_data_control", bt_vpi_behavior.test_vpi_data_control),
    ("vpi_callbackinfo_lifecycle", bt_vpi_behavior.test_vpi_callbackinfo_lifecycle),
    ("vpi_userdata_keepalive", bt_vpi_behavior.test_vpi_userdata_keepalive),
    ("vpi_mcd_multichannel", bt_vpi_value.test_vpi_mcd_multichannel),
    ("vpi_property_matrix", bt_vpi_value.test_vpi_property_matrix),
    ("vpi_value_array_control", bt_vpi_value.test_vpi_value_array_control),
    ("vpi_handle_by_multi_index", bt_vpi_value.test_vpi_handle_by_multi_index),
    ("vpi_delay_variants", bt_vpi_behavior.test_vpi_delay_variants),
    ("vpi_assertion_control", bt_vpi_behavior.test_vpi_assertion_control),
    ("vpi_coverage_get", bt_vpi_behavior.test_vpi_coverage_get),
    ("vpi_coverage_control", bt_vpi_behavior.test_vpi_coverage_control),
    ("vpi_assertion_callback_reasons", bt_vpi_behavior.test_vpi_assertion_callback_reasons),
    ("vpi_assert_cover_object_types", bt_vpi_behavior.test_vpi_assert_cover_object_types),
    ("process_pool", bt_uvm.test_process_pool),
    ("phase_objection", bt_uvm.test_phase_objection),
    ("component_topology", bt_uvm.test_component_topology),
    ("uvm_event", bt_uvm.test_uvm_event),
    ("config_db_extended", bt_uvm.test_config_db_extended),
    ("register_model", bt_uvm.test_register_model),
    ("sequencer", bt_uvm.test_sequencer),
    ("barrier", bt_uvm.test_barrier),
    ("pool", bt_uvm.test_pool),
    ("callback", bt_uvm.test_callback),
    ("printer_comparer_knobs", bt_uvm.test_printer_comparer_knobs),
    ("report_summarize", bt_uvm.test_report_summarize),
]


def main():
    for name, fn in TESTS:
        bt_common.run_case(name, fn)
    bt_common.finalize()


# The cocotb-driven variant of this regression lives in test/cocotb_test.
