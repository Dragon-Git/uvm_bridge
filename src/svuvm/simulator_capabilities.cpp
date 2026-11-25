// Capability observation layer. This file only observes; it deliberately does
// not participate in the runtime fallbacks of exec_tcl_cmd() or
// vpi_func_optional(), which stay unchanged in their original TUs.

#include "simulator_capabilities.h"

#include <dlfcn.h>

namespace {

// A symbol counts as present only when dlsym neither set an error nor
// returned null. dlerror() must be cleared first, as required by POSIX.
bool probe(const char *name) {
  dlerror();
  void *ptr = dlsym(RTLD_DEFAULT, name);
  return dlerror() == nullptr && ptr != nullptr;
}

const char *simulator_name(int code) {
  switch (code) {
  case 0:
    return "UNKNOWN";
  case 1:
    return "VCS";
  case 2:
    return "VCSMX";
  case 3:
    return "XCELIUM";
  case 4:
    return "NCSC";
  case 5:
    return "MENTOR";
  case 6:
    return "VERILATOR";
  default:
    return "UNKNOWN";
  }
}

} // namespace

const SimulatorCapabilities &capabilities() {
  static const SimulatorCapabilities caps = [] {
    SimulatorCapabilities result;
    result.simulator = simulator_detect_code();
    result.name = simulator_name(result.simulator);

    // One dlsym() per entry point feeds both the observation flag and the
    // pointer retained for dispatch. probe() keeps its original semantics for
    // the remaining observation-only symbols.
    auto probe_time = [](const char *sym, bool &present) -> void * {
      dlerror();
      void *ptr = dlsym(RTLD_DEFAULT, sym);
      present = (dlerror() == nullptr && ptr != nullptr);
      return present ? ptr : nullptr;
    };

    result.tf_get_time = probe_time("tf_gettime", result.has_tf_gettime);
    result.tf_get_time_unit =
        probe_time("tf_gettimeunit", result.has_tf_gettimeunit);
    result.tf_get_time_precision =
        probe_time("tf_gettimeprecision", result.has_tf_gettimeprecision);
    result.dpi_get_time = probe_time("svGetTime", result.has_svGetTime);
    result.dpi_get_time_unit =
        probe_time("svGetTimeUnit", result.has_svGetTimeUnit);
    result.dpi_get_time_precision =
        probe_time("svGetTimePrecision", result.has_svGetTimePrecision);
    result.has_vpi_get_vlog_info = probe("vpi_get_vlog_info");

    // Observation only: these flags are exported to Python but never used to
    // choose a code path in the bridge.
    result.has_tcl_mhpi = probe("mhpi_ucliTclExec");
    result.has_tcl_cfc = probe("cfcExecuteCommand");
    result.has_tcl_mti = probe("mti_Cmd");
    result.has_vpi_get_data = probe("vpi_get_data");
    result.has_vpi_put_data = probe("vpi_put_data");
    return result;
  }();
  return caps;
}
