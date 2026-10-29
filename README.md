# InoProShop MCP

中文 · [English](README.en.md)

通过 MCP 调用 InoProShop 的公开 ScriptEngine，创建和编辑工程、读写 ST、执行原生编译、保存和导出软件控制器启动包。

## 安装

需要 Windows、Node.js ≥ 18 和带有 ScriptEngine 的兼容 InoProShop。工程接口基线为 InoProShop 1.9.1.6 / SP11；设备描述和运动组件按本机安装版本配置。Python 工作脚本由 IDE 自带的脚本环境执行。

```powershell
git clone https://github.com/Polarzin/Inoproshop-MCP.git
cd Inoproshop-MCP
npm.cmd ci --ignore-scripts
```

将以下配置加入支持 stdio MCP 的客户端，并替换为本机绝对路径：

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

先通过 `tree` 获取实际对象路径；上述程序路径适用于包含该程序的控制器工程。`batch` 可用操作包括：

- 程序与结构：`tree`、`list`、`read`、`read_lines`、`patch`、`write`、`create`。
- 工程：`compile`、`save`、`generate_code`、`export_boot`。
- 设备：`device`、`device_parameters`、`device_parameter_write`、`device_add`、`repository_devices`。
- 任务与库：`task`、`task_configure`、`libraries`、`library_add`。
- 符号：`symbols_create`、`symbols`、`symbol_access`、`verify_symbols`。

`write` 使用 `path`、`declaration` 和 `implementation`。修改任务、设备参数或符号前，先读取对应版本/权限信息，并传回操作要求的校验字段。各操作参数定义见 [worker_api.py](worker_api.py)。

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

## 展示页

[静态展示页源码](docs/site/index.html)使用现有飞剪录制素材，默认中文，支持英文切换。页面仅展示工具和使用步骤，不连接 PLC。

本地预览可在仓库根目录运行以下命令（需要 Python 3）：

```powershell
python -m http.server 8841 --bind 127.0.0.1
```

打开 [本地展示页](http://127.0.0.1:8841/docs/site/index.html)。

## 许可

个人独立开发，自有工具代码与合成 ST 采用 [MIT](LICENSE)。第三方依赖和互操作说明见 [NOTICE](NOTICE.md)。
