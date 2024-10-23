#include "svdpi.h"
#include <dlfcn.h>
#include <libgen.h>
#include <pybind11/embed.h>
#include <pybind11/pybind11.h>
#include <string>
#if defined(VCS) || defined(VCSMX)
#include <mhpi_user.h>
#elif defined(XCELIUM) || defined(NCSC)
#include <cfclib.h>
#elif defined(MENTOR)
#include <mti.h>
#endif

#ifndef NO_VPI
#include "vpi_user.h"
#endif

extern "C" {

namespace py = pybind11;
#include "uvm_dpi.h"

void print_factory(int all_types = 1);
void set_factory_inst_override(const char *original_type_name,
                               const char *override_type_name,
                               const char *full_inst_path);
void set_factory_type_override(const char *original_type_name,
                               const char *override_type_name,
                               bool replace = 1);
void create_object_by_name(const char *requested_type, const char *context = "",
                           const char *name = "");
void create_component_by_name(const char *requested_type,
                              const char *context = "", const char *name = "",
                              const char *parent_name = "");
void debug_factory_create(const char *requested_type, const char *context = "");
void find_factory_override(const char *requested_type, const char *context,
                           const char *override_type_name);
void print_topology(const char *context = "");
void set_timeout(long long timeout, unsigned char overridable = 1);
void uvm_objection_op(const char *op, const char *name, const char *contxt,
                      const char *description, unsigned int count);
void dbg_print(const char *name = "");

#if defined(VCS) || defined(VCSMX) || defined(XCELIUM) || defined(NCSC)
void wait_on(const char *ev_name, int delta);
void wait_off(const char *ev_name, int delta);
void wait_trigger(const char *ev_name);
void wait_ptrigger(const char *ev_name);
// void wait_trigger_data(uvm_object *data, const char* ev_name);
// void wait_ptrigger_data(uvm_object *data, const char* ev_name);
uint64_t get_trigger_time(const char *ev_name);
int is_on(const char *ev_name);
int is_off(const char *ev_name);
void reset(const char *ev_name, int wakeup);
void cancel(const char *ev_name);
int get_num_waiters(const char *ev_name);
void trigger(const char *ev_name);
// uvm_object *get_trigger_data();
// uvm_object *get_default_data();
// void set_default_data(uvm_object *data);
#endif

void set_config_int(const char *contxt, const char *inst_name,
                    const char *field_name, uint64_t value);
uint64_t get_config_int(const char *contxt, const char *inst_name,
                        const char *field_name);
void set_config_string(const char *contxt, const char *inst_name,
                       const char *field_name, const char *value);
const char *get_config_string(const char *contxt, const char *inst_name,
                              const char *field_name);

#if defined(VCS) || defined(VCSMX) || defined(XCELIUM) || defined(NCSC)
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
#endif

void start_seq(const char *seq_name, const char *sqr_name, svBit rand_en,
               svBit background);
void write_reg(const char *name, int data);
void read_reg(const char *name, int *data);
void check_reg(const char *name, int data = 0, unsigned char predict = 0);
void run_test_wrap(const char *test_name = "");
void wait_unit(int n);
void stop();

int wrap_read_reg(const char *name) {
  int data;
  read_reg(name, &data);
  return data;
}

// execute a tcl comamnd in simulator
void exec_tcl_cmd(char *cmd) {
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

#ifndef NO_VPI
vpiHandle vpi_handle_multi_wrap(int type, vpiHandle refHandle1,
                                vpiHandle refHandle2, py::args ref_handles) {
  std::vector<vpiHandle> c_ref_handles;
  for (const auto &arg : ref_handles) {
    if (py::isinstance<py::capsule>(arg)) {
      c_ref_handles.push_back(
          reinterpret_cast<vpiHandle>(arg.cast<py::capsule>().ptr()));
    } else {
      throw std::runtime_error(
          "Invalid argument type for vpiHandle conversion.");
    }
  }
  return vpi_handle_multi(type, refHandle1, refHandle2, c_ref_handles.data());
}

int vpi_mcd_printf_wrap(unsigned int mcd, py::str format, py::args args,
                        py::kwargs kwargs) {
  std::string formatted = format.format(*args, **kwargs);
  int result = vpi_mcd_printf(mcd, "%s", formatted.c_str());
  return result;
}

int vpi_printf_wrap(py::str format, py::args args, py::kwargs kwargs) {
  std::string formatted = format.format(*args, **kwargs);
  int result = vpi_printf("%s", formatted.c_str());
  return result;
}

int vpi_control_wrap(int operation, py::args args) {
  std::vector<void *> c_args;
  for (const auto &arg : args) {
    c_args.push_back(arg.cast<void *>());
  }
  return vpi_control(operation, c_args.data());
}
#endif

PYBIND11_MODULE(svuvm, m) {
  m.doc() = "svuvm api module";

#ifndef NO_VPI
  // VPI wrapper
  py::module_ vpi = m.def_submodule("vpi");

  // vpi handle types
  vpi.attr("vpiAlways") = vpiAlways;
  vpi.attr("vpiAssignStmt") = vpiAssignStmt;
  vpi.attr("vpiAssignment") = vpiAssignment;
  vpi.attr("vpiBegin") = vpiBegin;
  vpi.attr("vpiCase") = vpiCase;
  vpi.attr("vpiCaseItem") = vpiCaseItem;
  vpi.attr("vpiConstant") = vpiConstant;
  vpi.attr("vpiContAssign") = vpiContAssign;
  vpi.attr("vpiDeassign") = vpiDeassign;
  vpi.attr("vpiDefParam") = vpiDefParam;
  vpi.attr("vpiDelayControl") = vpiDelayControl;
  vpi.attr("vpiDisable") = vpiDisable;
  vpi.attr("vpiEventControl") = vpiEventControl;
  vpi.attr("vpiEventStmt") = vpiEventStmt;
  vpi.attr("vpiFor") = vpiFor;
  vpi.attr("vpiForce") = vpiForce;
  vpi.attr("vpiForever") = vpiForever;
  vpi.attr("vpiFork") = vpiFork;
  vpi.attr("vpiFuncCall") = vpiFuncCall;
  vpi.attr("vpiFunction") = vpiFunction;
  vpi.attr("vpiGate") = vpiGate;
  vpi.attr("vpiIf") = vpiIf;
  vpi.attr("vpiIfElse") = vpiIfElse;
  vpi.attr("vpiInitial") = vpiInitial;
  vpi.attr("vpiIntegerVar") = vpiIntegerVar;
  vpi.attr("vpiInterModPath") = vpiInterModPath;
  vpi.attr("vpiIterator") = vpiIterator;
  vpi.attr("vpiIODecl") = vpiIODecl;
  vpi.attr("vpiMemory") = vpiMemory;
  vpi.attr("vpiMemoryWord") = vpiMemoryWord;
  vpi.attr("vpiModPath") = vpiModPath;
  vpi.attr("vpiModule") = vpiModule;
  vpi.attr("vpiNamedBegin") = vpiNamedBegin;
  vpi.attr("vpiNamedEvent") = vpiNamedEvent;
  vpi.attr("vpiNamedFork") = vpiNamedFork;
  vpi.attr("vpiNet") = vpiNet;
  vpi.attr("vpiNetBit") = vpiNetBit;
  vpi.attr("vpiNullStmt") = vpiNullStmt;
  vpi.attr("vpiOperation") = vpiOperation;
  vpi.attr("vpiParamAssign") = vpiParamAssign;
  vpi.attr("vpiParameter") = vpiParameter;
  vpi.attr("vpiPartSelect") = vpiPartSelect;
  vpi.attr("vpiPathTerm") = vpiPathTerm;
  vpi.attr("vpiPort") = vpiPort;
  vpi.attr("vpiPortBit") = vpiPortBit;
  vpi.attr("vpiPrimTerm") = vpiPrimTerm;
  vpi.attr("vpiRealVar") = vpiRealVar;
  vpi.attr("vpiReg") = vpiReg;
  vpi.attr("vpiRegBit") = vpiRegBit;
  vpi.attr("vpiRelease") = vpiRelease;
  vpi.attr("vpiRepeat") = vpiRepeat;
  vpi.attr("vpiRepeatControl") = vpiRepeatControl;
  vpi.attr("vpiSchedEvent") = vpiSchedEvent;
  vpi.attr("vpiSpecParam") = vpiSpecParam;
  vpi.attr("vpiSwitch") = vpiSwitch;
  vpi.attr("vpiSysFuncCall") = vpiSysFuncCall;
  vpi.attr("vpiSysTaskCall") = vpiSysTaskCall;
  vpi.attr("vpiTableEntry") = vpiTableEntry;
  vpi.attr("vpiTask") = vpiTask;
  vpi.attr("vpiTaskCall") = vpiTaskCall;
  vpi.attr("vpiTchk") = vpiTchk;
  vpi.attr("vpiTchkTerm") = vpiTchkTerm;
  vpi.attr("vpiTimeVar") = vpiTimeVar;
  vpi.attr("vpiTimeQueue") = vpiTimeQueue;
  vpi.attr("vpiUdp") = vpiUdp;
  vpi.attr("vpiUdpDefn") = vpiUdpDefn;
  vpi.attr("vpiUserSystf") = vpiUserSystf;
  vpi.attr("vpiVarSelect") = vpiVarSelect;
  vpi.attr("vpiWait") = vpiWait;
  vpi.attr("vpiWhile") = vpiWhile;
  vpi.attr("vpiAttribute") = vpiAttribute;
  vpi.attr("vpiBitSelect") = vpiBitSelect;
  vpi.attr("vpiCallback") = vpiCallback;
  vpi.attr("vpiDelayTerm") = vpiDelayTerm;
  vpi.attr("vpiDelayDevice") = vpiDelayDevice;
  vpi.attr("vpiFrame") = vpiFrame;
  vpi.attr("vpiGateArray") = vpiGateArray;
  vpi.attr("vpiModuleArray") = vpiModuleArray;
  vpi.attr("vpiPrimitiveArray") = vpiPrimitiveArray;
  vpi.attr("vpiNetArray") = vpiNetArray;
  vpi.attr("vpiRange") = vpiRange;
  vpi.attr("vpiRegArray") = vpiRegArray;
  vpi.attr("vpiSwitchArray") = vpiSwitchArray;
  vpi.attr("vpiUdpArray") = vpiUdpArray;
  vpi.attr("vpiContAssignBit") = vpiContAssignBit;
  vpi.attr("vpiNamedEventArray") = vpiNamedEventArray;
  vpi.attr("vpiIndexedPartSelect") = vpiIndexedPartSelect;
  vpi.attr("vpiGenScopeArray") = vpiGenScopeArray;
  vpi.attr("vpiGenScope") = vpiGenScope;
  vpi.attr("vpiGenVar") = vpiGenVar;
  vpi.attr("vpiCondition") = vpiCondition;
  vpi.attr("vpiDelay") = vpiDelay;
  vpi.attr("vpiElseStmt") = vpiElseStmt;
  vpi.attr("vpiForIncStmt") = vpiForIncStmt;
  vpi.attr("vpiForInitStmt") = vpiForInitStmt;
  vpi.attr("vpiHighConn") = vpiHighConn;
  vpi.attr("vpiLhs") = vpiLhs;
  vpi.attr("vpiIndex") = vpiIndex;
  vpi.attr("vpiLeftRange") = vpiLeftRange;
  vpi.attr("vpiLowConn") = vpiLowConn;
  vpi.attr("vpiParent") = vpiParent;
  vpi.attr("vpiRhs") = vpiRhs;
  vpi.attr("vpiRightRange") = vpiRightRange;
  vpi.attr("vpiScope") = vpiScope;
  vpi.attr("vpiSysTfCall") = vpiSysTfCall;
  vpi.attr("vpiTchkDataTerm") = vpiTchkDataTerm;
  vpi.attr("vpiTchkNotifier") = vpiTchkNotifier;
  vpi.attr("vpiTchkRefTerm") = vpiTchkRefTerm;
  vpi.attr("vpiArgument") = vpiArgument;
  vpi.attr("vpiBit") = vpiBit;
  vpi.attr("vpiDriver") = vpiDriver;
  vpi.attr("vpiInternalScope") = vpiInternalScope;
  vpi.attr("vpiLoad") = vpiLoad;
  vpi.attr("vpiModDataPathIn") = vpiModDataPathIn;
  vpi.attr("vpiModPathIn") = vpiModPathIn;
  vpi.attr("vpiModPathOut") = vpiModPathOut;
  vpi.attr("vpiOperand") = vpiOperand;
  vpi.attr("vpiPortInst") = vpiPortInst;
  vpi.attr("vpiProcess") = vpiProcess;
  vpi.attr("vpiVariables") = vpiVariables;
  vpi.attr("vpiUse") = vpiUse;
  vpi.attr("vpiExpr") = vpiExpr;
  vpi.attr("vpiPrimitive") = vpiPrimitive;
  vpi.attr("vpiStmt") = vpiStmt;
  vpi.attr("vpiActiveTimeFormat") = vpiActiveTimeFormat;
  vpi.attr("vpiInTerm") = vpiInTerm;
  vpi.attr("vpiInstanceArray") = vpiInstanceArray;
  vpi.attr("vpiLocalDriver") = vpiLocalDriver;
  vpi.attr("vpiLocalLoad") = vpiLocalLoad;
  vpi.attr("vpiOutTerm") = vpiOutTerm;
  vpi.attr("vpiPorts") = vpiPorts;
  vpi.attr("vpiSimNet") = vpiSimNet;
  vpi.attr("vpiTaskFunc") = vpiTaskFunc;
  vpi.attr("vpiBaseExpr") = vpiBaseExpr;
  vpi.attr("vpiWidthExpr") = vpiWidthExpr;
  vpi.attr("vpiAutomatics") = vpiAutomatics;
  vpi.attr("vpiType") = vpiType;
  vpi.attr("vpiName") = vpiName;
  vpi.attr("vpiFullName") = vpiFullName;
  vpi.attr("vpiSize") = vpiSize;
  vpi.attr("vpiFile") = vpiFile;
  vpi.attr("vpiLineNo") = vpiLineNo;
  vpi.attr("vpiTopModule") = vpiTopModule;
  vpi.attr("vpiCellInstance") = vpiCellInstance;
  vpi.attr("vpiDefName") = vpiDefName;
  vpi.attr("vpiProtected") = vpiProtected;
  vpi.attr("vpiTimeUnit") = vpiTimeUnit;
  vpi.attr("vpiTimePrecision") = vpiTimePrecision;
  vpi.attr("vpiDefNetType") = vpiDefNetType;
  vpi.attr("vpiUnconnDrive") = vpiUnconnDrive;
  vpi.attr("vpiHighZ") = vpiHighZ;
  vpi.attr("vpiPull1") = vpiPull1;
  vpi.attr("vpiPull0") = vpiPull0;
  vpi.attr("vpiDefFile") = vpiDefFile;
  vpi.attr("vpiDefLineNo") = vpiDefLineNo;
  vpi.attr("vpiDefDelayMode") = vpiDefDelayMode;
  vpi.attr("vpiDelayModeNone") = vpiDelayModeNone;
  vpi.attr("vpiDelayModePath") = vpiDelayModePath;
  vpi.attr("vpiDelayModeDistrib") = vpiDelayModeDistrib;
  vpi.attr("vpiDelayModeUnit") = vpiDelayModeUnit;
  vpi.attr("vpiDelayModeZero") = vpiDelayModeZero;
  vpi.attr("vpiDelayModeMTM") = vpiDelayModeMTM;
  vpi.attr("vpiDefDecayTime") = vpiDefDecayTime;
  vpi.attr("vpiScalar") = vpiScalar;
  vpi.attr("vpiVector") = vpiVector;
  vpi.attr("vpiExplicitName") = vpiExplicitName;
  vpi.attr("vpiDirection") = vpiDirection;
  vpi.attr("vpiInput") = vpiInput;
  vpi.attr("vpiOutput") = vpiOutput;
  vpi.attr("vpiInout") = vpiInout;
  vpi.attr("vpiMixedIO") = vpiMixedIO;
  vpi.attr("vpiNoDirection") = vpiNoDirection;
  vpi.attr("vpiConnByName") = vpiConnByName;
  vpi.attr("vpiNetType") = vpiNetType;
  vpi.attr("vpiWire") = vpiWire;
  vpi.attr("vpiWand") = vpiWand;
  vpi.attr("vpiWor") = vpiWor;
  vpi.attr("vpiTri") = vpiTri;
  vpi.attr("vpiTri0") = vpiTri0;
  vpi.attr("vpiTri1") = vpiTri1;
  vpi.attr("vpiTriReg") = vpiTriReg;
  vpi.attr("vpiTriAnd") = vpiTriAnd;
  vpi.attr("vpiTriOr") = vpiTriOr;
  vpi.attr("vpiSupply1") = vpiSupply1;
  vpi.attr("vpiSupply0") = vpiSupply0;
  vpi.attr("vpiNone") = vpiNone;
  vpi.attr("vpiUwire") = vpiUwire;
  vpi.attr("vpiNettypeNet") = vpiNettypeNet;
  vpi.attr("vpiNettypeNetSelect") = vpiNettypeNetSelect;
  vpi.attr("vpiInterconnect") = vpiInterconnect;
  vpi.attr("vpiExplicitScalared") = vpiExplicitScalared;
  vpi.attr("vpiExplicitVectored") = vpiExplicitVectored;
  vpi.attr("vpiExpanded") = vpiExpanded;
  vpi.attr("vpiImplicitDecl") = vpiImplicitDecl;
  vpi.attr("vpiChargeStrength") = vpiChargeStrength;
  vpi.attr("vpiLargeCharge") = vpiLargeCharge;
  vpi.attr("vpiMediumCharge") = vpiMediumCharge;
  vpi.attr("vpiSmallCharge") = vpiSmallCharge;
  vpi.attr("vpiArray") = vpiArray;
  vpi.attr("vpiPortIndex") = vpiPortIndex;
  vpi.attr("vpiTermIndex") = vpiTermIndex;
  vpi.attr("vpiStrength0") = vpiStrength0;
  vpi.attr("vpiStrength1") = vpiStrength1;
  vpi.attr("vpiPrimType") = vpiPrimType;
  vpi.attr("vpiAndPrim") = vpiAndPrim;
  vpi.attr("vpiNandPrim") = vpiNandPrim;
  vpi.attr("vpiNorPrim") = vpiNorPrim;
  vpi.attr("vpiOrPrim") = vpiOrPrim;
  vpi.attr("vpiXorPrim") = vpiXorPrim;
  vpi.attr("vpiXnorPrim") = vpiXnorPrim;
  vpi.attr("vpiBufPrim") = vpiBufPrim;
  vpi.attr("vpiNotPrim") = vpiNotPrim;
  vpi.attr("vpiBufif0Prim") = vpiBufif0Prim;
  vpi.attr("vpiBufif1Prim") = vpiBufif1Prim;
  vpi.attr("vpiNotif0Prim") = vpiNotif0Prim;
  vpi.attr("vpiNotif1Prim") = vpiNotif1Prim;
  vpi.attr("vpiNmosPrim") = vpiNmosPrim;
  vpi.attr("vpiPmosPrim") = vpiPmosPrim;
  vpi.attr("vpiCmosPrim") = vpiCmosPrim;
  vpi.attr("vpiRnmosPrim") = vpiRnmosPrim;
  vpi.attr("vpiRpmosPrim") = vpiRpmosPrim;
  vpi.attr("vpiRcmosPrim") = vpiRcmosPrim;
  vpi.attr("vpiRtranPrim") = vpiRtranPrim;
  vpi.attr("vpiRtranif0Prim") = vpiRtranif0Prim;
  vpi.attr("vpiRtranif1Prim") = vpiRtranif1Prim;
  vpi.attr("vpiTranPrim") = vpiTranPrim;
  vpi.attr("vpiTranif0Prim") = vpiTranif0Prim;
  vpi.attr("vpiTranif1Prim") = vpiTranif1Prim;
  vpi.attr("vpiPullupPrim") = vpiPullupPrim;
  vpi.attr("vpiPulldownPrim") = vpiPulldownPrim;
  vpi.attr("vpiSeqPrim") = vpiSeqPrim;
  vpi.attr("vpiCombPrim") = vpiCombPrim;
  vpi.attr("vpiPolarity") = vpiPolarity;
  vpi.attr("vpiDataPolarity") = vpiDataPolarity;
  vpi.attr("vpiPositive") = vpiPositive;
  vpi.attr("vpiNegative") = vpiNegative;
  vpi.attr("vpiUnknown") = vpiUnknown;
  vpi.attr("vpiEdge") = vpiEdge;
  vpi.attr("vpiNoEdge") = vpiNoEdge;
  vpi.attr("vpiEdge01") = vpiEdge01;
  vpi.attr("vpiEdge10") = vpiEdge10;
  vpi.attr("vpiEdge0x") = vpiEdge0x;
  vpi.attr("vpiEdgex1") = vpiEdgex1;
  vpi.attr("vpiEdge1x") = vpiEdge1x;
  vpi.attr("vpiEdgex0") = vpiEdgex0;
  vpi.attr("vpiPathType") = vpiPathType;
  vpi.attr("vpiPathFull") = vpiPathFull;
  vpi.attr("vpiPathParallel") = vpiPathParallel;
  vpi.attr("vpiTchkType") = vpiTchkType;
  vpi.attr("vpiSetup") = vpiSetup;
  vpi.attr("vpiHold") = vpiHold;
  vpi.attr("vpiPeriod") = vpiPeriod;
  vpi.attr("vpiWidth") = vpiWidth;
  vpi.attr("vpiSkew") = vpiSkew;
  vpi.attr("vpiRecovery") = vpiRecovery;
  vpi.attr("vpiNoChange") = vpiNoChange;
  vpi.attr("vpiSetupHold") = vpiSetupHold;
  vpi.attr("vpiFullskew") = vpiFullskew;
  vpi.attr("vpiRecrem") = vpiRecrem;
  vpi.attr("vpiRemoval") = vpiRemoval;
  vpi.attr("vpiTimeskew") = vpiTimeskew;
  vpi.attr("vpiOpType") = vpiOpType;
  vpi.attr("vpiMinusOp") = vpiMinusOp;
  vpi.attr("vpiPlusOp") = vpiPlusOp;
  vpi.attr("vpiNotOp") = vpiNotOp;
  vpi.attr("vpiBitNegOp") = vpiBitNegOp;
  vpi.attr("vpiUnaryAndOp") = vpiUnaryAndOp;
  vpi.attr("vpiUnaryNandOp") = vpiUnaryNandOp;
  vpi.attr("vpiUnaryOrOp") = vpiUnaryOrOp;
  vpi.attr("vpiUnaryNorOp") = vpiUnaryNorOp;
  vpi.attr("vpiUnaryXorOp") = vpiUnaryXorOp;
  vpi.attr("vpiUnaryXNorOp") = vpiUnaryXNorOp;
  vpi.attr("vpiSubOp") = vpiSubOp;
  vpi.attr("vpiDivOp") = vpiDivOp;
  vpi.attr("vpiModOp") = vpiModOp;
  vpi.attr("vpiEqOp") = vpiEqOp;
  vpi.attr("vpiNeqOp") = vpiNeqOp;
  vpi.attr("vpiCaseEqOp") = vpiCaseEqOp;
  vpi.attr("vpiCaseNeqOp") = vpiCaseNeqOp;
  vpi.attr("vpiGtOp") = vpiGtOp;
  vpi.attr("vpiGeOp") = vpiGeOp;
  vpi.attr("vpiLtOp") = vpiLtOp;
  vpi.attr("vpiLeOp") = vpiLeOp;
  vpi.attr("vpiLShiftOp") = vpiLShiftOp;
  vpi.attr("vpiRShiftOp") = vpiRShiftOp;
  vpi.attr("vpiAddOp") = vpiAddOp;
  vpi.attr("vpiMultOp") = vpiMultOp;
  vpi.attr("vpiLogAndOp") = vpiLogAndOp;
  vpi.attr("vpiLogOrOp") = vpiLogOrOp;
  vpi.attr("vpiBitAndOp") = vpiBitAndOp;
  vpi.attr("vpiBitOrOp") = vpiBitOrOp;
  vpi.attr("vpiBitXorOp") = vpiBitXorOp;
  vpi.attr("vpiBitXNorOp") = vpiBitXNorOp;
  vpi.attr("vpiConditionOp") = vpiConditionOp;
  vpi.attr("vpiConcatOp") = vpiConcatOp;
  vpi.attr("vpiMultiConcatOp") = vpiMultiConcatOp;
  vpi.attr("vpiEventOrOp") = vpiEventOrOp;
  vpi.attr("vpiNullOp") = vpiNullOp;
  vpi.attr("vpiListOp") = vpiListOp;
  vpi.attr("vpiMinTypMaxOp") = vpiMinTypMaxOp;
  vpi.attr("vpiPosedgeOp") = vpiPosedgeOp;
  vpi.attr("vpiNegedgeOp") = vpiNegedgeOp;
  vpi.attr("vpiArithLShiftOp") = vpiArithLShiftOp;
  vpi.attr("vpiArithRShiftOp") = vpiArithRShiftOp;
  vpi.attr("vpiPowerOp") = vpiPowerOp;
  vpi.attr("vpiConstType") = vpiConstType;
  vpi.attr("vpiDecConst") = vpiDecConst;
  vpi.attr("vpiRealConst") = vpiRealConst;
  vpi.attr("vpiBinaryConst") = vpiBinaryConst;
  vpi.attr("vpiOctConst") = vpiOctConst;
  vpi.attr("vpiHexConst") = vpiHexConst;
  vpi.attr("vpiStringConst") = vpiStringConst;
  vpi.attr("vpiIntConst") = vpiIntConst;
  vpi.attr("vpiTimeConst") = vpiTimeConst;
  vpi.attr("vpiBlocking") = vpiBlocking;
  vpi.attr("vpiCaseType") = vpiCaseType;
  vpi.attr("vpiCaseExact") = vpiCaseExact;
  vpi.attr("vpiCaseX") = vpiCaseX;
  vpi.attr("vpiCaseZ") = vpiCaseZ;
  vpi.attr("vpiNetDeclAssign") = vpiNetDeclAssign;
  vpi.attr("vpiFuncType") = vpiFuncType;
  vpi.attr("vpiIntFunc") = vpiIntFunc;
  vpi.attr("vpiRealFunc") = vpiRealFunc;
  vpi.attr("vpiTimeFunc") = vpiTimeFunc;
  vpi.attr("vpiSizedFunc") = vpiSizedFunc;
  vpi.attr("vpiSizedSignedFunc") = vpiSizedSignedFunc;
  vpi.attr("vpiUserDefn") = vpiUserDefn;
  vpi.attr("vpiScheduled") = vpiScheduled;
  vpi.attr("vpiActive") = vpiActive;
  vpi.attr("vpiAutomatic") = vpiAutomatic;
  vpi.attr("vpiCell") = vpiCell;
  vpi.attr("vpiConfig") = vpiConfig;
  vpi.attr("vpiConstantSelect") = vpiConstantSelect;
  vpi.attr("vpiDecompile") = vpiDecompile;
  vpi.attr("vpiDefAttribute") = vpiDefAttribute;
  vpi.attr("vpiDelayType") = vpiDelayType;
  vpi.attr("vpiModPathDelay") = vpiModPathDelay;
  vpi.attr("vpiInterModPathDelay") = vpiInterModPathDelay;
  vpi.attr("vpiMIPDelay") = vpiMIPDelay;
  vpi.attr("vpiIteratorType") = vpiIteratorType;
  vpi.attr("vpiLibrary") = vpiLibrary;
  vpi.attr("vpiOffset") = vpiOffset;
  vpi.attr("vpiResolvedNetType") = vpiResolvedNetType;
  vpi.attr("vpiSaveRestartID") = vpiSaveRestartID;
  vpi.attr("vpiSaveRestartLocation") = vpiSaveRestartLocation;
  vpi.attr("vpiValid") = vpiValid;
  vpi.attr("vpiValidFalse") = vpiValidFalse;
  vpi.attr("vpiValidTrue") = vpiValidTrue;
  vpi.attr("vpiSigned") = vpiSigned;
  vpi.attr("vpiLocalParam") = vpiLocalParam;
  vpi.attr("vpiModPathHasIfNone") = vpiModPathHasIfNone;
  vpi.attr("vpiIndexedPartSelectType") = vpiIndexedPartSelectType;
  vpi.attr("vpiPosIndexed") = vpiPosIndexed;
  vpi.attr("vpiNegIndexed") = vpiNegIndexed;
  vpi.attr("vpiIsMemory") = vpiIsMemory;
  vpi.attr("vpiIsProtected") = vpiIsProtected;
  vpi.attr("vpiStop") = vpiStop;
  vpi.attr("vpiFinish") = vpiFinish;
  vpi.attr("vpiReset") = vpiReset;
  vpi.attr("vpiSetInteractiveScope") = vpiSetInteractiveScope;
  vpi.attr("vpiScaledRealTime") = vpiScaledRealTime;
  vpi.attr("vpiSimTime") = vpiSimTime;
  vpi.attr("vpiSuppressTime") = vpiSuppressTime;
  vpi.attr("vpiSupplyDrive") = vpiSupplyDrive;
  vpi.attr("vpiStrongDrive") = vpiStrongDrive;
  vpi.attr("vpiPullDrive") = vpiPullDrive;
  vpi.attr("vpiWeakDrive") = vpiWeakDrive;
  vpi.attr("vpiLargeCharge") = vpiLargeCharge;
  vpi.attr("vpiMediumCharge") = vpiMediumCharge;
  vpi.attr("vpiSmallCharge") = vpiSmallCharge;
  vpi.attr("vpiHiZ") = vpiHiZ;
  vpi.attr("vpiBinStrVal") = vpiBinStrVal;
  vpi.attr("vpiOctStrVal") = vpiOctStrVal;
  vpi.attr("vpiDecStrVal") = vpiDecStrVal;
  vpi.attr("vpiHexStrVal") = vpiHexStrVal;
  vpi.attr("vpiScalarVal") = vpiScalarVal;
  vpi.attr("vpiIntVal") = vpiIntVal;
  vpi.attr("vpiRealVal") = vpiRealVal;
  vpi.attr("vpiStringVal") = vpiStringVal;
  vpi.attr("vpiVectorVal") = vpiVectorVal;
  vpi.attr("vpiStrengthVal") = vpiStrengthVal;
  vpi.attr("vpiTimeVal") = vpiTimeVal;
  vpi.attr("vpiObjTypeVal") = vpiObjTypeVal;
  vpi.attr("vpiSuppressVal") = vpiSuppressVal;
  vpi.attr("vpiShortIntVal") = vpiShortIntVal;
  vpi.attr("vpiLongIntVal") = vpiLongIntVal;
  vpi.attr("vpiShortRealVal") = vpiShortRealVal;
  vpi.attr("vpiRawTwoStateVal") = vpiRawTwoStateVal;
  vpi.attr("vpiRawFourStateVal") = vpiRawFourStateVal;
  vpi.attr("vpiNoDelay") = vpiNoDelay;
  vpi.attr("vpiInertialDelay") = vpiInertialDelay;
  vpi.attr("vpiTransportDelay") = vpiTransportDelay;
  vpi.attr("vpiPureTransportDelay") = vpiPureTransportDelay;
  vpi.attr("vpiForceFlag") = vpiForceFlag;
  vpi.attr("vpiReleaseFlag") = vpiReleaseFlag;
  vpi.attr("vpiCancelEvent") = vpiCancelEvent;
  vpi.attr("vpiReturnEvent") = vpiReturnEvent;
  vpi.attr("vpiUserAllocFlag") = vpiUserAllocFlag;
  vpi.attr("vpiOneValue") = vpiOneValue;
  vpi.attr("vpiPropagateOff") = vpiPropagateOff;
  vpi.attr("vpi0") = vpi0;
  vpi.attr("vpi1") = vpi1;
  vpi.attr("vpiZ") = vpiZ;
  vpi.attr("vpiX") = vpiX;
  vpi.attr("vpiH") = vpiH;
  vpi.attr("vpiL") = vpiL;
  vpi.attr("vpiDontCare") = vpiDontCare;
  vpi.attr("vpiNoChange") = vpiNoChange;
  vpi.attr("vpiSysTask") = vpiSysTask;
  vpi.attr("vpiSysFunc") = vpiSysFunc;
  vpi.attr("vpiCompile") = vpiCompile;
  vpi.attr("vpiPLI") = vpiPLI;
  vpi.attr("vpiRun") = vpiRun;
  vpi.attr("vpiNotice") = vpiNotice;
  vpi.attr("vpiWarning") = vpiWarning;
  vpi.attr("vpiError") = vpiError;
  vpi.attr("vpiSystem") = vpiSystem;
  vpi.attr("vpiInternal") = vpiInternal;
  vpi.attr("cbValueChange") = cbValueChange;
  vpi.attr("cbStmt") = cbStmt;
  vpi.attr("cbForce") = cbForce;
  vpi.attr("cbRelease") = cbRelease;
  vpi.attr("cbAtStartOfSimTime") = cbAtStartOfSimTime;
  vpi.attr("cbReadWriteSynch") = cbReadWriteSynch;
  vpi.attr("cbReadOnlySynch") = cbReadOnlySynch;
  vpi.attr("cbNextSimTime") = cbNextSimTime;
  vpi.attr("cbAfterDelay") = cbAfterDelay;
  vpi.attr("cbEndOfCompile") = cbEndOfCompile;
  vpi.attr("cbStartOfSimulation") = cbStartOfSimulation;
  vpi.attr("cbEndOfSimulation") = cbEndOfSimulation;
  vpi.attr("cbError") = cbError;
  vpi.attr("cbTchkViolation") = cbTchkViolation;
  vpi.attr("cbStartOfSave") = cbStartOfSave;
  vpi.attr("cbEndOfSave") = cbEndOfSave;
  vpi.attr("cbStartOfRestart") = cbStartOfRestart;
  vpi.attr("cbEndOfRestart") = cbEndOfRestart;
  vpi.attr("cbStartOfReset") = cbStartOfReset;
  vpi.attr("cbEndOfReset") = cbEndOfReset;
  vpi.attr("cbEnterInteractive") = cbEnterInteractive;
  vpi.attr("cbExitInteractive") = cbExitInteractive;
  vpi.attr("cbInteractiveScopeChange") = cbInteractiveScopeChange;
  vpi.attr("cbUnresolvedSystf") = cbUnresolvedSystf;
  vpi.attr("cbAssign") = cbAssign;
  vpi.attr("cbDeassign") = cbDeassign;
  vpi.attr("cbDisable") = cbDisable;
  vpi.attr("cbPLIError") = cbPLIError;
  vpi.attr("cbSignal") = cbSignal;
  vpi.attr("cbNBASynch") = cbNBASynch;
  vpi.attr("cbAtEndOfSimTime") = cbAtEndOfSimTime;
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

  //     py::class_<s_vpi_systf_data>(vpi, "VpiSystfData")
  //         .def(py::init([](int type, int sysfunctype, const char *tfname,
  //                          int (*calltf)(char *), int (*compiletf)(char *),
  //                          int (*sizetf)(char *), const char *user_data) {
  //           return new s_vpi_systf_data{
  //               type,      sysfunctype, tfname,           calltf,
  //               compiletf, sizetf,      (char *)user_data};
  //         }))
  //         .def(py::init<>())
  //         .def_readwrite("type", &s_vpi_systf_data::type)
  //         .def_readwrite("sysfunctype", &s_vpi_systf_data::sysfunctype)
  //         .def_readwrite("tfname", &s_vpi_systf_data::tfname)
  //         .def_readwrite("calltf", &s_vpi_systf_data::calltf)
  //         .def_readwrite("compiletf", &s_vpi_systf_data::compiletf)
  //         .def_readwrite("sizetf", &s_vpi_systf_data::sizetf)
  //         .def_readwrite("user_data", &s_vpi_systf_data::user_data);

  //   py::class_<s_vpi_vlog_info>(vpi, "VpiVlogInfo")
  //       .def(py::init([](const std::vector<std::string>& args, std::string
  //       product,
  //                        std::string version) {
  //         std::vector<char *> c_args;
  //         for (const auto &arg : args) {
  //           c_args.push_back(const_cast<char *>(arg.c_str()));
  //         }
  //         char **argv = c_args.data();
  //         int argc = static_cast<int>(args.size());
  //         return new s_vpi_vlog_info{argc, argv,
  //         const_cast<char*>(product.c_str()),
  //         const_cast<char*>(version.c_str())};
  //       }))
  //       .def(py::init<>())
  //       .def_readwrite("argc", &s_vpi_vlog_info::argc)
  //       .def_readwrite("argv", &s_vpi_vlog_info::argv)
  //       .def_readwrite("product", &s_vpi_vlog_info::product)
  //       .def_readwrite("version", &s_vpi_vlog_info::version);

  py::class_<s_vpi_error_info>(vpi, "VpiErrorInfo")
      .def(py::init([](int state, int level, char *message, char *product,
                       char *code, char *file, int line) {
        return new s_vpi_error_info{state, level, message, product,
                                    code,  file,  line};
      }))
      .def(py::init<>())
      .def_readwrite("state", &s_vpi_error_info::state)
      .def_readwrite("level", &s_vpi_error_info::level)
      .def_readwrite("message", &s_vpi_error_info::message)
      .def_readwrite("product", &s_vpi_error_info::product)
      .def_readwrite("code", &s_vpi_error_info::code)
      .def_readwrite("file", &s_vpi_error_info::file)
      .def_readwrite("line", &s_vpi_error_info::line);

  //   py::class_<s_cb_data>(vpi, "CbData")
  //       .def(py::init([](int reason, py::object cb_rtn, vpiHandle obj,
  //                        p_vpi_time time, p_vpi_value value, int index,
  //                        std::string user_data) {
  //         s_cb_data data;
  //         data.reason = reason;
  //         data.cb_rtn = [](struct t_cb_data *cb_data) -> PLI_INT32 {
  //           py::gil_scoped_acquire gil; // 获取 GIL
  //           py::object cb_rtn = py::cast(cb_data->cb_rtn);
  //           return cb_rtn(cb_data).cast<PLI_INT32>();
  //         };
  //         data.obj = obj;
  //         data.time = time;
  //         data.value = value;
  //         data.index = index;
  //         data.user_data = const_cast<PLI_BYTE8 *>(user_data.c_str());
  //         return data;
  //       }))
  //       .def(py::init<>())
  //       .def_readwrite("reason", &s_cb_data::reason)
  //       .def_property(
  //           "cb_rtn",
  //           [](s_cb_data &data) -> py::object {
  //             return py::cpp_function(data.cb_rtn, py::keep_alive<0, 1>());
  //           },
  //           [](s_cb_data &data, py::object cb_rtn) {
  //             data.cb_rtn = [](struct t_cb_data *cb_data) -> PLI_INT32 {
  //               py::gil_scoped_acquire gil; // 获取 GIL
  //               py::object cb_rtn_obj = py::cast(cb_data->cb_rtn);
  //               return cb_rtn_obj(cb_data).cast<PLI_INT32>();
  //             };
  //           })
  //       .def_readwrite("obj", &s_cb_data::obj)
  //       .def_readwrite("time", &s_cb_data::time)
  //       .def_readwrite("value", &s_cb_data::value)
  //       .def_readwrite("index", &s_cb_data::index)
  //       .def_property(
  //           "user_data",
  //           [](s_cb_data &data) -> std::string {
  //             return std::string(data.user_data);
  //           },
  //           [](s_cb_data &data, std::string user_data) {
  //             data.user_data = const_cast<PLI_BYTE8 *>(user_data.c_str());
  //           });
  // functions
  vpi.def("vpi_register_cb", &vpi_register_cb, py::arg("cb_data_p"),
          "Register a callback.");

  vpi.def("vpi_remove_cb", &vpi_remove_cb, py::arg("cb_obj"),
          "Remove a callback.");

  vpi.def("vpi_get_cb_info", &vpi_get_cb_info, py::arg("object"),
          py::arg("cb_data_p"), "Get callback information.");

  vpi.def("vpi_register_systf", &vpi_register_systf, py::arg("systf_data_p"),
          "Register a system task/function.");

  vpi.def("vpi_get_systf_info", &vpi_get_systf_info, py::arg("object"),
          py::arg("systf_data_p"), "Get system task/function information.");

  vpi.def("vpi_handle_by_name", &vpi_handle_by_name, py::arg("name"),
          py::arg("scope"), "Get a handle by name.");

  vpi.def("vpi_handle_by_index", &vpi_handle_by_index, py::arg("object"),
          py::arg("indx"), "Get a handle by index.");

  vpi.def("vpi_handle", &vpi_handle, py::arg("type"), py::arg("refHandle"),
          "Get a handle for a specific type and reference handle.");

  vpi.def("vpi_handle_multi", &vpi_handle_multi_wrap,
          "Get a handle for multiple reference handles.");

  vpi.def("vpi_iterate", &vpi_iterate, py::arg("type"), py::arg("refHandle"),
          "Iterate over objects of a specific type.");

  vpi.def("vpi_scan", &vpi_scan, py::arg("iterator"), "Scan an iterator.");

  vpi.def("vpi_get", &vpi_get, py::arg("property"), py::arg("object"),
          "Get a property value.");

  vpi.def("vpi_get64", &vpi_get64, py::arg("property"), py::arg("object"),
          "Get a 64-bit property value.");

  vpi.def("vpi_get_str", &vpi_get_str, py::arg("property"), py::arg("object"),
          "Get a string property value.");

  vpi.def("vpi_get_delays", &vpi_get_delays, py::arg("object"),
          py::arg("delay_p"), "Get delays for an object.");

  vpi.def("vpi_put_delays", &vpi_put_delays, py::arg("object"),
          py::arg("delay_p"), "Put delays for an object.");

  vpi.def("vpi_get_value", &vpi_get_value, py::arg("expr"), py::arg("value_p"),
          "Get a value.");

  vpi.def("vpi_put_value", &vpi_put_value, py::arg("object"),
          py::arg("value_p"), py::arg("time_p"), py::arg("flags"),
          "Put a value.");

  vpi.def("vpi_get_value_array", &vpi_get_value_array, py::arg("object"),
          py::arg("arrayvalue_p"), py::arg("index_p"), py::arg("num"),
          "Get an array of values.");

  vpi.def("vpi_put_value_array", &vpi_put_value_array, py::arg("object"),
          py::arg("arrayvalue_p"), py::arg("index_p"), py::arg("num"),
          "Put an array of values.");

  vpi.def("vpi_get_time", &vpi_get_time, py::arg("object"), py::arg("time_p"),
          "Get time for an object.");

  vpi.def("vpi_mcd_open", &vpi_mcd_open, py::arg("fileName"),
          "Open a multichannel description file.");

  vpi.def("vpi_mcd_close", &vpi_mcd_close, py::arg("mcd"),
          "Close a multichannel description file.");

  vpi.def("vpi_mcd_name", &vpi_mcd_name, py::arg("cd"),
          "Get the name of a multichannel description file.");

  vpi.def("vpi_mcd_printf", &vpi_mcd_printf_wrap,
          "Print to a multichannel description file.");

  vpi.def("vpi_printf", &vpi_printf_wrap, "Print to standard output.");

  vpi.def("vpi_compare_objects", &vpi_compare_objects, py::arg("object1"),
          py::arg("object2"), "Compare two objects.");

  vpi.def("vpi_chk_error", &vpi_chk_error, py::arg("error_info_p"),
          "Check for errors.");

  vpi.def("vpi_free_object", &vpi_free_object, py::arg("object"),
          "Free an object. (Deprecated)");

  vpi.def("vpi_release_handle", &vpi_release_handle, py::arg("object"),
          "Release a handle.");

  vpi.def("vpi_get_vlog_info", &vpi_get_vlog_info, py::arg("vlog_info_p"),
          "Get vlog information.");

#if !defined(VCS) && !defined(VCSMX)
  vpi.def("vpi_get_data", &vpi_get_data, py::arg("id"), py::arg("dataLoc"),
          py::arg("numOfBytes"), "Get data.");

  vpi.def("vpi_put_data", &vpi_put_data, py::arg("id"), py::arg("dataLoc"),
          py::arg("numOfBytes"), "Put data.");
#endif

  vpi.def("vpi_get_userdata", &vpi_get_userdata, py::arg("obj"),
          "Get user data.");

  vpi.def("vpi_put_userdata", &vpi_put_userdata, py::arg("obj"),
          py::arg("userdata"), "Put user data.");

  vpi.def("vpi_flush", &vpi_flush, "Flush output.");

  vpi.def("vpi_mcd_flush", &vpi_mcd_flush, py::arg("mcd"),
          "Flush a multichannel description file.");

  vpi.def("vpi_control", &vpi_control_wrap, "Control simulator operations.");

  vpi.def("vpi_handle_by_multi_index", &vpi_handle_by_multi_index,
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

#if defined(VCS) || defined(VCSMX) || defined(XCELIUM) || defined(NCSC)
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
#endif

  m.def("print_factory", &print_factory, "Prints factory information.",
        py::arg("all_types") = 1);

  m.def("set_factory_inst_override", &set_factory_inst_override,
        "Sets an instance override in the factory.",
        py::arg("original_type_name"), py::arg("override_type_name"),
        py::arg("full_inst_path"));

  m.def("set_factory_type_override", &set_factory_type_override,
        "Sets a type override in the factory.", py::arg("original_type_name"),
        py::arg("override_type_name"), py::arg("replace") = true);

  m.def("debug_factory_create", &debug_factory_create,
        "Debugs the creation of a factory object.", py::arg("requested_type"),
        py::arg("context") = "");

  m.def("create_object_by_name", &create_object_by_name, "create a uvm object.",
        py::arg("requested_type"), py::arg("context") = "",
        py::arg("name") = "");

  m.def("create_component_by_name", &create_component_by_name,
        "create a uvm object.", py::arg("requested_type"),
        py::arg("context") = "", py::arg("parent_name") = "",
        py::arg("name") = "");

  m.def("find_factory_override", &find_factory_override,
        "Finds an override for a given factory type.",
        py::arg("requested_type"), py::arg("context"),
        py::arg("override_type_name"));

  m.def("print_topology", &print_topology, "Prints the topology.",
        py::arg("context") = "");

  m.def("set_timeout", &set_timeout, "Set the timeout value.",
        py::arg("timeout"), py::arg("overridable") = 1);

  m.def("uvm_objection_op", &uvm_objection_op, "uvm_objection_op",
        py::arg("op"), py::arg("name"), py::arg("contxt"),
        py::arg("description"), py::arg("delta") = 0);

  m.def("dbg_print", &dbg_print, "Prints the object.", py::arg("name") = "");

#if defined(VCS) || defined(VCSMX) || defined(XCELIUM) || defined(NCSC)
  // uvm event
  m.def("wait_on", &wait_on, "Wait until the signal is on", py::arg("ev_name"),
        py::arg("delta") = 0);
  m.def("wait_off", &wait_off, "Wait until the signal is off",
        py::arg("ev_name"), py::arg("delta") = 0);
  m.def("wait_trigger", &wait_trigger, "Wait for the trigger event",
        py::arg("ev_name"));
  m.def("wait_ptrigger", &wait_ptrigger, "Wait for the positive trigger event",
        py::arg("ev_name"));
  m.def("get_trigger_time", &get_trigger_time,
        "Get the time of the last trigger event", py::arg("ev_name"));
  m.def("is_on", &is_on, "Check if the signal is on", py::arg("ev_name"));
  m.def("is_off", &is_off, "Check if the signal is off", py::arg("ev_name"));
  m.def("reset", &reset, "Reset the signal state", py::arg("ev_name"),
        py::arg("wakeup") = 0);
  m.def("cancel", &cancel, "Cancel the current wait operation",
        py::arg("ev_name"));
  m.def("get_num_waiters", &get_num_waiters, "Get the number of waiters",
        py::arg("ev_name"));
  m.def("trigger", &trigger, "Trigger the event", py::arg("ev_name"));
#endif
  // config db
  m.def("set_config_int", &set_config_int,
        "Set integer configuration in the UVM environment");
  m.def("get_config_int", &get_config_int,
        "Get integer configuration from the UVM environment");
  m.def("set_config_string", &set_config_string,
        "Set string configuration in the UVM environment");
  m.def("get_config_string", &get_config_string,
        "Get string configuration from the UVM environment");

  m.def("write_reg", &write_reg, "write register");
  m.def("read_reg", &wrap_read_reg, "read register");
  m.def("check_reg", &check_reg, "check register", py::arg("name"),
        py::arg("data") = 0, py::arg("predict") = 0);
  m.def("start_seq", &start_seq, "start seq on sqr", py::arg("seq_name"),
        py::arg("sqr_name"), py::arg("rand_en") = 1, py::arg("background") = 0);
  m.def("run_test", &run_test_wrap, "uvm run test", py::arg("test_name"));
  m.def("wait_unit", &wait_unit, "wait unit time");
  m.def("stop", &stop, "suspend the simulation");
}

void py_func(const char *mod_name, const char *func_name,
             const char *mod_paths) {
  char *dir_path;
  py::scoped_interpreter guard{}; // start the interpreter and keep it alive

  py::module_ sys = py::module_::import("sys");
  py::list path = sys.attr("path");

  py::module_ sysconfig = py::module_::import("sysconfig");
  std::string ext_suffix =
      sysconfig.attr("get_config_var")("EXT_SUFFIX").cast<std::string>();

#ifdef __linux__
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
  Dl_info dl_info;
  if (dladdr((void *)py_func, &dl_info)) {
    dir_path = dirname(dirname(const_cast<char *>(dl_info.dli_fname)));
    path.attr("append")(dir_path);
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
}
