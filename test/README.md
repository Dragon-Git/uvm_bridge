# 测试入口

所有测试统一由 pytest 驱动；三个 RAL 测试（pyral / unicorn / renode）的 Makefile 已删除，
不再有 `make gen` / `make -f ... run` 入口。生成物（peakrdl 模型、RTL、C header、firmware）
由 session 级 `artifacts` fixture 按需生成并按内容哈希缓存。

## 常用命令

```sh
# 全部套件（RAL 默认跑 verilator + xezim 两个后端）
python3 -m pytest -v test/

# 单个 RAL 测试，指定后端；CI 用同样命令逐 suite 执行
SVUVM_BACKENDS=verilator python3 -m pytest -v test/pyral_test -m ral
SVUVM_BACKENDS=xezim python3 -m pytest -v test/unicorn_test -m ral

# CI 严格模式：缺依赖 / 仿真失败一律让 job 变红，不静默 skip
SVUVM_BACKENDS=xezim RAL_STRICT=1 python3 -m pytest -v test/renode_test -m ral
```

- `SVUVM_BACKENDS`：逗号分隔的后端列表，默认 `verilator,xezim`；CI 每个 leg 只选一个。
- `-m ral`：只跑三个寄存器访问测试的 JSON 重放；base/cocotb 不用该 marker。
- `RAL_STRICT=1`：把缺依赖从本地的显式 skip 升级为显式 fail（fixture 中表现为 setup ERROR，退出码 1）。
- `SIM_TIMEOUT`：单次仿真运行的墙钟超时秒数（默认 300）；`--max-time` 只限制仿真时间，callback/DPI 卡住时不会触发，此变量才是防挂死的兜底。
- `SIM_BUILD_TIMEOUT`：单次编译的墙钟超时秒数（默认 `SIM_TIMEOUT` 的 2 倍，即 600），慢编译可自行调大；非法值回退默认并在 stderr 告警。
- RAL 首期串行执行，不要加 `pytest -n`；生成物锁与后端隔离是为以后并行预留的。

## renode 的环境要求

renode 需要 `PYRENODE_PATH`（解压后的 Renode 目录）、pyrenode3 和可用的 .NET runtime，
缺任一项时 conftest 守卫会在本地明确 skip、在 `RAL_STRICT=1` 下明确 fail。
CI 中 renode 的两个 leg 都接在 `xezim-tests.yml`：该 workflow 安装 Renode，并只在代表
cell（Python 3.12 + ubuntu-24.04）额外装 verilator 跑 verilator leg；`test.yml` 的
verilator 矩阵只装 `ral` 组，跑 pyral/unicorn，不拉取 pyrenode3 的 git URL。

若 CI 实测 verilator + Renode 不可行，按设计 §5.4 L1 用 `renode_verilator_unsupported`
marker 显式 skip 并打印诊断，禁止直接删除该 CI 步骤。
