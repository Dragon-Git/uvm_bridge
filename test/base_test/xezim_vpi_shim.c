/* No-op shims for the VPI surface that xezim does not implement (its
 * vpi_user.h deliberately omits them). Only these symbols are defined
 * here so nothing shadows xezim's real implementations. Parameters that
 * would need struct types xezim's headers don't declare are typed void*
 * (ABI-compatible: all pointers). */

#include "vpi_user.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>

/* The shim is inserted into processes that have no VPI (xezim's compiler
 * child), and macOS resolves dynamic_lookup imports eagerly at load time —
 * which would kill those processes. Weak imports bind to NULL when no
 * definition is present (never called there) and still resolve to the real
 * implementations inside xezim. */
__attribute__((weak)) int       vpi_get(PLI_INT32 property, vpiHandle object);
__attribute__((weak)) void      vpi_get_time(vpiHandle object, s_vpi_time *time_p);
__attribute__((weak)) vpiHandle vpi_handle(PLI_INT32 type, vpiHandle ref);

/* uvm_dpi_xezim.cc (preloaded) calls this SV export, which xezim's export
 * trampoline provides only after startup, i.e. too late for a preloaded
 * library to relocate against. Provide a weak fallback so the preload
 * always loads; a strong definition from the trampoline still wins when
 * the loader can see it. */
__attribute__((weak)) void m__uvm_report_dpi(int severity, const char *id,
                                             const char *message, int verbosity,
                                             const char *file, int line) {
    fprintf(stderr, "[xezim-shim] uvm_report (sev=%d id=%s): %s\n", severity,
            id ? id : "?", message ? message : "?");
}

/* xezim exports neither svGetTime nor svGetTimeUnit/svGetTimePrecision, all
 * of which svuvm looks up with dlsym(RTLD_DEFAULT); a miss throws and aborts
 * the Python test. Map them onto VPI. Time is available (vpi_get_time);
 * xezim's vpi_get has no vpiTimeUnit/vpiTimePrecision property, so those two
 * report 0 instead of failing. */
#ifndef vpiTimeUnit
#define vpiTimeUnit 50
#endif
#ifndef vpiTimePrecision
#define vpiTimePrecision 51
#endif

void svGetTime(void *scope, s_vpi_time *time_p) {
    (void)scope;
    if (time_p) vpi_get_time(0, time_p);
}

void svGetTimeUnit(void *scope, PLI_INT32 *unit) {
    (void)scope;
    if (unit) *unit = vpi_get(vpiTimeUnit, vpi_handle(vpiScope, 0));
}

void svGetTimePrecision(void *scope, PLI_INT32 *precision) {
    (void)scope;
    if (precision) *precision = vpi_get(vpiTimePrecision, vpi_handle(vpiScope, 0));
}

/* Bootstrap loader (macOS). DYLD_INSERT_LIBRARIES with libpython itself is
 * not possible there: the python.org dylib has no arm64e slice, and the
 * compiler child xezim spawns for the export trampoline is an arm64e
 * platform binary, so dyld terminates it. Only this shim is inserted
 * (built as a fat arm64+arm64e dylib so it loads in both); its constructor
 * dlopens the libraries listed in XEZIM_PRELOAD_LIBS into the global
 * scope. Inside xezim every entry resolves; in other processes (the
 * compiler child) the failures are expected and harmless. */
__attribute__((constructor)) static void xezim_preload_bootstrap(void) {
    const char *list = getenv("XEZIM_PRELOAD_LIBS");
    char *buf;
    char *p;
    if (!list || !*list) return;
    buf = strdup(list);
    if (!buf) return;
    for (p = strtok(buf, " "); p; p = strtok(NULL, " ")) {
        if (!dlopen(p, RTLD_NOW | RTLD_GLOBAL))
            fprintf(stderr, "[xezim-shim] preload %s: %s\n", p, dlerror());
    }
    free(buf);
}

int       vpi_compare_objects(vpiHandle h1, vpiHandle h2) { return 0; }
int       vpi_flush(void) { return 0; }
long long vpi_get64(PLI_INT32 property, vpiHandle ref) { return 0; }
void      vpi_get_delays(vpiHandle ref, void *delays) {}
void      vpi_get_systf_info(vpiHandle ref, void *info) {}
void     *vpi_get_userdata(vpiHandle obj) { return 0; }
void      vpi_get_value_array(vpiHandle obj, void *values, void *times, PLI_INT32 num) {}
vpiHandle vpi_handle_by_multi_index(PLI_INT32 type, vpiHandle ref, PLI_INT32 num, PLI_INT32 *index) { return 0; }
vpiHandle vpi_handle_multi(PLI_INT32 type, vpiHandle ref1, vpiHandle ref2) { return 0; }
PLI_INT32 vpi_mcd_close(PLI_UINT32 mcd) { return 0; }
PLI_INT32 vpi_mcd_flush(PLI_UINT32 mcd) { return 0; }
PLI_BYTE8 *vpi_mcd_name(PLI_UINT32 mcd) { return 0; }
PLI_UINT32 vpi_mcd_open(const PLI_BYTE8 *name) { return 0; }
void      vpi_put_delays(vpiHandle ref, void *delays) {}
PLI_INT32 vpi_put_userdata(vpiHandle obj, void *userdata) { return 0; }
void      vpi_put_value_array(vpiHandle obj, void *values, void *times, PLI_INT32 num) {}
