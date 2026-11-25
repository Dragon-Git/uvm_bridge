#ifndef UVM_BRIDGE_SIMULATOR_CAPABILITIES_H
#define UVM_BRIDGE_SIMULATOR_CAPABILITIES_H

#include <string>

// Snapshot of the simulator type, the optional symbols exposed by the host,
// and the resolved addresses of the six simulation-time entry points. The two
// dimensions are deliberately orthogonal:
//   * `simulator` comes from the existing simulator::detect() classifier;
//   * each `has_*` flag is a live dlsym() probe of the named symbol.
// The retained DPI/TF pointers let callers dispatch on actual symbol
// availability rather than on the simulator name. They are stored as void* so
// this header stays independent of svdpi.h; callers reinterpret_cast them to
// the correct signature at the use site. Nothing here changes the runtime
// probes in exec_tcl_cmd() or vpi_func_optional(), and a missing symbol never
// silently switches a path: callers still throw when no usable entry point
// exists.
struct SimulatorCapabilities {
  int simulator = 0; // Numeric value of the existing enum Simulator; 0 = UNKNOWN.
  std::string name;

  // Resolved simulation-time entry points; nullptr means the symbol is absent.
  // DPI (svGetTime*) wins over TF (tf_gettime*) when both are available.
  void *dpi_get_time = nullptr;
  void *dpi_get_time_unit = nullptr;
  void *dpi_get_time_precision = nullptr;
  void *tf_get_time = nullptr;
  void *tf_get_time_unit = nullptr;
  void *tf_get_time_precision = nullptr;

  bool has_tf_gettime = false;
  bool has_tf_gettimeunit = false;
  bool has_tf_gettimeprecision = false;
  bool has_svGetTime = false;
  bool has_svGetTimeUnit = false;
  bool has_svGetTimePrecision = false;
  bool has_vpi_get_vlog_info = false;
  // Observation-only: no dispatch anywhere uses these four flags.
  bool has_tcl_mhpi = false;
  bool has_tcl_cfc = false;
  bool has_tcl_mti = false;
  bool has_vpi_get_data = false;
  bool has_vpi_put_data = false;
};

// Function-local static: detect() and every probe run exactly once.
const SimulatorCapabilities &capabilities();

// Thin accessor implemented next to simulator::detect() in svuvm.cpp; it lets
// the capability TU reuse the unchanged detector without moving that code.
int simulator_detect_code();

#endif // UVM_BRIDGE_SIMULATOR_CAPABILITIES_H
