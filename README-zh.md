# uvm-bridge 文档

[English](README.md) | 简体中文

## 概述

svuvm 是一款硬件验证框架, 通过该框架，用户可以在 Python 中调用 SystemVerilog UVM 的常用 API 来编写case或者动态配置环境，从而节省编译时间并提高开发效率。 
与cocotb等主流基于 Python 的硬件验证框架相比，svuvm与systemverilog uvm 框架兼容性较好，可以充分利用基于uvm的商业 VIP 和丰富的 python 生态，并且对现有的基于uvm的验证环境没有破坏性，用户可以自由的选择环境中部分功能使用python编写而不影响该环境中使用systemverilog的其他用户。

## 特点
- 支持Python编写SystemVerilog UVM测试用例，动态配置环境
- 显著减少编译次数
- 可以利用python丰富的生态
- 兼容标准UVM框架，可充分利用商业VIP生态
- 方便现有uvm用户迁移

## 安装

### 安装依赖:
- Python 3.9.0+
- nanobind, pyslang (运行时不需要)
### 命令：
```sh
pip install svuvm
```

## 编译

需要在编译命令中添加` $(python -m svuvm.config)`

## 快速参考
- 创建组件: `svuvm.create_component_by_name("base_env", "uvm_test_top", "m_env")`
- 创建对象: `svuvm.create_object_by_name("env_cfg", "uvm_test_top", "m_cfg")`
- 类型注册查询: `svuvm.is_type_registered("my_component")`
- 打印拓扑: `svuvm.print_topology()`
- Write register: `svuvm.write_reg("rm.reg_a", 0x12345678)`
- Read register: `data = svuvm.read_reg("rm.reg_a")`
- Check register: `svuvm.check_reg("rm.reg_a", 0x12345678)`
- 设置顶层寄存器块: `svuvm.set_top_reg_block_by_path("uvm_test_top.m_reg_block")`
- 枚举寄存器: `svuvm.get_reg_names("")`
- 获取镜像值: `svuvm.get_reg_mirrored_value("rm.reg_a")`
- 获取寄存器地址: `svuvm.get_reg_address("rm.reg_a")`
- Start sequence: `svuvm.start_seq("my_seq", "uvm_test_top.m_env.m_agent.my_sqr")`
- 后台运行序列: `svuvm.start_seq("my_seq", "uvm_test_top.m_env.m_agent.my_sqr", background=1)`
- 停止序列: `svuvm.stop_sequences("uvm_test_top.m_env.m_agent.my_sqr")`
- 查询序列器状态: `svuvm.is_sequencer_busy("uvm_test_top.m_env.m_agent.my_sqr")`
- 设置 drain time: `svuvm.set_drain_time(1000)`
- 查询当前相位: `svuvm.get_current_phase_name()`
- 查询异议计数: `svuvm.get_objection_count("main", "uvm_test_top")`
- 组件子节点数: `svuvm.component_get_num_children("uvm_test_top")`
- 组件 sprint: `svuvm.component_sprint("uvm_test_top")`
- 触发事件: `svuvm.trigger("my_event")`
- Barrier 设置: `svuvm.barrier_set_threshold("my_barrier", 3)`
- 池操作: `svuvm.pool_num("event")`, `svuvm.pool_keys("event")`
- Config DB 存在查询: `svuvm.config_db_exists("", "", "my_key")`
- 报告汇总: `svuvm.report_summarize()`
- 打印机旋钮: `svuvm.set_default_printer_knob("indent", 2)`
- Wait for 500 time units: `svuvm.wait_unit(500)`
- Force signal: `svuvm.uvm_hdl_force("tb.dut.sig", svuvm.vpi.VpiVecVal(0,1))`
- Release signal: `svuvm.uvm_hdl_release("tb.dut.sig")`
- Read signal: `data = svuvm.uvm_hdl_read("tb.dut.sig")`
- Print info: `svuvm.uvm_info("msg", svuvm.UVM_LOW)`
- Print error: `svuvm.uvm_error("msg")`

## 使用示例

### 在sv中启动python函数
```systemverilog
// top.sv
module top ();
    import uvm_pkg::*;
    `include "uvm_macros.svh"
    import python_bridge_pkg::*;

    class example_test extends uvm_test;
        `uvm_component_utils(example_test)
        `uvm_new_func

        virtual task main_phase(uvm_phase phase);
            phase.raise_objection(this);
            py_func(get_type_name(), "main", dirname(`__FILE__));
            phase.drop_objection(this);
        endtask
    endclass

    logic clk/*verilator public_flat*/ = 1'b0;
    always #5 clk = ~clk;

    initial begin 
        run_test();
    end
endmodule
```
### python 中调用api

```python
# example_test.py
import svuvm

def main():
    # 基础：创建组件并访问寄存器
    svuvm.create_component_by_name("base_env", "uvm_test_top", "m_env")
    svuvm.write_reg("rm.ctrl_reg", 0xDEADBEEF)
    data = svuvm.read_reg("rm.ctrl_reg")
    svuvm.uvm_info(f"Read data: 0x{data:08X}", svuvm.UVM_LOW)

    # 扩展：设置顶层寄存器块，枚举所有寄存器
    svuvm.set_top_reg_block_by_path("uvm_test_top.m_reg_block")
    for name in svuvm.get_reg_names("").split(","):
        addr = svuvm.get_reg_address(name)
        val = svuvm.get_reg_mirrored_value(name)
        svuvm.uvm_info(f"{name}: addr=0x{addr:X}, mirrored=0x{val:X}", svuvm.UVM_LOW)

    # 扩展：序列器控制
    sqr = "uvm_test_top.m_env.m_agent.m_sqr"
    svuvm.start_seq("my_seq", sqr, rand_en=1, background=0)
    if svuvm.is_sequencer_busy(sqr):
        svuvm.uvm_info("Sequencer is busy", svuvm.UVM_LOW)
    svuvm.stop_sequences(sqr)

    # 扩展：相位与异议
    svuvm.set_drain_time(1000)
    phase = svuvm.get_current_phase_name()
    svuvm.uvm_info(f"In phase: {phase}", svuvm.UVM_LOW)
    cnt = svuvm.get_objection_count("main", "uvm_test_top")
    svuvm.display_objections("main", "uvm_test_top")

    # 扩展：组件拓扑查询
    n = svuvm.component_get_num_children("uvm_test_top")
    for i in range(n):
        child = svuvm.component_get_child_name("uvm_test_top", i)
        t = svuvm.component_get_type_name("uvm_test_top." + child)
        svuvm.uvm_info(f"[{i}] {child} (type: {t})", svuvm.UVM_LOW)
    text = svuvm.component_sprint("uvm_test_top")

    # 扩展：事件、barrier、池
    svuvm.ev_reset("done_event")
    svuvm.trigger("done_event")
    svuvm.barrier_set_threshold("my_barrier", 3)
    pool_sz = svuvm.pool_num("event")
    pool_ks = svuvm.pool_keys("event")

    # 扩展：报告汇总、打印机旋钮
    svuvm.report_summarize()
    svuvm.set_default_printer_knob("indent", 2)
    svuvm.set_default_comparer_knob("show_max", 100)
```
### 编译命令
```bash
git clone https://github.com/Dragon-Git/uvm-verilator.git # Workaround 版本，verilator 还完全未支持uvm
mkdir build
verilator -j $(nproc) --vpi --binary -top top -Mdir build --output-groups $(($(nproc))) \
+incdir+$PWD/uvm-verilator/src $PWD/uvm-verilator/src/uvm_pkg.sv \
$(python -m svuvm.config) $PWD/top.sv \
-Wno-lint -Wno-style -Wno-SYMRSVDWORD -Wno-IGNOREDRETURN -Wno-CONSTRAINTIGN -Wno-ZERODLY \
$PWD/uvm-verilator/src/dpi/uvm_dpi.cc \
-CFLAGS "-I$PWD/uvm-verilator/src/dpi -I$PWD/inc -DVERILATOR" \

./build/Vtop +UVM_TESTNAME=example_test

```

## API 函数

### 1. 工厂

- **`print_factory(all_types=1)`**
  - 打印工厂信息。
  - 参数：
    - `all_types` (int): 是否打印所有类型，默认为 1。

- **`is_type_registered(type_name)`**
  - 检查类型是否已在工厂中注册。
  - 参数：
    - `type_name` (str): 类型名称（如 `base_env`、`my_driver`）。
  - 返回：
    - `bool`: 是否已注册。

- **`create_component_by_name(type_name, parent_name, name)`**
  - 通过类型名称动态创建 UVM 组件。
  - 参数：
    - `type_name` (str): 要创建的组件类型名称。
    - `parent_name` (str): 父组件路径。
    - `name` (str): 新组件的实例名称。

- **`create_object_by_name(type_name, parent_name, name)`**
  - 通过类型名称动态创建 UVM 对象（非组件）。
  - 参数：
    - `type_name` (str): 要创建的对象类型名称。
    - `parent_name` (str): 父对象路径。
    - `name` (str): 新对象的实例名称。

- **`set_factory_inst_override(original_type_name, override_type_name, full_inst_path)`**
  - 设置实例覆盖。
  - 参数：
    - `original_type_name` (str): 原始类型名称。
    - `override_type_name` (str): 覆盖类型名称。
    - `full_inst_path` (str): 实例路径。

- **`set_factory_type_override(original_type_name, override_type_name, replace=True)`**
  - 设置类型覆盖。
  - 参数：
    - `original_type_name` (str): 原始类型名称。
    - `override_type_name` (str): 覆盖类型名称。
    - `replace` (bool): 是否替换，默认为 True。

- **`debug_factory_create(requested_type, context='')`**
  - 调试工厂对象创建。
  - 参数：
    - `requested_type` (str): 请求的类型名称。
    - `context` (str): 上下文，默认为空字符串。

- **`find_factory_override(requested_type, context, override_type_name)`**
  - 查找工厂覆盖。
  - 参数：
    - `requested_type` (str): 请求的类型名称。
    - `context` (str): 上下文。
    - `override_type_name` (str): 输出覆盖类型名称。

### 2. 根节点与仿真配置

- **`set_timeout(timeout, overridable=1)`**
  - 设置超时值。
  - 参数：
    - `timeout` (long long): 超时时间。
    - `overridable` (unsigned char): 是否可覆盖，默认为 1。

- **`set_finish_on_completion(finish)`**
  - 设置是否在测试完成时自动结束仿真。
  - 参数：
    - `finish` (int): 1 = 结束，0 = 不结束。

- **`print_topology(context='')`**
  - 打印拓扑结构。
  - 参数：
    - `context` (str): 上下文，默认为空字符串。

- **`dbg_print(name='')`**
  - 打印对象。
  - 参数：
    - `name` (str): 对象名称，默认为空字符串。

### 3. 组件拓扑查询

- **`component_get_num_children(comp_path)`**
  - 获取组件的直接子节点数量。
  - 参数：
    - `comp_path` (str): 组件层次路径。
  - 返回：
    - `int`: 子节点数量。

- **`component_get_child_name(comp_path, index)`**
  - 获取指定索引的子节点名称。
  - 参数：
    - `comp_path` (str): 组件层次路径。
    - `index` (int): 子节点索引（从 0 开始）。
  - 返回：
    - `str`: 子节点名称。

- **`component_get_parent(comp_path)`**
  - 获取父组件路径。
  - 参数：
    - `comp_path` (str): 组件层次路径。
  - 返回：
    - `str`: 父组件路径。

- **`component_get_type_name(comp_path)`**
  - 获取组件的类型名称（如 `uvm_test`、`base_env`）。
  - 参数：
    - `comp_path` (str): 组件层次路径。
  - 返回：
    - `str`: 组件类型名称。

- **`component_sprint(comp_path)`**
  - 生成组件的字符串表示（类似 uvm_component::sprint）。
  - 参数：
    - `comp_path` (str): 组件层次路径。
  - 返回：
    - `str`: 组件信息字符串。

- **`uvm_top_sprint()`**
  - 生成整个 UVM 层次的字符串表示。
  - 返回：
    - `str`: 整个 UVM 层次的字符串表示。

- **`component_compare(comp_path_a, comp_path_b)`**
  - 比较两个组件是否相等。
  - 参数：
    - `comp_path_a` (str): 第一个组件路径。
    - `comp_path_b` (str): 第二个组件路径。
  - 返回：
    - `bool`: 比较结果。

### 4. 相位与异议管理

- **`set_drain_time(drain_time)`**
  - 设置异议的 drain time（等待时间）。
  - 参数：
    - `drain_time` (long long): 以时间单位表示的等待时间。

- **`get_drain_time()`**
  - 获取当前设置的 drain time。
  - 返回：
    - `long long`: drain time 值。

- **`get_current_phase_name()`**
  - 获取当前正在执行的相位名称（如 `main`、`reset`）。
  - 返回：
    - `str`: 相位名称。

- **`get_phase_state(phase_name)`**
  - 获取指定相位的状态（UVM_PHASE_STARTED/ENDED 等）。
  - 参数：
    - `phase_name` (str): 相位名称。
  - 返回：
    - `int`: 状态枚举值。

- **`get_phase_state_name(phase_name)`**
  - 获取指定相位的状态名称（字符串形式）。
  - 参数：
    - `phase_name` (str): 相位名称。
  - 返回：
    - `str`: 状态名称。

- **`uvm_objection_op(op, name, contxt, description, count)`**
  - 操作异议。
  - 参数：
    - `op` (str): 操作类型（如 "RAISE" 或 "DROP"）。
    - `name` (str): 名称。
    - `contxt` (str): 上下文。
    - `description` (str): 描述。
    - `count` (unsigned int): 计数。

- **`get_objection_count(phase_name, context)`**
  - 获取指定相位/上下文中当前的异议计数。
  - 参数：
    - `phase_name` (str): 相位名称。
    - `context` (str): 组件上下文路径。
  - 返回：
    - `int`: 异议计数。

- **`get_objection_total(phase_name, context)`**
  - 获取累计的异议总数。
  - 参数：
    - `phase_name` (str): 相位名称。
    - `context` (str): 组件上下文路径。
  - 返回：
    - `int`: 异议总数。

- **`display_objections(phase_name, context)`**
  - 打印指定相位的异议详细信息，用于调试。
  - 参数：
    - `phase_name` (str): 相位名称。
    - `context` (str): 组件上下文路径。

### 5. 事件管理

- **`wait_on(ev_name, delta=0)`**
  - 等待信号变为高电平。
  - 参数：
    - `ev_name` (str): 事件名称。
    - `delta` (int): 循环次数，默认为 0。

- **`wait_off(ev_name, delta=0)`**
  - 等待信号变为低电平。
  - 参数：
    - `ev_name` (str): 事件名称。
    - `delta` (int): 循环次数，默认为 0。

- **`wait_trigger(ev_name)`**
  - 等待触发事件。
  - 参数：
    - `ev_name` (str): 事件名称。

- **`get_trigger_time(ev_name)`**
  - 获取上次触发事件的时间。
  - 参数：
    - `ev_name` (str): 事件名称。

- **`is_on(ev_name)`**
  - 检查信号是否为高电平。
  - 参数：
    - `ev_name` (str): 事件名称。

- **`is_off(ev_name)`**
  - 检查信号是否为低电平。
  - 参数：
    - `ev_name` (str): 事件名称。

- **`reset(ev_name, wakeup=0)`**
  - 重置信号状态。
  - 参数：
    - `ev_name` (str): 事件名称。
    - `wakeup` (int): 是否唤醒，默认为 0。

- **`cancel(ev_name)`**
  - 取消当前等待操作。
  - 参数：
    - `ev_name` (str): 事件名称。

- **`get_num_waiters(ev_name)`**
  - 获取等待者数量。
  - 参数：
    - `ev_name` (str): 事件名称。

- **`trigger(ev_name)`**
  - 触发事件。
  - 参数：
    - `ev_name` (str): 事件名称。

- **`ev_reset(ev_name, wakeup=0)`**
  - 重置事件状态（事件专用 API，与全局 `reset()` 区分）。
  - 参数：
    - `ev_name` (str): 事件名称。
    - `wakeup` (int): 是否唤醒等待该事件的进程。

### 6. Barrier 管理

- **`barrier_set_threshold(name, threshold)`**
  - 设置 barrier 的阈值（需要多少个等待者才放行）。
  - 参数：
    - `name` (str): barrier 名称。
    - `threshold` (int): 阈值。

- **`barrier_get_threshold(name)`**
  - 获取当前的 barrier 阈值。
  - 参数：
    - `name` (str): barrier 名称。
  - 返回：
    - `int`: 阈值。

- **`barrier_get_num_waiters(name)`**
  - 获取当前在 barrier 上等待的进程数。
  - 参数：
    - `name` (str): barrier 名称。
  - 返回：
    - `int`: 等待者数量。

- **`barrier_wait(name)`**
  - 在 barrier 上等待（阻塞直到阈值满足）。
  - 参数：
    - `name` (str): barrier 名称。

- **`barrier_reset(name, wakeup=0)`**
  - 重置 barrier 的等待计数。
  - 参数：
    - `name` (str): barrier 名称。
    - `wakeup` (int): 是否唤醒等待者。

### 7. 池 / 事件池管理

- **`pool_add(name, key, value)`**
  - 向池中添加键值对。
  - 参数：
    - `name` (str): 池名称。
    - `key` (str): 键名。
    - `value` (str): 值。

- **`pool_get(name, key)`**
  - 从池中获取指定键的值。
  - 参数：
    - `name` (str): 池名称。
    - `key` (str): 键名。
  - 返回：
    - `str`: 值。

- **`pool_remove(name, key)`**
  - 从池中移除指定键。
  - 参数：
    - `name` (str): 池名称。
    - `key` (str): 键名。

- **`pool_num(name)`**
  - 获取池中键的总数。
  - 参数：
    - `name` (str): 池名称。
  - 返回：
    - `int`: 键数。

- **`pool_keys(name)`**
  - 获取池中所有键的字符串表示。
  - 参数：
    - `name` (str): 池名称。
  - 返回：
    - `str`: 以逗号分隔的键列表。

- **`pool_delete(name)`**
  - 删除整个池。
  - 参数：
    - `name` (str): 池名称。

- **`pool_exists(name, key)`**
  - 检查池中是否存在指定键。
  - 参数：
    - `name` (str): 池名称。
    - `key` (str): 键名。
  - 返回：
    - `bool`: 是否存在。

### 8. 配置数据库

- **`set_config_int(contxt, inst_name, field_name, value)`**
  - 设置整型配置。
  - 参数：
    - `contxt` (str): 上下文。
    - `inst_name` (str): 实例名称。
    - `field_name` (str): 字段名称。
    - `value` (uint64_t): 值。

- **`get_config_int(contxt, inst_name, field_name)`**
  - 获取整型配置。
  - 参数：
    - `contxt` (str): 上下文。
    - `inst_name` (str): 实例名称。
    - `field_name` (str): 字段名称。

- **`set_config_string(contxt, inst_name, field_name, value)`**
  - 设置字符串配置。
  - 参数：
    - `contxt` (str): 上下文。
    - `inst_name` (str): 实例名称。
    - `field_name` (str): 字段名称。
    - `value` (str): 值。

- **`get_config_string(contxt, inst_name, field_name)`**
  - 获取字符串配置。
  - 参数：
    - `contxt` (str): 上下文。
    - `inst_name` (str): 实例名称。
    - `field_name` (str): 字段名称。

- **`set_config_real(contxt, inst_name, field_name, value)`**
  - 设置浮点型配置项。
  - 参数：
    - `contxt` (str): 上下文。
    - `inst_name` (str): 实例名。
    - `field_name` (str): 字段名。
    - `value` (double): 浮点值。

- **`get_config_real(contxt, inst_name, field_name)`**
  - 获取浮点型配置项。
  - 参数：
    - `contxt` (str): 上下文。
    - `inst_name` (str): 实例名。
    - `field_name` (str): 字段名。
  - 返回：
    - `double`: 浮点值。

- **`config_db_exists(contxt, inst_name, field_name)`**
  - 检查 config_db 中是否存在指定的配置项。
  - 参数：
    - `contxt` (str): 上下文。
    - `inst_name` (str): 实例名。
    - `field_name` (str): 字段名。
  - 返回：
    - `bool`: 是否存在。

- **`config_db_trace_on()`**
  - 开启 config_db 的访问追踪（用于调试）。

- **`config_db_trace_off()`**
  - 关闭 config_db 的访问追踪。

### 9. 寄存器访问

- **`write_reg(name, data)`**
  - 写寄存器。
  - 参数：
    - `name` (str): 寄存器名称。
    - `data` (int): 数据。

- **`read_reg(name)`**
  - 读寄存器。
  - 参数：
    - `name` (str): 寄存器名称。

- **`check_reg(name, data=0, predict=0)`**
  - 检查寄存器。
  - 参数：
    - `name` (str): 寄存器名称。
    - `data` (int): 数据，默认为 0。
    - `predict` (int): 是否预测，默认为 0。

- **`set_top_reg_block_by_path(block_path)`**
  - 设置作为顶层访问入口的寄存器块组件。
  - 参数：
    - `block_path` (str): 寄存器块组件的层次路径。

- **`get_reg_names(block_path="")`**
  - 获取指定寄存器块内所有寄存器的名称列表（逗号分隔）。
  - 参数：
    - `block_path` (str): 寄存器块路径，默认为顶层块。
  - 返回：
    - `str`: 逗号分隔的寄存器名称。

- **`get_block_names(block_path="")`**
  - 获取指定块内的子寄存器块名称列表。
  - 参数：
    - `block_path` (str): 寄存器块路径。
  - 返回：
    - `str`: 逗号分隔的子块名称。

- **`get_reg_mirrored_value(reg_name)`**
  - 获取寄存器的镜像值（期望的硬件值）。
  - 参数：
    - `reg_name` (str): 寄存器名称。
  - 返回：
    - `int`: 镜像值。

- **`get_reg_desired_value(reg_name)`**
  - 获取寄存器的 desired 值（下次要写入的值）。
  - 参数：
    - `reg_name` (str): 寄存器名称。
  - 返回：
    - `int`: desired 值。

- **`get_reg_address(reg_name)`**
  - 获取寄存器的总线地址。
  - 参数：
    - `reg_name` (str): 寄存器名称。
  - 返回：
    - `int`: 地址。

- **`reset_reg(reg_name, kind="SOFT")`**
  - 重置寄存器到其复位值。
  - 参数：
    - `reg_name` (str): 寄存器名称。
    - `kind` (str): 复位类型，"SOFT" 或 "HARD"。

- **`predict_reg(reg_name, value)`**
  - 预测寄存器的值（不进行总线访问）。
  - 参数：
    - `reg_name` (str): 寄存器名称。
    - `value` (int): 预测值。
  - 返回：
    - `bool`: 预测操作是否成功。

- **`get_reg_field_names(reg_name)`**
  - 获取指定寄存器的字段名称列表（逗号分隔）。
  - 参数：
    - `reg_name` (str): 寄存器名称。
  - 返回：
    - `str`: 逗号分隔的字段名称。

- **`read_field_by_name(reg_name, field_name)`**
  - 读取指定字段的值。
  - 参数：
    - `reg_name` (str): 寄存器名称。
    - `field_name` (str): 字段名称。
  - 返回：
    - `int`: 字段值。

- **`write_field_by_name(reg_name, field_name, value)`**
  - 写入指定字段的值。
  - 参数：
    - `reg_name` (str): 寄存器名称。
    - `field_name` (str): 字段名称。
    - `value` (int): 字段值。

- **`reg_block_sprint(block_path)`**
  - 生成整个寄存器块的字符串表示。
  - 参数：
    - `block_path` (str): 寄存器块组件路径。
  - 返回：
    - `str`: 寄存器块信息字符串。

### 10. 序列器与序列控制

- **`start_seq(seq_name, sqr_name, rand_en=1, background=0)`**
  - 启动序列。
  - 参数：
    - `seq_name` (str): 序列名称。
    - `sqr_name` (str): 序列器名称。
    - `rand_en` (svBit): 是否随机化，默认为 1。
    - `background` (svBit): 是否后台运行，默认为 0。

- **`stop_sequences(sqr_name)`**
  - 停止指定序列器上当前正在运行的所有序列。
  - 参数：
    - `sqr_name` (str): 序列器路径。

- **`is_sequencer_busy(sqr_name)`**
  - 查询序列器上是否有活动的序列。
  - 参数：
    - `sqr_name` (str): 序列器路径。
  - 返回：
    - `bool`: 是否忙。

- **`get_current_sequence_name(sqr_name)`**
  - 获取正在序列器上运行的当前序列名称。
  - 参数：
    - `sqr_name` (str): 序列器路径。
  - 返回：
    - `str`: 当前序列名称。

### 11. 测试运行

- **`run_test(test_name='')`**
  - 运行测试。
  - 参数：
    - `test_name` (str): 测试名称，默认为空字符串。

- **`wait_unit(n)`**
  - 等待指定时间单位。
  - 参数：
    - `n` (int): 时间单位。

### 12. 仿真控制

- **`reset()`**
  - 重置仿真。

- **`stop()`**
  - 暂停仿真。

- **`finish()`**
  - 结束仿真。

- **`get_sim_time(name)`**
  - 获取当前仿真时间。
  - 参数：
    - `name` (str): 作用域名称。

- **`get_time_unit(name)`**
  - 获取时间单位。
  - 参数：
    - `name` (str): 作用域名称。

- **`get_time_precision(name)`**
  - 获取时间精度。
  - 参数：
    - `name` (str): 作用域名称。

### 13. 报告系统

- **`uvm_info(message, verbosity=UVM_LOW)`**
  - UVM_INFO 报告函数。
  - 参数：
    - message (str): 要报告的消息。
    - verbosity (int): 报告的详细程度级别，默认为 UVM_LOW。

- **`uvm_warning(message, verbosity=UVM_NONE)`**
  - UVM_WARNING 报告函数。
  - 参数：
    - message (str): 要报告的消息。
    - verbosity (int): 报告的详细程度级别，默认为 UVM_NONE。

- **`uvm_error(message, verbosity=UVM_NONE)`**
  - UVM_ERROR 报告函数。
  - 参数：
    - message (str): 要报告的消息。
    - verbosity (int): 报告的详细程度级别，默认为 UVM_NONE。

- **`uvm_fatal(message, verbosity=UVM_NONE)`**
  - UVM_FATAL 报告函数。
  - 参数：
    - message (str): 要报告的消息。
    - verbosity (int): 报告的详细程度级别，默认为 UVM_NONE。

- **`get_report_verbosity_level(contxt, severity, id="")`**
  - 获取特定上下文和消息ID的详细程度级别。
  - 参数：
    - contxt (str): UVM组件上下文路径。
    - severity (int): UVM严重性级别。
    - id (str): 消息标识符，默认为空字符串。

- **`get_report_max_verbosity_level(contxt)`**
  - 获取上下文的最大允许详细程度级别。
  - 参数：
    - contxt (str): UVM组件上下文路径。

- **`set_report_verbosity_level(contxt, level)`**
  - 设置组件层次结构的默认详细程度级别。
  - 参数：
    - contxt (str): UVM组件上下文路径。
    - level (int): 要设置的详细程度级别。

- **`set_report_id_verbosity(contxt, id, verbosity)`**
  - 配置特定消息ID的详细程度。
  - 参数：
    - contxt (str): UVM组件上下文路径。
    - id (str): 要配置的目标消息ID。
    - verbosity (int): 要应用的详细程度级别。

- **`set_report_severity_id_verbosity(contxt, severity, id, verbosity)`**
  - 配置特定严重性、ID或严重性-ID对的详细程度。
  - 参数：
    - contxt (str): UVM组件上下文路径。
    - severity (int): 要检查的UVM严重性级别。
    - id (str): 目标消息ID。
    - verbosity (int): 要应用的详细程度级别。

- **`get_report_action(contxt, severity, id="")`**
  - 获取当前报告动作配置。
  - 参数：
    - contxt (str): UVM组件上下文路径。
    - severity (int): 要检查的UVM严重性级别。
    - id (str): 消息标识符，默认为空字符串。

- **`set_report_severity_action(contxt, severity, action)`**
  - 配置特定严重性级别的报告动作。
  - 参数：
    - contxt (str): UVM组件上下文路径。
    - severity (int): 要配置的目标严重性级别。
    - action (int): 动作位掩码。

- **`set_report_id_action(contxt, id, action)`**
  - 配置特定消息ID的报告动作。
  - 参数：
    - contxt (str): UVM组件上下文路径。
    - id (str): 消息标识符，默认为空字符串。
    - action (int): 动作位掩码。

- **`set_report_severity_id_action(contxt, severity, id, action)`**
  - 配置特定严重性、ID或严重性-ID对的报告动作。
  - 参数：
    - contxt (str): UVM组件上下文路径。
    - severity (int): 要配置的目标严重性级别。
    - id (str): 目标消息ID。
    - action (int): 动作位掩码。

- **`set_report_severity_override(contxt, original_severity, new_severity)`**
  - 重写报告消息的严重性级别。
  - 参数：
    - contxt (str): UVM组件上下文路径。
    - original_severity (int): 要重写的原始严重性级别。
    - new_severity (int): 要应用的新严重性级别。

- **`set_report_severity_id_override(contxt, original_severity, id, new_severity)`**
  - 重写特定消息ID的严重性级别。
  - 参数：
    - contxt (str): UVM组件上下文路径。
    - original_severity (int): 要重写的原始严重性级别。
    - id (str): 目标消息ID。
    - new_severity (int): 要应用的新严重性级别。

- **`set_max_quit_count(count, overridable=True)`**
  - 设置报告服务器的最大退出计数。
  - 参数：
    - count (int): 最大退出计数。
    - overridable (bool): 是否可以被覆盖，默认为True。

- **`get_max_quit_count()`**
  - 从报告服务器获取最大退出计数。
  - 返回：
    - int: 最大退出计数设置。

- **`set_quit_count(quit_count)`**
  - 设置报告服务器的当前退出计数。
  - 参数：
    - quit_count (int): 新的退出计数值。

- **`get_quit_count()`**
  - 从报告服务器获取当前退出计数。
  - 返回：
    - int: 当前退出计数值。

- **`set_severity_count(severity, count)`**
  - 设置特定严重性级别的计数。
  - 参数：
    - severity (int): 要设置的严重性级别（使用UVM严重性常量）。
    - count (int): 要设置的计数值。

- **`get_severity_count(severity)`**
  - 获取特定严重性级别的计数。
  - 参数：
    - severity (int): 要查询的严重性级别（使用UVM严重性常量）。
  - 返回：
    - int: 指定严重性的当前计数值。

- **`set_id_count(id, count)`**
  - 设置特定消息ID的计数。
  - 参数：
    - id (str): 要设置的消息ID。
    - count (int): 要设置的计数值。

- **`get_id_count(id)`**
  - 获取特定消息ID的计数。
  - 参数：
    - id (str): 要查询的消息ID。
  - 返回：
    - int: 指定消息ID的当前计数值。

- **`print_report_server()`**
  - 以人类可读格式打印当前报告服务器信息。
  - 返回：
    - 详细的报告服务器状态，包括严重性级别、ID计数和其他指标。

- **`report_summarize()`**
  - 生成所有报告的摘要。
  - 返回：
    - 包括每个严重性级别的总计数和其他相关指标的简洁摘要。

### 14. HDL 信号访问

- **`uvm_hdl_check_path(path)`**
  - 检查 HDL 信号路径是否存在。
  - 参数：
    - path (str): HDL 信号路径。
  - 返回：
    - bool: 是否存在。

- **`uvm_hdl_deposit(path, value)`**
  - 向 HDL 信号写入值（非强制，不保持）。
  - 参数：
    - path (str): HDL 信号路径。
    - value (VpiVecVal): 要写入的值。

- **`uvm_hdl_force(path, value)`**
  - 强制 HDL 信号为指定值（保持直到 release）。
  - 参数：
    - path (str): HDL 信号路径。
    - value (VpiVecVal): 要强制的值。

- **`uvm_hdl_release(path)`**
  - 释放被 force 的 HDL 信号。
  - 参数：
    - path (str): HDL 信号路径。

- **`uvm_hdl_read(path, value_obj)`**
  - 读取 HDL 信号的当前值。
  - 参数：
    - path (str): HDL 信号路径。
    - value_obj (VpiVecVal): 用于存储读取结果的对象。
  - 返回：
    - int: 操作是否成功。

- **`uvm_hdl_release_and_read(path, value_obj)`**
  - 先 release 再读取信号值。
  - 参数：
    - path (str): HDL 信号路径。
    - value_obj (VpiVecVal): 用于存储读取结果的对象。
  - 返回：
    - int: 操作是否成功。

### 15. 回调查询

- **`get_callback_count(comp_path, cb_type_name="")`**
  - 获取注册在组件上的回调数量。
  - 参数：
    - comp_path (str): 组件路径。
    - cb_type_name (str): 回调类型名称（可选，为空则查询所有类型）。
  - 返回：
    - int: 回调数量。

- **`get_callback_type_names(comp_path)`**
  - 获取组件上已注册的回调类型名称列表（逗号分隔）。
  - 参数：
    - comp_path (str): 组件路径。
  - 返回：
    - str: 逗号分隔的回调类型名称。

### 16. 打印机与比较器旋钮控制

- **`set_default_printer_knob(knob_name, value)`**
  - 设置默认打印机的旋钮参数。
  - 参数：
    - knob_name (str): 旋钮名称（`indent`、`show_root`、`header`、`footer`、`depth`、`reference`、`type_name`、`size`）。
    - value (int): 新的旋钮值。

- **`get_default_printer_knob(knob_name)`**
  - 获取默认打印机的旋钮参数值。
  - 参数：
    - knob_name (str): 旋钮名称。
  - 返回：
    - int: 当前旋钮值。

- **`set_default_comparer_knob(knob_name, value)`**
  - 设置默认比较器的旋钮参数。
  - 参数：
    - knob_name (str): 旋钮名称（`show_max`、`verbosity` 等）。
    - value (int): 新的旋钮值。

- **`get_default_comparer_knob(knob_name)`**
  - 获取默认比较器的旋钮参数值。
  - 参数：
    - knob_name (str): 旋钮名称。
  - 返回：
    - int: 当前旋钮值。

### 17. 进程池

- **`process_pool_run(func_ref)`**
  - 调度并执行指定的 Python 函数。
  - 参数：
    - func_ref (str): 函数引用，格式为 `module.function`。

- **`process_pool_clear()`**
  - 清空进程池中所有已调度的任务。

### 18. VPI 子模块 (svuvm.vpi.*)

- **`vpi_printf(format, ...)`**
  - 通过 VPI 打印到仿真输出。

- **`vpi_mcd_open(filename)`**
  - 打开文件以进行多通道输出。
  - 返回：
    - int: 文件句柄。

- **`vpi_mcd_printf(mcd, format, ...)`**
  - 写入格式化内容到已打开的文件。

- **`vpi_mcd_flush(mcd)`**
  - 刷新文件输出缓冲。

- **`vpi_mcd_close(mcd)`**
  - 关闭已打开的文件。

- **`vpi_handle_by_name(name)`**
  - 通过层次名称获取 VPI 句柄。
  - 返回：
    - int: VPI 句柄。

- **`vpi_get(property, handle)`**
  - 获取句柄的整数属性。
  - 返回：
    - int: 属性值。

- **`vpi_get_str(property, handle)`**
  - 获取句柄的字符串属性。
  - 返回：
    - str: 属性值。

- **`vpi_get_time(handle, time_obj)`**
  - 获取仿真时间。

- **`vpi_register_cb(cb_data_obj)`**
  - 注册 VPI 回调。

### VPI 数据类型

- **`VpiVecVal(aval, bval)`**
  - 向量值（A/B bit 表示）。

- **`VpiTime(type, high, low, real)`**
  - 时间值容器。

- **`VpiValue(type, value)`**
  - 通用值容器。

- **`VpiErrorInfo`**
  - 错误信息容器。

- **`VpiVlogInfo(argc, argv, product, version)`**
  - Verilog 信息容器。

- **`CbData(reason, cb_rtn, obj, time, value, index, file)`**
  - 回调数据容器。

## 常量参考

### 报告严重性常量

- `svuvm.UVM_INFO` - 信息性消息
- `svuvm.UVM_WARNING` - 警告消息
- `svuvm.UVM_ERROR` - 错误消息
- `svuvm.UVM_FATAL` - 致命消息

### Verbosity 级别常量

- `svuvm.UVM_NONE` (0) - 始终打印
- `svuvm.UVM_LOW` (100) - 低详细度
- `svuvm.UVM_MEDIUM` (200) - 中等详细度
- `svuvm.UVM_HIGH` (300) - 高详细度
- `svuvm.UVM_FULL` (400) - 完全详细度
- `svuvm.UVM_DEBUG` (500) - 调试级详细度

### Action 常量

- `svuvm.UVM_NO_ACTION` (0x0000) - 无操作
- `svuvm.UVM_DISPLAY` (0x0001) - 显示
- `svuvm.UVM_LOG` (0x0002) - 记录日志
- `svuvm.UVM_COUNT` (0x0004) - 计数
- `svuvm.UVM_STOP` (0x0008) - 停止
- `svuvm.UVM_EXIT` (0x0010) - 退出
- `svuvm.UVM_CALL_HOOK` (0x0020) - 调用钩子
- `svuvm.UVM_RM_RECORD` (0x0040) - 记录