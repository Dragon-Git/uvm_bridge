from svuvm import svuvm

def cb_test(data):
    print("hello cb")
    return 1
def main():
    svuvm.vpi.vpi_printf("*"*120+"\n")
    svuvm.vpi.vpi_printf("*        TEST print_topology \n")
    svuvm.vpi.vpi_printf("*"*120+"\n")

    svuvm.print_topology()
    svuvm.print_factory()

    svuvm.vpi.vpi_printf("*"*120+"\n")
    svuvm.vpi.vpi_printf("*        TEST config_db \n")
    svuvm.vpi.vpi_printf("*"*120+"\n")

    svuvm.set_config_int("", "", "int_value", 1)
    int_value = svuvm.get_config_int("", "", "int_value")
    svuvm.vpi.vpi_printf("int_value: {}\n", int_value)
    svuvm.set_config_string("", "", "string_value", "hello world")
    string_value = svuvm.get_config_string("", "", "string_value")
    svuvm.vpi.vpi_printf("string_value: {}\n", string_value)

    svuvm.vpi.vpi_printf("*"*120+"\n")
    svuvm.vpi.vpi_printf("*        TEST reg opretor \n")
    svuvm.vpi.vpi_printf("*"*120+"\n")
    data = 0xdeadbeef
    for i in range(3):
        svuvm.write_reg(str(i), i)
        svuvm.wait_unit(i)
        data = svuvm.read_reg(str(i))
        svuvm.vpi.vpi_printf(f"read data: {data}\n")

    svuvm.vpi.vpi_printf("*"*120+"\n")
    svuvm.vpi.vpi_printf("*        TEST vpi io \n")
    svuvm.vpi.vpi_printf("*"*120+"\n")
    
    f = svuvm.vpi.vpi_mcd_open("test.log")
    svuvm.vpi.vpi_mcd_printf(f, "hello world\n")
    svuvm.vpi.vpi_mcd_flush(f)
    svuvm.vpi.vpi_printf("vpi_printf success\n")
    svuvm.vpi.vpi_flush()
    svuvm.vpi.vpi_mcd_close(f)

    svuvm.vpi.vpi_printf("*"*120+"\n")
    svuvm.vpi.vpi_printf("*        TEST vpi info \n")
    svuvm.vpi.vpi_printf("*"*120+"\n")
    obj = svuvm.vpi.vpi_handle_by_name("top.test_wire")
    error = svuvm.vpi.VpiErrorInfo()
    svuvm.vpi.vpi_printf("vpiVpiErrorInfo: {}\n", error.level)
    print(obj)
    info = svuvm.vpi.VpiVlogInfo()
    print(info.argc, info.argv, info.product, info.version)

    svuvm.vpi.vpi_printf("*"*120+"\n")
    svuvm.vpi.vpi_printf("*        TEST dpi time \n")
    svuvm.vpi.vpi_printf("*"*120+"\n")
    time_obj = svuvm.get_sim_time("Vtop")
    svuvm.vpi.vpi_printf("time: {}\n", time_obj)
    time_obj = svuvm.get_timeunit("Vtop")
    svuvm.vpi.vpi_printf("timeunit: {}\n", time_obj)
    time_obj = svuvm.get_precision("Vtop")
    svuvm.vpi.vpi_printf("precision: {}\n", time_obj)

    svuvm.vpi.vpi_printf("*"*120+"\n")
    svuvm.vpi.vpi_printf("*        TEST vpi callback \n")
    svuvm.vpi.vpi_printf("*"*120+"\n")
    time_obj = svuvm.vpi.VpiTime(svuvm.vpi.vpiSimTime, 0, 0, 0)
    svuvm.vpi.vpi_get_time(obj, time_obj)

    a = svuvm.vpi.CbData(svuvm.vpi.cbNextSimTime, cb_test, obj, time_obj, svuvm.vpi.VpiValue(), 0, "")
    print(a)
    svuvm.vpi.vpi_register_cb(a)


    # svuvm.vpi.vpi_control(svuvm.vpi.vpiReset)
    # svuvm.vpi.vpi_control(svuvm.vpi.vpiFinish)

        