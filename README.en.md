# InoProShop MCP

[中文](README.md) · English

Use MCP to access InoProShop's public ScriptEngine: create and edit projects, read and write Structured Text, run native builds, save projects, and export software-controller boot applications.

## Engineering operations

A small tool for PLC project work, with a three-axis flying shear example.

| Task | Supported operations |
|---|---|
| Create and edit | Create empty projects, read/write ST, and manage POUs, methods, properties, DUTs, and project folders |
| Build and save | Run the native compiler, collect diagnostics, and save projects |
| Configure and export | Configure devices, tasks, libraries, and symbols; export software-controller boot applications |

## Example: three-axis flying shear

Starting from a user-prepared blank software-controller template, MCP adds three virtual axes, writes the flying shear ST, configures a 10 ms task and 48 interface fields, and runs the native compiler. The user deploys the project to a software PLC through the official workflow.

![Three-axis flying shear: recorded software PLC feedback](https://raw.githubusercontent.com/Polarzin/Inoproshop-MCP/main/docs/assets/flying-shear.gif)

The GIF records a 3D visualization of software PLC feedback. This repository provides the engineering tool and ST example; the 3D interface used for the recording is not included. Build instructions follow below.

Earlier engineering tools were used to verify project reading/writing, compilation, and downloading on our own hardware platform. The current public tool provides offline engineering operations; the flying shear example was verified on a software PLC.

## Installation

Requires Windows, Node.js ≥ 18, and a compatible InoProShop installation with ScriptEngine support. The engineering baseline is InoProShop 1.9.1.6 / SP11; configure device descriptions and motion components for your installed version. Python worker scripts run in the IDE's own scripting environment.

### 1. Get the tool (Git clone recommended)

```powershell
git clone https://github.com/Polarzin/Inoproshop-MCP.git
cd Inoproshop-MCP
```

If Git is not installed, [download the tool ZIP](https://github.com/Polarzin/Inoproshop-MCP/archive/refs/heads/main.zip) instead. Extract it and open PowerShell in the directory containing `package.json` and `server.mjs`. The ZIP contains the tool, required ST example files, and usage instructions; the README demonstration GIF is excluded.

### 2. Install dependencies

Run this in the tool directory:

```powershell
npm.cmd ci --ignore-scripts
```

Once dependencies are installed, the tool is ready to configure. No build step or separate Python installation is required. After updating with `git pull`, run the command above again to synchronize dependencies.

### 3. Configure your MCP client

Add a stdio service in your client's MCP settings. For clients that support the `mcpServers` JSON format, merge the configuration below. For a settings form or another configuration format, enter the corresponding command, arguments, and environment variables.

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

- `command`: the Node.js command. If the client cannot find `node`, use the absolute path to `node.exe`; run `(Get-Command node).Source` in PowerShell to find it.
- `args`: replace the example with the absolute path to `server.mjs` in your downloaded directory.
- `INOPROSHOP_EXE`: the absolute path to your installed `InoProShop.exe`.
- `INOPROSHOP_PROFILE`: the IDE profile name for your installation. The example uses 1.9.1.6; check the `--profile` argument in your IDE launch shortcut.

Use `/` in Windows paths within JSON, as above, or escape each backslash as `\\`.

### 4. Enable and check the connection

Save the configuration, then enable or reconnect the MCP service in your client; restart the client if needed. The appearance of `codesys_engineering` in the tool list confirms the MCP connection. Use the examples below for calls. The client starts the service automatically, so there is no need to run `npm start` separately. A successful connection confirms MCP availability; IDE paths, profiles, and project compatibility are checked during actual engineering calls.

Close other IDE instances before normal-mode use. To coexist with an existing IDE, explicitly pass `isolated=true` in the tool arguments. Builds may take several minutes; set the client call timeout to at least 660 seconds.

## Tool: `codesys_engineering`

| `action` | Purpose |
|---|---|
| `create_empty` | Create an empty `.project` container without a controller |
| `batch` | Perform bounded read, edit, build, save, and export operations on an existing project |
| `build_c6` | Build a three-axis flying shear project from a user-prepared blank software-controller template |

Create an empty project at a nonexistent output path:

```json
{
  "action": "create_empty",
  "isolated": true,
  "project": "C:/projects/example.project"
}
```

Read the project tree and a program:

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

Use `tree` to discover actual object paths first. Paths use `/` separators and exact matching; the `Application/...` shorthand is accepted only when the Application is unique. Dot-separated paths and recursive same-name fallback are not supported. `read`, `create`, and `write` return full object paths for subsequent calls. Supported `batch` operations:

- Programs and structure: `tree`, `list`, `read`, `read_lines`, `patch`, `write`, `create`, `rename`, `move`, `delete`.
- Engineering: `compile`, `save`, `generate_code`, `export_boot`.
- Devices: `device`, `device_parameters`, `device_parameter_write`, `device_add`, `repository_devices`.
- Tasks and libraries: `task`, `task_configure`, `libraries`, `library_add`.
- Symbols: `symbols_create`, `symbols`, `symbol_access`, `verify_symbols`.

`write` accepts `path`, `declaration`, and `implementation`. Before modifying tasks, device parameters, or symbols, read their version/access metadata and pass back the validation fields required by the operation. See [worker_api.py](worker_api.py) for parameter definitions.

### Create and organize objects

`create` accepts `parent`, `name`, and `kind`. An empty `parent` string selects the project root.

| `kind` | Object and optional parameters |
|---|---|
| `pou` / `program` / `function` | Function block / program / function; functions accept `return_type`, defaulting to `INT` |
| `method` | Method; omit `return_type` for no return value |
| `property` | Property with Get/Set; `return_type` defaults to `INT` |
| `dut` | Data type; `dut_type` is `structure` (default), `enumeration`, `alias`, or `union`; aliases require `base_type` |
| `folder` | Project folder |
| `action` / `gvl` / `task` | Action / global variable list / task |

For example, create a function block, method, and property under an existing Application, then read the property's Get/Set paths:

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

Use `write` or `patch` on the Get/Set paths returned in `children` to edit property implementations. The property node itself has no ST implementation section. `write` accepts only sections supported by the object and returns their contents after the write.

- Rename: `rename`, with `path` and `name`.
- Move: `move`, with `path` and the destination `parent`.
- Delete: `delete`, with `path`; objects with children require explicit `recursive: true`. The result lists removed paths and GUIDs.

Object operations check name conflicts, move cycles, and readback. Compile after renaming or moving to check program references; these operations do not promise automatic refactoring of all ST references. The tool exposes predefined operations and has no arbitrary IronPython execution endpoint.

## Optional: build the flying shear example

Prepare a blank software-controller template using the official IDE or public ScriptEngine. It must contain `Device`, one `Application`, `MainTask`, `SoftMotion General Axis Pool`, and an empty `PLC_PRG`, with IDE Simulation disabled. Do not prepopulate example axes or a flying shear program.

The builder requires the SoftMotion Win software target `4102 / 0000 0001`; the existing baseline version is `3.5.11.10`. The virtual-axis description must match the local installation; query `repository_devices` if needed.

```json
{
  "action": "build_c6",
  "isolated": true,
  "template": "C:/templates/blank-softmotion.project",
  "project": "C:/projects/flying-shear.project",
  "axis": {"type": 1024, "id": "FFFF 0001", "version": "4.0.0.0"}
}
```

The tool copies the template to a new path, adds three virtual axes, the included ST, a 10 ms task, and 48 interface fields, then runs the native compiler and symbol checks. The source template is preserved; existing output files are rejected. The three original files in `examples/c6/` are runtime dependencies for this action.

To export a boot application, run `batch` on the generated project with the step `{"op":"export_boot","args":{}}`. This operation accepts software controllers only and produces native `Application.app/.crc` files. Deploy and run using the official software workflow.

## Usage notes

- The tool performs offline engineering operations; it does not log into or download to a PLC.
- Local results and the lock are stored under `var/`. Failed batches are not automatically replayed. If a timeout leaves the outcome unknown, inspect the IDE and the result referenced by `var/engineering.lock`; resolve the lock only after confirming its IDE has closed.
- Project creation and template builds require new output paths. `batch` saves changes to existing projects.
- Obtain vendor software, device descriptions, motion components, native project templates, and licenses from official sources.

## License

Independently developed. Original tool code and synthetic ST are [MIT licensed](LICENSE). See [NOTICE](NOTICE.md) for third-party dependencies and interoperability information.

API reference: [CODESYS ScriptEngine documentation](https://content.helpme-codesys.com/en/ScriptingEngine/index.html).
