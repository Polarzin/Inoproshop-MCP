# InoProShop MCP

中文 · [English](README.en.md)

通过 MCP 调用 InoProShop 的公开 ScriptEngine，创建和编辑工程、读写 ST、执行原生编译、保存和导出软件控制器启动包。

## 支持的工程操作

一个面向 PLC 工程操作的小工具，附三轴飞剪示例。

| 工作 | 支持的操作 |
|---|---|
| 创建与编辑 | 创建空工程容器、读写 ST、管理 POU/Method/Property/DUT 与工程文件夹 |
| 编译与保存 | 调用原生编译器、获取诊断信息、保存工程 |
| 配置与导出 | 配置设备、任务、库与符号，导出软件控制器启动包 |

## 示例：三轴飞剪

从用户准备的空白软件控制器模板开始，MCP 添加三根虚拟轴、写入飞剪 ST，配置 10 ms 任务与 48 个接口字段，再执行原生编译。工程由用户按官方流程部署到软件 PLC。

![三轴飞剪示例：软件 PLC 运行反馈录制](https://raw.githubusercontent.com/Polarzin/Inoproshop-MCP/main/docs/assets/flying-shear.gif)

动图是软件 PLC 运行反馈的 3D 可视化录制；仓库提供工程构建工具和 ST 示例，不包含录制用的 3D 界面。构建方法见下方说明。

前期工程工具已在自有硬件平台上验证过工程读写、编译与下载操作。当前公开工具提供离线工程操作；三轴飞剪示例在软件 PLC 上验证。

## 安装

需要 Windows、Node.js ≥ 18 和带有 ScriptEngine 的兼容 InoProShop。工程接口基线为 InoProShop 1.9.1.6 / SP11；设备描述和运动组件按本机安装版本配置。Python 工作脚本由 IDE 自带的脚本环境执行。

### 1. 获取工具（推荐 Git clone）

```powershell
git clone https://github.com/Polarzin/Inoproshop-MCP.git
cd Inoproshop-MCP
```

没有安装 Git 时，也可[下载工具 ZIP](https://github.com/Polarzin/Inoproshop-MCP/archive/refs/heads/main.zip)。解压后，在包含 `package.json` 和 `server.mjs` 的目录打开 PowerShell。ZIP 包含工具、必要 ST 示例和使用说明，排除 README 展示动图。

### 2. 安装依赖

在工具目录运行：

```powershell
npm.cmd ci --ignore-scripts
```

依赖安装完成即可配置使用，无需构建，也无需单独安装 Python。以后通过 `git pull` 更新工具后，再运行一次上述命令同步依赖。

### 3. 配置 MCP 客户端

在客户端的 MCP 设置中添加一个 stdio 服务。支持 `mcpServers` JSON 格式的客户端可合并以下配置；使用表单或其他配置格式时，填写对应的命令、参数和环境变量。

```json
{
  "mcpServers": {
    "inoproshop": {
      "command": "node",
      "args": ["C:/path/to/Inoproshop-MCP/server.mjs"],
      "env": {
        "INOPROSHOP_EXE": "C:/path/to/InoProShop.exe",
        "INOPROSHOP_PROFILE": "InoProShop(V1.9.1.6)"
      }
    }
  }
}
```

- `command`：Node.js 启动命令。客户端找不到 `node` 时，填入 `node.exe` 的绝对路径，可在 PowerShell 中运行 `(Get-Command node).Source` 查询。
- `args`：将示例路径替换为下载目录内 `server.mjs` 的绝对路径。
- `INOPROSHOP_EXE`：本机 `InoProShop.exe` 的绝对路径。
- `INOPROSHOP_PROFILE`：本机实际安装的 IDE profile 名称；示例对应 1.9.1.6，可在 IDE 启动快捷方式的 `--profile` 参数中核对。

JSON 中的 Windows 路径建议使用 `/`，如上例；使用反斜杠时需写成 `\\`。

### 4. 启用并确认连接

保存配置后，在客户端启用或重新连接该 MCP 服务；必要时重启客户端。工具列表中出现 `codesys_engineering` 即表示 MCP 已连接，后续按下方示例调用。服务由客户端自动启动，无需另外运行 `npm start`。连接成功只表示 MCP 可用；IDE 路径、profile 和工程兼容性会在实际工程调用时检查。

普通模式使用前关闭其他 IDE。需要与已有 IDE 并存时，在工具参数中显式设置 `isolated=true`。构建可能需要数分钟，客户端调用超时应至少为 660 秒。

## 工具：`codesys_engineering`

| `action` | 用途 |
|---|---|
| `create_empty` | 创建空 `.project` 容器，尚无控制器 |
| `batch` | 对已有工程执行有限的读取、编辑、编译、保存和导出操作 |
| `build_c6` | 从用户准备的空白软件控制器模板构建三轴飞剪工程 |

创建空工程，输出路径必须不存在：

```json
{
  "action": "create_empty",
  "isolated": true,
  "project": "C:/projects/example.project"
}
```

读取工程树与程序：

```json
{
  "action": "batch",
  "isolated": true,
  "project": "C:/projects/example.project",
  "steps": [
    {"op": "tree", "args": {}},
    {"op": "read", "args": {"path": "Application/PLC_PRG"}}
  ]
}
```

先通过 `tree` 获取实际对象路径。路径使用 `/` 分隔并精确匹配；`Application/...` 简写仅在 Application 唯一时可用。不支持点分隔路径或递归同名回退。`read`、`create`、`write` 返回完整对象路径，后续调用可直接复用。`batch` 可用操作包括：

- 程序与结构：`tree`、`list`、`read`、`read_lines`、`patch`、`write`、`create`、`rename`、`move`、`delete`。
- 工程：`compile`、`save`、`generate_code`、`export_boot`。
- 设备：`device`、`device_parameters`、`device_parameter_write`、`device_add`、`repository_devices`。
- 任务与库：`task`、`task_configure`、`libraries`、`library_add`。
- 符号：`symbols_create`、`symbols`、`symbol_access`、`verify_symbols`。

`write` 使用 `path`、`declaration` 和 `implementation`。修改任务、设备参数或符号前，先读取对应版本/权限信息，并传回操作要求的校验字段。各操作参数定义见 [worker_api.py](worker_api.py)。

### 对象创建与整理

`create` 使用 `parent`、`name`、`kind`；`parent` 为空字符串时表示工程根节点。

| `kind` | 对象与可选参数 |
|---|---|
| `pou` / `program` / `function` | 功能块 / 程序 / 函数；函数可指定 `return_type`，默认 `INT` |
| `method` | 方法；可指定 `return_type`，省略表示无返回值 |
| `property` | 属性及 Get/Set；`return_type` 默认 `INT` |
| `dut` | 数据类型；`dut_type` 为 `structure`（默认）、`enumeration`、`alias` 或 `union`；别名类型需 `base_type` |
| `folder` | 工程文件夹 |
| `action` / `gvl` / `task` | 动作 / 全局变量列表 / 任务 |

例如，在已有 Application 中创建功能块、方法和属性，读取属性的 Get/Set 路径：

```json
{
  "action": "batch",
  "isolated": true,
  "project": "C:/projects/example.project",
  "steps": [
    {"op": "create", "args": {"parent": "Application", "name": "SampleFB", "kind": "pou"}},
    {"op": "create", "args": {"parent": "Application/SampleFB", "name": "Reset", "kind": "method"}},
    {"op": "create", "args": {"parent": "Application/SampleFB", "name": "Value", "kind": "property", "return_type": "INT"}},
    {"op": "read", "args": {"path": "Application/SampleFB/Value"}}
  ]
}
```

对返回的 `children` 中 Get/Set 路径执行 `write` 或 `patch` 可编辑属性实现；属性节点本身没有 ST 实现段。`write` 只接受对象实际具有的声明/实现段，并返回写后内容。

- 重命名：`rename`，参数 `path`、`name`。
- 移动：`move`，参数 `path`、目标 `parent`。
- 删除：`delete`，参数 `path`；有子对象时需显式传入 `recursive: true`，结果列出删除的路径和 GUID。

创建或整理对象时会检查目标重名、移动环路和写后结果。重命名、移动后请编译检查程序引用；接口不承诺自动重构所有 ST 引用。工具仅提供固定操作，不提供任意 IronPython 脚本执行入口。

## 可选：构建飞剪示例

通过官方 IDE 或公开 ScriptEngine 准备空白软件控制器模板，包含 `Device`、一个 `Application`、`MainTask`、`SoftMotion General Axis Pool` 和空 `PLC_PRG`，关闭 IDE Simulation 模式。不预置示例轴或飞剪程序。

构建器要求 SoftMotion Win 软件目标 `4102 / 0000 0001`；已有基线版本为 `3.5.11.10`。虚拟轴描述必须与本机安装匹配，可先通过 `repository_devices` 查询。调用示例：

```json
{
  "action": "build_c6",
  "isolated": true,
  "template": "C:/templates/blank-softmotion.project",
  "project": "C:/projects/flying-shear.project",
  "axis": {"type": 1024, "id": "FFFF 0001", "version": "4.0.0.0"}
}
```

工具复制模板到新路径，添加三根虚拟轴、随附 ST、10 ms 任务和 48 个接口字段，执行原生编译与符号检查。源模板保持不变，已有输出不覆盖。`examples/c6/` 中三份原创文件是此操作的运行依赖。

需要导出启动包时，对生成的工程执行 `batch`，步骤为 `{"op":"export_boot","args":{}}`。该操作仅接受软件控制器，输出原生 `Application.app/.crc`。部署与运行通过官方软件流程完成。

## 使用说明

- 工具执行离线工程操作，不登录或下载到 PLC。
- 本地结果和锁保存在 `var/`。失败不自动重发；超时结果未知时先检查 IDE 与 `var/engineering.lock` 所指的结果，确认对应 IDE 已关闭后再处理锁。
- 工程创建与模板构建要求新输出路径；`batch` 会保存对已有工程的修改。
- 厂商软件、设备描述、运动组件、原生工程模板和许可由使用者从官方来源取得。

## 许可

个人独立开发，自有工具代码与合成 ST 采用 [MIT](LICENSE)。第三方依赖和互操作说明见 [NOTICE](NOTICE.md)。

接口依据：[CODESYS ScriptEngine 文档](https://content.helpme-codesys.com/en/ScriptingEngine/index.html)。
