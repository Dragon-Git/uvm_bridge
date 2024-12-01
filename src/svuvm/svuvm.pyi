from typing import List, Any
from . import vpi  # noqa: F401
class VpiVecVal:
    """
    Represents a VPI (Verilog Programming Interface) vector value.
    
    Attributes:
        aval (int): The first part of the vector value.
        bval (int): The second part of the vector value.
        
    Methods:
        __init__(self, aval: int, bval: int) -> None:
            Initializes the VpiVecVal with given integer values.
    """

def uvm_report(severity: str, id: str, message: str, verbosity: str, file: str, linenum: int) -> None:
    """
    Reports a message in the UVM framework according to the specified severity, ID, and verbosity level.
    """

def int_str_max(*args: str) -> int:
    """
    Returns the maximum integer value represented as a string among the provided arguments.
    """

def uvm_re_match(re: str, s: str) -> bool:
    """
    Determines if the provided string `s` matches the regular expression `re`.
    """

def uvm_glob_to_re(pattern: str) -> str:
    """
    Converts a glob pattern into a regular expression string.
    """

def uvm_hdl_check_path(path: str) -> bool:
    """
    Verifies the existence of a hardware design path.
    """

def uvm_hdl_read(path: str, value: VpiVecVal) -> None:
    """
    Reads the value at the specified hardware path into the `VpiVecVal` object.
    """

def uvm_hdl_deposit(path: str, value: VpiVecVal) -> None:
    """
    Deposits (writes) the `VpiVecVal` object's value onto the hardware path.
    """

def uvm_hdl_force(path: str, value: VpiVecVal) -> None:
    """
    Forces the value of the `VpiVecVal` onto the specified hardware path.
    """

def uvm_hdl_release_and_read(path: str, value: VpiVecVal) -> None:
    """
    Releases any force or deposit operations on the path and then reads the value into `value`.
    """

def uvm_hdl_release(path: str) -> None:
    """
    Releases any force or deposit operations on the hardware path.
    """

def push_data(lvl: int, entry: str, cmd: int) -> None:
    """
    Pushes command-specific data onto a processing stack.
    """

def walk_level(lvl: int, argv: List[str], cmd: int) -> None:
    """
    Walks through a directory hierarchy performing actions based on the provided level and arguments.
    """

def uvm_dpi_get_next_arg_c(init: bool) -> str:
    """
    Retrieves the next command-line argument in a DPI context.
    """

def uvm_dpi_get_tool_name_c() -> str:
    """
    Returns the name of the simulation tool in a DPI context.
    """

def uvm_dpi_get_tool_version_c() -> str:
    """
    Retrieves the version of the simulation tool in a DPI context.
    """

def uvm_dpi_regcomp(pattern: str) -> Any:
    """
    Compiles a regular expression pattern for use in DPI calls.
    """

def uvm_dpi_regexec(re: Any, s: str) -> bool:
    """
    Executes a compiled regular expression against a string.
    """

def uvm_dpi_regfree(re: Any) -> None:
    """
    Frees resources associated with a compiled regular expression.
    """

def exec_tcl_cmd(cmd: str) -> None:
    """
    Execute a tcl command.
    """

def print_factory(all_types: int = 1) -> None:
    """
    Prints information about registered factory types.
    """

def set_factory_inst_override(original_type_name: str, override_type_name: str, full_inst_path: str) -> None:
    """
    Sets an instance-level type override in the UVM factory.
    """

def set_factory_type_override(original_type_name: str, override_type_name: str, replace: bool = True) -> None:
    """
    Sets a type override in the UVM factory.
    """

def create_object_by_name(requested_type: str, context: str = "", name: str = "") -> None:
    """
    Creates an object by its type name within a specified context.
    """

def create_component_by_name(requested_type: str, context: str = "", parent_name: str = "", name: str = "") -> None:
    """
    Creates a UVM component by name, specifying its context and optionally its parent and own name.
    """

def debug_factory_create(requested_type: str, context: str = "") -> None:
    """
    Debug utility to create an object using the factory and prints creation details.
    """

def find_factory_override(requested_type: str, context: str, override_type_name: str) -> None:
    """
    Finds and displays information about a factory type override.
    """

def uvm_info(msg: str, verbosity: int) -> None:
    """
    Reports an informational message with the specified ID and verbosity level.
    """

def uvm_warning(msg: str, verbosity: int) -> None:
    """
    Reports a warning message with the specified ID and verbosity level.
    """

def uvm_error(msg: str, verbosity: int) -> None:
    """
    Reports an error message with the specified ID and verbosity level.
    """

def uvm_fatal(msg: str, verbosity: int) -> None:
    """
    Reports a fatal error message with the specified ID and verbosity level.
    """

def print_topology(context: str = "") -> None:
    """
    Prints the component topology starting from the given context.
    """

def set_timeout(timeout: int, overridable: int = 1) -> None:
    """
    Sets a global timeout value for simulations.
    """

def uvm_objection_op(op: str, name: str, contxt: str, description: str, count: int) -> None:
    """
    Operates on a UVM objection with the specified operation.
    """

def dbg_print(name: str = "") -> None:
    """
    Debug print function, which can optionally include an identifier `name`.
    """

def wait_on(ev_name: str, delta: int = 0) -> None:
    """
    Waits for an event to become active, optionally with a time delay.
    """

def wait_off(ev_name: str, delta: int = 0) -> None:
    """
    Waits for an event to become inactive, optionally with a time delay.
    """

def wait_trigger(ev_name: str) -> None:
    """
    Waits until an event's triggered state is observed.
    """

def wait_ptrigger(ev_name: str) -> None:
    """
    Waits for a previous trigger on the event.
    """

def get_trigger_time(ev_name: str) -> int:
    """
    Retrieves the time at which an event was last triggered.
    """

def is_on(ev_name: str) -> int:
    """
    Checks if an event is currently active, returning 1 for true, 0 for false.
    """

def is_off(ev_name: str) -> int:
    """
    Checks if an event is currently inactive, returning 1 for true, 0 for false.
    """

def ev_reset(ev_name: str, wakeup: int = 0) -> None:
    """
    Resets an event, optionally waking up waiters.
    """

def cancel(ev_name: str) -> None:
    """
    Cancels all waits on the event.
    """

def get_num_waiters(ev_name: str) -> int:
    """
    Returns the number of processes waiting on the event.
    """

def trigger(ev_name: str) -> None:
    """
    Triggers an event, signaling waiting processes.
    """

def set_config_int(contxt: str, inst_name: str, field_name: str, value: int) -> None:
    """
    Sets an integer configuration field in the UVM configuration database.
    """

def get_config_int(contxt: str, inst_name: str, field_name: str) -> int:
    """
    Retrieves an integer configuration field from the UVM configuration database.
    """

def set_config_string(contxt: str, inst_name: str, field_name: str, value: str) -> None:
    """
    Sets a string configuration field in the UVM configuration database.
    """

def get_config_string(contxt: str, inst_name: str, field_name: str) -> str:
    """
    Retrieves a string configuration field from the UVM configuration database.
    """

def write_reg(name: str, data: int) -> None:
    """
    Writes an integer value to a register by name.
    """

def read_reg(name: str) -> int:
    """
    Reads and returns the integer value of a register by name.
    """

def check_reg(name: str, data: int = 0, predict: int = 0) -> None:
    """
    Checks the value of a register against an expected value with optional prediction.
    """

def start_seq(seq_name: str, sqr_name: str) -> None:
    """
    Starts a sequence by name within a specified sequencer.
    """

def run_test(test_name: str = "") -> None:
    """
    Executes a UVM test by name.
    """

def wait_unit(n: int) -> None:
    """
    Waits for a specified unit of time.
    """

def reset() -> None:
    """
    Stops the simulation.
    """

def stop() -> None:
    """
    Stops the simulation.
    """

def finish() -> None:
    """
    Finishes the simulation.
    """

def get_sim_time(name: str) -> int:
    """
    Returns the current simulation time.
    """

def get_time_unit(name: str) -> int:
    """
    Returns the current time unit.
    """

def get_time_precision(name: str) -> int:
    """
    Returns the current time precision.
    """
