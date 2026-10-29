# InoProShop MCP

[中文](README.md) · English

Use MCP to access InoProShop's public ScriptEngine: create and edit projects, read and write Structured Text, run native builds, save projects, and export software-controller boot applications.

## Engineering operations

A small tool for PLC project work, with a three-axis flying shear example.

| Task | Supported operations |
|---|---|
| Create and edit | Create empty project containers, inspect project structure, read and modify ST and project objects |
| Build and save | Run the native compiler, collect diagnostics, and save projects |
| Configure and export | Configure devices, tasks, libraries, and symbols; export software-controller boot applications |

## Example: three-axis flying shear

Starting from a user-prepared blank software-controller template, MCP adds three virtual axes, writes the flying shear ST, configures a 10 ms task and 48 interface fields, and runs the native compiler. The user deploys the project to a software PLC through the official workflow.

![Three-axis flying shear: recorded software PLC feedback](https://raw.githubusercontent.com/Polarzin/Inoproshop-MCP/main/docs/assets/flying-shear.gif)

The GIF records a 3D visualization of software PLC feedback. This repository provides the engineering tool and ST example; the 3D interface used for the recording is not included. Build instructions follow below.

Earlier engineering tools were used to verify project reading/writing, compilation, and downloading on our own hardware platform. The current public tool provides offline engineering operations; the flying shear example was verified on a software PLC.

## Installation

Requires Windows, Node.js ≥ 18, and a compatible InoProShop installation with ScriptEngine support. The engineering baseline is InoProShop 1.9.1.6 / SP11; configure device descriptions and motion components for your installed version. Python worker scripts run in the IDE's own scripting environment.

[Download the tool ZIP](https://github.com/Polarzin/Inoproshop-MCP/archive/refs/heads/main.zip), extract it, and run this in the tool directory:

```powershell
npm.cmd ci --ignore-scripts
```

The ZIP contains the tool, required ST example files, and usage instructions; the README demonstration GIF is excluded. To receive updates through Git, clone the repository instead:

```powershell
git clone --depth 1 https://github.com/Polarzin/Inoproshop-MCP.git
cd Inoproshop-MCP
npm.cmd ci --ignore-scripts
```

Add this configuration to a stdio MCP client and replace the paths with absolute local paths:

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

Use `tree` to discover actual object paths first. The example program path applies to controller projects containing that program. Supported `batch` operations:

- Programs and structure: `tree`, `list`, `read`, `read_lines`, `patch`, `write`, `create`.
- Engineering: `compile`, `save`, `generate_code`, `export_boot`.
- Devices: `device`, `device_parameters`, `device_parameter_write`, `device_add`, `repository_devices`.
- Tasks and libraries: `task`, `task_configure`, `libraries`, `library_add`.
- Symbols: `symbols_create`, `symbols`, `symbol_access`, `verify_symbols`.

`write` accepts `path`, `declaration`, and `implementation`. Before modifying tasks, device parameters, or symbols, read their version/access metadata and pass back the validation fields required by the operation. See [worker_api.py](worker_api.py) for parameter definitions.

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
