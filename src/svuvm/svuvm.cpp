#include "svdpi.h"
#include <dlfcn.h>
#include <iostream>
#include <libgen.h>
#include <pybind11/embed.h>
#include <pybind11/functional.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#if defined(VCS) || defined(VCSMX)
#include <mhpi_user.h>
#elif defined(XCELIUM) || defined(NCSC)
#include <cfclib.h>
#elif defined(MENTOR)
#include <mti.h>
#endif

namespace py = pybind11;
#ifndef NO_VPI
#include "vpi_user_wrap.h"
#endif

#include <type_traits> // 添加头文件

template <typename Func> auto dpi_func_wrap(Func func) {
  // 使用 std::remove_pointer 去除函数指针的指针，获取函数类型
  using FuncPointerType = std::decay_t<Func>;
  using FuncType = std::remove_pointer_t<FuncPointerType>;
  return std::function<FuncType>([func](auto &&...args) {
    svSetScope(svGetScopeFromName("python_bridge_pkg"));
    return func(std::forward<decltype(args)>(args)...);
  });
}

extern "C" {
#include "export_dpi.h"
#include "uvm_dpi.h"
// 使用pybind11创建的包装器函数
void wrap_walk_level(int lvl, std::vector<std::string> args, int cmd) {
  // Convert Python string list to C-style char**
  std::vector<char *> c_args;
  for (const auto &arg : args) {
    c_args.push_back(const_cast<char *>(arg.c_str()));
  }
  char **argv = c_args.data();
  int argc = static_cast<int>(args.size());

  // Call the original function
  walk_level(lvl, argc, argv, cmd);
}

void wrap_uvm_report(char *message, int verbosity, int severity) {
  py::object inspect = py::module::import("inspect");
  py::object current_frame = inspect.attr("currentframe")();

  if (!current_frame.is_none()) {
    std::string funcname =
        current_frame.attr("f_code").attr("co_name").cast<std::string>();
    std::string filename =
        current_frame.attr("f_code").attr("co_filename").cast<std::string>();
    int lineno = current_frame.attr("f_lineno").cast<int>();
    m_uvm_report_dpi(severity, const_cast<char *>(funcname.c_str()), message,
                     verbosity, const_cast<char *>(filename.c_str()), lineno);
  } else {
    std::cout << "currentframe is not available!" << std::endl;
  }
}

int wrap_read_reg(const char *name) {
  int data;
  read_reg(name, &data);
  return data;
}

// execute a tcl comamnd in simulator
char *exec_tcl_cmd(char *cmd) {
#if defined(VCS) || defined(VCSMX)
  return mhpi_ucliTclExec(cmd);
#elif defined(XCELIUM) || defined(NCSC)
  cfcExecuteCommand(cmd);
  return cfcGetOutput();
#elif defined(MENTOR)
  mti_Cmd(cmd);
  return const_cast<char *>("");
#else
  // not supported
  printf("tcl intregation is not support in this simulator\n");
  return const_cast<char *>("");
#endif
};

PYBIND11_MODULE(svuvm, m) {
  m.doc() = "svuvm api module";

#ifndef NO_VPI
  // VPI wrapper
  py::module_ vpi = m.def_submodule("vpi");

// vpi handle types
#include <vpi_attr.h>
  // datatypes
  py::class_<s_vpi_time>(vpi, "VpiTime")
      .def(py::init(
          [](int type, unsigned int high, unsigned int low, double real) {
            return new s_vpi_time{type, high, low, real};
          }))
      .def(py::init<>())
      .def_readwrite("type", &s_vpi_time::type)
      .def_readwrite("high", &s_vpi_time::high)
      .def_readwrite("low", &s_vpi_time::low)
      .def_readwrite("real", &s_vpi_time::real);

  py::class_<s_vpi_delay>(vpi, "VpiDelay")
      .def(py::init([](s_vpi_time *da, int no_of_delays, int time_type,
                       int mtm_flag, int append_flag, int pulsere_flag) {
        return new s_vpi_delay{da,       no_of_delays, time_type,
                               mtm_flag, append_flag,  pulsere_flag};
      }))
      .def(py::init<>())
      .def_readwrite("da", &s_vpi_delay::da)
      .def_readwrite("no_of_delays", &s_vpi_delay::no_of_delays)
      .def_readwrite("time_type", &s_vpi_delay::time_type)
      .def_readwrite("mtm_flag", &s_vpi_delay::mtm_flag)
      .def_readwrite("append_flag", &s_vpi_delay::append_flag)
      .def_readwrite("pulsere_flag", &s_vpi_delay::pulsere_flag);

  py::class_<s_vpi_vecval>(vpi, "VpiVecVal")
      .def(py::init([](unsigned int aval, unsigned int bval) {
        return new s_vpi_vecval{aval, bval};
      }))
      .def(py::init<>())
      .def_readwrite("aval", &s_vpi_vecval::aval)
      .def_readwrite("bval", &s_vpi_vecval::bval);

  py::class_<s_vpi_strengthval>(vpi, "VpiStrengthVal")
      .def(py::init([](int logic, int s0, int s1) {
        return new s_vpi_strengthval{logic, s0, s1};
      }))
      .def(py::init<>())
      .def_readwrite("logic", &s_vpi_strengthval::logic)
      .def_readwrite("s0", &s_vpi_strengthval::s0)
      .def_readwrite("s1", &s_vpi_strengthval::s1);

  py::class_<s_vpi_value>(vpi, "VpiValue")
      .def(py::init([](int format, char *value) {
        return new s_vpi_value{format, {.str = value}};
      }))
      .def(py::init([](int format, int value) {
        return new s_vpi_value{format, {.integer = value}};
      }))
      .def(py::init([](int format, double value) {
        return new s_vpi_value{format, {.real = value}};
      }))
      .def(py::init([](int format, p_vpi_time value) {
        return new s_vpi_value{format, {.time = value}};
      }))
      .def(py::init([](int format, p_vpi_vecval value) {
        return new s_vpi_value{format, {.vector = value}};
      }))
      .def(py::init([](int format, p_vpi_strengthval value) {
        return new s_vpi_value{format, {.strength = value}};
      }))
      .def(py::init<>())
      .def_readwrite("format", &s_vpi_value::format)
      .def_readwrite("value", &s_vpi_value::value);

  py::class_<s_vpi_arrayvalue>(vpi, "VpiArrayValue")
      .def(py::init([](unsigned int format, unsigned int flags,
                       std::vector<PLI_INT32> integers) {
        return new s_vpi_arrayvalue{
            format, flags, {.integers = new PLI_INT32[integers.size()]}};
      }))
      .def(py::init([](unsigned int format, unsigned int flags,
                       std::vector<PLI_INT16> shortints) {
        return new s_vpi_arrayvalue{
            format, flags, {.shortints = new PLI_INT16[shortints.size()]}};
      }))
      .def(py::init([](unsigned int format, unsigned int flags,
                       std::vector<PLI_INT64> longints) {
        return new s_vpi_arrayvalue{
            format, flags, {.longints = new PLI_INT64[longints.size()]}};
      }))
      .def(py::init([](unsigned int format, unsigned int flags,
                       std::vector<PLI_BYTE8> rawvals) {
        return new s_vpi_arrayvalue{
            format, flags, {.rawvals = new PLI_BYTE8[rawvals.size()]}};
      }))
      .def(py::init([](unsigned int format, unsigned int flags,
                       std::vector<s_vpi_vecval> vectors) {
        return new s_vpi_arrayvalue{
            format, flags, {.vectors = new s_vpi_vecval[vectors.size()]}};
      }))
      .def(py::init([](unsigned int format, unsigned int flags,
                       std::vector<s_vpi_time> times) {
        return new s_vpi_arrayvalue{
            format, flags, {.times = new s_vpi_time[times.size()]}};
      }))
      .def(py::init([](unsigned int format, unsigned int flags,
                       std::vector<double> reals) {
        return new s_vpi_arrayvalue{
            format, flags, {.reals = new double[reals.size()]}};
      }))
      .def(py::init([](unsigned int format, unsigned int flags,
                       std::vector<float> shortreals) {
        return new s_vpi_arrayvalue{
            format, flags, {.shortreals = new float[shortreals.size()]}};
      }))
      .def(py::init<>())
      .def_readwrite("format", &s_vpi_arrayvalue::format)
      .def_readwrite("flags", &s_vpi_arrayvalue::flags)
      .def_readwrite("value", &s_vpi_arrayvalue::value);

  py::class_<s_vpi_systf_data>(vpi, "VpiSystfData")
      .def(py::init([](int type, int sysfunctype, py::function calltf) {
        std::string func_name = calltf.attr("__name__").cast<std::string>();
        std::string tfname = "$" + func_name;
        auto callback_info = new CallbackInfo(calltf, "user_data");
        PLI_BYTE8 *user_data = reinterpret_cast<PLI_BYTE8 *>(callback_info);
        return new s_vpi_systf_data{type,
                                    sysfunctype,
                                    (PLI_BYTE8 *)tfname.c_str(),
                                    systf_callback_wrap,
                                    NULL,
                                    NULL,
                                    user_data};
      }))
      .def(py::init<>())
      .def_readwrite("type", &s_vpi_systf_data::type)
      .def_readwrite("sysfunctype", &s_vpi_systf_data::sysfunctype)
      .def_readwrite("tfname", &s_vpi_systf_data::tfname)
      .def_readwrite("user_data", &s_vpi_systf_data::user_data);

  py::class_<s_vpi_vlog_info>(vpi, "VpiVlogInfo")
      .def(py::init([]() {
        s_vpi_vlog_info info;
        vpi_get_vlog_info(&info);
        return info;
      }))
      .def(py::init<>())
      .def_readonly("argc", &s_vpi_vlog_info::argc)
      .def_property_readonly("argv",
                             [](const s_vpi_vlog_info &info) {
                               std::vector<std::string> result;
                               for (int i = 0; i < info.argc; ++i) {
                                 result.push_back(info.argv[i]);
                               }
                               return result;
                             })
      .def_readonly("product", &s_vpi_vlog_info::product)
      .def_readonly("version", &s_vpi_vlog_info::version);

  py::class_<s_vpi_error_info>(vpi, "VpiErrorInfo")
      .def(py::init([]() {
        s_vpi_error_info info;
        memset(&info, 0, sizeof(info));
        int level = vpi_chk_error(&info);
        vpi_printf((PLI_BYTE8 *)"error level is:%d", level);
        return info;
      }))
      .def(py::init<>())
      .def_readwrite("state", &s_vpi_error_info::state)
      .def_readwrite("level", &s_vpi_error_info::level)
      .def_readwrite("message", &s_vpi_error_info::message)
      .def_readwrite("product", &s_vpi_error_info::product)
      .def_readwrite("code", &s_vpi_error_info::code)
      .def_readwrite("file", &s_vpi_error_info::file)
      .def_readwrite("line", &s_vpi_error_info::line);

  py::class_<s_cb_data>(vpi, "CbData")
      .def(py::init([](int reason, py::function cb_rtn, py::object object,
                       p_vpi_time time, p_vpi_value value, int index,
                       std::string user_data) {
        s_cb_data data;
        vpiHandle obj = convert(object);
        data = {reason, vpi_callback_wrap, obj, time, value, index, NULL};
        auto callback_info = new CallbackInfo(cb_rtn, user_data);
        data.user_data = reinterpret_cast<PLI_BYTE8 *>(callback_info);
        return data;
      }))
      .def(py::init<>())
      .def_readwrite("reason", &s_cb_data::reason)
      .def_readwrite("obj", &s_cb_data::obj)
      .def_readwrite("time", &s_cb_data::time)
      .def_readwrite("value", &s_cb_data::value)
      .def_readwrite("index", &s_cb_data::index)
      .def_property(
          "user_data",
          [](s_cb_data &data) -> std::string {
            return std::string(data.user_data);
          },
          [](s_cb_data &data, std::string user_data) {
            data.user_data = const_cast<PLI_BYTE8 *>(user_data.c_str());
          });
  // functions
  vpi.def("vpi_register_cb", vpi_func_wrap(vpi_register_cb),
          py::arg("cb_data_p"), "Register a callback.");

  vpi.def("vpi_remove_cb", vpi_func_wrap(vpi_remove_cb), py::arg("cb_obj"),
          "Remove a callback.");

  vpi.def("vpi_get_cb_info", &vpi_get_cb_info_wrap, py::arg("object"),
          py::arg("cb_data_p"), "Get callback information.");

  vpi.def("vpi_register_systf", vpi_func_wrap(vpi_register_systf),
          py::arg("systf_data_p"), "Register a system task/function.");

  vpi.def("vpi_get_systf_info", &vpi_get_systf_info_wrap, py::arg("object"),
          py::arg("systf_data_p"), "Get system task/function information.");

  vpi.def("vpi_handle_by_name", vpi_func_wrap(vpi_handle_by_name),
          py::arg("name"), py::arg("scope") = py::none(),
          "Get a handle by name.");

  vpi.def("vpi_handle_by_index", vpi_func_wrap(vpi_handle_by_index),
          py::arg("object"), py::arg("indx"), "Get a handle by index.");

  vpi.def("vpi_handle", vpi_func_wrap(vpi_handle), py::arg("type"),
          py::arg("refHandle"),
          "Get a handle for a specific type and reference handle.");

  vpi.def("vpi_handle_multi", &vpi_handle_multi_wrap,
          "Get a handle for multiple reference handles.");

  vpi.def("vpi_iterate", vpi_func_wrap(vpi_iterate), py::arg("type"),
          py::arg("refHandle"), "Iterate over objects of a specific type.");

  vpi.def("vpi_scan", vpi_func_wrap(vpi_scan), py::arg("iterator"),
          "Scan an iterator.");

  vpi.def("vpi_get", vpi_func_wrap(vpi_get), py::arg("property"),
          py::arg("object"), "Get a property value.");

  vpi.def("vpi_get64", vpi_func_wrap(vpi_get64), py::arg("property"),
          py::arg("object"), "Get a 64-bit property value.");

  vpi.def("vpi_get_str", vpi_func_wrap(vpi_get_str), py::arg("property"),
          py::arg("object"), "Get a string property value.");

  vpi.def("vpi_get_delays", &vpi_get_delays_wrap, py::arg("object"),
          py::arg("delay_p"), "Get delays for an object.");

  vpi.def("vpi_put_delays", &vpi_put_delays_wrap, py::arg("object"),
          py::arg("delay_p"), "Put delays for an object.");

  vpi.def("vpi_get_value", &vpi_get_value_wrap, py::arg("expr"),
          py::arg("value_p"), "Get a value.");

  vpi.def("vpi_put_value", &vpi_put_value_wrap, py::arg("object"),
          py::arg("value_p"), py::arg("time_p"), py::arg("flags"),
          "Put a value.");

  vpi.def("vpi_get_value_array", &vpi_get_value_array_wrap, py::arg("object"),
          py::arg("arrayvalue_p"), py::arg("index_p"), py::arg("num"),
          "Get an array of values.");

  vpi.def("vpi_put_value_array", &vpi_put_value_array_wrap, py::arg("object"),
          py::arg("arrayvalue_p"), py::arg("index_p"), py::arg("num"),
          "Put an array of values.");

  vpi.def("vpi_get_time", &vpi_get_time_wrap, py::arg("object"),
          py::arg("time_p"), "Get time for an object.");

  vpi.def("vpi_mcd_open", &vpi_mcd_open, py::arg("fileName"),
          "Open a multichannel description file.");

  vpi.def("vpi_mcd_close", &vpi_mcd_close, py::arg("mcd"),
          "Close a multichannel description file.");

  vpi.def("vpi_mcd_name", &vpi_mcd_name, py::arg("cd"),
          "Get the name of a multichannel description file.");

  vpi.def("vpi_mcd_printf", &vpi_mcd_printf_wrap,
          "Print to a multichannel description file.");

  vpi.def("vpi_printf", &vpi_printf_wrap, "Print to standard output.");

  vpi.def("vpi_compare_objects", vpi_func_wrap(vpi_compare_objects),
          py::arg("object1"), py::arg("object2"), "Compare two objects.");

  vpi.def("vpi_free_object", vpi_func_wrap(vpi_free_object), py::arg("object"),
          "Free an object. (Deprecated)");

  vpi.def("vpi_release_handle", vpi_func_wrap(vpi_release_handle),
          py::arg("object"), "Release a handle.");

#if !defined(VCS) && !defined(VCSMX)
  vpi.def("vpi_get_data", &vpi_get_data, py::arg("id"), py::arg("dataLoc"),
          py::arg("numOfBytes"), "Get data.");

  vpi.def("vpi_put_data", &vpi_put_data, py::arg("id"), py::arg("dataLoc"),
          py::arg("numOfBytes"), "Put data.");
#endif

  vpi.def("vpi_get_userdata", &vpi_get_userdata_wrap, py::arg("obj"),
          "Get user data.");

  vpi.def("vpi_put_userdata", &vpi_put_userdata_wrap, py::arg("obj"),
          py::arg("userdata"), "Put user data.");

  vpi.def("vpi_flush", &vpi_flush, "Flush output.");

  vpi.def("vpi_mcd_flush", &vpi_mcd_flush, py::arg("mcd"),
          "Flush a multichannel description file.");

  vpi.def("vpi_control", &vpi_control_wrap, "Control simulator operations.");

  vpi.def("vpi_handle_by_multi_index", &vpi_handle_by_multi_index_wrap,
          py::arg("obj"), py::arg("num_index"), py::arg("index_array"),
          "Get a handle by multiple indices.");
#endif
  // UVM severity levels
  m.attr("UVM_INFO") = M_UVM_INFO;
  m.attr("UVM_WARNING") = M_UVM_WARNING;
  m.attr("UVM_ERROR") = M_UVM_ERROR;
  m.attr("UVM_FATAL") = M_UVM_FATAL;

  m.attr("UVM_NONE") = M_UVM_NONE;
  m.attr("UVM_LOW") = M_UVM_LOW;
  m.attr("UVM_MEDIUM") = M_UVM_MEDIUM;
  m.attr("UVM_HIGH") = M_UVM_HIGH;
  m.attr("UVM_FULL") = M_UVM_FULL;
  m.attr("UVM_DEBUG") = M_UVM_DEBUG;
  m.attr("VpiVecVal") = vpi.attr("VpiVecVal");

  // UVM report action
  m.attr("UVM_NO_ACTION") = 0b0000000;
  m.attr("UVM_DISPLAY") = 0b0000001;
  m.attr("UVM_LOG") = 0b0000010;
  m.attr("UVM_COUNT") = 0b0000100;
  m.attr("UVM_EXIT") = 0b0001000;
  m.attr("UVM_CALL_HOOK") = 0b0010000;
  m.attr("UVM_STOP") = 0b0100000;
  m.attr("UVM_RM_RECORD") = 0b1000000;

  // Binding functions

  m.def("uvm_report", &m_uvm_report_dpi, "report function", py::arg("severity"),
        py::arg("id"), py::arg("message"), py::arg("verbosity"),
        py::arg("file"), py::arg("linenum"));

  m.def("int_str_max", &int_str_max,
        "Find the maximum of integers represented as strings.");

  m.def("uvm_re_match", &uvm_re_match,
        "Match a regular expression against a string.", py::arg("re"),
        py::arg("str"));

  m.def("uvm_glob_to_re", &uvm_glob_to_re,
        "Convert a glob pattern into a regular expression.",
        py::return_value_policy::reference);

  m.def("uvm_hdl_check_path", &uvm_hdl_check_path,
        "Check if a path exists in the HDL model.", py::arg("path"));

  m.def("uvm_hdl_read", &uvm_hdl_read,
        "Read data from a path in the HDL model.", py::arg("path"),
        py::arg("value"));

  m.def("uvm_hdl_deposit", &uvm_hdl_deposit,
        "Deposit data at a path in the HDL model.", py::arg("path"),
        py::arg("value"));

  m.def("uvm_hdl_force", &uvm_hdl_force,
        "Force a value at a path in the HDL model.", py::arg("path"),
        py::arg("value"));

  m.def("uvm_hdl_release_and_read", &uvm_hdl_release_and_read,
        "Release and read data from a path in the HDL model.", py::arg("path"),
        py::arg("value"));

  m.def("uvm_hdl_release", &uvm_hdl_release, "Release a path in the HDL model.",
        py::arg("path"));

  m.def("push_data", &push_data, "Push data to a specified level.",
        py::arg("lvl"), py::arg("entry"), py::arg("cmd"));

  m.def("walk_level", &wrap_walk_level,
        "Walk through a hierarchy at a given level.", py::arg("lvl"),
        py::arg("argv"), py::arg("cmd"));

  m.def("uvm_dpi_get_next_arg_c", &uvm_dpi_get_next_arg_c,
        "Get the next argument from the command line.", py::arg("init"));

  m.def("uvm_dpi_get_tool_name_c", &uvm_dpi_get_tool_name_c,
        "Get the name of the current tool.",
        py::return_value_policy::reference);

  m.def("uvm_dpi_get_tool_version_c", &uvm_dpi_get_tool_version_c,
        "Get the version of the current tool.",
        py::return_value_policy::reference);

  m.def("uvm_dpi_regcomp", &uvm_dpi_regcomp, "Compile a regular expression.",
        py::arg("pattern"), py::return_value_policy::take_ownership);

  m.def("uvm_dpi_regexec", &uvm_dpi_regexec,
        "Execute a compiled regular expression against a string.",
        py::arg("re"), py::arg("str"));

  m.def("uvm_dpi_regfree", &uvm_dpi_regfree,
        "Free a compiled regular expression.", py::arg("re"));

  m.def("exec_tcl_cmd", &exec_tcl_cmd, "Execute a tcl command.",
        py::arg("cmd"));

  m.def("uvm_info", &wrap_uvm_report, "UVM_INFO report function.",
        py::arg("message"), py::arg("verbosity"),
        py::arg("severity") = M_UVM_INFO);

  m.def("uvm_warning", &wrap_uvm_report, "UVM_WARNING report function.",
        py::arg("message"), py::arg("verbosity") = M_UVM_NONE,
        py::arg("severity") = M_UVM_WARNING);

  m.def("uvm_error", &wrap_uvm_report, "UVM_ERROR report function.",
        py::arg("message"), py::arg("verbosity") = M_UVM_NONE,
        py::arg("severity") = M_UVM_ERROR);

  m.def("uvm_fatal", &wrap_uvm_report, "UVM_FATAL report function.",
        py::arg("message"), py::arg("verbosity") = M_UVM_NONE,
        py::arg("severity") = M_UVM_FATAL);

  m.def("print_factory", dpi_func_wrap(print_factory),
        "Prints factory information.", py::arg("all_types") = 1);

  m.def("set_factory_inst_override", dpi_func_wrap(set_factory_inst_override),
        "Sets an instance override in the factory.",
        py::arg("original_type_name"), py::arg("override_type_name"),
        py::arg("full_inst_path"));

  m.def("set_factory_type_override", dpi_func_wrap(set_factory_type_override),
        "Sets a type override in the factory.", py::arg("original_type_name"),
        py::arg("override_type_name"), py::arg("replace") = true);

  m.def("debug_factory_create", dpi_func_wrap(debug_factory_create),
        "Debugs the creation of a factory object.", py::arg("requested_type"),
        py::arg("context") = "");

  m.def("create_object_by_name", dpi_func_wrap(create_object_by_name),
        "create a uvm object.", py::arg("requested_type"),
        py::arg("context") = "", py::arg("name") = "");

  m.def("create_component_by_name", dpi_func_wrap(create_component_by_name),
        "create a uvm object.", py::arg("requested_type"),
        py::arg("context") = "", py::arg("name") = "");

  m.def("find_factory_override", dpi_func_wrap(find_factory_override),
        "Finds an override for a given factory type.",
        py::arg("requested_type"), py::arg("context"),
        py::arg("override_type_name"));

  m.def("print_topology", dpi_func_wrap(print_topology), "Prints the topology.",
        py::arg("context") = "");

  m.def("set_timeout", dpi_func_wrap(set_timeout), "Set the timeout value.",
        py::arg("timeout"), py::arg("overridable") = 1);

  m.def("set_finish_on_completion", dpi_func_wrap(set_finish_on_completion),
        "if set 1, then $finish is called after phasing completes.",
        py::arg("f") = 1);

  m.def("uvm_objection_op", dpi_func_wrap(uvm_objection_op), "uvm_objection_op",
        py::arg("op"), py::arg("name"), py::arg("contxt"),
        py::arg("description"), py::arg("delta") = 0);

  m.def("dbg_print", dpi_func_wrap(dbg_print), "Prints the object.",
        py::arg("name") = "");

  m.def("tlm_connect", dpi_func_wrap(tlm_connect), "Connects two TLM ports.",
        py::arg("src"), py::arg("dst"));

  // uvm event
  m.def("wait_on", dpi_func_wrap(wait_on), "Wait until the signal is on",
        py::arg("ev_name"), py::arg("delta") = 0);
  m.def("wait_off", dpi_func_wrap(wait_off), "Wait until the signal is off",
        py::arg("ev_name"), py::arg("delta") = 0);
  m.def("wait_trigger", dpi_func_wrap(wait_trigger),
        "Wait for the trigger event", py::arg("ev_name"));
  m.def("wait_ptrigger", dpi_func_wrap(wait_ptrigger),
        "Wait for the positive trigger event", py::arg("ev_name"));
  m.def("get_trigger_time", dpi_func_wrap(get_trigger_time),
        "Get the time of the last trigger event", py::arg("ev_name"));
  m.def("is_on", dpi_func_wrap(is_on), "Check if the signal is on",
        py::arg("ev_name"));
  m.def("is_off", dpi_func_wrap(is_off), "Check if the signal is off",
        py::arg("ev_name"));
  m.def("ev_reset", dpi_func_wrap(reset), "Reset the signal state",
        py::arg("ev_name"), py::arg("wakeup") = 0);
  m.def("cancel", dpi_func_wrap(cancel), "Cancel the current wait operation",
        py::arg("ev_name"));
  m.def("get_num_waiters", dpi_func_wrap(get_num_waiters),
        "Get the number of waiters", py::arg("ev_name"));
  m.def("trigger", dpi_func_wrap(trigger), "Trigger the event",
        py::arg("ev_name"));
  // config db
  m.def("set_config_int", dpi_func_wrap(set_config_uint64_t),
        "Set integer configuration in the UVM environment");
  m.def("get_config_int", dpi_func_wrap(get_config_uint64_t),
        "Get integer configuration from the UVM environment");
  m.def("set_config_real", dpi_func_wrap(set_config_double),
        "Set real(double) configuration in the UVM environment");
  m.def("get_config_real", dpi_func_wrap(get_config_double),
        "Get real(double) configuration from the UVM environment");
  m.def("set_config_string", dpi_func_wrap(set_config_string),
        "Set string configuration in the UVM environment");
  m.def("get_config_string", dpi_func_wrap(get_config_string),
        "Get string configuration from the UVM environment");
  m.def("config_db_trace_on", dpi_func_wrap(config_db_trace_on),
        "Enable configuration database tracing");
  m.def("config_db_trace_off", dpi_func_wrap(config_db_trace_off),
        "Disable configuration database tracing");
  // 报告相关函数绑定
  m.def("get_report_verbosity_level", dpi_func_wrap(get_report_verbosity_level),
        "Get the verbosity level for a given severity and id");
  m.def("get_report_max_verbosity_level",
        dpi_func_wrap(get_report_max_verbosity_level),
        "Get the maximum verbosity level");
  m.def("set_report_verbosity_level", dpi_func_wrap(set_report_verbosity_level),
        "Set the verbosity level for a given context");
  m.def("set_report_id_verbosity", dpi_func_wrap(set_report_id_verbosity),
        "Set the verbosity level for a given id");
  m.def("set_report_severity_id_verbosity",
        dpi_func_wrap(set_report_severity_id_verbosity),
        "Set the verbosity level for a given severity and id");
  m.def("get_report_action", dpi_func_wrap(get_report_action),
        "Get the action for a given severity and id");
  m.def("set_report_severity_action", dpi_func_wrap(set_report_severity_action),
        "Set the action for a given severity");
  m.def("set_report_id_action", dpi_func_wrap(set_report_id_action),
        "Set the action for a given id");
  m.def("set_report_severity_id_action",
        dpi_func_wrap(set_report_severity_id_action),
        "Set the action for a given severity and id");
  m.def("set_report_severity_override",
        dpi_func_wrap(set_report_severity_override),
        "Set the severity override for a given context");
  m.def("set_report_severity_id_override",
        dpi_func_wrap(set_report_severity_id_override),
        "Set the severity override for a given id");
  // 报告服务相关函数绑定
  m.def("set_max_quit_count", dpi_func_wrap(set_max_quit_count),
        "Sets the maximum quit count for the report server.", py::arg("count"),
        py::arg("overridable") = true);
  m.def("get_max_quit_count", dpi_func_wrap(get_max_quit_count),
        "Gets the maximum quit count from the report server.");
  m.def("set_quit_count", dpi_func_wrap(set_quit_count),
        "Sets the current quit count in the report server.",
        py::arg("quit_count"));
  m.def("get_quit_count", dpi_func_wrap(get_quit_count),
        "Gets the current quit count from the report server.");
  m.def("set_severity_count", dpi_func_wrap(set_severity_count),
        "Sets the count for a specific severity level.", py::arg("severity"),
        py::arg("count"));
  m.def("get_severity_count", dpi_func_wrap(get_severity_count),
        "Gets the count for a specific severity level.", py::arg("severity"));
  m.def("set_id_count", dpi_func_wrap(set_id_count),
        "Sets the count for a specific message ID.", py::arg("id"),
        py::arg("count"));
  m.def("get_id_count", dpi_func_wrap(get_id_count),
        "Gets the count for a specific message ID.", py::arg("id"));
  m.def("print_report_server", dpi_func_wrap(print_report_server),
        "Prints the current report server information.");
  m.def("report_summarize", dpi_func_wrap(report_summarize),
        "Generates a summary of all reports.");
  // 寄存器相关函数绑定
  m.def("write_reg", dpi_func_wrap(write_reg), "write register");
  m.def("read_reg", dpi_func_wrap(wrap_read_reg),
        "read register"); // 注意：wrap_read_reg 已经是函数包装
  m.def("check_reg", dpi_func_wrap(check_reg), "check register",
        py::arg("name"), py::arg("data") = 0, py::arg("predict") = 0);
  m.def("start_seq", dpi_func_wrap(start_seq), "start seq on sqr",
        py::arg("seq_name"), py::arg("sqr_name"), py::arg("rand_en") = 1,
        py::arg("background") = 0);
  m.def("run_test", dpi_func_wrap(run_test_wrap), "uvm run test",
        py::arg("test_name"));
  m.def("wait_unit", dpi_func_wrap(wait_unit), "wait unit time");
  m.def("process_pool_run", dpi_func_wrap(process_pool_run), "process pool run",
        py::arg("name"));
  m.def("process_pool_clear", dpi_func_wrap(process_pool_clear),
        "process pool clear");
  m.def(
      "reset", []() { return vpi_control(vpiReset); }, "Reset the simulation");
  m.def(
      "stop", []() { return vpi_control(vpiStop); }, "Suspend the simulation");
  m.def(
      "finish", []() { return vpi_control(vpiFinish); },
      "Finished the simulation");
  m.def(
      "get_sim_time",
      [](const char *name) {
        uint64_t time;
#if defined(VCS) || defined(VCSMX)
        time = (uint64_t)tf_gettime();
#else
        s_vpi_time vpi_time_s;
        vpi_time_s.type = vpiSimTime;
        const svScope scope = svGetScopeFromName(name);
        svGetTime(scope, &vpi_time_s);
        time = (uint64_t)vpi_time_s.high << 32 | vpi_time_s.low;
#endif
        return time;
      },
      "Get the current simulation time, scaled to the time unit of the scope.");
  m.def(
      "get_timeunit",
      [](const char *name) {
        int32_t time_unit;
#if defined(VCS) || defined(VCSMX)
        time_unit = tf_gettimeunit();
#else
        const svScope scope = svGetScopeFromName(name);
        svGetTimeUnit(scope, &time_unit);
#endif
        return time_unit;
      },
      "Get the time unit for scope");
  m.def(
      "get_precision",
      [](const char *name) {
        int32_t precision;
#if defined(VCS) || defined(VCSMX)
        precision = tf_gettimeprecision();
#else
        const svScope scope = svGetScopeFromName(name);
        svGetTimePrecision(scope, &precision);
#endif
        return precision;
      },
      "Get time precision for scope");
}

void py_func(const char *mod_name, const char *func_name,
             const char *mod_paths) {

  std::optional<py::scoped_interpreter> interpreter;

  if (!Py_IsInitialized()) {
    interpreter.emplace();
  }

  py::gil_scoped_acquire gil;

  py::module_ sys = py::module_::import("sys");
  py::list path = sys.attr("path");

  py::module_ sysconfig = py::module_::import("sysconfig");
  std::string ext_suffix =
      sysconfig.attr("get_config_var")("EXT_SUFFIX").cast<std::string>();

#ifdef __linux__
  char *dir_path;
  FILE *maps = fopen("/proc/self/maps", "r");
  if (!maps) {
    perror("Failed to open /proc/self/maps");
    return;
  }

  char self_addr_str[20];
  snprintf(self_addr_str, sizeof(self_addr_str), "%p", (void *)py_func);

  char line[256];
  while (fgets(line, sizeof(line), maps)) {
    if (strstr(line, ext_suffix.c_str())) {
      char *sopath = strchr(line, '/');
      if (sopath) {
        sopath = strtok(sopath, "\n");
        fclose(maps);
        dir_path = dirname(sopath);
        path.attr("append")(dir_path);
        break;
      }
    }
  }
#elif defined(__APPLE__)
  //   char *dir_path;
  //   Dl_info dl_info;
  //   if (dladdr((void *)py_func, &dl_info)) {
  //     dir_path = dirname(dirname(const_cast<char *>(dl_info.dli_fname)));
  //     path.attr("append")(dir_path);
  //   }
  // Add the virtual environment site package path
  if (getenv("VIRTUAL_ENV")) {
    auto version_info = sysconfig.attr("get_config_var")("VERSION");
    std::string site_packages_path =
        std::string(getenv("VIRTUAL_ENV")) + "/lib/python" +
        version_info.cast<std::string>() + "/site-packages";
    ;
    path.attr("append")(site_packages_path);
  }
#else
#error Platform not supported.
#endif

  if (strcmp(mod_paths, "") != 0) {
    path.attr("append")(mod_paths);
  }
  py::print(path);
  py::module_ py_seq_mod = py::module_::import(mod_name);
  py_seq_mod.attr(func_name)();
}

void py_task(const char *mod_name, const char *func_name,
             const char *mod_paths) {
  py_func(mod_name, func_name, mod_paths);
}
}
