#include <dlfcn.h>
#include <libgen.h>
#include <pybind11/pybind11.h>
#include <pybind11/embed.h>
#include "svdpi.h"
#if defined(VCS) || defined(VCSMX)
    #include <mhpi_user.h>
#elif defined(XCELIUM) || defined(NCSC)
    #include <cfclib.h>         
#elif defined(MENTOR)
    #include <mti.h>            
#endif

extern "C" {

namespace py = pybind11;
#include "uvm_dpi.h"

void print_factory (int all_types=1);
void set_factory_inst_override(const char* original_type_name, const char* override_type_name, const char* full_inst_path);
void set_factory_type_override (const char* original_type_name, const char* override_type_name, bool replace=1);
void create_object_by_name (const char* requested_type,const char* context="",const char* name="");
void create_component_by_name (const char* requested_type,const char* context="",const char* name="",const char* parent_name="");
void debug_factory_create (const char* requested_type,const char* context="");
void find_factory_override (const char* requested_type, const char* context, const char* override_type_name);
void print_topology(const char* context="");
void set_timeout(long long timeout, unsigned char overridable=1);
void uvm_objection_op (const char* op, const char* name, const char* contxt, const char* description, unsigned int count);
void dbg_print(const char* name="");

#if defined(VCS) || defined(VCSMX) || defined(XCELIUM) || defined(NCSC)
void wait_on(const char* ev_name, int delta);
void wait_off(const char* ev_name, int delta);
void wait_trigger(const char* ev_name);
void wait_ptrigger(const char* ev_name);
// void wait_trigger_data(uvm_object *data, const char* ev_name);
// void wait_ptrigger_data(uvm_object *data, const char* ev_name);
uint64_t get_trigger_time(const char* ev_name);
int is_on(const char* ev_name);
int is_off(const char* ev_name);
void reset(const char* ev_name, int wakeup);
void cancel(const char* ev_name);
int get_num_waiters(const char* ev_name);
void trigger(const char* ev_name);
//uvm_object *get_trigger_data();
//uvm_object *get_default_data();
//void set_default_data(uvm_object *data);
#endif

void set_config_int(const char*  contxt, const char*  inst_name, const char*  field_name, uint64_t value);
uint64_t get_config_int(const char*  contxt, const char*  inst_name, const char*  field_name);
void set_config_string(const char*  contxt, const char*  inst_name, const char*  field_name, const char* value);
const char* get_config_string(const char*  contxt, const char*  inst_name, const char*  field_name);

#if defined(VCS) || defined(VCSMX) || defined(XCELIUM) || defined(NCSC)
// 使用pybind11创建的包装器函数
void wrap_walk_level(int lvl, std::vector<std::string> args, int cmd) {
    // Convert Python string list to C-style char**
    std::vector<char*> c_args;
    for (const auto& arg : args) {
        c_args.push_back(const_cast<char*>(arg.c_str()));
    }
    char** argv = c_args.data();
    int argc = static_cast<int>(args.size());

    // Call the original function
    walk_level(lvl, argc, argv, cmd);
}
#endif

void start_seq(const char* seq_name, const char* sqr_name);
void write_reg(const char* name, int data);
void read_reg(const char* name, int *data);
void check_reg(const char* name, int data=0, unsigned char predict=0);
void run_test_wrap(const char* test_name="");
void wait_unit(int n);
void stop();

int wrap_read_reg(const char* name) {
    int data;
    read_reg(name, &data);
    return data;
}

// execute a tcl comamnd in simulator
void exec_tcl_cmd(char* cmd) {
    #if defined(VCS) || defined(VCSMX)
        mhpi_ucliTclExec(cmd);
    #elif defined(XCELIUM) || defined(NCSC) 
        cfcExecuteCommand(cmd);
    #elif defined(MENTOR)
        mti_Cmd(cmd);
    #else
        // not supported
        printf("tcl intregation is not support in this simulator\n");
    #endif
};

PYBIND11_MODULE(svuvm, m) {
    m.doc() = "svuvm api module";

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

#if defined(VCS) || defined(VCSMX) || defined(XCELIUM) || defined(NCSC)
    // Binding functions

    py::class_<s_vpi_vecval>(m, "VpiVecVal")
        .def(py::init<>())  // 默认构造函数
        .def(py::init([](uint32_t aval, uint32_t bval){
            s_vpi_vecval s;
            s.aval = aval;
            s.bval = bval;
            return s;
        }), py::arg("aval") = 0, py::arg("bval") = 0)
        .def_readwrite("aval", &s_vpi_vecval::aval)
        .def_readwrite("bval", &s_vpi_vecval::bval);

    m.def("uvm_report", &m_uvm_report_dpi, "report function", py::arg("severity"), py::arg("id"), py::arg("message"), py::arg("verbosity"), py::arg("file"), py::arg("linenum"));

    m.def("int_str_max", &int_str_max, "Find the maximum of integers represented as strings.");

    m.def("uvm_re_match", &uvm_re_match, "Match a regular expression against a string.",
          py::arg("re"), py::arg("str"));

    m.def("uvm_glob_to_re", &uvm_glob_to_re, "Convert a glob pattern into a regular expression.",
          py::return_value_policy::reference);

    m.def("uvm_hdl_check_path", &uvm_hdl_check_path, "Check if a path exists in the HDL model.",
          py::arg("path"));

    m.def("uvm_hdl_read", &uvm_hdl_read, "Read data from a path in the HDL model.",
          py::arg("path"), py::arg("value"));

    m.def("uvm_hdl_deposit", &uvm_hdl_deposit, "Deposit data at a path in the HDL model.",
          py::arg("path"), py::arg("value"));

    m.def("uvm_hdl_force", &uvm_hdl_force, "Force a value at a path in the HDL model.",
          py::arg("path"), py::arg("value"));

    m.def("uvm_hdl_release_and_read", &uvm_hdl_release_and_read, "Release and read data from a path in the HDL model.",
          py::arg("path"), py::arg("value"));

    m.def("uvm_hdl_release", &uvm_hdl_release, "Release a path in the HDL model.",
          py::arg("path"));

    m.def("push_data", &push_data, "Push data to a specified level.",
          py::arg("lvl"), py::arg("entry"), py::arg("cmd"));

    m.def("walk_level", &wrap_walk_level, "Walk through a hierarchy at a given level.",
          py::arg("lvl"), py::arg("argv"), py::arg("cmd"));

    m.def("uvm_dpi_get_next_arg_c", &uvm_dpi_get_next_arg_c, "Get the next argument from the command line.",
          py::arg("init"));

    m.def("uvm_dpi_get_tool_name_c", &uvm_dpi_get_tool_name_c, "Get the name of the current tool.",
          py::return_value_policy::reference);

    m.def("uvm_dpi_get_tool_version_c", &uvm_dpi_get_tool_version_c, "Get the version of the current tool.",
          py::return_value_policy::reference);

    m.def("uvm_dpi_regcomp", &uvm_dpi_regcomp, "Compile a regular expression.",
          py::arg("pattern"), py::return_value_policy::take_ownership);

    m.def("uvm_dpi_regexec", &uvm_dpi_regexec, "Execute a compiled regular expression against a string.",
          py::arg("re"), py::arg("str"));

    m.def("uvm_dpi_regfree", &uvm_dpi_regfree, "Free a compiled regular expression.",
          py::arg("re"));

    m.def("exec_tcl_cmd", &exec_tcl_cmd, "Execute a tcl command.", py::arg("cmd"));
#endif

    m.def("print_factory", &print_factory, "Prints factory information.", py::arg("all_types")=1);

    m.def("set_factory_inst_override", &set_factory_inst_override,
          "Sets an instance override in the factory.", 
          py::arg("original_type_name"), py::arg("override_type_name"), py::arg("full_inst_path"));

    m.def("set_factory_type_override", &set_factory_type_override,
          "Sets a type override in the factory.", 
          py::arg("original_type_name"), py::arg("override_type_name"), py::arg("replace")=true);

    m.def("debug_factory_create", &debug_factory_create,
          "Debugs the creation of a factory object.", 
          py::arg("requested_type"), py::arg("context")="");

    m.def("create_object_by_name", &create_object_by_name,
          "create a uvm object.", 
          py::arg("requested_type"), py::arg("context")="", py::arg("name")="");

    m.def("create_component_by_name", &create_component_by_name,
          "create a uvm object.", 
          py::arg("requested_type"), py::arg("context")="", py::arg("parent_name")="", py::arg("name")="");

    m.def("find_factory_override", &find_factory_override,
          "Finds an override for a given factory type.", 
          py::arg("requested_type"), py::arg("context"), py::arg("override_type_name"));

    m.def("print_topology", &print_topology,
          "Prints the topology.", 
          py::arg("context")="");

    m.def("set_timeout", &set_timeout, "Set the timeout value.", py::arg("timeout"), py::arg("overridable")=1);

    m.def("uvm_objection_op", &uvm_objection_op, "uvm_objection_op", py::arg("op"), py::arg("name"), py::arg("contxt"), py::arg("description"), py::arg("delta")=0);

    m.def("dbg_print", &dbg_print,
          "Prints the object.", 
          py::arg("name")="");

#if defined(VCS) || defined(VCSMX) || defined(XCELIUM) || defined(NCSC)
    // uvm event
    m.def("wait_on", &wait_on, "Wait until the signal is on", py::arg("ev_name"), py::arg("delta") = 0);
    m.def("wait_off", &wait_off, "Wait until the signal is off", py::arg("ev_name"), py::arg("delta") = 0);
    m.def("wait_trigger", &wait_trigger, "Wait for the trigger event", py::arg("ev_name"));
    m.def("wait_ptrigger", &wait_ptrigger, "Wait for the positive trigger event", py::arg("ev_name"));
    m.def("get_trigger_time", &get_trigger_time, "Get the time of the last trigger event", py::arg("ev_name"));
    m.def("is_on", &is_on, "Check if the signal is on", py::arg("ev_name"));
    m.def("is_off", &is_off, "Check if the signal is off", py::arg("ev_name"));
    m.def("reset", &reset, "Reset the signal state", py::arg("ev_name"), py::arg("wakeup") = 0);
    m.def("cancel", &cancel, "Cancel the current wait operation", py::arg("ev_name"));
    m.def("get_num_waiters", &get_num_waiters, "Get the number of waiters", py::arg("ev_name"));
    m.def("trigger", &trigger, "Trigger the event", py::arg("ev_name"));
#endif
    // config db
    m.def("set_config_int", &set_config_int, "Set integer configuration in the UVM environment");
    m.def("get_config_int", &get_config_int, "Get integer configuration from the UVM environment");
    m.def("set_config_string", &set_config_string, "Set string configuration in the UVM environment");
    m.def("get_config_string", &get_config_string, "Get string configuration from the UVM environment");


    m.def("write_reg", &write_reg, "write register");
    m.def("read_reg", &wrap_read_reg, "read register");
    m.def("check_reg", &check_reg, "check register", py::arg("name"), py::arg("data")=0, py::arg("predict")=0);
    m.def("start_seq", &start_seq, "start seq on sqr");
    m.def("run_test", &run_test_wrap, "uvm run test", py::arg("test_name"));
    m.def("wait_unit", &wait_unit, "wait unit time");
    m.def("stop", &stop, "suspend the simulation");

}

void py_func(const char* mod_name, const char* func_name, const char* mod_paths) {
    char *dir_path;
    py::scoped_interpreter guard{}; // start the interpreter and keep it alive

    py::module_ sys = py::module_::import("sys");
    py::list path = sys.attr("path");

    py::module_ sysconfig = py::module_::import("sysconfig");
    std::string ext_suffix = sysconfig.attr("get_config_var")("EXT_SUFFIX").cast<std::string>();

#ifdef __linux__
    FILE* maps = fopen("/proc/self/maps", "r");
    if (!maps) {
        perror("Failed to open /proc/self/maps");
        return;
    }

    char self_addr_str[20];
    snprintf(self_addr_str, sizeof(self_addr_str), "%p", (void*)py_func);

    char line[256];
    while (fgets(line, sizeof(line), maps)) {
        if (strstr(line, ext_suffix.c_str())) {
            char* sopath = strchr(line, '/');
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
    Dl_info dl_info;
    if (dladdr((void*)py_func, &dl_info)) {
        dir_path = dirname(dirname(const_cast<char*>(dl_info.dli_fname)));
        path.attr("append")(dir_path);
    }
#else
#error Platform not supported.
#endif

    if(strcmp(mod_paths, "") != 0) {
        path.attr("append")(mod_paths);
    }
    py::print(path);
    py::module_ py_seq_mod = py::module_::import(mod_name);
    py_seq_mod.attr(func_name)();
}

}
