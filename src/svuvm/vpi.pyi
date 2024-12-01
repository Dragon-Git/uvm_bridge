from typing import List, Union, Callable, Any, Optional

class VpiTime:
    """
    Represents a time in the VPI (Verilog Procedural Interface).

    Attributes:
        type (int): The type of time.
        high (int): The high part of the time.
        low (int): The low part of the time.
        real (float): The real representation of the time.
    """
    def __init__(self, type: int, high: int, low: int, real: float) -> None: ...

    type: int
    high: int
    low: int
    real: float

class VpiDelay:
    """
    Represents a delay in the VPI.

    Attributes:
        da (VpiTime): The time associated with the delay.
        no_of_delays (int): The number of delays.
        time_type (int): The type of time for the delay.
        mtm_flag (int): Multi-time modeling flag.
        append_flag (int): Append flag.
        pulsere_flag (int): Pulse repeat flag.
    """
    def __init__(self, da: 'VpiTime', no_of_delays: int, time_type: int, mtm_flag: int, append_flag: int, pulsere_flag: int) -> None: ...

    da: 'VpiTime'
    no_of_delays: int
    time_type: int
    mtm_flag: int
    append_flag: int
    pulsere_flag: int

class VpiVecVal:
    """
    Represents a vector value in the VPI.

    Attributes:
        aval (int): The A value.
        bval (int): The B value.
    """
    def __init__(self, aval: int, bval: int) -> None: ...

    aval: int
    bval: int

class VpiStrengthVal:
    """
    Represents a strength value in the VPI.

    Attributes:
        logic (int): The logic value.
        s0 (int): The strength 0.
        s1 (int): The strength 1.
    """
    def __init__(self, logic: int, s0: int, s1: int) -> None: ...

    logic: int
    s0: int
    s1: int

class VpiValue:
    """
    Represents a value in the VPI.

    Attributes:
        format (int): The format of the value.
        value (Union[str, int, float, VpiTime, VpiVecVal, VpiStrengthVal]): The actual value.
    """
    def __init__(self, format: int, value: Union[str, int, float, 'VpiTime', 'VpiVecVal', 'VpiStrengthVal']) -> None: ...

    format: int
    value: Union[str, int, float, 'VpiTime', 'VpiVecVal', 'VpiStrengthVal']

class VpiArrayValue:
    """
    Represents an array value in the VPI.

    Attributes:
        format (int): The format of the array value.
        flags (int): Flags associated with the array value.
        value (Union[List[int], List[float], List[VpiVecVal], List[VpiTime]]): The array of values.
    """
    def __init__(self, format: int, flags: int, value: Union[List[int], List[float], List['VpiVecVal'], List['VpiTime']]) -> None: ...

    format: int
    flags: int
    value: Union[List[int], List[float], List['VpiVecVal'], List['VpiTime']]

class VpiSystfData:
    """
    Represents system task or function data in the VPI.

    Attributes:
        type (int): The type of the system task or function.
        sysfunctype (int): The type of the system function.
        tfname (bytes): The name of the system task or function.
        user_data (Any): User-defined data.
    """
    def __init__(self, type: int, sysfunctype: int, calltf: Callable) -> None: ...

    type: int
    sysfunctype: int
    tfname: bytes
    user_data: Any

class VpiVlogInfo:
    """
    Represents information about the Verilog simulator.

    Attributes:
        argc (int): The number of command-line arguments.
        argv (List[str]): The list of command-line arguments.
        product (bytes): The product name.
        version (bytes): The version of the product.
    """
    def __init__(self) -> None: ...

    argc: int
    argv: List[str]
    product: bytes
    version: bytes

class VpiErrorInfo:
    """
    Represents error information in the VPI.

    Attributes:
        state (int): The state of the error.
        level (int): The severity level of the error.
        message (bytes): The error message.
        product (bytes): The product name.
        code (bytes): The error code.
        file (bytes): The file where the error occurred.
        line (int): The line number where the error occurred.
    """
    def __init__(self) -> None: ...

    state: int
    level: int
    message: bytes
    product: bytes
    code: bytes
    file: bytes
    line: int

class CbData:
    """
    Represents callback data in the VPI.

    Attributes:
        reason (int): The reason for the callback.
        cb_rtn (Callable): The callback routine.
        obj (Any): The object associated with the callback.
        time (VpiTime): The time associated with the callback.
        value (VpiValue): The value associated with the callback.
        index (int): The index associated with the callback.
        user_data (str): User-defined data.
    """
    def __init__(self, reason: int, cb_rtn: Callable, object: Any, time: 'VpiTime', value: 'VpiValue', index: int, user_data: str) -> None: ...

    reason: int
    obj: Any
    time: 'VpiTime'
    value: 'VpiValue'
    index: int
    user_data: str

def vpi_register_cb(cb_data_p: 'CbData') -> Any:
    """
    Registers a callback with the VPI.

    Args:
        cb_data_p (CbData): The callback data to register.

    Returns:
        Any: The result of the registration.
    """

def vpi_remove_cb(cb_obj: Any) -> None:
    """
    Removes a callback from the VPI.

    Args:
        cb_obj (Any): The callback object to remove.
    """

def vpi_get_cb_info(object: Any, cb_data_p: 'CbData') -> Any:
    """
    Gets information about a callback.

    Args:
        object (Any): The object associated with the callback.
        cb_data_p (CbData): The callback data.

    Returns:
        Any: Information about the callback.
    """

def vpi_register_systf(systf_data_p: 'VpiSystfData') -> None:
    """
    Registers a system task or function with the VPI.

    Args:
        systf_data_p (VpiSystfData): The system task or function data to register.
    """

def vpi_get_systf_info(object: Any, systf_data_p: 'VpiSystfData') -> Any:
    """
    Gets information about a registered system task or function.

    Args:
        object (Any): The object associated with the system task or function.
        systf_data_p (VpiSystfData): The system task or function data.

    Returns:
        Any: Information about the system task or function.
    """

def vpi_handle_by_name(name: str, scope: Optional[Any] = None) -> Any:
    """
    Gets a handle by name.

    Args:
        name (str): The name of the object.
        scope (Optional[Any]): The scope in which to search for the object.

    Returns:
        Any: The handle to the object.
    """

def vpi_handle_by_index(object: Any, indx: int) -> Any:
    """
    Gets a handle by index.

    Args:
        object (Any): The object containing the indexed item.
        indx (int): The index of the item.

    Returns:
        Any: The handle to the indexed item.
    """

def vpi_handle(type: int, refHandle: Any) -> Any:
    """
    Gets a handle of a specified type.

    Args:
        type (int): The type of handle to get.
        refHandle (Any): The reference handle.

    Returns:
        Any: The handle of the specified type.
    """

def vpi_handle_multi() -> Any:
    """
    Gets multiple handles.

    Returns:
        Any: Multiple handles.
    """

def vpi_iterate(type: int, refHandle: Any) -> Any:
    """
    Iterates over objects of a specified type.

    Args:
        type (int): The type of objects to iterate over.
        refHandle (Any): The reference handle.

    Returns:
        Any: An iterator over the objects.
    """

def vpi_scan(iterator: Any) -> Any:
    """
    Scans the next object from an iterator.

    Args:
        iterator (Any): The iterator.

    Returns:
        Any: The next object from the iterator.
    """

def vpi_get(property: int, object: Any) -> Any:
    """
    Gets a property of an object.

    Args:
        property (int): The property to get.
        object (Any): The object.

    Returns:
        Any: The value of the property.
    """

def vpi_get64(property: int, object: Any) -> Any:
    """
    Gets a 64-bit property of an object.

    Args:
        property (int): The property to get.
        object (Any): The object.

    Returns:
        Any: The 64-bit value of the property.
    """

def vpi_get_str(property: int, object: Any) -> bytes:
    """
    Gets a string property of an object.

    Args:
        property (int): The property to get.
        object (Any): The object.

    Returns:
        bytes: The string value of the property.
    """

def vpi_get_delays(object: Any, delay_p: 'VpiDelay') -> None:
    """
    Gets the delays associated with an object.

    Args:
        object (Any): The object.
        delay_p (VpiDelay): The delay data.
    """

def vpi_put_delays(object: Any, delay_p: 'VpiDelay') -> None:
    """
    Sets the delays for an object.

    Args:
        object (Any): The object.
        delay_p (VpiDelay): The delay data.
    """

def vpi_get_value(expr: Any, value_p: 'VpiValue') -> None:
    """
    Gets the value of an expression.

    Args:
        expr (Any): The expression.
        value_p (VpiValue): The value data.
    """

def vpi_put_value(object: Any, value_p: 'VpiValue', time_p: 'VpiTime', flags: int) -> None:
    """
    Sets the value of an object.

    Args:
        object (Any): The object.
        value_p (VpiValue): The value data.
        time_p (VpiTime): The time at which to set the value.
        flags (int): Flags associated with the operation.
    """

def vpi_get_value_array(object: Any, arrayvalue_p: 'VpiArrayValue', index_p: List[int], num: int) -> None:
    """
    Gets an array value from an object.

    Args:
        object (Any): The object.
        arrayvalue_p (VpiArrayValue): The array value data.
        index_p (List[int]): The indices of the array elements to get.
        num (int): The number of elements to get.
    """

def vpi_put_value_array(object: Any, arrayvalue_p: 'VpiArrayValue', index_p: List[int], num: int) -> None:
    """
    Sets an array value for an object.

    Args:
        object (Any): The object.
        arrayvalue_p (VpiArrayValue): The array value data.
        index_p (List[int]): The indices of the array elements to set.
        num (int): The number of elements to set.
    """

def vpi_get_time(object: Any, time_p: 'VpiTime') -> None:
    """
    Gets the time associated with an object.

    Args:
        object (Any): The object.
        time_p (VpiTime): The time data.
    """

def vpi_mcd_open(fileName: str) -> Any:
    """
    Opens a multichannel descriptor.

    Args:
        fileName (str): The name of the file to open.

    Returns:
        Any: The multichannel descriptor.
    """

def vpi_mcd_close(mcd: Any) -> None:
    """
    Closes a multichannel descriptor.

    Args:
        mcd (Any): The multichannel descriptor.
    """

def vpi_mcd_name(cd: Any) -> bytes:
    """
    Gets the name of a multichannel descriptor.

    Args:
        cd (Any): The multichannel descriptor.

    Returns:
        bytes: The name of the multichannel descriptor.
    """

def vpi_mcd_printf(*args) -> None:
    """
    Prints formatted output to a multichannel descriptor.

    Args:
        *args: Arguments to be printed.
    """

def vpi_printf(*args) -> None:
    """
    Prints formatted output.

    Args:
        *args: Arguments to be printed.
    """

def vpi_compare_objects(*args) -> bool:
    """
    Compares two objects.

    Args:
        *args: The objects to compare.

    Returns:
        bool: True if the objects are equal, False otherwise.
    """

def vpi_free_object(object: Any) -> None:
    """
    Frees an object.

    Args:
        object (Any): The object to free.
    """

def vpi_release_handle(object: Any) -> None:
    """
    Releases a handle.

    Args:
        object (Any): The handle to release.
    """

def vpi_get_data(id: Any, dataLoc: Any, numOfBytes: int) -> None:
    """
    Gets data from an object.

    Args:
        id (Any): The identifier of the object.
        dataLoc (Any): The location to store the data.
        numOfBytes (int): The number of bytes to get.
    """

def vpi_put_data(id: Any, dataLoc: Any, numOfBytes: int) -> None:
    """
    Sets data for an object.

    Args:
        id (Any): The identifier of the object.
        dataLoc (Any): The location of the data.
        numOfBytes (int): The number of bytes to set.
    """

def vpi_get_userdata(obj: Any) -> Any:
    """
    Gets user-defined data associated with an object.

    Args:
        obj (Any): The object.

    Returns:
        Any: The user-defined data.
    """

def vpi_put_userdata(obj: Any, userdata: Any) -> None:
    """
    Sets user-defined data for an object.

    Args:
        obj (Any): The object.
        userdata (Any): The user-defined data.
    """

def vpi_flush() -> None:
    """
    Flushes all pending operations.
    """

def vpi_mcd_flush(mcd: Any) -> None:
    """
    Flushes a multichannel descriptor.

    Args:
        mcd (Any): The multichannel descriptor.
    """

def vpi_control(*args) -> None:
    """
    Controls various aspects of the VPI.

    Args:
        *args: Control arguments.
    """

def vpi_handle_by_multi_index(obj: Any, num_index: int, index_array: List[int]) -> Any:
    """
    Gets a handle using multiple indices.

    Args:
        obj (Any): The object.
        num_index (int): The number of indices.
        index_array (List[int]): The array of indices.

    Returns:
        Any: The handle.
    """