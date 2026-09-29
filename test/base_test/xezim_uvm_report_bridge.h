/* Force C linkage for SV-exported callbacks that uvm_common.c declares
 * without a linkage specification.
 *
 * uvm_dpi_xezim.cc #includes uvm_common.c, which declares
 * `extern void m__uvm_report_dpi(...)`. Compiled as C++ that picks up
 * C++ linkage, so the resulting .so asks for the mangled name while the
 * simulator's export trampoline provides the C name. Forcing the
 * declaration through -include (before uvm_common.c is seen) makes the
 * C linkage stick. */

#ifndef XEZIM_UVM_REPORT_BRIDGE_H
#define XEZIM_UVM_REPORT_BRIDGE_H

#ifdef __cplusplus
extern "C" {
#endif

void m__uvm_report_dpi(int severity, const char *id, const char *message,
                       int verbosity, const char *file, int line);

#ifdef __cplusplus
}
#endif

#endif /* XEZIM_UVM_REPORT_BRIDGE_H */
