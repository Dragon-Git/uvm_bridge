# 仿真器接入

桥接层与仿真器无关。`python_bridge_pkg.sv` 只使用标准 DPI-C 的 `import` / `export`，`inc/` 下是
通用的 VPI 与 svdpi 头文件；除 `getenv` 的一处符号冲突处理外（见 Verilator 一节），不针对仿真器
裁剪功能。三条接入路径的差别仅在于桥接层以何种方式进入构建：Verilator 与 VCS 在编译期纳入，
xezim 在运行期加载。

| 仿真器 | 完整 API | CI 覆盖 |
|--------|---------|---------|
| Verilator | 是 | 每次推送 |
| xezim | 是 | 每次推送 |
| VCS | 是 | 无（无 license） |

CI 只覆盖 Verilator 与 xezim 两条路径。VCS 按下文接入，未纳入自动化验证。UVM 版本矩阵见
[uvm-version-compatibility.md](uvm-version-compatibility.md)。

**三条路径共同的前提是 UVM 1.2 及以上。** 1.0 与 1.1 系列的 DPI 源文件布局早于 1.2，桥接层的
DPI 适配层无法在其上编译；选用 VCS 内置 UVM 时尤须注意，它的版本通常低于此下限。

## 公共部分

### 命令行的三样内容

`python -m svuvm.config` 输出三项：桥接的 SV 包、已编译的扩展模块、Python 链接参数。

```console
$ python -m svuvm.config
/path/to/svuvm/python_bridge_pkg.sv /path/to/svuvm/_svuvm.cpython-312-x86_64-linux-gnu.so -LDFLAGS "-L/usr/lib -lpython3.12 -ldl -lm"
```

第三项的值内部含空格并由双引号包围，因此**不能**直接以命令替换的方式传入仿真器：

```bash
vcs $(python -m svuvm.config) top.sv    # 错误
```

命令替换的结果只经过分词，不重新解析引号，`-LDFLAGS` 会收到 `"-L/usr/lib`、`-lpython3.12`、
`-ldl`、`-lm"` 四个残缺参数（`"` 成为字面字符），链接阶段失败。先赋值再展开同样不行：

```bash
SVUVM_ARGS=$(python -m svuvm.config)
vcs $SVUVM_ARGS top.sv                  # 同样错误
```

正确做法是用 `eval` 把输出解析为**数组**，再以数组展开传入。这样引号被重新解析，且不会影响命令
其余部分的引号：

```bash
eval "SVUVM_ARGS=($(python -m svuvm.config))"
vcs "${SVUVM_ARGS[@]}" top.sv           # 正确
```

上述三条写法已在本机以等价命令逐条验证。注意数组语法需要 bash。

仓库自身的 `test/*/Makefile` 不受此影响：GNU make 先把 `$(shell ...)` 的结果展开进配方行，再由
shell 解析整行，此时引号仍按常规规则处理。

### 测试模块的可见性

测试模块所在目录必须在 `PYTHONPATH` 上。桥接层以测试类型名导入同名的 `.py`，而该目录不会
自动进入 `sys.path`；缺失时的表现为

```
ModuleNotFoundError: No module named '<测试名>'
```

下文示例假定 `top.sv` 与 `<测试名>.py` 位于同一目录，即当前目录。

## Verilator

```bash
git clone --depth 1 --branch uvm-2020-3.2 \
  https://github.com/chipsalliance/uvm-verilator.git
mkdir -p build

eval "SVUVM_ARGS=($(python -m svuvm.config))"

verilator -j "$(nproc)" --vpi --binary -top top -Mdir build \
  +incdir+"$PWD/uvm-verilator/src" "$PWD/uvm-verilator/src/uvm_pkg.sv" \
  "${SVUVM_ARGS[@]}" "$PWD/top.sv" \
  "$PWD/uvm-verilator/src/dpi/uvm_dpi.cc" \
  -CFLAGS "-I$PWD/uvm-verilator/src/dpi -I$PWD/inc -DVERILATOR"

PYTHONPATH=$PWD ./build/Vtop +UVM_TESTNAME=example_test
```

四处需要注意。

**Verilator 需要包含 suspendable DPI export 的版本。** 该功能由上游
[PR #8863](https://github.com/verilator/verilator/pull/8863) 于 2026-11-12 合入：启用
timing 后（`--binary` 隐含该选项），Verilator 把 DPI **import task** 放到工作线程上执行，
export task 遇到延时或事件时把控制权交还仿真线程，时间推进后再恢复。可用含该功能的 nightly，
也可使用该功能合入之后发布的正式版本；判断依据是导出的 task 里能否出现延时控制——5.054 及更早的
版本会给出 `%Error-UNSUPPORTED: Timing controls inside DPI-exported tasks`。本仓库 CI 目前用
`ktbarrett/setup-verilator@dev` 的 `nightly`；含该功能的正式版本发布后可直接改用正式版本。

**只有 cocotb 需要显式写出 `--timing`。** `--binary` 隐含 `--timing`（可用 `--no-timing`
关闭），所以 `test/base_test/sim_runner.py` 的 build、`compile.sh` 和 README 的编译命令都不用写；
`lint` 走 `--lint-only`，实测带或不带 `--timing` 结果完全相同，也不需要。cocotb 用
`--cc --exe --build`（没有 `--binary`），少了 `--timing` 会报 `%Error-NEEDTIMINGOPT`
（UVM 的 `#force_time`、`process::self()` 等），因此 `test/cocotb_test/Makefile` 保留该选项。

**按 phase 选择 Python 入口。** IEEE 1800-2023 35.8 不允许在 DPI import **function**
的上下文中调用耗时的 export task，Verilator 会在运行时以
`DPI exported task called from function context` 报错中止。桥接层为此提供两个入口：

| 入口 | DPI 声明 | C 侧返回 | 使用位置 | 可否调用耗时接口 |
| --- | --- | --- | --- | --- |
| `py_func` | `import function int` | `int`（恒 0） | `build_phase` / `connect_phase`（UVM 的 function phase） | 否 |
| `py_task` | `import task` | `int`（恒 0） | `main_phase`、`process_pool` | 是 |

`call_py_func` 已计划弃用，仍经 `py_func` 进入，因此只能用零时间接口；不再为它扩展耗时能力。

按 IEEE 1800-2023 35.5.4，import **task** 在 SV 侧声明时不写返回类型，但它的外部语言实现
**必须返回 `int`**：这个 `int` 不是 task 的结果（SV task 没有返回值，输出经指针参数传出），而是
DPI disable protocol 的完成状态（0 正常完成，非 0 表示被调用方 `disable`）。含该特性的
Verilator 在 `verilated_dpi.h` 用 `static_assert` 强制检查该返回类型。import **function** 则允许 `void`
或任意值；本桥把两个入口在 C 侧统一为 `int`，因此 `py_func` 的 SV 声明显式写成
`function int py_func(...)`，Verilator 生成 `extern int py_func(...)`，与 `py_task` 的
`extern int py_task(...)` ABI 一致。桥从不 disable 这两个入口，状态恒为 0（`py_task` 直接
透传 `py_func` 的返回值）。SV 侧把 `py_func` 当语句调用时必须写 `void'(py_func(...))` 显式
丢弃返回值，避免 `IGNOREDRETURN`（IEEE 1800-2023 13.4.1）；本仓库的仿真构建另以
`-Wno-IGNOREDRETURN` 兜底，但显式写法对其他仿真器和更严格的 lint 配置更稳妥。

`main_phase` 的 Python 回调（默认 `main`）经 `py_task` 进入，寄存器访问、事件等待、
`barrier_wait`、`start_seq`、`wait_unit` 均在其中可用；`build` / `connect` 回调仍只能使用
零时间的配置类接口。这是 UVM function phase 的 SV 语义，桥接层按此提供两个入口。
工作线程上还要处理 CPython 的 GIL：`svuvm.cpp` 在首次进入 `py_func`
时把主线程持有的 GIL 释放一次（不论解释器由桥本身还是由 cocotb 这类嵌入方初始化），并在
每次 DPI 调用期间再次释放。否则一个 worker 在 export task 里让出调度权时，另一个 worker
会卡在 `PyGILState_Ensure()` 上，与等待它的主线程形成死锁。

**UVM 源码必须使用带 Verilator 后端的版本。** 上游 UVM 自 2020-3.2 起才提供 Verilator 的 HDL
后端，更早的版本在 `uvm_hdl.c` 中因缺少后端直接报错。上例取上游 2020-3.2；
`Dragon-Git/uvm-verilator` fork 在此基础上额外支持更早的版本。`-CFLAGS` 里的 `-DVERILATOR`
是给这层 UVM DPI 代码用的；桥接层的 SV 包不再按仿真器裁剪功能，与仿真器相关的条件编译只剩
一处与符号冲突有关的 `ifndef VERILATOR`：`import "DPI-C" function string getenv` 在 Verilator
下会生成
`const char* getenv(const char*)`，与 `<stdlib.h>` 里 libc 的 `char* getenv(const char*)`
冲突，因此仍在 `` `ifndef VERILATOR `` 下；其他仿真器把它直接链到 libc。

## xezim

xezim 以解释方式执行，无需预编译。有两项运行期要求：

- UVM 源码树通过 `XEZIM_UVM_DIR` 指定，取含 `src/` 的根目录；`-uvm` 选项依赖该变量。
- `_svuvm.so` 未链接 libpython，而 xezim 以 `RTLD_NOW` 加载它时 `--dpi-lib` 无法保证 libpython
  的符号全局可见，因此需在操作系统层面另行预加载。

```bash
git clone --depth 1 --branch uvm-2020-3.2 \
  https://github.com/chipsalliance/uvm-verilator.git

XEZIM_LIBPYTHON=$(python -c 'import sysconfig, os, glob; d = sysconfig.get_config_var("LIBDIR"); v = sysconfig.get_config_var("LDVERSION") or ""; print(next(p for f in ("*.so", "*.dylib") for p in glob.glob(os.path.join(d, "libpython" + v + f))))')
XEZIM_SVUVM=$(python -c 'import svuvm, os; print(os.path.dirname(svuvm.__file__))')
XEZIM_DPI_LIB=$(python -c 'import svuvm, os, glob; print(glob.glob(os.path.join(os.path.dirname(svuvm.__file__), "_svuvm*.so"))[0])')

PYTHONPATH=$PWD XEZIM_UVM_DIR=$PWD/uvm-verilator xezim --simulate -s top \
  --dpi-lib "$XEZIM_LIBPYTHON" \
  --dpi-lib "$PWD/build/uvm_dpi_xezim.so" \
  --dpi-lib "$XEZIM_DPI_LIB" \
  --max-time 10ms --error-exit -uvm \
  "$XEZIM_SVUVM/python_bridge_pkg.sv" "$PWD/top.sv" \
  +UVM_TESTNAME=example_test
```

`uvm_dpi_xezim.so` 由 UVM DPI 层的 xezim 变体 `uvm_dpi_xezim.cc` 编得；EDAPack 的 xezim 发布包
在 `include/` 下提供该文件，以标准 IEEE 1800 VPI 实现 `uvm_hdl_*` 接口。编译命令见
`test/base_test/sim_runner.py` 的 xezim 分支。此路径可直接使用上游 UVM 源码。

## VCS

VCS 在编译期纳入桥接层，与 Verilator 同类，但选项上有一处关键差异：**不要定义 `VERILATOR`**。
该宏属于 UVM 的 Verilator HDL 后端，VCS 侧不需要它。

**UVM 版本必须显式指定，且不低于 1.2。** `-ntb_opts uvm` 引入的是 VCS 内置的 UVM，版本随 VCS
发行版本而定，早于桥接层支持的 1.2，不可使用。应显式写出 1.2 及以上的版本，例如
`-ntb_opts uvm-1.2`；对应 2017 / 2020 版本另有专门选项，具体名称以所用 VCS 的文档为准。支持的
版本范围见 [uvm-version-compatibility.md](uvm-version-compatibility.md)。若已有独立的 UVM 编译
流程（自行指定源码树与 include 路径），则沿用原有参数，不再写 `-ntb_opts`。

`-timescale` 供 UVM 的时间单位使用，建议显式给出。

```bash
eval "SVUVM_ARGS=($(python -m svuvm.config))"

vcs -full64 -sverilog \
  -timescale=1ns/1ps \
  -ntb_opts uvm-1.2 \
  "${SVUVM_ARGS[@]}" \
  top.sv

PYTHONPATH=$PWD ./simv +UVM_TESTNAME=example_test
```

说明：

- `-timescale` 与 `-ntb_opts` 的取值应按所用 VCS 与 UVM 版本调整；UVM 低于 1.2 时桥接层不适用。
- `uvm_hdl_*` 依赖 VPI 访问信号，需要相应的调试访问选项（例如 `-debug_access+all`），否则信号
  级操作不可用。
- 运行时 `_svuvm.so` 需要找到 libpython。链接参数已由 `-LDFLAGS` 提供；若运行时报找不到
  `libpython`，将 Python 的 `LIBDIR` 加入 `LD_LIBRARY_PATH`。
- `uvm-verilator` fork 仅为 Verilator 提供后端，对其余仿真器不是必需项，VCS 下用上游 UVM 即可。

## 其他仿真器

Questa 与 Xcelium 暂无单独说明。桥接层未针对它们做任何条件编译，接入方式与 VCS 一致：同一段
`svuvm.config` 输出、不定义 `VERILATOR`、显式指定 UVM 1.2 及以上版本、按需给出 timescale；
CI 覆盖情况见开头表格。
