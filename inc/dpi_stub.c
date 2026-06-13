/*
 * DPI Stub Library
 *
 * 提供 DPI / VPI / UVM DPI 以及项目自定义 export 函数的空实现，
 * 使得 svuvm 共享库可以在没有 Verilog 模拟器的情况下被 Python 加载，
 * 以便生成 stub 与 IDE 提示。生产环境中这些符号由 Verilog 模拟器提供。
 *
 * 类型定义统一来自项目 inc/ 目录下的标准头文件 (svdpi.h / vpi_user.h)，
 * 不在此文件中重复声明。函数签名严格匹配这些头文件中的原型。
 */

#include <stdint.h>
#include <stddef.h>
#include "svdpi.h"
#include "vpi_user.h"
#include "uvm_dpi.h"

/* ===== SV DPI stubs ===== */

svScope svGetScope(void) { return (svScope)0; }
svScope svSetScope(const svScope scope) { return scope; }
svScope svGetScopeFromName(const char *name) { (void)name; return (svScope)0; }
const char *svGetNameFromScope(const svScope scope) { (void)scope; return ""; }
int svGetTime(const svScope scope, svTimeVal *time_p) { (void)scope; (void)time_p; return 0; }
int svGetTimeUnit(const svScope scope, int32_t *time_unit) {
    (void)scope; (void)time_unit; return 0;
}
int svGetTimePrecision(const svScope scope, int32_t *precision) {
    (void)scope; (void)precision; return 0;
}

/* ===== VPI function stubs ===== */

vpiHandle vpi_register_cb(p_cb_data cb_data) { (void)cb_data; return (vpiHandle)0; }
PLI_INT32 vpi_remove_cb(vpiHandle cb_obj) { (void)cb_obj; return 0; }
void vpi_get_cb_info(vpiHandle object, p_cb_data cb_data) { (void)object; (void)cb_data; }

vpiHandle vpi_register_systf(p_vpi_systf_data systf_data) {
    (void)systf_data; return (vpiHandle)0;
}
void vpi_get_systf_info(vpiHandle obj, p_vpi_systf_data data) { (void)obj; (void)data; }

vpiHandle vpi_handle_by_name(PLI_BYTE8 *name, vpiHandle scope) {
    (void)name; (void)scope; return (vpiHandle)0;
}
vpiHandle vpi_handle_by_index(vpiHandle obj, PLI_INT32 indx) {
    (void)obj; (void)indx; return (vpiHandle)0;
}
vpiHandle vpi_handle(PLI_INT32 type, vpiHandle ref) {
    (void)type; (void)ref; return (vpiHandle)0;
}
vpiHandle vpi_handle_multi(PLI_INT32 type, vpiHandle ref1, vpiHandle ref2, ...) {
    (void)type; (void)ref1; (void)ref2; return (vpiHandle)0;
}
vpiHandle vpi_iterate(PLI_INT32 type, vpiHandle ref) {
    (void)type; (void)ref; return (vpiHandle)0;
}
vpiHandle vpi_scan(vpiHandle iter) { (void)iter; return (vpiHandle)0; }

PLI_INT32 vpi_get(PLI_INT32 property, vpiHandle obj) { (void)property; (void)obj; return 0; }
PLI_INT64 vpi_get64(PLI_INT32 property, vpiHandle obj) {
    (void)property; (void)obj; return 0;
}
PLI_BYTE8 *vpi_get_str(PLI_INT32 property, vpiHandle obj) {
    (void)property; (void)obj; return (PLI_BYTE8 *)"";
}

void vpi_get_delays(vpiHandle obj, p_vpi_delay delay_p) { (void)obj; }
void vpi_put_delays(vpiHandle obj, p_vpi_delay delay_p) { (void)obj; }
void vpi_get_time(vpiHandle obj, p_vpi_time t) { (void)obj; (void)t; }

void vpi_get_value(vpiHandle expr, p_vpi_value value) { (void)expr; (void)value; }
vpiHandle vpi_put_value(vpiHandle expr, p_vpi_value value, p_vpi_time when, PLI_INT32 flags) {
    (void)expr; (void)value; (void)when; (void)flags; return (vpiHandle)0;
}
void vpi_get_value_array(vpiHandle expr, p_vpi_arrayvalue arrayvalue_p, PLI_INT32 *index_p, PLI_UINT32 num) {
    (void)expr; (void)arrayvalue_p; (void)index_p; (void)num;
}
void vpi_put_value_array(vpiHandle expr, p_vpi_arrayvalue arrayvalue, PLI_INT32 *index_p, PLI_UINT32 num) {
    (void)expr; (void)arrayvalue; (void)index_p; (void)num;
}

PLI_UINT32 vpi_mcd_open(PLI_BYTE8 *fileName) { (void)fileName; return 0; }
PLI_UINT32 vpi_mcd_close(PLI_UINT32 mcd) { (void)mcd; return 0; }
PLI_BYTE8 *vpi_mcd_name(PLI_UINT32 mcd) { (void)mcd; return (PLI_BYTE8 *)""; }
PLI_INT32 vpi_mcd_printf(PLI_UINT32 mcd, PLI_BYTE8 *format, ...) {
    (void)mcd; (void)format; return 0;
}
PLI_INT32 vpi_printf(PLI_BYTE8 *format, ...) { (void)format; return 0; }
PLI_INT32 vpi_compare_objects(vpiHandle obj1, vpiHandle obj2) {
    (void)obj1; (void)obj2; return 0;
}
PLI_INT32 vpi_free_object(vpiHandle obj) { (void)obj; return 0; }
PLI_INT32 vpi_release_handle(vpiHandle obj) { (void)obj; return 0; }
PLI_INT32 vpi_flush(void) { return 0; }
PLI_INT32 vpi_mcd_flush(PLI_UINT32 mcd) { (void)mcd; return 0; }
PLI_INT32 vpi_chk_error(p_vpi_error_info info) { (void)info; return 0; }
PLI_INT32 vpi_get_vlog_info(p_vpi_vlog_info info) { (void)info; return 0; }
void *vpi_get_userdata(vpiHandle obj) { (void)obj; return (void *)0; }
PLI_INT32 vpi_put_userdata(vpiHandle obj, void *userdata) {
    (void)obj; (void)userdata; return 0;
}
PLI_INT32 vpi_get_data(PLI_INT32 id, PLI_BYTE8 *dataLoc, PLI_INT32 numOfBytes) {
    (void)id; (void)dataLoc; (void)numOfBytes; return 0;
}
PLI_INT32 vpi_put_data(PLI_INT32 id, PLI_BYTE8 *dataLoc, PLI_INT32 numOfBytes) {
    (void)id; (void)dataLoc; (void)numOfBytes; return 0;
}
PLI_INT32 vpi_control(PLI_INT32 operation, ...) { (void)operation; return 0; }
vpiHandle vpi_handle_by_multi_index(vpiHandle obj, PLI_INT32 num_index, PLI_INT32 *index_array) {
    (void)obj; (void)num_index; (void)index_array; return (vpiHandle)0;
}

/* ===== UVM DPI stubs ===== */

int int_str_max(int val) { (void)val; return 0; }

void m_uvm_report_dpi(int severity, char *id, char *message,
                      int verbosity, char *filename, int line) {
    (void)severity; (void)id; (void)message;
    (void)verbosity; (void)filename; (void)line;
}

int uvm_hdl_check_path(char *path) { (void)path; return 0; }
int uvm_hdl_read(char *path, p_vpi_vecval value) { (void)path; (void)value; return 0; }
int uvm_hdl_deposit(char *path, p_vpi_vecval value) { (void)path; (void)value; return 0; }
int uvm_hdl_force(char *path, p_vpi_vecval value) { (void)path; (void)value; return 0; }
int uvm_hdl_release_and_read(char *path, p_vpi_vecval value) { (void)path; (void)value; return 0; }
int uvm_hdl_release(char *path) { (void)path; return 0; }

void push_data(int lvl, char *entry, int cmd) { (void)lvl; (void)entry; (void)cmd; }
void walk_level(int lvl, int argc, char **argv, int cmd) {
    (void)lvl; (void)argc; (void)argv; (void)cmd;
}

const char *uvm_dpi_get_next_arg_c(int init) { (void)init; return (const char *)0; }
char *uvm_dpi_get_tool_name_c(void) { return (char *)"stub-simulator"; }
char *uvm_dpi_get_tool_version_c(void) { return (char *)"0.0"; }

/* ===== DPI Export stubs (from SystemVerilog to C++) ===== */
/* 此段由 scripts/generate_dpi_stub.py 自动生成，请勿手工修改。
 * 若需要新增 export function，请在 src/svuvm/python_bridge_pkg.sv
 * 中添加对应的 `export "DPI-C" function/task` 声明，
 * 然后执行 `scripts/generate_dpi_stub.py <project_root>` 即可。
 */

void process_pool_run(const char *name) { (void)name; }
void process_pool_clear(void) {}

void print_factory(int all_types) { (void)all_types; }
void set_factory_inst_override(const char *req, const char *over, const char *ctx) {
    (void)req; (void)over; (void)ctx;
}
void set_factory_type_override(const char *req, const char *over, unsigned char replace) {
    (void)req; (void)over; (void)replace;
}
void create_object_by_name(const char *req, const char *ctx, const char *name) {
    (void)req; (void)ctx; (void)name;
}
void create_component_by_name(const char *req, const char *ctx, const char *name) {
    (void)req; (void)ctx; (void)name;
}
void debug_factory_create(const char *req, const char *ctx) { (void)req; (void)ctx; }
void find_factory_override(const char *req, const char *ctx, const char *over) {
    (void)req; (void)ctx; (void)over;
}
void print_topology(const char *ctx) { (void)ctx; }
void set_timeout(long long timeout, unsigned char overridable) { (void)timeout; (void)overridable; }
void set_finish_on_completion(unsigned char f) { (void)f; }

void uvm_objection_op(const char *op, const char *name, const char *ctx,
                      const char *desc, unsigned int count) {
    (void)op; (void)name; (void)ctx; (void)desc; (void)count;
}
void dbg_print(const char *name) { (void)name; }
void tlm_connect(const char *src, const char *dst) { (void)src; (void)dst; }

void wait_on(const char *ev_name, unsigned char delta) { (void)ev_name; (void)delta; }
void wait_off(const char *ev_name, unsigned char delta) { (void)ev_name; (void)delta; }
void wait_trigger(const char *ev_name) { (void)ev_name; }
void wait_ptrigger(const char *ev_name) { (void)ev_name; }
long long get_trigger_time(const char *ev_name) { (void)ev_name; return 0; }
unsigned char is_on(const char *ev_name) { (void)ev_name; return 0; }
unsigned char is_off(const char *ev_name) { (void)ev_name; return 0; }
void reset(const char *ev_name, unsigned char wakeup) { (void)ev_name; (void)wakeup; }
void cancel(const char *ev_name) { (void)ev_name; }
int get_num_waiters(const char *ev_name) { (void)ev_name; return 0; }
void trigger(const char *ev_name) { (void)ev_name; }

void set_config_uint64_t(const char *ctx, const char *inst, const char *field, uint64_t value) {
    (void)ctx; (void)inst; (void)field; (void)value;
}
uint64_t get_config_uint64_t(const char *ctx, const char *inst, const char *field) {
    (void)ctx; (void)inst; (void)field; return 0;
}
void set_config_double(const char *ctx, const char *inst, const char *field, double value) {
    (void)ctx; (void)inst; (void)field; (void)value;
}
double get_config_double(const char *ctx, const char *inst, const char *field) {
    (void)ctx; (void)inst; (void)field; return 0.0;
}
void set_config_string(const char *ctx, const char *inst, const char *field, const char *value) {
    (void)ctx; (void)inst; (void)field; (void)value;
}
const char *get_config_string(const char *ctx, const char *inst, const char *field) {
    (void)ctx; (void)inst; (void)field; return "";
}
void config_db_trace_on(void) {}
void config_db_trace_off(void) {}

int get_report_verbosity_level(const char *ctx, int severity, const char *id) {
    (void)ctx; (void)severity; (void)id; return 0;
}
int get_report_max_verbosity_level(const char *ctx) { (void)ctx; return 0; }
void set_report_verbosity_level(const char *ctx, int level) { (void)ctx; (void)level; }
void set_report_id_verbosity(const char *ctx, const char *id, int verbosity) {
    (void)ctx; (void)id; (void)verbosity;
}
void set_report_severity_id_verbosity(const char *ctx, int severity, const char *id, int verbosity) {
    (void)ctx; (void)severity; (void)id; (void)verbosity;
}
int get_report_action(const char *ctx, int severity, const char *id) {
    (void)ctx; (void)severity; (void)id; return 0;
}
void set_report_severity_action(const char *ctx, int severity, int action) {
    (void)ctx; (void)severity; (void)action;
}
void set_report_id_action(const char *ctx, const char *id, int action) {
    (void)ctx; (void)id; (void)action;
}
void set_report_severity_id_action(const char *ctx, int severity, const char *id, int action) {
    (void)ctx; (void)severity; (void)id; (void)action;
}
void set_report_severity_override(const char *ctx, int cur, int new_sev) {
    (void)ctx; (void)cur; (void)new_sev;
}
void set_report_severity_id_override(const char *ctx, int cur, const char *id, int new_sev) {
    (void)ctx; (void)cur; (void)id; (void)new_sev;
}
void set_max_quit_count(int count, unsigned char overridable) { (void)count; (void)overridable; }
int get_max_quit_count(void) { return 0; }
void set_quit_count(int quit_count) { (void)quit_count; }
int get_quit_count(void) { return 0; }
void set_severity_count(int severity, int count) { (void)severity; (void)count; }
int get_severity_count(int severity) { (void)severity; return 0; }
void set_id_count(const char *id, int count) { (void)id; (void)count; }
int get_id_count(const char *id) { (void)id; return 0; }
void print_report_server(void) {}
void report_summarize(void) {}

void start_seq(const char *seq, const char *sqr, unsigned char rand_en, unsigned char background) {
    (void)seq; (void)sqr; (void)rand_en; (void)background;
}
void write_reg(const char *name, int data) { (void)name; (void)data; }
void read_reg(const char *name, int *data) { (void)name; (void)data; }
void check_reg(const char *name, int data, unsigned char predict) { (void)name; (void)data; (void)predict; }
void wait_unit(int n) { (void)n; }
void run_test_wrap(const char *test_name) { (void)test_name; }
