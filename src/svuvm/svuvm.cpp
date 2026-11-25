#include "svdpi.h"
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <iostream>
#include <libgen.h>
#include <nanobind/nanobind.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/vector.h>
#include <stdexcept>
#include <tuple>

namespace nb = nanobind;

// Own a heap array allocated for an s_vpi_arrayvalue union member with a
// nanobind capsule, so it is freed when the Python wrapper dies (or when a
// setter replaces it). The old code used bare new[] with no owner and leaked
// the buffer on every construct/overwrite.
template <typename T>
static nb::capsule make_array_owner(T *p) {
  return nb::capsule(p, [](void *q) noexcept {
    delete[] static_cast<T *>(q);
  });
}

// DPI 导出函数声明（供 SystemVerilog 调用）

#ifndef NO_VPI
#include "vpi_user_wrap.h"

// IEEE 1800-2023 Table 38-3: these formats store a NUL-terminated char* in
// s_vpi_value.value.str. Used both to guard the .str getter and to clear a
// stale non-pointer arm when `format` is switched to a string format.
inline bool is_string_value_format(PLI_INT32 format) {
  return format == vpiStringVal || format == vpiBinStrVal ||
         format == vpiOctStrVal || format == vpiDecStrVal ||
         format == vpiHexStrVal;
}
#endif

// 运行时仿真器检测
namespace simulator {
enum class Simulator { UNKNOWN, VCS, VCSMX, XCELIUM, NCSC, MENTOR, VERILATOR };

// 检测仿真器类型的函数
inline Simulator detect() {
  // 首先尝试通过 VPI 获取仿真器信息
#ifndef NO_VPI
  s_vpi_vlog_info info;
  if (vpi_get_vlog_info(&info)) {
    std::string product = info.product ? info.product : "";
    std::string version = info.version ? info.version : "";

    // 根据产品字符串判断仿真器类型
    if (product.find("VCS") != std::string::npos) {
      return Simulator::VCS;
    } else if (product.find("Xcelium") != std::string::npos ||
               product.find("IES") != std::string::npos) {
      return Simulator::XCELIUM;
    } else if (product.find("Questa") != std::string::npos ||
               product.find("ModelSim") != std::string::npos) {
      return Simulator::MENTOR;
    } else if (product.find("Verilator") != std::string::npos) {
      return Simulator::VERILATOR;
    }
  }
#endif

  // 如果 VPI 方法失败，尝试环境变量
  const char *sim_env = std::getenv("SIMULATOR");
  if (sim_env) {
    std::string sim_name(sim_env);
    if (sim_name == "vcs")
      return Simulator::VCS;
    if (sim_name == "vcsmx")
      return Simulator::VCSMX;
    if (sim_name == "xcelium")
      return Simulator::XCELIUM;
    if (sim_name == "ncsc")
      return Simulator::NCSC;
    if (sim_name == "mentor" || sim_name == "questa")
      return Simulator::MENTOR;
    if (sim_name == "verilator")
      return Simulator::VERILATOR;
  }

  // 检查特定的环境变量
  if (std::getenv("VCS_HOME"))
    return Simulator::VCS;
  if (std::getenv("XCELIUM_HOME"))
    return Simulator::XCELIUM;
  if (std::getenv("QUESTA_HOME") || std::getenv("MGC_HOME"))
    return Simulator::MENTOR;
  if (std::getenv("VERILATOR_ROOT"))
    return Simulator::VERILATOR;

  return Simulator::UNKNOWN;
}

// 辅助函数
inline bool is_vcs() {
  Simulator t = detect();
  return t == Simulator::VCS || t == Simulator::VCSMX;
}

inline bool is_xcelium() {
  Simulator t = detect();
  return t == Simulator::XCELIUM || t == Simulator::NCSC;
}

inline bool is_mentor() { return detect() == Simulator::MENTOR; }

inline bool is_verilator() { return detect() == Simulator::VERILATOR; }
} // namespace simulator

// 条件编译时仍然包含必要的头文件，但会在运行时选择使用

template <typename Func> auto dpi_func_wrap(Func func) {
  // 使用 std::remove_pointer 去除函数指针的指针，获取函数类型
  using FuncPointerType = std::decay_t<Func>;
  using FuncType = std::remove_pointer_t<FuncPointerType>;
  return std::function<FuncType>([func](auto &&...args) {
    svSetScope(svGetScopeFromName("python_bridge_pkg"));
    // A suspendable DPI export task hands control back to the Verilator
    // scheduler (VlDpiCall::stopWorker) and blocks this worker until the SV
    // task finishes. While the scheduler is running it may start another
    // imported task on a different worker, which needs the GIL to enter
    // Python. Release the GIL across the DPI call so those workers cannot
    // deadlock on it; it is re-acquired before nanobind converts the result.
    nb::gil_scoped_release no_gil;
    return func(std::forward<decltype(args)>(args)...);
  });
}

extern "C" {
#include "export_dpi.h"
#include "uvm_dpi.h"

void wrap_walk_level(int lvl, std::vector<std::string> args, int cmd) {
  std::vector<char *> c_args;
  for (const auto &arg : args) {
    c_args.push_back(const_cast<char *>(arg.c_str()));
  }
  char **argv = c_args.data();
  int argc = static_cast<int>(args.size());
  walk_level(lvl, argc, argv, cmd);
}

} // extern "C"

void wrap_uvm_report(const char *message, int verbosity, int severity) {
  try {
    nb::object inspect = nb::module_::import_("inspect");
    nb::object current_frame = inspect.attr("currentframe")();

    if (!current_frame.is_none()) {
      std::string funcname =
          nb::cast<std::string>(current_frame.attr("f_code").attr("co_name"));
      std::string filename = nb::cast<std::string>(
          current_frame.attr("f_code").attr("co_filename"));
      int lineno = nb::cast<int>(current_frame.attr("f_lineno"));

      // Explicitly clear the frame reference to break reference cycles
      current_frame = nb::none();

      m_uvm_report_dpi(severity, const_cast<char *>(funcname.c_str()),
                       const_cast<char *>(message), verbosity,
                       const_cast<char *>(filename.c_str()), lineno);
    } else {
      std::cout << "currentframe is not available!" << std::endl;
    }
  } catch (const std::exception &e) {
    std::cerr << "Error in wrap_uvm_report: " << e.what() << std::endl;
    // Fallback to basic reporting without frame info
    m_uvm_report_dpi(severity, const_cast<char *>("unknown_function"),
                     const_cast<char *>(message), verbosity,
                     const_cast<char *>("unknown_file"), 0);
  }
}

int wrap_read_reg(const char *name) {
  int data;
  read_reg(const_cast<char *>(name), &data);
  return data;
}

int wrap_mirror_reg(const char *name, int check) {
  int data;
  mirror_reg(const_cast<char *>(name), check, &data);
  return data;
}

// execute a tcl command in simulator
const char *exec_tcl_cmd(const char *cmd) {
  static simulator::Simulator sim = simulator::detect();

  switch (sim) {
  case simulator::Simulator::VCSMX:
  case simulator::Simulator::VCS: {
    static auto func =
        (char *(*)(char *))dlsym(RTLD_DEFAULT, "mhpi_ucliTclExec");
    return func ? func(const_cast<char *>(cmd)) : "";
  }
  case simulator::Simulator::XCELIUM:
  case simulator::Simulator::NCSC: {
    static auto exec =
        (void (*)(char *))dlsym(RTLD_DEFAULT, "cfcExecuteCommand");
    static auto get_out = (char *(*)(void))dlsym(RTLD_DEFAULT, "cfcGetOutput");
    if (exec)
      exec(const_cast<char *>(cmd));
    return get_out ? get_out() : "";
  }
  case simulator::Simulator::MENTOR: {
    static auto func = (void (*)(char *))dlsym(RTLD_DEFAULT, "mti_Cmd");
    if (func)
      func(const_cast<char *>(cmd));
    return "";
  }
  default:
    fprintf(stderr,
            "TCL integration not supported in this simulator (type: %d)\n",
            static_cast<int>(sim));
    return "";
  }
}

NB_MODULE(_svuvm, m) {
  m.doc() = "svuvm api module";

#ifndef NO_VPI
  // VPI wrapper
  nb::module_ vpi = m.def_submodule("vpi", "VPI interface submodule");

// vpi handle types
#include <vpi_attr.h>
  // datatypes
  nb::class_<s_vpi_time>(vpi, "VpiTime")
      // IEEE 1800: s_vpi_time.type must be vpiScaledRealTime (1) or
      // vpiSimTime (2); 0 is reserved/illegal and both backends reject or
      // misread it. nanobind's nb::init<> would zero-initialise the struct,
      // so use an explicit __init__ that installs the legal default and
      // clears all remaining fields.
      .def("__init__", [](s_vpi_time *self) {
        self->type = vpiSimTime;
        self->high = 0;
        self->low = 0;
        self->real = 0.0;
      })
      .def(nb::init<PLI_INT32, PLI_UINT32, PLI_UINT32, double>(),
           nb::arg("type") = vpiSimTime, nb::arg("high") = 0,
           nb::arg("low") = 0, nb::arg("real") = 0.0)
      .def_rw("type", &s_vpi_time::type)
      .def_rw("high", &s_vpi_time::high)
      .def_rw("low", &s_vpi_time::low)
      .def_rw("real", &s_vpi_time::real);

  nb::class_<s_vpi_delay>(vpi, "VpiDelay", nb::dynamic_attr())
      // IEEE 1800: s_vpi_time.type must be vpiSimTime (2) or
      // vpiScaledRealTime (1); 0 is illegal. nb::init<> would zero the struct
      // and hand the simulator an invalid time_type, so install the legal
      // default explicitly (same pattern as VpiTime above). da stays nullptr.
      .def("__init__", [](s_vpi_delay *self) {
        self->da = nullptr;
        self->no_of_delays = 0;
        self->time_type = vpiSimTime;
        self->mtm_flag = 0;
        self->append_flag = 0;
        self->pulsere_flag = 0;
      })
      .def(
          "__init__",
          [](s_vpi_delay *self, nb::object da_obj, int no_of_delays,
             int time_type, int mtm_flag, int append_flag,
             int pulsere_flag) {
            self->da = da_obj.is_none()
                           ? nullptr
                           : (p_vpi_time)nb::cast<nb::capsule>(da_obj).data();
            self->no_of_delays = no_of_delays;
            self->time_type = time_type;
            self->mtm_flag = mtm_flag;
            self->append_flag = append_flag;
            self->pulsere_flag = pulsere_flag;
          },
          nb::arg("da"), nb::arg("no_of_delays"),
          nb::arg("time_type") = vpiSimTime,
          nb::arg("mtm_flag") = 0, nb::arg("append_flag") = 0,
          nb::arg("pulsere_flag") = 0,
          // da is a caller-owned array; keep the capsule alive so the pointer
          // stored in s_vpi_delay.da stays valid (self=1, da_obj=2).
          nb::keep_alive<1, 2>())
      .def_rw("no_of_delays", &s_vpi_delay::no_of_delays)
      .def_rw("time_type", &s_vpi_delay::time_type)
      .def_rw("mtm_flag", &s_vpi_delay::mtm_flag)
      .def_rw("append_flag", &s_vpi_delay::append_flag)
      .def_rw("pulsere_flag", &s_vpi_delay::pulsere_flag)
      // IEEE 1800 38.10: s_vpi_delay.da is a *caller-allocated* array of
      // no_of_delays s_vpi_time entries. A default-constructed VpiDelay has
      // da == nullptr, which every conforming simulator (including xezim and
      // Verilator) rejects with "null da array". alloc_da(n) allocates that
      // array, stores it in da, and keeps it alive on the Python object via a
      // capsule attribute so the pointer stays valid for vpi_get/put_delays.
      .def("alloc_da", [](nb::object self, int n) {
        s_vpi_delay &o = nb::cast<s_vpi_delay &>(self);
        if (n < 0) {
          throw std::invalid_argument("alloc_da: negative count");
        }
        auto *arr = new s_vpi_time[static_cast<size_t>(n)]();
        nb::capsule holder(arr, [](void *p) noexcept {
          delete[] static_cast<s_vpi_time *>(p);
        });
        self.attr("_da_owner") = holder;
        o.da = arr;
        o.no_of_delays = n;
      }, nb::arg("n"))
      // Read back one delay entry after vpi_get_delays so tests can assert
      // the simulator actually filled the caller-allocated array.
      .def("get_da_time", [](s_vpi_delay &o, int i) {
        if (o.da == nullptr || i < 0 || i >= o.no_of_delays) {
          throw std::out_of_range("get_da_time: index out of range");
        }
        s_vpi_time &t = o.da[i];
        return std::make_tuple(t.type, t.high, t.low, t.real);
      }, nb::arg("i"))
      .def("get_da", [](s_vpi_delay &o) { return convert((vpiHandle)o.da); })
      .def("set_da", [](s_vpi_delay &o, nb::object obj) {
        o.da = (p_vpi_time)nb::cast<nb::capsule>(obj).data();
      }, nb::arg("obj"), nb::keep_alive<1, 2>());

  nb::class_<s_vpi_vecval>(vpi, "VpiVecVal")
      .def(nb::init<>())
      .def(nb::init<PLI_UINT32, PLI_UINT32>(), nb::arg("aval") = 0,
           nb::arg("bval") = 0)
      .def_rw("aval", &s_vpi_vecval::aval)
      .def_rw("bval", &s_vpi_vecval::bval);

  nb::class_<s_vpi_strengthval>(vpi, "VpiStrengthVal")
      .def(nb::init<>())
      .def(nb::init<PLI_INT32, PLI_INT32, PLI_INT32>(), nb::arg("logic") = 0,
           nb::arg("s0") = 0, nb::arg("s1") = 0)
      .def_rw("logic", &s_vpi_strengthval::logic)
      .def_rw("s0", &s_vpi_strengthval::s0)
      .def_rw("s1", &s_vpi_strengthval::s1);

  nb::class_<s_vpi_value>(vpi, "VpiValue")
      .def(nb::init<>())
      .def(
          "__init__",
          [](s_vpi_value *self, PLI_INT32 format) {
            // See the other constructors: no implicit zero-init for a custom
            // __init__, and IEEE 1800-2023 38.15 says only the format-selected
            // union member is valid.
            *self = s_vpi_value{};
            self->format = format;
          },
          nb::arg("format"))
      .def(
          "__init__",
          [](s_vpi_value *self, PLI_INT32 format, nb::str str) {
            // A custom __init__ does NOT get nanobind's zero-initialisation:
            // zero the whole struct first so the union never holds garbage
            // that a getter for a mismatched arm would dereference.
            *self = s_vpi_value{};
            self->format = format;
            // nb::str::c_str() is PyUnicode_AsUTF8AndSize(): the UTF-8 buffer
            // lives inside the Python str object and stays valid as long as
            // that object does. keep_alive<1,3> below ties the str argument
            // (index 3: self=1, format=2, value=3) to this VpiValue instance,
            // so value.str never dangles. A const std::string& parameter would
            // be a type caster: its temporary dies on return and keep_alive
            // cannot help (it only tracks Python objects).
            self->value.str = const_cast<char *>(str.c_str());
          },
          nb::arg("format"), nb::arg("value"), nb::keep_alive<1, 3>())
      // IEEE 1800: `format` decides which union member is valid. Only
      // vpiIntVal / vpiScalarVal / vpiRealVal can be built from a plain
      // Python scalar. Pointer/string formats have dedicated constructors;
      // writing `integer` for them would make the simulator interpret an
      // integer as a pointer (wild-pointer crash). Reject every other
      // format, including the s_vpi_arrayvalue-only short/long/shortreal
      // formats which are not members of this union at all. The C++
      // parameter type still selects the overload (Python int -> PLI_INT32,
      // Python float -> double), preserving VpiValue(vpiRealVal, 5).real
      // == 5.0 and VpiValue(vpiIntVal, 5.5).integer == 5.
      .def(
          "__init__",
          [](s_vpi_value *self, PLI_INT32 format, PLI_INT32 val) {
            // A custom __init__ does NOT get nanobind's zero-initialisation:
            // zero the whole struct first so the union never holds garbage
            // that a getter for a mismatched arm would dereference.
            *self = s_vpi_value{};
            self->format = format;
            switch (format) {
            case vpiRealVal:
              self->value.real = static_cast<double>(val);
              break;
            case vpiIntVal:
              self->value.integer = val;
              break;
            case vpiScalarVal:
              self->value.scalar = val;
              break;
            default:
              throw std::invalid_argument(
                  "VpiValue: scalar value not valid for this format");
            }
          },
          nb::arg("format"), nb::arg("value"))
      .def(
          "__init__",
          [](s_vpi_value *self, PLI_INT32 format, double val) {
            // A custom __init__ does NOT get nanobind's zero-initialisation:
            // zero the whole struct first so the union never holds garbage
            // that a getter for a mismatched arm would dereference.
            *self = s_vpi_value{};
            self->format = format;
            switch (format) {
            case vpiRealVal:
              self->value.real = val;
              break;
            case vpiIntVal:
              self->value.integer = static_cast<PLI_INT32>(val);
              break;
            case vpiScalarVal:
              self->value.scalar = static_cast<PLI_INT32>(val);
              break;
            default:
              throw std::invalid_argument(
                  "VpiValue: scalar value not valid for this format");
            }
          },
          nb::arg("format"), nb::arg("value"))
      .def(
          "__init__",
          [](s_vpi_value *self, PLI_INT32 format, nb::object obj) {
            // A custom __init__ does NOT get nanobind's zero-initialisation:
            // zero the whole struct first so the union never holds garbage
            // that a getter for a mismatched arm would dereference.
            *self = s_vpi_value{};
            self->format = format;
            self->value.time = (p_vpi_time)nb::cast<nb::capsule>(obj).data();
          },
          nb::arg("format"), nb::arg("value"), nb::keep_alive<1, 3>())
      .def(
          "__init__",
          [](s_vpi_value *self, PLI_INT32 format, nb::object obj) {
            // A custom __init__ does NOT get nanobind's zero-initialisation:
            // zero the whole struct first so the union never holds garbage
            // that a getter for a mismatched arm would dereference.
            *self = s_vpi_value{};
            self->format = format;
            self->value.vector = (p_vpi_vecval)nb::cast<nb::capsule>(obj).data();
          },
          nb::arg("format"), nb::arg("value"), nb::keep_alive<1, 3>())
      .def(
          "__init__",
          [](s_vpi_value *self, PLI_INT32 format, nb::object obj) {
            // A custom __init__ does NOT get nanobind's zero-initialisation:
            // zero the whole struct first so the union never holds garbage
            // that a getter for a mismatched arm would dereference.
            *self = s_vpi_value{};
            self->format = format;
            self->value.strength =
                (p_vpi_strengthval)nb::cast<nb::capsule>(obj).data();
          },
          nb::arg("format"), nb::arg("value"), nb::keep_alive<1, 3>())
      .def_prop_rw(
          "format", [](const s_vpi_value &o) { return o.format; },
          [](s_vpi_value &o, PLI_INT32 fmt) {
            // IEEE 1800-2023 38.15: format selects the valid union arm. When
            // Python switches from a scalar arm (e.g. integer == 5) to a
            // string format, the old bits would be read as a char* by the
            // .str getter and dereferenced as address 0x5. The old arm is no
            // longer meaningful under the new format, so clear the union.
            if (fmt != o.format && is_string_value_format(fmt) &&
                !is_string_value_format(o.format)) {
              std::memset(&o.value, 0, sizeof(o.value));
            }
            o.format = fmt;
          })
      .def_prop_rw(
          "str",
          [](const s_vpi_value &o) {
            // IEEE 1800-2023 38.15 / Table 38-3: the union arm is only
            // meaningful when `format` selects it. Reading .str after an
            // int-format construction (or after mutating `format`) used to
            // dereference garbage. Guard by the string formats and return an
            // empty string for every other format.
            if (!is_string_value_format(o.format) ||
                o.value.str == nullptr) {
              return std::string();
            }
            return std::string(o.value.str);
          },
          [](s_vpi_value &o, nb::str s) {
            // See the constructor: keep the Python str alive for as long as
            // this instance so the pointer we store into value.str is stable.
            o.value.str = const_cast<char *>(s.c_str());
          },
          nb::for_setter(nb::keep_alive<1, 2>()))
      .def_prop_rw(
          "scalar", [](s_vpi_value &o) { return o.value.scalar; },
          [](s_vpi_value &o, PLI_INT32 val) { o.value.scalar = val; })
      .def_prop_rw(
          "integer", [](s_vpi_value &o) { return o.value.integer; },
          [](s_vpi_value &o, PLI_INT32 val) { o.value.integer = val; })
      .def_prop_rw(
          "real", [](s_vpi_value &o) { return o.value.real; },
          [](s_vpi_value &o, double val) { o.value.real = val; })
      .def_prop_rw(
          "time",
          [](s_vpi_value &o) { return convert((vpiHandle)o.value.time); },
          [](s_vpi_value &o, nb::object obj) {
            o.value.time = (p_vpi_time)nb::cast<nb::capsule>(obj).data();
          },
          nb::for_setter(nb::keep_alive<1, 2>()))
      .def_prop_rw(
          "vector",
          [](s_vpi_value &o) { return convert((vpiHandle)o.value.vector); },
          [](s_vpi_value &o, nb::object obj) {
            o.value.vector = (p_vpi_vecval)nb::cast<nb::capsule>(obj).data();
          },
          nb::for_setter(nb::keep_alive<1, 2>()))
      .def_prop_rw(
          "strength",
          [](s_vpi_value &o) { return convert((vpiHandle)o.value.strength); },
          [](s_vpi_value &o, nb::object obj) {
            o.value.strength =
                (p_vpi_strengthval)nb::cast<nb::capsule>(obj).data();
          },
          nb::for_setter(nb::keep_alive<1, 2>()));

  // The constructors below allocate the union's array on the heap. Keep that
  // memory owned by a capsule stored on the Python object (_buf_owner) and
  // record its element count (_buf_len). This fixes two bugs in the old code:
  //   (1) bare new[] with no owner leaked on every construct and on every
  //       setter overwrite (verified: 50k x 1000 ints leaked ~196 MB);
  //   (2) get_integers_values(n) read past the allocation with no upper bound
  //       (verified: reading 100000 from a 3-element buffer returned garbage).
  nb::class_<s_vpi_arrayvalue>(vpi, "VpiArrayValue", nb::dynamic_attr())
      .def(nb::init<>())
      // A single constructor dispatches on `format`. Previously there were
      // 8 overloads distinguished only by the C++ element type of a Python
      // list; nanobind resolves those in registration order, so every integer
      // list hit vector<PLI_INT32> and every float list hit vector<double>
      // (shortint/longint/byte/shortreal/... were unreachable). That mismatched
      // the union member width with the advertised format, making the
      // simulator read the buffer with the wrong element stride. The format
      // argument is authoritative per IEEE 1800, so use it to pick the type.
      .def(
          "__init__",
          [](s_vpi_arrayvalue *self, unsigned int format, unsigned int flags,
             nb::object values) {
            nb::object py = nb::cast(self);
            auto &o = *self;
            o.format = format;
            o.flags = flags;
            switch (format) {
              case vpiIntVal: {
                auto v = nb::cast<std::vector<PLI_INT32>>(values);
                auto *p = new PLI_INT32[v.size()];
                for (size_t i = 0; i < v.size(); ++i) p[i] = v[i];
                o.value.integers = p;
                py.attr("_buf_owner") = make_array_owner(p);
                py.attr("_buf_len") = (long long)v.size();
                break;
              }
              case vpiShortIntVal: {
                auto v = nb::cast<std::vector<PLI_INT16>>(values);
                auto *p = new PLI_INT16[v.size()];
                for (size_t i = 0; i < v.size(); ++i) p[i] = v[i];
                o.value.shortints = p;
                py.attr("_buf_owner") = make_array_owner(p);
                py.attr("_buf_len") = (long long)v.size();
                break;
              }
              case vpiLongIntVal: {
                auto v = nb::cast<std::vector<PLI_INT64>>(values);
                auto *p = new PLI_INT64[v.size()];
                for (size_t i = 0; i < v.size(); ++i) p[i] = v[i];
                o.value.longints = p;
                py.attr("_buf_owner") = make_array_owner(p);
                py.attr("_buf_len") = (long long)v.size();
                break;
              }
              case vpiRawTwoStateVal:
              case vpiRawFourStateVal: {
                // PLI_BYTE8 is char; nanobind treats vector<char> as bytes and
                // will not accept a Python list of ints. Go through vector<int>.
                auto v = nb::cast<std::vector<int>>(values);
                auto *p = new PLI_BYTE8[v.size()];
                for (size_t i = 0; i < v.size(); ++i)
                  p[i] = static_cast<PLI_BYTE8>(v[i]);
                o.value.rawvals = p;
                py.attr("_buf_owner") = make_array_owner(p);
                py.attr("_buf_len") = (long long)v.size();
                break;
              }
              case vpiVectorVal: {
                auto v = nb::cast<std::vector<s_vpi_vecval>>(values);
                auto *p = new s_vpi_vecval[v.size()];
                for (size_t i = 0; i < v.size(); ++i) p[i] = v[i];
                o.value.vectors = p;
                py.attr("_buf_owner") = make_array_owner(p);
                py.attr("_buf_len") = (long long)v.size();
                break;
              }
              case vpiTimeVal: {
                auto v = nb::cast<std::vector<s_vpi_time>>(values);
                auto *p = new s_vpi_time[v.size()];
                for (size_t i = 0; i < v.size(); ++i) p[i] = v[i];
                o.value.times = p;
                py.attr("_buf_owner") = make_array_owner(p);
                py.attr("_buf_len") = (long long)v.size();
                break;
              }
              case vpiRealVal: {
                auto v = nb::cast<std::vector<double>>(values);
                auto *p = new double[v.size()];
                for (size_t i = 0; i < v.size(); ++i) p[i] = v[i];
                o.value.reals = p;
                py.attr("_buf_owner") = make_array_owner(p);
                py.attr("_buf_len") = (long long)v.size();
                break;
              }
              case vpiShortRealVal: {
                auto v = nb::cast<std::vector<float>>(values);
                auto *p = new float[v.size()];
                for (size_t i = 0; i < v.size(); ++i) p[i] = v[i];
                o.value.shortreals = p;
                py.attr("_buf_owner") = make_array_owner(p);
                py.attr("_buf_len") = (long long)v.size();
                break;
              }
              default:
                throw std::invalid_argument(
                    "VpiArrayValue: unsupported value format");
            }
          },
          nb::arg("format"), nb::arg("flags"), nb::arg("value"))
      .def_rw("format", &s_vpi_arrayvalue::format)
      .def_rw("flags", &s_vpi_arrayvalue::flags)
      .def("get_integers",
           [](s_vpi_arrayvalue &o) {
             return convert((vpiHandle)o.value.integers);
           })
      // Read n PLI_INT32 values out of the integers buffer so tests can
      // assert what vpi_get_value_array actually wrote into caller memory.
      // _buf_len is recorded by the constructor that allocated the buffer;
      // set_integers() clears it (external buffer, length unknown), in which
      // case only null/negative checks apply as before.
      .def("get_integers_values", [](nb::object self, int n) {
        auto &o = nb::cast<s_vpi_arrayvalue &>(self);
        // This helper reads PLI_INT32 elements. Other formats use a different
        // union member with a different element width, so reading them as
        // int32 would run past the allocation. Constructors now honour the
        // format, so reject those explicitly instead of returning garbage.
        if (o.format != vpiIntVal) {
          throw std::invalid_argument(
              "get_integers_values: only valid for vpiIntVal buffers");
        }
        if (o.value.integers == nullptr || n < 0) {
          throw std::invalid_argument("get_integers_values: null buffer or count");
        }
        nb::object len_obj = self.attr("_buf_len");
        if (len_obj.is_valid() && !len_obj.is_none()) {
          long long cap = nb::cast<long long>(len_obj);
          if (n > cap) {
            throw std::out_of_range("get_integers_values: n exceeds buffer length");
          }
        }
        std::vector<PLI_INT32> out;
        out.reserve(n);
        for (int i = 0; i < n; ++i) out.push_back(o.value.integers[i]);
        return out;
      }, nb::arg("n"))
      // Setters adopt the supplied capsule as the new owner (releasing any
      // buffer allocated by a constructor) and keep it alive for as long as
      // this object points into it. Length is unknown for external buffers.
      // Every setter replaces the union arm AND must update `format` to match
      // it; otherwise a reader still trusts the old format and walks the new
      // buffer with the wrong element stride (verified: set_reals on an int
      // array then get_integers_values(3) read 12 bytes out of an 8-byte
      // buffer). External capsule lengths are not observable from Python, so
      // `_buf_len` is uniformly cleared to "unknown"; the format guard in the
      // getters is what rejects a mismatched read.
      .def("set_integers",
           [](nb::object self, nb::object obj) {
             auto &o = nb::cast<s_vpi_arrayvalue &>(self);
             o.value.integers = (PLI_INT32 *)nb::cast<nb::capsule>(obj).data();
             o.format = vpiIntVal;
             self.attr("_buf_owner") = obj;
             self.attr("_buf_len") = nb::none();
           })
      .def(
          "get_times",
          [](s_vpi_arrayvalue &o) { return convert((vpiHandle)o.value.times); })
      .def("set_times",
           [](nb::object self, nb::object obj) {
             auto &o = nb::cast<s_vpi_arrayvalue &>(self);
             o.value.times = (p_vpi_time)nb::cast<nb::capsule>(obj).data();
             o.format = vpiTimeVal;
             self.attr("_buf_owner") = obj;
             self.attr("_buf_len") = nb::none();
           })
      .def(
          "get_reals",
          [](s_vpi_arrayvalue &o) { return convert((vpiHandle)o.value.reals); })
      .def("set_reals",
           [](nb::object self, nb::object obj) {
             auto &o = nb::cast<s_vpi_arrayvalue &>(self);
             o.value.reals = (double *)nb::cast<nb::capsule>(obj).data();
             o.format = vpiRealVal;
             self.attr("_buf_owner") = obj;
             self.attr("_buf_len") = nb::none();
           })
      .def("get_vectors",
           [](s_vpi_arrayvalue &o) {
             return convert((vpiHandle)o.value.vectors);
           })
      .def("set_vectors",
           [](nb::object self, nb::object obj) {
             auto &o = nb::cast<s_vpi_arrayvalue &>(self);
             o.value.vectors = (p_vpi_vecval)nb::cast<nb::capsule>(obj).data();
             o.format = vpiVectorVal;
             self.attr("_buf_owner") = obj;
             self.attr("_buf_len") = nb::none();
           })
      .def("get_rawvals",
           [](s_vpi_arrayvalue &o) {
             return convert((vpiHandle)o.value.rawvals);
           })
      .def("set_rawvals", [](nb::object self, nb::object obj) {
        auto &o = nb::cast<s_vpi_arrayvalue &>(self);
        o.value.rawvals = (PLI_BYTE8 *)nb::cast<nb::capsule>(obj).data();
        // The header exposes vpiRawTwoStateVal / vpiRawFourStateVal (17/18);
        // a bare byte capsule has no four-state info, so two-state is the
        // consistent choice and matches the constructor's raw buffer.
        o.format = vpiRawTwoStateVal;
        self.attr("_buf_owner") = obj;
        self.attr("_buf_len") = nb::none();
      });

  // dynamic_attr lets the constructors/setters attach an nb::capsule that
  // owns a shared_ptr<CallbackInfo>: the Python object then keeps the
  // simulator's user_data target alive without ever deleting it early.
  nb::class_<s_vpi_systf_data>(vpi, "VpiSystfData", nb::dynamic_attr())
      .def(nb::init<>())
      .def(
          "__init__",
          [](nb::pointer_and_handle<s_vpi_systf_data> self, PLI_INT32 type,
             PLI_INT32 sysfunctype, nb::callable calltf) {
            std::string func_name =
                nb::cast<std::string>(calltf.attr("__name__"));
            auto callback_info = make_callback_info(calltf, "user_data");
            // Keep the generated "$name" in the CallbackInfo that this systf
            // data already owns via user_data; the simulator reads tfname for
            // the whole registration, so it must not be a stack temporary.
            callback_info->owned_str = "$" + func_name;
            self.p->type = type;
            self.p->sysfunctype = sysfunctype;
            self.p->tfname =
                const_cast<char *>(callback_info->owned_str.c_str());
            self.p->calltf = systf_callback_wrap;
            self.p->compiletf = nullptr;
            self.p->sizetf = nullptr;
            self.p->user_data =
                reinterpret_cast<PLI_BYTE8 *>(callback_info.get());
            self.h.attr("_vpi_callback_info_owner") =
                make_callback_info_owner(callback_info);
          },
          nb::arg("type"), nb::arg("sysfunctype"), nb::arg("calltf"))
      .def(
          "__init__",
          [](s_vpi_systf_data *self, PLI_INT32 type, PLI_INT32 sysfunctype,
             nb::str tfname) {
            self->type = type;
            self->sysfunctype = sysfunctype;
            self->tfname = const_cast<char *>(tfname.c_str());
            self->calltf = nullptr;
            self->compiletf = nullptr;
            self->sizetf = nullptr;
            self->user_data = nullptr;
          },
          nb::arg("type"), nb::arg("sysfunctype"), nb::arg("tfname"),
          nb::keep_alive<1, 4>())
      .def_rw("type", &s_vpi_systf_data::type)
      .def_rw("sysfunctype", &s_vpi_systf_data::sysfunctype)
      .def_prop_rw(
          "tfname",
          [](s_vpi_systf_data &o) {
            return o.tfname ? std::string(o.tfname) : std::string();
          },
          [](s_vpi_systf_data &o, nb::str s) {
            o.tfname = const_cast<char *>(s.c_str());
          },
          nb::for_setter(nb::keep_alive<1, 2>()))
      // user_data always holds a CallbackInfo* (see both constructors below):
      // the callable ctor allocates one to carry the systf callback + name,
      // and vpi_get_systf_info writes that same pointer back. Reading it as a
      // C string (the old code) decoded the CallbackInfo object's bytes and
      // raised UnicodeDecodeError. Mirror s_cb_data.user_data: dereference.
      .def_prop_rw(
          "user_data",
          [](s_vpi_systf_data &o) -> std::string {
            if (o.user_data == nullptr)
              return std::string();
            auto *cb = reinterpret_cast<CallbackInfo *>(o.user_data);
            return cb->user_data;
          },
          [](nb::object self, nb::str s) {
            auto &o = nb::cast<s_vpi_systf_data &>(self);
            // Preserve the existing callback; only replace the user-data
            // string. Allocating a fresh CallbackInfo with a null callback
            // here would silently drop the systf's calltf target.
            if (o.user_data != nullptr) {
              auto *cb = reinterpret_cast<CallbackInfo *>(o.user_data);
              cb->user_data = std::string(s.c_str());
            } else {
              auto cb = make_callback_info(nb::none(), std::string(s.c_str()));
              o.user_data = reinterpret_cast<PLI_BYTE8 *>(cb.get());
              self.attr("_vpi_callback_info_owner") = make_callback_info_owner(cb);
            }
          })
      // IEEE 1800 36: s_vpi_systf_data::compiletf and ::sizetf are optional
      // callbacks with the same signature as calltf. Bind them the same way:
      // store the Python callable in the CallbackInfo behind user_data and
      // install the matching C wrapper in the struct. The getter reports
      // whether the field is bound (mirrors the cb_rtn read-only property).
      // A (type, sysfunctype, tfname) constructed object has no CallbackInfo
      // yet, so the setters allocate one on first use.
      .def_prop_rw(
          "compiletf",
          [](s_vpi_systf_data &o) { return o.compiletf != nullptr; },
          [](nb::object self, nb::callable cb) {
            auto &o = nb::cast<s_vpi_systf_data &>(self);
            auto *info = reinterpret_cast<CallbackInfo *>(o.user_data);
            if (info == nullptr) {
              auto sp = make_callback_info(nb::none(), "");
              o.user_data = reinterpret_cast<PLI_BYTE8 *>(sp.get());
              self.attr("_vpi_callback_info_owner") = make_callback_info_owner(sp);
              info = sp.get();
            }
            info->nb_compiletf = nb::object(cb);
            o.compiletf = systf_compiletf_wrap;
          })
      .def_prop_rw(
          "sizetf",
          [](s_vpi_systf_data &o) { return o.sizetf != nullptr; },
          [](nb::object self, nb::callable cb) {
            auto &o = nb::cast<s_vpi_systf_data &>(self);
            auto *info = reinterpret_cast<CallbackInfo *>(o.user_data);
            if (info == nullptr) {
              auto sp = make_callback_info(nb::none(), "");
              o.user_data = reinterpret_cast<PLI_BYTE8 *>(sp.get());
              self.attr("_vpi_callback_info_owner") = make_callback_info_owner(sp);
              info = sp.get();
            }
            info->nb_sizetf = nb::object(cb);
            o.sizetf = systf_sizetf_wrap;
          });

  // Use nb::new_ instead of def("__init__", ...) so that the side-effect
  // call to the simulator runtime happens in __new__ (before placement-new
  // settles) and the returned object is fully populated by the time
  // __init__ is invoked. A bare .def("__init__", [](T* self){...}) would
  // place the side effect after Python already constructed an uninitialized
  // T, so reading the field from Python would still see garbage.
  nb::class_<s_vpi_vlog_info>(vpi, "VpiVlogInfo")
      .def(nb::new_([]() -> s_vpi_vlog_info * {
        s_vpi_vlog_info *info = new s_vpi_vlog_info();
        vpi_get_vlog_info(info);
        return info;
      }))
      .def_prop_ro("argc", [](s_vpi_vlog_info &o) { return o.argc; })
      .def_prop_ro("argv",
                   [](s_vpi_vlog_info &o) {
                     nb::list args;
                     for (int i = 0; i < o.argc; i++) {
                       if (o.argv[i])
                         args.append(std::string(o.argv[i]));
                     }
                     return args;
                   })
      .def_prop_ro("product",
                   [](s_vpi_vlog_info &o) {
                     return o.product ? std::string(o.product) : std::string();
                   })
      .def_prop_ro("version", [](s_vpi_vlog_info &o) {
        return o.version ? std::string(o.version) : std::string();
      });

  nb::class_<s_vpi_error_info>(vpi, "VpiErrorInfo")
      .def(nb::new_([]() -> s_vpi_error_info * {
        s_vpi_error_info *info = new s_vpi_error_info();
        std::memset(info, 0, sizeof(s_vpi_error_info));
        vpi_chk_error(info);
        return info;
      }))
      .def_rw("state", &s_vpi_error_info::state)
      .def_rw("level", &s_vpi_error_info::level)
      .def_rw("line", &s_vpi_error_info::line)
      .def("get_message",
           [](s_vpi_error_info &o) {
             return o.message ? std::string(o.message) : std::string();
           })
      // Keep each Python str alive as long as the error-info instance so the
      // char* stored in the C struct never points at a dead temporary.
      .def("set_message",
           [](s_vpi_error_info &o, nb::str s) {
             o.message = const_cast<char *>(s.c_str());
           },
           nb::keep_alive<1, 2>())
      .def("get_product",
           [](s_vpi_error_info &o) {
             return o.product ? std::string(o.product) : std::string();
           })
      .def("set_product",
           [](s_vpi_error_info &o, nb::str s) {
             o.product = const_cast<char *>(s.c_str());
           },
           nb::keep_alive<1, 2>())
      .def("get_code",
           [](s_vpi_error_info &o) {
             return o.code ? std::string(o.code) : std::string();
           })
      .def("set_code",
           [](s_vpi_error_info &o, nb::str s) {
             o.code = const_cast<char *>(s.c_str());
           },
           nb::keep_alive<1, 2>())
      .def("get_file",
           [](s_vpi_error_info &o) {
             return o.file ? std::string(o.file) : std::string();
           })
      .def("set_file",
           [](s_vpi_error_info &o, nb::str s) {
             o.file = const_cast<char *>(s.c_str());
           },
           nb::keep_alive<1, 2>());

  // dynamic_attr lets the constructor/setter attach the nb::capsule that
  // owns this object's shared_ptr<CallbackInfo> (see VpiSystfData above).
  nb::class_<s_cb_data>(vpi, "CbData", nb::dynamic_attr())
      .def(nb::init<>())
      .def(
          "__init__",
          [](nb::pointer_and_handle<s_cb_data> self, PLI_INT32 reason,
             nb::callable cb_rtn, nb::object object, nb::object time,
             nb::object value, PLI_INT32 index,
             const std::string &user_data) {
            vpiHandle obj = convert(object);
            p_vpi_time t =
                time.is_none() ? nullptr : &nb::cast<s_vpi_time &>(time);
            p_vpi_value v =
                value.is_none() ? nullptr : &nb::cast<s_vpi_value &>(value);
            self.p->reason = reason;
            self.p->cb_rtn = vpi_callback_wrap;
            self.p->obj = obj;
            self.p->time = t;
            self.p->value = v;
            self.p->index = index;
            self.p->user_data = nullptr;
            // Pin `time` and `value` on the shared CallbackInfo as well as via
            // keep_alive<1,5>/<1,6>. keep_alive only lasts while this Python
            // CbData wrapper lives; the simulator keeps the raw pointers after
            // registration (IEEE 1800 36.1). The registry's shared_ptr now
            // keeps both objects alive until vpi_remove_cb succeeds.
            auto callback_info =
                make_callback_info(cb_rtn, user_data, time, value);
            self.p->user_data =
                reinterpret_cast<PLI_BYTE8 *>(callback_info.get());
            self.h.attr("_vpi_callback_info_owner") =
                make_callback_info_owner(callback_info);
          },
          nb::arg("reason"), nb::arg("cb_rtn"), nb::arg("object"),
          nb::arg("time"), nb::arg("value"), nb::arg("index"),
          nb::arg("user_data"),
          // vpi_register_cb copies s_cb_data but keeps the time/value *pointers*
          // (IEEE 1800 36.1); the pointed-to objects must outlive the callback.
          // Without keep_alive, passing temporaries leaves cb_data->time/value
          // dangling and the simulator reads freed memory when it fires.
          // Indices: self=1, reason=2, cb_rtn=3, object=4, time=5, value=6.
          nb::keep_alive<1, 5>(), nb::keep_alive<1, 6>())
      .def_rw("reason", &s_cb_data::reason)
      .def_prop_ro("cb_rtn", [](s_cb_data &o) { return o.cb_rtn != nullptr; })
      .def_prop_rw(
          "obj", [](s_cb_data &o) { return convert(o.obj); },
          [](s_cb_data &o, nb::object obj) { o.obj = convert(obj); })
      .def_prop_rw(
          "time",
          [](s_cb_data &o) -> nb::object {
            return o.time ? nb::cast(*o.time) : nb::none();
          },
          [](s_cb_data &o, nb::object obj) {
            o.time = obj.is_none() ? nullptr : &nb::cast<s_vpi_time &>(obj);
          },
          nb::for_setter(nb::keep_alive<1, 2>()))
      .def_prop_rw(
          "value",
          [](s_cb_data &o) -> nb::object {
            return o.value ? nb::cast(*o.value) : nb::none();
          },
          [](s_cb_data &o, nb::object obj) {
            o.value = obj.is_none() ? nullptr : &nb::cast<s_vpi_value &>(obj);
          },
          nb::for_setter(nb::keep_alive<1, 2>()))
      .def_rw("index", &s_cb_data::index)
      .def_prop_rw(
          "user_data",
          [](s_cb_data &o) -> std::string {
            if (o.user_data == nullptr)
              return std::string();
            auto *cb = reinterpret_cast<CallbackInfo *>(o.user_data);
            return cb->user_data;
          },
          [](nb::object self, nb::str s) {
            auto &o = nb::cast<s_cb_data &>(self);
            // A property setter receives exactly (self, value). The previous
            // signature took an extra cb_rtn_obj, so `cb.user_data = "x"`
            // raised TypeError (nanobind reported it wanted (object, str)).
            // Mirror VpiSystfData.user_data: update the string in place and
            // preserve the already-registered calltf so a later callback
            // still reaches the original Python callable.
            if (o.user_data != nullptr) {
              auto *cb = reinterpret_cast<CallbackInfo *>(o.user_data);
              cb->user_data = std::string(s.c_str());
            } else {
              auto cb = make_callback_info(nb::none(), std::string(s.c_str()));
              o.user_data = reinterpret_cast<PLI_BYTE8 *>(cb.get());
              self.attr("_vpi_callback_info_owner") = make_callback_info_owner(cb);
            }
          });

  // CallbackInfo now has shared ownership: the Python CbData/VpiSystfData
  // object carries an nb::capsule holding a shared_ptr, and a successful
  // registration stores another copy in the global registry. vpi_remove_cb
  // releases the registry copy only after the simulator stops using the
  // pointer, so no use-after-free path exists. See vpi_user_wrap.h.
  // functions
  vpi.def("vpi_register_cb", &vpi_register_cb_wrap, nb::arg("cb_data_p"),
          "Register a callback.");

  vpi.def("vpi_remove_cb", &vpi_remove_cb_wrap, nb::arg("cb_obj"),
          "Remove a callback.");

  vpi.def("vpi_get_cb_info", &vpi_get_cb_info_wrap, nb::arg("object"),
          nb::arg("cb_data_p"), "Get callback information.");

  vpi.def("vpi_register_systf", &vpi_register_systf_wrap,
          nb::arg("systf_data_p"), "Register a system task/function.");

  vpi.def("vpi_get_systf_info", &vpi_get_systf_info_wrap, nb::arg("object"),
          nb::arg("systf_data_p"), "Get system task/function information.");

  vpi.def("vpi_handle_by_name", vpi_func_wrap(vpi_handle_by_name),
          nb::arg("name"), nb::arg("scope") = nb::none(),
          "Get a handle by name.");

  vpi.def("vpi_handle_by_index", vpi_func_wrap(vpi_handle_by_index),
          nb::arg("object"), nb::arg("indx"), "Get a handle by index.");

  vpi.def("vpi_handle", vpi_func_wrap(vpi_handle), nb::arg("type"),
          nb::arg("refHandle"),
          "Get a handle for a specific type and reference handle.");

  vpi.def("vpi_handle_multi", &vpi_handle_multi_wrap,
          "Get a handle for multiple reference handles.");

  vpi.def("vpi_iterate", vpi_func_wrap(vpi_iterate), nb::arg("type"),
          nb::arg("refHandle"), "Iterate over objects of a specific type.");

  vpi.def("vpi_scan", vpi_func_wrap(vpi_scan), nb::arg("iterator"),
          "Scan an iterator.");

  vpi.def("vpi_get", vpi_func_wrap(vpi_get), nb::arg("property"),
          nb::arg("object"), "Get a property value.");

  vpi.def("vpi_get64", vpi_func_wrap(vpi_get64), nb::arg("property"),
          nb::arg("object"), "Get a 64-bit property value.");

  vpi.def("vpi_get_str", vpi_func_wrap(vpi_get_str), nb::arg("property"),
          nb::arg("object"), "Get a string property value.");

  vpi.def("vpi_get_delays", &vpi_get_delays_wrap, nb::arg("object"),
          nb::arg("delay_p"), "Get delays for an object.");

  vpi.def("vpi_put_delays", &vpi_put_delays_wrap, nb::arg("object"),
          nb::arg("delay_p"), "Put delays for an object.");

  vpi.def("vpi_get_value", &vpi_get_value_wrap, nb::arg("expr"),
          nb::arg("value_p"), "Get a value.");

  // IEEE 1800 38.35: time_p may be NULL with vpiNoDelay / force / release,
  // and the object handle may be NULL too. nanobind rejects None for plain
  // object / pointer arguments unless .none() is declared on the argument,
  // so mark both explicitly; the wrapper performs the semantic validation.
  vpi.def("vpi_put_value", &vpi_put_value_wrap, nb::arg("object").none(),
          nb::arg("value_p"), nb::arg("time_p").none(), nb::arg("flags"),
          "Put a value.");

  vpi.def("vpi_get_value_array", &vpi_get_value_array_wrap, nb::arg("object"),
          nb::arg("arrayvalue_p"), nb::arg("index_p"), nb::arg("num"),
          "Get an array of values.");

  vpi.def("vpi_put_value_array", &vpi_put_value_array_wrap, nb::arg("object"),
          nb::arg("arrayvalue_p"), nb::arg("index_p"), nb::arg("num"),
          "Put an array of values.");

  // IEEE 1800 38.25: object may be NULL, meaning "the current simulation
  // time" rather than a time relative to a scope. The generic nb::object ->
  // vpiHandle conversion already maps Python None to a NULL handle, so only
  // the nanobind signature needs to accept None.
  vpi.def("vpi_get_time", &vpi_get_time_wrap, nb::arg("object").none(),
          nb::arg("time_p"), "Get time for an object.");

  vpi.def("vpi_mcd_open", vpi_func_wrap(vpi_mcd_open), nb::arg("fileName"),
          "Open a multichannel description file.");

  vpi.def("vpi_mcd_close", &vpi_mcd_close, nb::arg("mcd"),
          "Close a multichannel description file.");

  vpi.def("vpi_mcd_name", &vpi_mcd_name, nb::arg("cd"),
          "Get the name of a multichannel description file.");

  vpi.def("vpi_mcd_printf", &vpi_mcd_printf_wrap,
          "Print to a multichannel description file.");

  vpi.def("vpi_printf", &vpi_printf_wrap, "Print to standard output.");

  vpi.def("vpi_compare_objects", vpi_func_wrap(vpi_compare_objects),
          nb::arg("object1"), nb::arg("object2"), "Compare two objects.");

  // Dedicated wrappers also drop the vpi_put_userdata keep-alive for the
  // handle, so a recycled handle cannot inherit a stale capsule.
  vpi.def("vpi_free_object", &vpi_free_object_wrap, nb::arg("object"),
          "Free an object. (Deprecated)");

  vpi.def("vpi_release_handle", &vpi_release_handle_wrap,
          nb::arg("object"), "Release a handle.");

  // 运行时检测：VCS/VCSMX 不支持这些函数。使用 vpi_func_optional
  // 统一处理 "存在→包装 / 不存在→占位" 的两种分支，避免重复 if/else。
  // 名字只写一次：宏从 decltype(&f) 推导出函数名字符串。
#define VPI_DEF_OPTIONAL(name)                                  \
  vpi.def(#name, vpi_func_optional<decltype(&name)>(#name, nullptr))

  VPI_DEF_OPTIONAL(vpi_get_data);
  VPI_DEF_OPTIONAL(vpi_put_data);

#undef VPI_DEF_OPTIONAL
  vpi.def("vpi_get_userdata", &vpi_get_userdata_wrap, nb::arg("obj"),
          "Get user data.");

  // None is legal and means "clear the simulator's userdata pointer"; the
  // wrapper erases the keep-alive entry in that case, so declare .none().
  vpi.def("vpi_put_userdata", &vpi_put_userdata_wrap, nb::arg("obj"),
          nb::arg("userdata").none(), "Put user data.");

  vpi.def("vpi_flush", &vpi_flush, "Flush output.");

  vpi.def("vpi_mcd_flush", &vpi_mcd_flush, nb::arg("mcd"),
          "Flush a multichannel description file.");

  vpi.def("vpi_control", &vpi_control_wrap, "Control simulator operations.");

  vpi.def("vpi_handle_by_multi_index", &vpi_handle_by_multi_index_wrap,
          nb::arg("obj"), nb::arg("num_index"), nb::arg("index_array"),
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

  m.def(
      "uvm_report",
      [](int severity, const char *id, const char *message, int verbosity,
         const char *file, int linenum) {
        m_uvm_report_dpi(severity, const_cast<char *>(id),
                         const_cast<char *>(message), verbosity,
                         const_cast<char *>(file), linenum);
      },
      "report function", nb::arg("severity"), nb::arg("id"), nb::arg("message"),
      nb::arg("verbosity"), nb::arg("file"), nb::arg("linenum"));

  m.def("int_str_max", &int_str_max,
        "Find the maximum of integers represented as strings.");

  m.def(
      "uvm_hdl_check_path",
      [](const char *path) {
        return uvm_hdl_check_path(const_cast<char *>(path));
      },
      "Check if a path exists in the HDL model.", nb::arg("path"));

  m.def(
      "uvm_hdl_read",
      [](const char *path, p_vpi_vecval value) {
        return uvm_hdl_read(const_cast<char *>(path), value);
      },
      "Read data from a path in the HDL model.", nb::arg("path"),
      nb::arg("value"));

  m.def(
      "uvm_hdl_deposit",
      [](const char *path, p_vpi_vecval value) {
        return uvm_hdl_deposit(const_cast<char *>(path), value);
      },
      "Deposit data at a path in the HDL model.", nb::arg("path"),
      nb::arg("value"));

  m.def(
      "uvm_hdl_force",
      [](const char *path, p_vpi_vecval value) {
        return uvm_hdl_force(const_cast<char *>(path), value);
      },
      "Force a value at a path in the HDL model.", nb::arg("path"),
      nb::arg("value"));

  m.def(
      "uvm_hdl_release_and_read",
      [](const char *path, p_vpi_vecval value) {
        return uvm_hdl_release_and_read(const_cast<char *>(path), value);
      },
      "Release and read data from a path in the HDL model.", nb::arg("path"),
      nb::arg("value"));

  m.def(
      "uvm_hdl_release",
      [](const char *path) {
        return uvm_hdl_release(const_cast<char *>(path));
      },
      "Release a path in the HDL model.", nb::arg("path"));

  m.def(
      "push_data",
      [](int lvl, const char *entry, int cmd) {
        push_data(lvl, const_cast<char *>(entry), cmd);
      },
      "Push data to a specified level.", nb::arg("lvl"), nb::arg("entry"),
      nb::arg("cmd"));

  m.def("walk_level", &wrap_walk_level,
        "Walk through a hierarchy at a given level.", nb::arg("lvl"),
        nb::arg("argv"), nb::arg("cmd"));

  m.def("uvm_dpi_get_next_arg_c", &uvm_dpi_get_next_arg_c,
        "Get the next argument from the command line.", nb::arg("init"));

  m.def("uvm_dpi_get_tool_name_c", &uvm_dpi_get_tool_name_c,
        "Get the name of the current tool.", nb::rv_policy::reference);

  m.def("uvm_dpi_get_tool_version_c", &uvm_dpi_get_tool_version_c,
        "Get the version of the current tool.", nb::rv_policy::reference);

  m.def("exec_tcl_cmd", &exec_tcl_cmd, "Execute a tcl command.",
        nb::arg("cmd"));

  m.def("uvm_info", &wrap_uvm_report, "UVM_INFO report function.",
        nb::arg("message"), nb::arg("verbosity"),
        nb::arg("severity") = M_UVM_INFO);

  m.def("uvm_warning", &wrap_uvm_report, "UVM_WARNING report function.",
        nb::arg("message"), nb::arg("verbosity") = M_UVM_NONE,
        nb::arg("severity") = M_UVM_WARNING);

  m.def("uvm_error", &wrap_uvm_report, "UVM_ERROR report function.",
        nb::arg("message"), nb::arg("verbosity") = M_UVM_NONE,
        nb::arg("severity") = M_UVM_ERROR);

  m.def("uvm_fatal", &wrap_uvm_report, "UVM_FATAL report function.",
        nb::arg("message"), nb::arg("verbosity") = M_UVM_NONE,
        nb::arg("severity") = M_UVM_FATAL);

  m.def("print_factory", dpi_func_wrap(print_factory),
        "Prints factory information.", nb::arg("all_types") = 1);

  m.def("set_factory_inst_override", dpi_func_wrap(set_factory_inst_override),
        "Sets an instance override in the factory.",
        nb::arg("original_type_name"), nb::arg("override_type_name"),
        nb::arg("full_inst_path"));

  m.def("set_factory_type_override", dpi_func_wrap(set_factory_type_override),
        "Sets a type override in the factory.", nb::arg("original_type_name"),
        nb::arg("override_type_name"), nb::arg("replace") = (unsigned char)1);

  m.def("debug_factory_create", dpi_func_wrap(debug_factory_create),
        "Debugs the creation of a factory object.", nb::arg("requested_type"),
        nb::arg("context") = "");

  m.def("create_object_by_name", dpi_func_wrap(create_object_by_name),
        "create a uvm object.", nb::arg("requested_type"),
        nb::arg("context") = "", nb::arg("name") = "");

  m.def("create_component_by_name", dpi_func_wrap(create_component_by_name),
        "create a uvm object.", nb::arg("requested_type"),
        nb::arg("context") = "", nb::arg("name") = "");

  m.def("find_factory_override", dpi_func_wrap(find_factory_override),
        "Finds an override for a given factory type.",
        nb::arg("requested_type"), nb::arg("context"),
        nb::arg("override_type_name"));

  m.def("print_topology", dpi_func_wrap(print_topology), "Prints the topology.",
        nb::arg("context") = "");

  m.def("set_timeout", dpi_func_wrap(set_timeout), "Set the timeout value.",
        nb::arg("timeout"), nb::arg("overridable") = 1);

  m.def("set_finish_on_completion", dpi_func_wrap(set_finish_on_completion),
        "if set 1, then $finish is called after phasing completes.",
        nb::arg("f") = 1);

  m.def("uvm_objection_op", dpi_func_wrap(uvm_objection_op), "uvm_objection_op",
        nb::arg("op"), nb::arg("name"), nb::arg("contxt"),
        nb::arg("description"), nb::arg("delta") = 0);

  // --- objection / phase / topology (high priority) ---
  m.def("set_drain_time", dpi_func_wrap(set_drain_time),
        "Set the drain time (in ns) for a phase.", nb::arg("drain_ns"));

  m.def("get_drain_time", dpi_func_wrap(get_drain_time),
        "Get the drain time (in ns) for a phase.");

  m.def("get_objection_count", dpi_func_wrap(get_objection_count),
        "Get the objection count raised by a specific component.",
        nb::arg("phase_name"), nb::arg("contxt") = "");

  m.def("get_objection_total", dpi_func_wrap(get_objection_total),
        "Get the total objection count (including hierarchical propagation).",
        nb::arg("phase_name"), nb::arg("contxt") = "");

  m.def("display_objections", dpi_func_wrap(display_objections),
        "Print all current objectors (useful when simulation hangs).",
        nb::arg("phase_name") = "run", nb::arg("contxt") = "");

  m.def("get_current_phase_name", dpi_func_wrap(get_current_phase_name),
        "Return the name of the currently executing phase.");

  m.def("get_phase_state", dpi_func_wrap(get_phase_state),
        "Return the integer state of a phase (-1=unknown, see UVM_PHASE_*).",
        nb::arg("phase_name"));

  m.def("get_phase_state_name", dpi_func_wrap(get_phase_state_name),
        "Return the human-readable state name of a phase.",
        nb::arg("phase_name"));

  m.def("phase_jump", dpi_func_wrap(phase_jump),
        "Jump to a target phase from the currently executing phase.",
        nb::arg("phase_name"));

  // --- component / topology ---
  m.def("component_get_num_children", dpi_func_wrap(component_get_num_children),
        "Get the number of children of a component.", nb::arg("contxt") = "");

  m.def("component_get_child_name", dpi_func_wrap(component_get_child_name),
        "Get the name of the idx-th child of a component.", nb::arg("contxt"),
        nb::arg("idx"));

  m.def("component_get_parent", dpi_func_wrap(component_get_parent),
        "Get the full path of a component's parent.", nb::arg("contxt"));

  m.def("component_get_type_name", dpi_func_wrap(component_get_type_name),
        "Get the UVM type name of a component.", nb::arg("contxt"));

  m.def("component_sprint", dpi_func_wrap(component_sprint),
        "Return the sprint() string of a component.", nb::arg("contxt") = "");

  m.def("uvm_top_sprint", dpi_func_wrap(uvm_top_sprint),
        "Return the sprint() string of the entire uvm_root.");

  // --- factory query ---
  m.def("is_type_registered", dpi_func_wrap(is_type_registered),
        "Check if a type name is registered in the UVM factory.",
        nb::arg("type_name"));

  m.def("dbg_print", dpi_func_wrap(dbg_print), "Prints the object.",
        nb::arg("name") = "");

  m.def("tlm_connect", dpi_func_wrap(tlm_connect), "Connects two TLM ports.",
        nb::arg("src"), nb::arg("dst"));

  // uvm event
  m.def("wait_on", dpi_func_wrap(wait_on), "Wait until the signal is on",
        nb::arg("ev_name"), nb::arg("delta") = 0);
  m.def("wait_off", dpi_func_wrap(wait_off), "Wait until the signal is off",
        nb::arg("ev_name"), nb::arg("delta") = 0);
  m.def("wait_trigger", dpi_func_wrap(wait_trigger),
        "Wait for the trigger event", nb::arg("ev_name"));
  m.def("wait_ptrigger", dpi_func_wrap(wait_ptrigger),
        "Wait for the positive trigger event", nb::arg("ev_name"));
  m.def("get_trigger_time", dpi_func_wrap(get_trigger_time),
        "Get the time of the last trigger event", nb::arg("ev_name"));
  m.def("is_on", dpi_func_wrap(is_on), "Check if the signal is on",
        nb::arg("ev_name"));
  m.def("is_off", dpi_func_wrap(is_off), "Check if the signal is off",
        nb::arg("ev_name"));
  m.def("ev_reset", dpi_func_wrap(reset), "Reset the signal state",
        nb::arg("ev_name"), nb::arg("wakeup") = 0);
  m.def("cancel", dpi_func_wrap(cancel), "Cancel the current wait operation",
        nb::arg("ev_name"));
  m.def("get_num_waiters", dpi_func_wrap(get_num_waiters),
        "Get the number of waiters", nb::arg("ev_name"));
  m.def("trigger", dpi_func_wrap(trigger), "Trigger the event",
        nb::arg("ev_name"));
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
        "Sets the maximum quit count for the report server.", nb::arg("count"),
        nb::arg("overridable") = 1);
  m.def("get_max_quit_count", dpi_func_wrap(get_max_quit_count),
        "Gets the maximum quit count from the report server.");
  m.def("set_quit_count", dpi_func_wrap(set_quit_count),
        "Sets the current quit count in the report server.",
        nb::arg("quit_count"));
  m.def("get_quit_count", dpi_func_wrap(get_quit_count),
        "Gets the current quit count from the report server.");
  m.def("set_severity_count", dpi_func_wrap(set_severity_count),
        "Sets the count for a specific severity level.", nb::arg("severity"),
        nb::arg("count"));
  m.def("get_severity_count", dpi_func_wrap(get_severity_count),
        "Gets the count for a specific severity level.", nb::arg("severity"));
  m.def("set_id_count", dpi_func_wrap(set_id_count),
        "Sets the count for a specific message ID.", nb::arg("id"),
        nb::arg("count"));
  m.def("get_id_count", dpi_func_wrap(get_id_count),
        "Gets the count for a specific message ID.", nb::arg("id"));
  m.def("print_report_server", dpi_func_wrap(print_report_server),
        "Prints the current report server information.");
  m.def("report_summarize", dpi_func_wrap(report_summarize),
        "Generates a summary of all reports.");
  // 寄存器相关函数绑定
  m.def("write_reg", dpi_func_wrap(write_reg), "write register");
  m.def("read_reg", dpi_func_wrap(wrap_read_reg),
        "read register"); // 注意：wrap_read_reg 已经是函数包装
  m.def("check_reg", dpi_func_wrap(check_reg), "check register",
        nb::arg("name"), nb::arg("data") = 0, nb::arg("predict") = 0);

  // --- register model extended APIs ---
  m.def("set_top_reg_block_by_path", dpi_func_wrap(set_top_reg_block_by_path),
        "Set the top-level register block by its UVM component path.",
        nb::arg("block_path"));

  m.def("get_reg_mirrored_value", dpi_func_wrap(get_reg_mirrored_value),
        "Get the mirrored (last-read) value of a register.", nb::arg("name"));

  m.def("get_reg_desired_value", dpi_func_wrap(get_reg_desired_value),
        "Get the desired (next-write) value of a register.", nb::arg("name"));

  m.def("get_reg_address", dpi_func_wrap(get_reg_address),
        "Get the bus address of a register.", nb::arg("name"));

  m.def("reset_reg", dpi_func_wrap(reset_reg),
        "Reset a register model to its reset value (kind: HARD|SOFT).",
        nb::arg("name"), nb::arg("kind") = "HARD");

  m.def("predict_reg", dpi_func_wrap(predict_reg),
        "Directly predict a register's mirrored value without bus access.",
        nb::arg("name"), nb::arg("data"), nb::arg("kind") = "DEFAULT");

  m.def(
      "mirror_reg", dpi_func_wrap(wrap_mirror_reg),
      "Read and update the mirrored value; optionally check against expected.",
      nb::arg("name"), nb::arg("check") = 0);

  m.def("get_reg_names", dpi_func_wrap(get_reg_names),
        "Return a comma-separated list of register names in a block.",
        nb::arg("block_path") = "");

  m.def("get_block_names", dpi_func_wrap(get_block_names),
        "Return a comma-separated list of sub-block names in a block.",
        nb::arg("block_path") = "");

  m.def("get_reg_field_names", dpi_func_wrap(get_reg_field_names),
        "Return a comma-separated list of field names in a register.",
        nb::arg("reg_name"));

  m.def("read_field_by_name", dpi_func_wrap(read_field_by_name),
        "Get the mirrored value of a named field in a register.",
        nb::arg("reg_name"), nb::arg("field_name"));

  m.def("write_field_by_name", dpi_func_wrap(write_field_by_name),
        "Direct-predict a named field in a register (does NOT write to bus).",
        nb::arg("reg_name"), nb::arg("field_name"), nb::arg("data"));

  m.def("reg_block_sprint", dpi_func_wrap(reg_block_sprint),
        "Return the sprint() string of a register block.",
        nb::arg("block_path") = "");

  // --- config db extended ---
  m.def("config_db_exists", dpi_func_wrap(config_db_exists),
        "Check if a config_db entry exists (0=no, 1=int, 2=string, 3=real).",
        nb::arg("contxt"), nb::arg("inst_name"), nb::arg("field_name"));

  // --- sequencer query ---
  m.def("start_seq", dpi_func_wrap(start_seq), "start seq on sqr",
        nb::arg("seq_name"), nb::arg("sqr_name"), nb::arg("rand_en") = 1,
        nb::arg("background") = 0);
  m.def("stop_sequences", dpi_func_wrap(stop_sequences),
        "Stop all sequences currently running on the given sequencer.",
        nb::arg("sqr_name"));

  m.def("is_sequencer_busy", dpi_func_wrap(is_sequencer_busy),
        "Check if a sequencer is currently running a sequence/item.",
        nb::arg("sqr_name"));

  m.def("get_current_sequence_name", dpi_func_wrap(get_current_sequence_name),
        "Return the name of the sequence currently running on the sequencer.",
        nb::arg("sqr_name"));

  // --- uvm_barrier ---
  m.def("barrier_set_threshold", dpi_func_wrap(barrier_set_threshold),
        "Set the waiters threshold for a named barrier.", nb::arg("name"),
        nb::arg("threshold"));

  m.def("barrier_get_threshold", dpi_func_wrap(barrier_get_threshold),
        "Get the waiters threshold of a named barrier.", nb::arg("name"));

  m.def("barrier_wait", dpi_func_wrap(barrier_wait),
        "Wait at a named barrier (blocks until threshold is reached).",
        nb::arg("name"));

  m.def("barrier_reset", dpi_func_wrap(barrier_reset),
        "Reset a named barrier. wakeup=1 releases currently waiting callers.",
        nb::arg("name"), nb::arg("wakeup") = 0);

  m.def("barrier_get_num_waiters", dpi_func_wrap(barrier_get_num_waiters),
        "Return the number of callers currently waiting at the named barrier.",
        nb::arg("name"));

  // --- uvm_pool ---
  m.def("pool_exists", dpi_func_wrap(pool_exists),
        "Check if a key exists in a named pool (pool_name='event' for "
        "uvm_event_pool).",
        nb::arg("pool_name"), nb::arg("key"));

  m.def("pool_num", dpi_func_wrap(pool_num),
        "Return the number of entries in a named pool.", nb::arg("pool_name"));

  m.def("pool_keys", dpi_func_wrap(pool_keys),
        "Return a comma-separated list of keys in a named pool.",
        nb::arg("pool_name"));

  // --- uvm_callback query ---
  m.def("get_callback_count", dpi_func_wrap(get_callback_count),
        "Return the number of callbacks registered on a component.",
        nb::arg("comp_path"), nb::arg("cb_type_name") = "");

  m.def("get_callback_type_names", dpi_func_wrap(get_callback_type_names),
        "Return a comma-separated list of callback type names on a component.",
        nb::arg("comp_path"));

  // --- printer / comparer knobs ---
  m.def("set_default_printer_knob", dpi_func_wrap(set_default_printer_knob),
        "Set an integer knob on the global default uvm_printer.",
        nb::arg("knob_name"), nb::arg("value"));

  m.def("get_default_printer_knob", dpi_func_wrap(get_default_printer_knob),
        "Get an integer knob from the global default uvm_printer.",
        nb::arg("knob_name"));

  m.def("set_default_comparer_knob", dpi_func_wrap(set_default_comparer_knob),
        "Set an integer knob on the global default uvm_comparer.",
        nb::arg("knob_name"), nb::arg("value"));

  m.def("get_default_comparer_knob", dpi_func_wrap(get_default_comparer_knob),
        "Get an integer knob from the global default uvm_comparer.",
        nb::arg("knob_name"));

  m.def("component_compare", dpi_func_wrap(component_compare),
        "Compare two components using the default comparer.", nb::arg("path_a"),
        nb::arg("path_b"));
  m.def("run_test", dpi_func_wrap(run_test_wrap), "uvm run test",
        nb::arg("test_name"));
  m.def("wait_unit", dpi_func_wrap(wait_unit), "wait unit time");
  m.def("process_pool_run", dpi_func_wrap(process_pool_run), "process pool run",
        nb::arg("name"));
  m.def("process_pool_clear", dpi_func_wrap(process_pool_clear),
        "process pool clear");
  // IEEE 1800-2023 38.4: vpiReset requires stop_value, reset_value and
  // diagnostics_value. Keep defaults so the historical reset() call stays
  // source-compatible at the bridge layer.
  m.def(
      "reset",
      [](int stop_value, int reset_value, int diagnostics_value) {
        return vpi_control(vpiReset, stop_value, reset_value,
                           diagnostics_value);
      },
      "Reset the simulation (stop_value, reset_value, diagnostics_value).",
      nb::arg("stop_value") = 0, nb::arg("reset_value") = 0,
      nb::arg("diagnostics_value") = 0);
  m.def(
      "stop", []() { return vpi_control(vpiStop); }, "Suspend the simulation");
  m.def(
      "finish", []() { return vpi_control(vpiFinish); },
      "Finished the simulation");
  m.def(
      "get_sim_time",
      [](const char *name) {
        uint64_t time;
        if (simulator::is_vcs()) {
          // VCS: 动态加载 tf_gettime
          using tf_gettime_t =
              decltype(&tf_gettime); // 若头文件可用；否则用 uint64_t(*)()
          auto tf_gettime_ptr =
              reinterpret_cast<tf_gettime_t>(dlsym(RTLD_DEFAULT, "tf_gettime"));
          if (!tf_gettime_ptr)
            throw std::runtime_error("tf_gettime not available in VCS");
          time = tf_gettime_ptr();
        } else {
          // 其他仿真器: svGetScopeFromName 静态可用，svGetTime 动态加载
          using svGetTime_t = void (*)(svScope, s_vpi_time *);
          static auto svGetTime_ptr =
              reinterpret_cast<svGetTime_t>(dlsym(RTLD_DEFAULT, "svGetTime"));

          if (!svGetTime_ptr)
            throw std::runtime_error("svGetTime not available");

          s_vpi_time vpi_time_s;
          vpi_time_s.type = vpiSimTime;
          const svScope scope = svGetScopeFromName(name); // 直接调用
          svGetTime_ptr(scope, &vpi_time_s);
          time = (uint64_t)vpi_time_s.high << 32 | vpi_time_s.low;
        }
        return time;
      },
      "Get the current simulation time, scaled to the time unit of the scope.");

  m.def(
      "get_time_unit",
      [](const char *name) {
        int32_t time_unit;
        if (simulator::is_vcs()) {
          // VCS: 动态加载 tf_gettimeunit
          using tf_gettimeunit_t = decltype(&tf_gettimeunit);
          auto tf_gettimeunit_ptr = reinterpret_cast<tf_gettimeunit_t>(
              dlsym(RTLD_DEFAULT, "tf_gettimeunit"));
          if (!tf_gettimeunit_ptr)
            throw std::runtime_error("tf_gettimeunit not available in VCS");
          time_unit = tf_gettimeunit_ptr();
        } else {
          // 其他仿真器: svGetScopeFromName 静态，svGetTimeUnit 动态
          using svGetTimeUnit_t = void (*)(svScope, int32_t *);
          static auto svGetTimeUnit_ptr = reinterpret_cast<svGetTimeUnit_t>(
              dlsym(RTLD_DEFAULT, "svGetTimeUnit"));

          if (!svGetTimeUnit_ptr)
            throw std::runtime_error("svGetTimeUnit not available");

          const svScope scope = svGetScopeFromName(name);
          svGetTimeUnit_ptr(scope, &time_unit);
        }
        return time_unit;
      },
      "Get the time unit for scope");

  m.def(
      "get_time_precision",
      [](const char *name) {
        int32_t precision;
        if (simulator::is_vcs()) {
          // VCS: 动态加载 tf_gettimeprecision
          using tf_gettimeprecision_t = decltype(&tf_gettimeprecision);
          auto tf_gettimeprecision_ptr =
              reinterpret_cast<tf_gettimeprecision_t>(
                  dlsym(RTLD_DEFAULT, "tf_gettimeprecision"));
          if (!tf_gettimeprecision_ptr)
            throw std::runtime_error(
                "tf_gettimeprecision not available in VCS");
          precision = tf_gettimeprecision_ptr();
        } else {
          // 其他仿真器: svGetScopeFromName 静态，svGetTimePrecision 动态
          using svGetTimePrecision_t = void (*)(svScope, int32_t *);
          static auto svGetTimePrecision_ptr =
              reinterpret_cast<svGetTimePrecision_t>(
                  dlsym(RTLD_DEFAULT, "svGetTimePrecision"));

          if (!svGetTimePrecision_ptr)
            throw std::runtime_error("svGetTimePrecision not available");

          const svScope scope = svGetScopeFromName(name);
          svGetTimePrecision_ptr(scope, &precision);
        }
        return precision;
      },
      "Get time precision for scope");
}

extern "C" {

// Both Python entry points return int on the C side. For py_task this is
// mandated by IEEE 1800-2023 35.5.4 (the DPI disable-protocol status, see
// below). py_func is an import *function*, for which IEEE allows void or a
// value; we choose int so the two entry points share one ABI and the SV
// declaration can state it explicitly. Neither entry point is ever disabled,
// so the status is always 0 (normal completion).
__attribute__((visibility("default"))) int
py_func(const char *mod_name, const char *func_name, const char *mod_paths) {

  if (!Py_IsInitialized()) {
    Py_Initialize();
  }

  // Whoever initialized CPython - this bridge or an embedder such as cocotb -
  // the thread that first gets here may still own the GIL: Py_Initialize()
  // leaves it held, and an embedder can do the same. With Verilator --timing
  // a DPI import task runs on a worker thread while the main thread waits in
  // VlDpiCall::handoffWorker(); if that thread keeps the GIL, the worker
  // blocks forever in PyGILState_Ensure() and the simulation deadlocks.
  // gil_scoped_acquire is a no-op on a thread that already holds the GIL (its
  // destructor will not release it), so drop the initial GIL once here and
  // let every call re-acquire it explicitly. The function-local static makes
  // this a single, thread-safe, one-time normalization.
  static const bool s_gil_normalized = [] {
    if (PyGILState_Check()) PyEval_SaveThread();
    return true;
  }();
  (void)s_gil_normalized;

  nb::gil_scoped_acquire gil;

  // Force-import the _svuvm extension so nanobind's internals
  // (nb::detail::internals, including the 3.0 interned-string
  // cache) are populated before we touch any nb::module_::import_
  // or nb::object::attr call below. py_func is a DPI export:
  // it is called by SystemVerilog through DPI, and the .so it
  // lives in is dlopen()ed by the simulator's VPI loader. The
  // Python side never gets a chance to do `import svuvm` first
  // (cocotb is driven by the testbench, not the other way
  // around), so the nanobind module init that would normally
  // populate nb_internals at `import _svuvm` time never runs.
  //
  // Pre-3.0 this was harmless because nb::module_::import_ used
  // a pure-Python C API path that didn't touch nb_internals.
  // Starting in 3.0 every attr() lookup routes through the
  // interned-string cache stored in nb_internals, and a NULL
  // nb_internals causes an immediate null-pointer dereference
  // in the very first `sys.attr("path")` call below.
  //
  // The import is idempotent: if some other path already
  // triggered svuvm's module init, PyImport_ImportModule
  // returns the existing module without re-running
  // _PyInit__svuvm.
  //
  // Note: import the package "svuvm", not the raw C
  // extension "_svuvm". __init__.py does
  //     from ._svuvm import *
  // so importing the package is what actually loads
  // _svuvm.so and runs PyInit__svuvm. A bare
  // PyImport_ImportModule("_svuvm") would fail with
  // ModuleNotFoundError because _svuvm is only registered
  // as a sub-module of the svuvm package, not at the
  // top level.
  PyImport_ImportModule("svuvm");
  if (PyErr_Occurred()) {
    PyErr_Print();
    return 0;
  }

  nb::module_ sys = nb::module_::import_("sys");
  nb::list path = sys.attr("path");

  nb::module_ sysconfig = nb::module_::import_("sysconfig");
  std::string ext_suffix =
      nb::cast<std::string>(sysconfig.attr("get_config_var")("EXT_SUFFIX"));

#ifdef __linux__
  char *dir_path;
  FILE *maps = fopen("/proc/self/maps", "r");
  if (!maps) {
    perror("Failed to open /proc/self/maps");
    return 0;
  }

  char self_addr_str[20];
  snprintf(self_addr_str, sizeof(self_addr_str), "%p", (void *)py_func);

  char line[256];
  bool found = false;
  while (fgets(line, sizeof(line), maps)) {
    if (strstr(line, ext_suffix.c_str())) {
      char *sopath = strchr(line, '/');
      if (sopath) {
        sopath = strtok(sopath, "\n");
        dir_path = dirname(sopath);
        path.attr("append")(dir_path);
        found = true;
        break;
      }
    }
  }

  // Always close the file handle to prevent resource leak
  fclose(maps);

  // Handle case when no matching extension is found
  if (!found) {
    std::cerr << "Warning: Could not find extension path in /proc/self/maps"
              << std::endl;
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
        nb::cast<std::string>(version_info) + "/site-packages";
    path.attr("append")(site_packages_path);
  }
#else
#error Platform not supported.
#endif

  if (strcmp(mod_paths, "") != 0) {
    path.attr("append")(mod_paths);
  }
  nb::print(path);

  // Defensive: an empty module name normally means a caller lost its
  // arguments (e.g. a forked SV child that had popped an empty queue).
  // import_("") raises ValueError, and an exception escaping this extern "C"
  // DPI entry reaches std::terminate and core-dumps the simulator. Skip the
  // call with a diagnostic instead.
  if (mod_name == nullptr || mod_name[0] == '\0') {
    std::cerr << "py_func: empty module name, skipping Python call" << std::endl;
    return 0;
  }

  // Route the import and the user-Python call through the shared C-boundary
  // guard. Unlike the old python_error-only catch, safe_invoke also contains
  // std::bad_cast / std::exception, so nothing can escape this extern "C" DPI
  // entry. Its python_error path still uses discard_as_unraisable(label) to
  // preserve the full Python traceback, and PLI_INT32 is int on this platform
  // so the return type matches this DPI function unchanged.
  return safe_invoke(
      [&]() {
        nb::module_ py_seq_mod = nb::module_::import_(mod_name);
        py_seq_mod.attr(func_name)();
      },
      "py_func");
}

// IEEE 1800-2023 35.5.4: an imported task's foreign-language implementation
// always returns int, matching the `extern int py_task(...)` prototype Verilator
// generates. That int is not a task result (SV tasks have no return value;
// outputs are passed by pointer) but the DPI disable-protocol status: 0 means
// the task completed normally, non-zero means it was disabled. Verilator
// enforces the int return with a static_assert in verilated_dpi.h.
// With --timing this import task runs on a worker thread, so Python reached
// from here may call suspendable exports. It forwards py_func's status; the
// bridge never disables either entry point, so that is always 0.
__attribute__((visibility("default"))) int
py_task(const char *mod_name, const char *func_name, const char *mod_paths) {
  return py_func(mod_name, func_name, mod_paths);
}

} // extern "C"