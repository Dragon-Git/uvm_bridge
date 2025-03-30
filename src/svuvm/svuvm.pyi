from typing import List, Any
from . import vpi  # noqa: F401

class VpiVecVal:
    """Represents a VPI (Verilog Programming Interface) vector value, bit encoding: aval bval: 00=0, 10=1, 11=X, 01=Z.


    Attributes:
        aval (int): The first part of the vector value.
        bval (int): The second part of the vector value.

    Args:
        aval (int): The first part of the vector value.
        bval (int): The second part of the vector value.
    """

def uvm_report(severity: str, id: str, message: str, verbosity: str, file: str, linenum: int) -> None:
    """Reports a message in the UVM framework according to the specified severity, ID, and verbosity level.

    Args:
        severity (str): The severity level of the report.
        id (str): The ID of the report.
        message (str): The message to be reported.
        verbosity (str): The verbosity level of the report.
        file (str): The file name where the report is generated.
        linenum (int): The line number in the file where the report is generated.
    """

def int_str_max(*args: str) -> int:
    """Returns the maximum integer value represented as a string among the provided arguments.

    Args:
        *args (str): Variable length argument list of strings representing integers.

    Returns:
        int: The maximum integer value.
    """

def uvm_re_match(re: str, s: str) -> bool:
    """Determines if the provided string `s` matches the regular expression `re`.

    Args:
        re (str): The regular expression pattern.
        s (str): The string to be matched.

    Returns:
        bool: True if the string matches the pattern, False otherwise.
    """

def uvm_glob_to_re(pattern: str) -> str:
    """Converts a glob pattern into a regular expression string.

    Args:
        pattern (str): The glob pattern.

    Returns:
        str: The equivalent regular expression string.
    """

def uvm_hdl_check_path(path: str) -> bool:
    """Verifies the existence of a hardware design path.

    Args:
        path (str): The hardware design path to check.

    Returns:
        bool: True if the path exists, False otherwise.
    """

def uvm_hdl_read(path: str, value: VpiVecVal) -> None:
    """Reads the value at the specified hardware path into the `VpiVecVal` object.

    Args:
        path (str): The hardware design path.
        value (VpiVecVal): The object to store the read value.
    """

def uvm_hdl_deposit(path: str, value: VpiVecVal) -> None:
    """Deposits (writes) the `VpiVecVal` object's value onto the hardware path.

    Args:
        path (str): The hardware design path.
        value (VpiVecVal): The value to deposit.
    """

def uvm_hdl_force(path: str, value: VpiVecVal) -> None:
    """Forces the value of the `VpiVecVal` onto the specified hardware path.

    Args:
        path (str): The hardware design path.
        value (VpiVecVal): The value to force.
    """

def uvm_hdl_release_and_read(path: str, value: VpiVecVal) -> None:
    """Releases any force or deposit operations on the path and then reads the value into `value`.

    Args:
        path (str): The hardware design path.
        value (VpiVecVal): The object to store the read value.
    """

def uvm_hdl_release(path: str) -> None:
    """Releases any force or deposit operations on the hardware path.

    Args:
        path (str): The hardware design path.
    """

def push_data(lvl: int, entry: str, cmd: int) -> None:
    """Pushes command-specific data onto a processing stack.

    Args:
        lvl (int): The level of the stack.
        entry (str): The data entry to push.
        cmd (int): The command identifier.
    """

def walk_level(lvl: int, argv: List[str], cmd: int) -> None:
    """Walks through a directory hierarchy performing actions based on the provided level and arguments.

    Args:
        lvl (int): The level of the directory hierarchy.
        argv (List[str]): The list of arguments.
        cmd (int): The command identifier.
    """

def uvm_dpi_get_next_arg_c(init: bool) -> str:
    """Retrieves the next command-line argument in a DPI context.

    Args:
        init (bool): Whether to initialize the argument retrieval.

    Returns:
        str: The next command-line argument.
    """

def uvm_dpi_get_tool_name_c() -> str:
    """Returns the name of the simulation tool in a DPI context.

    Returns:
        str: The name of the simulation tool.
    """

def uvm_dpi_get_tool_version_c() -> str:
    """Retrieves the version of the simulation tool in a DPI context.

    Returns:
        str: The version of the simulation tool.
    """

def uvm_dpi_regcomp(pattern: str) -> Any:
    """Compiles a regular expression pattern for use in DPI calls.

    Args:
        pattern (str): The regular expression pattern.

    Returns:
        Any: The compiled regular expression object.
    """

def uvm_dpi_regexec(re: Any, s: str) -> bool:
    """Executes a compiled regular expression against a string.

    Args:
        re (Any): The compiled regular expression object.
        s (str): The string to match against.

    Returns:
        bool: True if the string matches the pattern, False otherwise.
    """

def uvm_dpi_regfree(re: Any) -> None:
    """Frees resources associated with a compiled regular expression.

    Args:
        re (Any): The compiled regular expression object.
    """

def exec_tcl_cmd(cmd: str) -> None:
    """Executes a tcl command.

    Args:
        cmd (str): The tcl command to execute.
    """

def uvm_info(message: str, verbosity: int = ..., severity: int = ...) -> None:
    """UVM_INFO report function.

    Args:
        message (str): The message to be reported.
        verbosity (int): The verbosity level of the report. Defaults to M_UVM_INFO.
        severity (int): The severity level of the report. Defaults to M_UVM_INFO.
    """

def uvm_warning(message: str, verbosity: int = ..., severity: int = ...) -> None:
    """UVM_WARNING report function.

    Args:
        message (str): The message to be reported.
        verbosity (int): The verbosity level of the report. Defaults to M_UVM_NONE.
        severity (int): The severity level of the report. Defaults to M_UVM_WARNING.
    """

def uvm_error(message: str, verbosity: int = ..., severity: int = ...) -> None:
    """UVM_ERROR report function.

    Args:
        message (str): The message to be reported.
        verbosity (int): The verbosity level of the report. Defaults to M_UVM_NONE.
        severity (int): The severity level of the report. Defaults to M_UVM_ERROR.
    """

def uvm_fatal(message: str, verbosity: int = ..., severity: int = ...) -> None:
    """UVM_FATAL report function.

    Args:
        message (str): The message to be reported.
        verbosity (int): The verbosity level of the report. Defaults to M_UVM_NONE.
        severity (int): The severity level of the report. Defaults to M_UVM_FATAL.
    """

def print_factory(all_types: int = 1) -> None:
    """Prints information about registered factory types.

    Args:
        all_types (int): Whether to print all types. Defaults to 1.
    """

def set_factory_inst_override(original_type_name: str, override_type_name: str, full_inst_path: str) -> None:
    """Sets an instance-level type override in the UVM factory.

    Args:
        original_type_name (str): The name of the original type.
        override_type_name (str): The name of the override type.
        full_inst_path (str): The full instance path for the override.
    """

def set_factory_type_override(original_type_name: str, override_type_name: str, replace: bool = True) -> None:
    """Sets a type override in the UVM factory.

    Args:
        original_type_name (str): The name of the original type.
        override_type_name (str): The name of the override type.
        replace (bool): Whether to replace existing overrides. Defaults to True.
    """

def create_object_by_name(requested_type: str, contxt: str = "", name: str = "") -> None:
    """Creates an object by its type name within a specified context.

    Args:
        requested_type (str): The type name of the object to create.
        contxt (str): The context in which to create the object. Defaults to "".
        name (str): The name of the object. Defaults to "".
    """

def create_component_by_name(requested_type: str, contxt: str = "", name: str = "") -> None:
    """Creates a UVM component by name, specifying its context and optionally its parent and own name.

    Args:
        requested_type (str): The type name of the component to create.
        contxt (str): The context in which to create the component. Defaults to "".
        name (str): The name of the component. Defaults to "".
        parent_name (str): The name of the parent component. Defaults to "".
    """

def debug_factory_create(requested_type: str, contxt: str = "") -> None:
    """Debug utility to create an object using the factory and prints creation details.

    Args:
        requested_type (str): The type name of the object to create.
        contxt (str): The context in which to create the object. Defaults to "".
    """

def find_factory_override(requested_type: str, contxt: str, override_type_name: str) -> None:
    """Finds and displays information about a factory type override.

    Args:
        requested_type (str): The type name of the object to check.
        contxt (str): The context in which to check the override.
        override_type_name (str): The name of the override type.
    """

def print_topology(contxt: str = "") -> None:
    """Prints the component topology starting from the given context.

    Args:
        contxt (str): The context from which to start printing the topology. Defaults to "".
    """

def set_timeout(timeout: int, overridable: int = 1) -> None:
    """Sets a global timeout value for simulations.

    Args:
        timeout (int): The timeout value.
        overridable (int): Whether the timeout is overridable. Defaults to 1.
    """

def uvm_objection_op(op: str, name: str, contxt: str, description: str, count: int) -> None:
    """Operates on a UVM objection with the specified operation.

    Args:
        op (str): The operation to perform.
        name (str): The name of the objection.
        contxt (str): The context of the objection.
        description (str): The description of the objection.
        count (int): The count associated with the objection.
    """

def dbg_print(name: str = "") -> None:
    """Debug print function, which can optionally include an identifier `name`.

    Args:
        name (str): The identifier to include in the debug print. Defaults to "".
    """

def wait_on(ev_name: str, delta: int = 0) -> None:
    """Waits for an event to become active, optionally with a time delay.

    Args:
        ev_name (str): The name of the event.
        delta (int): The time delay. Defaults to 0.
    """

def wait_off(ev_name: str, delta: int = 0) -> None:
    """Waits for an event to become inactive, optionally with a time delay.

    Args:
        ev_name (str): The name of the event.
        delta (int): The time delay. Defaults to 0.
    """

def wait_trigger(ev_name: str) -> None:
    """Waits until an event's triggered state is observed.

    Args:
        ev_name (str): The name of the event.
    """

def wait_ptrigger(ev_name: str) -> None:
    """Waits for a previous trigger on the event.

    Args:
        ev_name (str): The name of the event.
    """

def get_trigger_time(ev_name: str) -> int:
    """Retrieves the time at which an event was last triggered.

    Args:
        ev_name (str): The name of the event.

    Returns:
        int: The time at which the event was last triggered.
    """

def is_on(ev_name: str) -> int:
    """Checks if an event is currently active, returning 1 for true, 0 for false.

    Args:
        ev_name (str): The name of the event.

    Returns:
        int: 1 if the event is active, 0 otherwise.
    """

def is_off(ev_name: str) -> int:
    """Checks if an event is currently inactive, returning 1 for true, 0 for false.

    Args:
        ev_name (str): The name of the event.

    Returns:
        int: 1 if the event is inactive, 0 otherwise.
    """

def ev_reset(ev_name: str, wakeup: int = 0) -> None:
    """Resets an event, optionally waking up waiters.

    Args:
        ev_name (str): The name of the event.
        wakeup (int): Whether to wake up waiters. Defaults to 0.
    """

def cancel(ev_name: str) -> None:
    """Cancels all waits on the event.

    Args:
        ev_name (str): The name of the event.
    """

def get_num_waiters(ev_name: str) -> int:
    """Returns the number of processes waiting on the event.

    Args:
        ev_name (str): The name of the event.

    Returns:
        int: The number of processes waiting on the event.
    """

def trigger(ev_name: str) -> None:
    """Triggers an event, signaling waiting processes.

    Args:
        ev_name (str): The name of the event.
    """

def set_config_int(contxt: str, inst_name: str, field_name: str, value: int) -> None:
    """Sets an integer configuration field in the UVM configuration database.

    Args:
        contxt (str): The context in which to set the configuration.
        inst_name (str): The instance name.
        field_name (str): The name of the configuration field.
        value (int): The integer value to set.
    """

def get_config_int(contxt: str, inst_name: str, field_name: str) -> int:
    """Retrieves an integer configuration field from the UVM configuration database.

    Args:
        contxt (str): The context from which to retrieve the configuration.
        inst_name (str): The instance name.
        field_name (str): The name of the configuration field.

    Returns:
        int: The integer value of the configuration field.
    """

def set_config_string(contxt: str, inst_name: str, field_name: str, value: str) -> None:
    """Sets a string configuration field in the UVM configuration database.

    Args:
        contxt (str): The context in which to set the configuration.
        inst_name (str): The instance name.
        field_name (str): The name of the configuration field.
        value (str): The string value to set.
    """

def get_config_string(contxt: str, inst_name: str, field_name: str) -> str:
    """Retrieves a string configuration field from the UVM configuration database.

    Args:
        contxt (str): The context from which to retrieve the configuration.
        inst_name (str): The instance name.
        field_name (str): The name of the configuration field.

    Returns:
        str: The string value of the configuration field.
    """

def write_reg(name: str, data: int) -> None:
    """Writes an integer value to a register by name.

    Args:
        name (str): The name of the register.
        data (int): The integer value to write.
    """

def get_report_verbosity_level(contxt: str, severity: int, id: str = "") -> int:
    """Get message verbosity level for specific context and message ID.

    Args:
        contxt: UVM component context path (e.g. "uvm_test_top.env")
        severity: UVM severity level (use UvmSeverity enum values)
        id: Message identifier, empty string for default

    Returns:
        int: Current verbosity level value
    """

def get_report_max_verbosity_level(contxt: str) -> int:
    """Get maximum allowed verbosity level for context.

    Args:
        contxt: UVM component context path

    Returns:
        int: Maximum permitted verbosity level
    """

def set_report_verbosity_level(contxt: str, level: int) -> None:
    """Set default verbosity level for a component hierarchy.

    Args:
        contxt: UVM component context path
        level: Verbosity level to set (use UVM_LEVEL constants)
    """

def set_report_id_verbosity(contxt: str, id: str, verbosity: int) -> None:
    """Configure verbosity for specific message ID.

    Args:
        contxt: UVM component context path
        id: Target message ID to configure
        verbosity: Verbosity level to apply
    """

def set_report_severity_id_verbosity(contxt: str, severity: int, id: str, verbosity: int) -> None:
    """Configure verbosity for specific severity, id, or severity-id pair.

    Args:
        contxt: UVM component context path
        severity: UVM severity level to check
        id: Target message ID to configure
        verbosity: Verbosity level to apply
    """

def get_report_action(contxt: str, severity: int, id: str = "") -> int:
    """Get current report action configuration.

    Args:
        contxt: UVM component context path
        severity: UVM severity level to check
        id: Message identifier, empty string for default

    Returns:
        int: Combined bitmask of current actions (use UvmAction flags)
    """

def set_report_severity_action(contxt: str, severity: int, action: int) -> None:
    """Configure report actions for specific severity level.

    Args:
        contxt: UVM component context path
        severity: Target severity level to configure
        action: Action bitmask (bitwise OR of UvmAction values)
    """

def set_report_id_action(contxt: str, id: str, action: int) -> None:
    """Configure report actions for specific message ID.

    Args:
        contxt: UVM component context path
        id: Message identifier, empty string for default
        action: Action bitmask (bitwise OR of UvmAction values)
    """

def set_report_severity_id_action(contxt: str, severity: int, id: str, action: int) -> None:
    """Configure report actions for specific severity, id, or severity-id pair.

    Args:
        contxt: UVM component context path
        severity: Target severity level to configure
        id: Message identifier, empty string for default
        action: Action bitmask (bitwise OR of UvmAction values)
    """

def set_report_severity_override(contxt: str, original_severity: int, new_severity: int) -> None:
    """Override severity level for report messages.

    Args:
        contxt: UVM component context path
        original_severity: Original severity level to override
        new_severity: New severity level to apply
    """

def set_report_severity_id_override(contxt: str, original_severity: int, id: str, new_severity: int) -> None:
    """Override severity level for specific message ID.

    Args:
        contxt: UVM component context path
        original_severity: Original severity level to override
        id: Target message ID
        new_severity: New severity level to apply
    """

def read_reg(name: str) -> int:
    """Reads and returns the integer value of a register by name.

    Args:
        name (str): The name of the register.

    Returns:
        int: The integer value of the register.
    """

def check_reg(name: str, data: int = 0, predict: int = 0) -> None:
    """Checks the value of a register against an expected value with optional prediction.

    Args:
        name (str): The name of the register.
        data (int): The expected value to check against. Defaults to 0.
        predict (int): Whether to perform prediction. Defaults to 0.
    """

def start_seq(seq_name: str, sqr_name: str) -> None:
    """Starts a sequence by name within a specified sequencer.

    Args:
        seq_name (str): The name of the sequence to start.
        sqr_name (str): The name of the sequencer.
    """

def run_test(test_name: str = "") -> None:
    """Executes a UVM test by name.

    Args:
        test_name (str): The name of the test to execute. Defaults to "".
    """

def wait_unit(n: int) -> None:
    """Waits for a specified unit of time.

    Args:
        n (int): The number of units to wait.
    """

def reset() -> None:
    """Stops the simulation."""

def stop() -> None:
    """Stops the simulation."""

def finish() -> None:
    """Finishes the simulation."""

def get_sim_time(name: str) -> int:
    """Returns the current simulation time.

    Args:
        name (str): The name of the simulation time context.

    Returns:
        int: The current simulation time.
    """

def get_time_unit(name: str) -> int:
    """Returns the current time unit.

    Args:
        name (str): The name of the time unit context.

    Returns:
        int: The current time unit.
    """

def get_time_precision(name: str) -> int:
    """Returns the current time precision.

    Args:
        name (str): The name of the time precision context.

    Returns:
        int: The current time precision.
    """
