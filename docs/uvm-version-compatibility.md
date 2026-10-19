# UVM 版本兼容

`src/svuvm/python_bridge_pkg.sv` 对各 UVM 发行版的适配情况与已知边界。

测试于 2026-10-19，xezim 0.11.2（main `661ab48`）、Verilator nightly `54314c5`。UVM 源码取自
`chipsalliance/uvm-verilator` 的 tag。表格的期望值以 `test/uvm_compat/test_compat.py` 为准，每次
推送由 CI 逐版本校验。

## 1. 结果

两个仿真器检查的东西不同：

- **xezim** 解释执行，跑完整的 `base_test`（`test/base_test`）。
- **verilator** 只做精化（`make -f test/base_test/Makefile lint`），不构建。原因是上游 UVM 到 2020-3.2 才提供 Verilator 的 HDL 后端，见 §3.3。

| UVM | xezim（运行） | verilator（lint） |
|-----|--------------|------------------|
| `uvm-1.0p1` | — | ✗ 缺 1 个 API、3 处改名（§3.2） |
| `uvm-1.1a` | — | ✓ |
| `uvm-1.1b` | — | ✗ UVM 自身缺陷（§3.1） |
| `uvm-1.1c` | — | ✗ 同上 |
| `uvm-1.1d` | — | ✓ |
| `uvm-1.2` | ✓ | ✓ |
| `uvm-2017-0.9` | ✓ | ✓ |
| `uvm-2017-1.0` | ✓ | ✓ |
| `uvm-2017-1.1` | ✓ | ✓ |
| `uvm-2020-1.0` | ✓ | ✓ |
| `uvm-2020-1.1` | ✓ | ✓ |
| `uvm-2020-2.0` | ✓ | ✓ |
| `uvm-2020-3.0` | ✓ | ✓ |
| `uvm-2020-3.1` | ✓ | ✓ |
| `uvm-2020-3.2` | ✓ | ✓ |

xezim 的 1.0 / 1.1 一栏为空：它们的 DPI 源文件布局早于 1.2（没有 `uvm_dpi.h` 与 `uvm_common.c`，这两个文件都是 1.2 引入的），xezim 的 DPI 适配层因此无法编译。这些版本在 verilator 上仍可 lint。

判定标准是 `make` 退出码为 0 且日志出现 `所有新增API测试完成`。日志中的 `UVM_FATAL: 10` / `UVM_ERROR: 20` 是 `base_test` 自身 API 测试的固定计数（含 `UVM_FATAL TEST SUCCESS!` 与 `set_severity_count` 用例），逐版本一致，不是失败。

## 2. 桥接层的版本适配

三组条件编译，各自用一个上游宏开关，未引入自定义宏。

### 2.1 drain time：`UVM_VERSION_POST_2020_1_1`

run 时 objection 的归属在 2020-2.0 改变：该版本起由 phase hopper 持有，`uvm_test_done_objection` 不复存在；此前是 run 相位自己的 objection。

`uvm_phase_hopper` 类只存在于 2020-2.0 及以后，而 `UVM_VERSION_POST_2020_1_1` 的定义范围与之逐版本一致（实测 15 个 tag），所以单个 `` `ifdef `` 就同时回答了"该类是否存在"。

旧路径不能用 `uvm_test_done_objection`（IEEE-2017 基线已移除），改用 run 相位的公开 objection。

hopper 单例由 `run_test()` 的 fork 在 `build_phase` 之前创建，因此暴露 `get_objection()` 的 type override 必须在 `base_test::new()` 里注册——注册晚了单例已是错误类型，`$cast` 会失败。

### 2.2 printer / comparer knob：两端析取

`set/get_default_printer_knob` 与 comparer 的同名函数需要访问默认对象的成员，而访问方式和可见性在两个版本区间里互补：

| | 1.2 | 2017-* / 2020-1.x | 2020-2.0+ |
|---|---|---|---|
| 默认 printer 取法 | `uvm_default_printer` 全局 | `uvm_printer::get_default()` | 同左 |
| `knobs` 可见性 | public | **local，外部不可达** | public |
| `header` / `footer` | 有 | 无 | 有 |
| 默认 comparer 取法 | `uvm_comparer::init()` | `uvm_comparer::get_default()` | 同左 |

条件因此写成 `` `ifdef PB_UVM_PRE_2017 `` 与 `` `elsif UVM_VERSION_POST_2020_1_1 `` 的析取——没有任何单个上游宏同时覆盖两端而不含中间。`knobs` 不可达的版本上 knob 名照常被接受、不产生效果，与既有的 `max_width` / `min_width` 同样处理。

### 2.3 1.1 / 1.0 的接口改名

| 桥接调用 | 1.1 及更早的名字 |
|---------|------------------|
| `uvm_factory::find_wrapper_by_name` | `find_by_name` |
| `uvm_report_server::report_summarize` | `summarize` |
| `uvm_component::get_report_max_verbosity_level` | `uvm_get_max_verbosity` |
| `uvm_root::set_finish_on_completion` | 公开变量 `finish_on_completion` |
| `uvm_comparer::set_severity` / `get_severity` | 成员 `sev`，无访问器 |

另有两处是缺失而非改名：`UVM_PHASE_UNINITIALIZED` 是 1.2 引入的，1.0/1.1 没有这个状态，所以那两条路径上不产生该 case 标签；`uvm_config_db_options` 是 1.1 引入的，1.0 的 tracing 开关无处可设，函数接受调用但不产生效果。

后三处的旧路径对 1.0、1.1、1.2 相同（1.2 也没有这三个），前三处只对 1.0 与 1.1 相同（1.2 已改名）。因此定义两个区间宏表示这两段范围，一处定义、全文引用：

```systemverilog
`ifdef UVM_VERSION_1_0
`define PB_UVM_PRE_1_2
`endif
`ifdef UVM_VERSION_1_1
`define PB_UVM_PRE_1_2
`endif
`ifdef PB_UVM_PRE_1_2
`define PB_UVM_PRE_2017
`endif
`ifdef UVM_VERSION_1_2
`define PB_UVM_PRE_2017
`endif
```

两个都是**否定判断**（定义了 `UVM_VERSION_1_0` / `_1_1` / `_1_2` 即在 2017 之前……）。正向判断不可行：`UVM_POST_VERSION_1_1` 在 2020-1.0 与 2020-1.1 里未定义。

## 3. 已知边界

以下三项都不在桥接层内，无法通过修改 `python_bridge_pkg.sv` 解决。

### 3.1 UVM 1.1b / 1.1c：自身的 redaction 宏无兜底

这两个版本的 `` `uvm_record_attribute `` 只在 `` `ifdef QUESTA `` 下定义，没有 `` `else ``，而它们自己的 `tlm2/uvm_tlm2_generic_payload.svh` 无条件使用（经 `` `uvm_record_field `` 展开）。在任何非 Questa 工具下都会产生 50 个语法错误。1.1d 补上了 `` `elsif VCS `` / `` `elsif INCA `` / `` `else ``（空定义），因此可用。

### 3.2 UVM 1.0p1：4 处 API 差异

| 桥接调用 | 1.0p1 |
|---------|-------|
| `uvm_reg::get_mirrored_value` | 叫 `get()`（2 处） |
| `uvm_reg_field::get_mirrored_value` | 叫 `get()` |
| `uvm_domain::m_get_transitive_children` | **不存在**，该版本也没有别的 phase 遍历接口 |

前三处是改名，未加守卫（改它们不会让该格通过）。最后一个是真缺口：`get_current_phase_name` 依赖遍历 domain 的相位，而 1.0p1 的 `uvm_domain` 只有 `add()`、`schedule` 与 `get_domains()`，没有等价物，因此 1.0p1 未能通过 lint。

### 3.3 verilator：上游 UVM 到 2020-3.2 才有 HDL 后端

上游 UVM 的 `uvm_hdl.c` 只认 VCS / QUESTA / XCELIUM，缺少后端时直接报错：

```
uvm-2017-0.9/src/dpi/uvm_hdl.c:33:2: error: #error "hdl vendor backend is missing"
```

`uvm_hdl_verilator.c` 是 2020-3.2 才加入的（`Dragon-Git/uvm-verilator` 的 fork 也有，既有的 `test` job 用的正是它）。

所以 verilator 腿检查的是 lint 而不是构建运行：`--lint-only` 不编译 DPI 的 C++，不受该后端缺失影响，同时仍然比对桥接与每个版本的 SystemVerilog 接口。

## 4. 复现

```sh
# 取某个版本
git clone --depth 1 --branch uvm-2020-3.2 \
  https://github.com/chipsalliance/uvm-verilator.git /tmp/uvm-2020-3.2

# xezim 跑 base_test（-uvm 需要 XEZIM_UVM_DIR）
make -f test/base_test/Makefile SIM=xezim run \
  UVM_HOME=/tmp/uvm-2020-3.2 XEZIM_PREFIX=<prefix>

# verilator lint（需要 verilator 已在 PATH）
make -f test/base_test/Makefile lint UVM_HOME=/tmp/uvm-2020-3.2/src
```

两个腿的 `UVM_HOME` 含义不同：xezim 的 Makefile 会自己附加 `/src`，verilator 的期待直接给 `src` 目录。

注意 xezim 加载的是 **svuvm 包内**的 `python_bridge_pkg.sv`，不是仓库里的那份；改动仓库后需同步：

```sh
cp src/svuvm/python_bridge_pkg.sv "$(python -c 'import svuvm,os;print(os.path.dirname(svuvm.__file__))')/"
```

CI 中的 `.github/workflows/test.yml`（`uvm-compat-*`）跑同一组版本：期望值在 `test/uvm_compat/test_compat.py` 的表里，两条腿各用 `pytest -m lint` / `pytest -m run` 并行执行，只在与期望不符时失败——已知的失败保持安静，开始通过的版本也会被点名。
