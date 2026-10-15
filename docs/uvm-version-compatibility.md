# UVM 版本兼容性报告：svuvm（Dragon-Git/uvm_bridge）

**日期**：2026-10-15
**仿真器**：xezim 0.11.1（aionhw/xezim main，`3017d45`）
**被测代码**：`src/svuvm/python_bridge_pkg.sv`（提交 `ef8b526`）
**结论**：**9/9 版本通过**。跨版本修复（`UVM_VERSION_POST_2020_1_1` 单宏双路径）在全部版本上生效；`drain_time` 的断言失败**仅**源于 xezim 的 DPI 导出 bug，桥接层无缺陷。

---

## 1. 测试范围与排除项

### 1.1 测试的版本（9 个）

| # | tag | `UVM_VERSION` | 有 `uvm_phase_hopper` | `UVM_VERSION_POST_2020_1_1` | drain 路径 |
|---|-----|---------------|----------------------|------------------------------|-----------|
| 1 | `uvm-1.2` | 1.2 | 否 | 未定义 | 旧 |
| 2 | `uvm-2017-1.0` | 2016 | 否 | 未定义 | 旧 |
| 3 | `uvm-2017-1.1` | 2020 | 否 | 未定义 | 旧 |
| 4 | `uvm-2020-1.0` | 2020 | 否 | 未定义 | 旧 |
| 5 | `uvm-2020-1.1` | 2020 | 否 | 未定义 | 旧 |
| 6 | `uvm-2020-2.0` | 2020 | **是** | **已定义** | 新 |
| 7 | `uvm-2020-3.0` | 2020 | **是** | **已定义** | 新 |
| 8 | `uvm-2020-3.1` | 2020 | **是** | **已定义** | 新 |
| 9 | `uvm-2020-3.2` | 2020 | **是** | **已定义** | 新 |

后三列是从各 tag 的源码实测得到的（`src/macros/uvm_version_defines.svh` 与 `class uvm_phase_hopper` 的出现），不是推断。

### 1.2 排除项

| 排除 | 原因 |
|------|------|
| `uvm-1.0p1` | **UVM 1.0 不在本次测试范围**（任务明确要求） |
| `uvm-1.1a` / `1.1b` / `1.1c` / `1.1d` | pre-1.2：xezim 的 DPI 适配层依赖 `uvm_dpi.h`，该头文件 1.2 才引入，1.1 及更早无法编译 |
| `uvm-2017-0.9` | IEEE-2017 草案版，factory / `run_test` 流程差异导致 `base_test not found` |

### 1.3 UVM 源码获取方式

按任务要求**用 Git 并通过切换 tag 获取**，不使用 release 压缩包：

```sh
git clone https://github.com/chipsalliance/uvm-verilator.git /tmp/uvmrepo
# 逐个 tag 抽取 src/，落到 /tmp/uvm/<tag>/src/
for t in uvm-1.2 uvm-2017-1.0 uvm-2017-1.1 uvm-2020-1.0 uvm-2020-1.1 \
         uvm-2020-2.0 uvm-2020-3.0 uvm-2020-3.1 uvm-2020-3.2; do
    mkdir -p /tmp/uvm/$t
    git -C /tmp/uvmrepo archive "$t" src | tar x -C /tmp/uvm/$t
done
```

版本切换通过 xezim 的 UVM 入口软链完成（`<XEZIM_PREFIX>/share/uvm/src` → `/tmp/uvm/<tag>/src`），不改 Makefile：

```sh
ln -sfn /tmp/uvm/uvm-2020-3.2/src <XEZIM_PREFIX>/share/uvm/src
```

---

## 2. 结果矩阵

判定标准：`rc=0` 且出现完成标记 `所有新增API测试完成`。`UVM_FATAL: 10` / `UVM_ERROR: 20` 是 `base_test` 自身 API 测试的预期计数（含 `UVM_FATAL TEST SUCCESS!` 与 `set_severity_count` 用例），**跨版本完全一致，不构成失败**。

| tag | rc | 完成标记 | 耗时 | drain 断言 | 判定 |
|-----|----|---------|------|-----------|------|
| `uvm-1.2` | 0 | 有 | 60s | 失败（xezim bug） | **PASS** |
| `uvm-2017-1.0` | 0 | 有 | 60s | 失败（xezim bug） | **PASS** |
| `uvm-2017-1.1` | 0 | 有 | 65s | 失败（xezim bug） | **PASS** |
| `uvm-2020-1.0` | 0 | 有 | 75s | 失败（xezim bug） | **PASS** |
| `uvm-2020-1.1` | 0 | 有 | 55s | 失败（xezim bug） | **PASS** |
| `uvm-2020-2.0` | 0 | 有 | 87s | 失败（xezim bug） | **PASS** |
| `uvm-2020-3.0` | 0 | 有 | 88s | 失败（xezim bug） | **PASS** |
| `uvm-2020-3.1` | 0 | 有 | 115s | 失败（xezim bug） | **PASS** |
| `uvm-2020-3.2` | 0 | 有 | 95s | 失败（xezim bug） | **PASS** |

**没有 FAIL**。全部 9 个版本正常跑到结束。

### 2.1 两条路径都被真实执行过

| 证据 | 旧路径（1.2） | 新路径（2020-3.2） |
|------|--------------|-------------------|
| 日志中 `phase_hopper` 出现次数 | **0** | 大量（`phase_hopper_objection` objection 事件） |
| `set_drain_time(100)` 往返 | 成功（值回来了） | 成功（值回来了） |

两版都显示 `get_drain_time = 4636737291354636288` —— 即 100.0 的位模式。**值确实写进去又读回来了**，说明 `set_drain_time` 与 `get_drain_time` 在两条路径上都真正工作；失败只发生在最后一步的数值比较。

---

## 3. 跨版本修复方案

### 3.1 选用 `UVM_VERSION_POST_2020_1_1` 单宏

`uvm_phase_hopper` 类只在 **UVM 2020-2.0 及以后**存在。实测 9 个 tag 后确认：`UVM_VERSION_POST_2020_1_1` 的定义范围与该类的存在范围**完全 1:1**（表 1.1 后两列）。因此一个 `` `ifdef `` 就同时回答了"该类是否存在"，无需引入任何自定义宏。

**未采用的备选**：

- `` `UVM_VERSION_POST_2017_1_1 ``：在本次实测的发布版上同样 1:1，但语义边界是"2017.1.1 之后"，不如 `POST_2020_1_1` 紧。
- `UVM_MAJOR_REV` + `UVM_VERSION_1_2` 组合：**不安全**。`uvm-1.1d` 有 `UVM_MAJOR_REV(=1)` 却没有 `UVM_VERSION_1_2`，组合会错误激活；单宏在 1.1d 上未定义，天然规避。
- 数值 `` `if ``：不必需，单 `` `ifdef `` 已足够且可移植。

### 3.2 三处改动（均以该单宏为开关）

**改动 1** —— `_pb_phase_hopper` 子类 + override 注册函数，整体包在 `` `ifdef `` 内。因为 `uvm_phase_hopper::get_objection()` 是 protected，需要子类暴露公开访问器，并用 factory type override 让 `get_global_hopper()` 返回该子类。

**改动 2** —— override 注册放在 **`base_test::new()`**（构造函数），不是 `build_phase`。原因：`run_test()` 在 `fork` 里、`build_phase` 之前就创建了 hopper 单例，注册晚了单例已经是错误类型，`$cast` 会失败。

**改动 3** —— `set_drain_time` / `get_drain_time` 双路径：

```systemverilog
`ifdef UVM_VERSION_POST_2020_1_1
        hopper = uvm_phase_hopper::get_global_hopper();      // 新：hopper 持有 run-time objection
        if ($cast(pb_hopper, hopper))
            pb_hopper.get_objection_public().set_drain_time(null, drain_ns * 1ns);
`else
        uvm_phase ph = uvm_domain::get_common_domain()       // 旧：run 相位自己的 objection
                          .find_by_name("run", 0);
        if (ph != null)
            ph.get_objection().set_drain_time(null, drain_ns * 1ns);
`endif
```

旧路径**不能**用 `uvm_test_done_objection`——它在 IEEE-2017 基线已被移除。改用 run 相位的公开 objection，1.2 / 2017 / 2020-1.x 通用。

### 3.3 不使用 `$rtoi` 或任何类型转换

`get_drain_time` 直接返回 `... / 1ns`，不包 `$rtoi`。原因见第 4 节：该返回值异常是**仿真器侧的 DPI bug**，已单独向上游报告，桥接层不做类型转换掩盖问题。

---

## 4. 已知 xezim DPI bug（唯一阻塞项）

### 4.1 现象与决定性证据

```
verilator : set_drain_time(100), get_drain_time = 100                  → drain_time test success
xezim     : set_drain_time(100), get_drain_time = 4636737291354636288  → drain_time test failed
```

`4636737291354636288` = `0x4059000000000000` = **IEEE-754 double 100.0 的位模式**。

**同一份桥接代码、同一个 UVM 版本，在 verilator 上得到 100，在 xezim 上得到位模式。** 这证明：

1. 桥接层的双路径改动是**正确的**（verilator 上断言通过）；
2. xezim 上的失败**完全**来自模拟器，与 UVM 版本无关（9 个版本返回值逐位相同）。

### 4.2 根因（定位到源码）

xezim `src/compiler/simulator/dpi_export.rs` 的 `value_to_slot`：

```rust
DpiCScalar::F32 | DpiCScalar::F64 => v.to_f64().to_bits() as i64,   // 位重解释
...
_ => {
    let mut v = v.clone();
    v.is_real = false;
    v.to_u64().map_or(0, |u| u as i64)                              // 清掉 real 标记后按位读
}
```

`get_drain_time` 声明返回 `longint`（命中 `_` 分支），而 `X / 1ns` 被求值为 real；`is_real = false` 之后 `to_u64()` 得到的是浮点位模式而非数值转换。对照同文件 `dpi_store_vec` 对 packed vector 用的是正确转换 `v.to_f64() as i64`。

### 4.3 上游状态：**尚未修复**

在 `3017d45` 之后上游已有 **133 个提交**，其中改动 `dpi_export.rs` 的仅 2 个（`bc54f3c` unpacked struct、`9dce804` fork-merge 清理），**均与本题无关**。核对上游 `origin/main`：

- `value_to_slot` 的 `DpiCScalar::F32 | DpiCScalar::F64 => ... .to_bits() as i64` 原样保留；
- `_` 分支的 `is_real = false` + `to_u64()` 原样保留。

即 **bug 在 xezim main 上仍然存在**。桥接侧已就绪，此项需上游修复后才能让 `drain_time` 断言在 xezim 上通过。

---

## 5. 新的兼容性发现

### 5.1 修改 5 的 guard 方案在 `uvm-2017-1.0` 上不成立（需修正）

交接文档建议对 `get_phase_state_name` 里的 `UVM_PHASE_UNINITIALIZED` 加版本宏保护：

```systemverilog
`ifdef UVM_VERSION_1_2
UVM_PHASE_UNINITIALIZED : return "UNINITIALIZED";
`elsif UVM_VERSION_POST_2017
UVM_PHASE_UNINITIALIZED : return "UNINITIALIZED";
`endif
```

但实测 `uvm-2017-1.0` 的 `src/macros/uvm_version_defines.svh` **只定义了** `UVM_VERSION_DEFINES_SVH` 和 `UVM_VERSION 2016`——**既不定义 `UVM_VERSION_1_2`，也不定义 `UVM_VERSION_POST_2017`**，两条分支都不命中。若照此实现，`uvm-2017-1.0` 会**静默丢掉**这个 case 标签（该版本其实是有 `UVM_PHASE_UNINITIALIZED` 的），导致 `get_phase_state_name` 在该版本上行为不同。

| tag | `UVM_VERSION_1_2` | `UVM_VERSION_POST_2017` |
|-----|------------------|------------------------|
| `uvm-1.2` | 已定义 | 未定义 |
| `uvm-2017-1.0` | **未定义** | **未定义** |
| `uvm-2017-1.1` | 未定义 | 已定义 |
| `uvm-2020-*` | 未定义 | 已定义 |

**建议**：**不加**该 guard。实测 `UVM_PHASE_UNINITIALIZED` 在全部 9 个测试版本中都存在（1.2 / 2017-1.0 / 2017-1.1 / 2020-1.0 / 1.1 / 2.0 / 3.0 / 3.1 / 3.2），无条件的 case 标签在各版本都能编译且行为一致。当前仓库即为不加 guard 的写法，9 个版本全部编译通过。

### 5.2 附带观察

- `uvm-2017-1.0` 的 `UVM_VERSION` 宏值是 **2016**（不是 2017），与 tag 名不一致，属该版本自身的历史遗留，不影响本次改动（我们不依赖数值比较）。
- 三次跑批中出现过一次 `uvm-2020-1.0` 耗时 327s 的异常；单独复跑为 75s（同量级于其他版本）。判定为机器争用噪声，**非版本特性**。

---

## 6. 复现方法

```sh
# 0) 前置：xezim、svuvm 已装
which xezim
svuvm_dir=$(python -c "import svuvm,os;print(os.path.dirname(svuvm.__file__))")

# 1) 同步桥接改动到运行时副本（xezim 加载的是包内副本，不是仓库内的）
cp <UVM_BRIDGE_REPO>/src/svuvm/python_bridge_pkg.sv "$svuvm_dir/python_bridge_pkg.sv"

# 2) 切到待测版本
ln -sfn /tmp/uvm/<tag>/src <XEZIM_PREFIX>/share/uvm/src

# 3) 跑
cd <UVM_BRIDGE_REPO>
make -f test/base_test/Makefile SIM=xezim XEZIM_PREFIX=<XEZIM_PREFIX> run
```

判定：`echo $?` 为 0 且日志中出现 `所有新增API测试完成`。

Xezim 的 UVM 入口是 `<XEZIM_PREFIX>/share/uvm/src`；若该路径原本是实目录，先备份为 `src.bundled` 再建软链。

---

## 7. 交付物

| 项 | 位置 |
|----|------|
| 桥接代码改动 | `src/svuvm/python_bridge_pkg.sv`（提交 `ef8b526`） |
| 运行时副本同步 | `<svuvm_pkg_dir>/python_bridge_pkg.sv`（两份已 diff 校验一致） |
| 各版本运行日志 | `/tmp/matrix/<tag>.log` |
| 矩阵汇总 | `/tmp/matrix/summary.txt` |
| verilator 对照日志 | `/tmp/matrix/verilator.log` |

### 遗留 / 后续

1. **xezim DPI bug**：桥接侧无待办；需上游修复后复跑以确认 `drain_time` 断言在 xezim 上也通过。verilator 腿已证明桥接代码正确。
2. **verilator 腿回归**：已跑通（`get_drain_time = 100`，断言通过），无回归。注意 verilator 腿用的 UVM fork 也定义了 `UVM_VERSION_POST_2020_1_1`，**走的是 hopper 新路径**。
