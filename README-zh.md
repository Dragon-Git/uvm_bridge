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
- Python 3.8.0+
- pybind11, pyslang (运行时不需要)
### 命令：
- verilator
```sh
pip install .
```
- vcs  
```sh
CFLAGS="-DVCS -I $VCS_HOME/include" pip install .
```
- xcelium
```sh
CFLAGS="-DXCELIUM -I $XRUN_HOME/include" pip install .                                                                            
```
- questa
```sh
CFLAGS="-DMENTOR -I $MENTOR_HOME/include" pip install .                                                             
```

## 编译

需要在编译命令中添加` $(python -m svuvm.config)`

## 快速参考
- Write register: `svuvm.write_reg("rm.reg_a", 0x12345678)`
- Read register: `data = svuvm.read_reg("rm.reg_a")`
- Check register: `svuvm.check_reg("rm.reg_a", 0x12345678)`
- Start sequence: `svuvm.start_seq("my_seq", "uvm_test_top.m_env.m_agent.my_sqr")`
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
    svuvm.uvm_info("example_test",svuvm.UVM_LOW)

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

### 2. 根节点管理

- **`set_timeout(timeout, overridable=1)`**
  - 设置超时值。
  - 参数：
    - `timeout` (long long): 超时时间。
    - `overridable` (unsigned char): 是否可覆盖，默认为 1。

- **`print_topology(context='')`**
  - 打印拓扑结构。
  - 参数：
    - `context` (str): 上下文，默认为空字符串。

- **`uvm_objection_op(op, name, contxt, description, count)`**
  - 操作异议。
  - 参数：
    - `op` (str): 操作类型（如 "RAISE" 或 "DROP"）。
    - `name` (str): 名称。
    - `contxt` (str): 上下文。
    - `description` (str): 描述。
    - `count` (unsigned int): 计数。

- **`dbg_print(name='')`**
  - 打印对象。
  - 参数：
    - `name` (str): 对象名称，默认为空字符串。

### 3. 事件管理

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

### 4. 配置数据库

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

### 5. 寄存器访问

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

### 6. 测试运行

- **`start_seq(seq_name, sqr_name, rand_en=1, background=0)`**
  - 启动序列。
  - 参数：
    - `seq_name` (str): 序列名称。
    - `sqr_name` (str): 序列器名称。
    - `rand_en` (svBit): 是否随机化，默认为 1。
    - `background` (svBit): 是否后台运行，默认为 0。

- **`run_test(test_name='')`**
  - 运行测试。
  - 参数：
    - `test_name` (str): 测试名称，默认为空字符串。

- **`wait_unit(n)`**
  - 等待指定时间单位。
  - 参数：
    - `n` (int): 时间单位。

### 7. 仿真控制

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

- **`get_timeunit(name)`**
  - 获取时间单位。
  - 参数：
    - `name` (str): 作用域名称。

- **`get_precision(name)`**
  - 获取时间精度。
  - 参数：
    - `name` (str): 作用域名称。

### 8. 报告系统

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
