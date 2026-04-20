# Packet Tracer MCP Server

MCP server that lets any LLM (Copilot, Claude, etc.) create, configure, validate, and deploy full network topologies to Cisco Packet Tracer in real time.

Tell it "build me a network with 3 routers, DHCP, and OSPF" and the server plans the topology, validates everything, generates scripts and configs, and deploys it straight into PT.

Built with Python 3.11+, Pydantic 2.0+, FastMCP, Streamable HTTP.

![Packet Tracer Screenshot](https://i.imgur.com/placeholder.png)

## Features

- **Full Pipeline** -- plan, validate, auto-fix, generate, and deploy topologies from a single prompt
- **Live Deploy** -- sends commands directly to Packet Tracer via HTTP bridge, no copy-paste
- **22 MCP Tools** -- covers everything from device catalog queries to real-time topology manipulation
- **Bidirectional CLI** -- read back CLI output from routers and switches inside PT
- **Auto IP Planning** -- assigns /24 LANs and /30 inter-router links automatically
- **Validation + Auto-Fix** -- catches 15 error types and auto-corrects cables, models, and ports
- **Multiple Routing Protocols** -- static, OSPF, RIP with full config generation
- **9 Topology Templates** -- single LAN, multi LAN, star, hub-spoke, branch office, router-on-a-stick, and more

## How It Works

```
┌─────────┐         ┌──────────────┐   HTTP    ┌──────────────┐  $se()  ┌──────────────┐
│   LLM   │  MCP    │  MCP Server  │  :54321   │  PTBuilder   │  IPC   │ Packet Tracer│
│(Copilot)│ ──────► │  (:39000)    │ ────────► │  (WebView)   │ ─────► │   (Engine)   │
└─────────┘         └──────────────┘           └──────────────┘        └──────────────┘
```

Two HTTP servers run simultaneously:

| Port | What | Purpose |
|------|------|---------|
| **39000** | MCP Server (streamable-http) | Receives tool requests from the LLM/editor |
| **54321** | Internal HTTP Bridge | Sends JS commands to PTBuilder inside Packet Tracer |

The MCP server plans topologies, generates PTBuilder JavaScript + IOS CLI configs, and pushes them through the bridge. PTBuilder's QWebEngine webview polls the bridge every 500ms and executes commands in PT's Script Engine via `$se('runCode', ...)`.

---

## Setup

### 1. Install

```bash
git clone https://github.com/DavidIlie/packet-tracer-mcp.git
cd packet-tracer-mcp
pip install -e .
```

### 2. Start the server

```bash
python -m src.packet_tracer_mcp
```

This starts both the MCP server on `:39000` and the HTTP bridge on `:54321` automatically.

> For stdio mode (debug/legacy): `python -m src.packet_tracer_mcp --stdio`

### 3. Configure your MCP client

**Claude Code:**

```bash
claude mcp add --transport http packet-tracer http://127.0.0.1:39000/mcp
```

**VS Code** -- `.vscode/mcp.json`:

```json
{
  "servers": {
    "packet-tracer": {
      "url": "http://127.0.0.1:39000/mcp"
    }
  }
}
```

**Claude Desktop** -- `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "packet-tracer": {
      "url": "http://127.0.0.1:39000/mcp"
    }
  }
}
```

### 4. Connect Packet Tracer

1. Open Packet Tracer 8.2+
2. Go to **Extensions > Builder Code Editor**
3. Paste the bootstrap script and click **Run**:

```javascript
/* PT-MCP Bridge */ window.webview.evaluateJavaScriptAsync("setInterval(function(){var x=new XMLHttpRequest();x.open('GET','http://127.0.0.1:54321/next',true);x.onload=function(){if(x.status===200&&x.responseText){$se('runCode',x.responseText)}};x.onerror=function(){};x.send()},500)");
```

This makes PTBuilder poll the bridge every 500ms. When the LLM generates commands, the MCP server queues them and PT executes them in real time.

> **Note:** The bootstrap injects a `setInterval` into the webview that does HTTP polling. `$se('runCode', ...)` bridges from the webview to PT's Script Engine. PTBuilder's `executeCode()` strips all newlines internally, which is why the bootstrap uses `/* */` comments instead of `//`.

#### Permanent setup (optional)

To auto-start the polling loop when Builder Code Editor opens:

1. In PT: Extensions > Scripting Interface
2. Select the Builder module
3. Replace `main.js` and `interface.js` with the modified versions in `PTBuilder/source/`
4. Save and restart the module

### 5. Done

The LLM can now create devices, links, and configure routers automatically. Ask it to build a network.

---

## MCP Tools (22)

### Catalog
| Tool | Description |
|------|-------------|
| `pt_list_devices` | List all available devices with their ports |
| `pt_list_templates` | List available topology templates |
| `pt_get_device_details` | Full details for a specific device model |

### Estimation
| Tool | Description |
|------|-------------|
| `pt_estimate_plan` | Dry-run: estimate devices, links, and complexity without generating |

### Planning
| Tool | Description |
|------|-------------|
| `pt_plan_topology` | Generate a complete plan from parameters (routers, PCs, routing, etc.) |

### Validation
| Tool | Description |
|------|-------------|
| `pt_validate_plan` | Validate a plan with 15 typed error codes |
| `pt_fix_plan` | Auto-correct common errors (cables, models, ports) |
| `pt_explain_plan` | Generate a natural language explanation of every decision |

### Generation
| Tool | Description |
|------|-------------|
| `pt_generate_script` | Generate PTBuilder JavaScript |
| `pt_generate_configs` | Generate per-device CLI (IOS) configs |

### Full Pipeline
| Tool | Description |
|------|-------------|
| `pt_full_build` | All-in-one: plan, validate, generate, and deploy |

### Live Deploy
| Tool | Description |
|------|-------------|
| `pt_deploy` | Copy script to clipboard + manual instructions |
| `pt_live_deploy` | Send commands directly to PT in real time via HTTP bridge |
| `pt_bridge_status` | Check if the bridge is active and PT is connected |

### Topology Interaction
| Tool | Description |
|------|-------------|
| `pt_query_topology` | Query devices currently in PT |
| `pt_delete_device` | Delete a device and its links from PT |
| `pt_rename_device` | Rename a device in the active topology |
| `pt_move_device` | Move a device to new canvas coordinates |
| `pt_delete_link` | Delete a link from a specific interface |
| `pt_send_raw` | Send arbitrary JS to PT's Script Engine |
| `pt_ipc` | Call an IPC method on a PT object by dotted path (shortcut for common raw calls) |
| `pt_read_cli` | Execute a CLI command and read back the output |

## For AI agents

See [AGENTS.md](AGENTS.md) for a practical guide covering tool tiers, silent failure patterns, canonical IPC paths, and when to drop to `pt_send_raw`.

### Export + Projects
| Tool | Description |
|------|-------------|
| `pt_export` | Export plan + scripts + configs to files |
| `pt_list_projects` / `pt_load_project` | Saved project management |

---

## MCP Resources (5)

| URI | Description |
|-----|-------------|
| `pt://catalog/devices` | All devices with ports |
| `pt://catalog/cables` | Cable types |
| `pt://catalog/aliases` | Model aliases |
| `pt://catalog/templates` | Topology templates |
| `pt://capabilities` | Server capabilities |

---

## Supported Devices

### Routers
| Model | Ports |
|-------|-------|
| 1941 | Gig0/0, Gig0/1 (+serial via HWIC-2T) |
| 2901 | Gig0/0, Gig0/1 (+serial via HWIC-2T) |
| 2911 | Gig0/0, Gig0/1, Gig0/2 (+serial via HWIC-2T) |
| ISR4321 | Gig0/0/0, Gig0/0/1 |

### Switches
| Model | Ports |
|-------|-------|
| 2960-24TT | Fa0/1-24, Gig0/1-2 |
| 3560-24PS | Fa0/1-24, Gig0/1-2 |

### End Devices
| Model | Ports |
|-------|-------|
| PC-PT | Fa0 |
| Server-PT | Fa0 |
| Laptop-PT | Fa0 |

### Other
| Model | Type |
|-------|------|
| Cloud-PT | WAN Cloud |
| AccessPoint-PT | Wireless AP |

---

## Cable Types

| Cable | Typical Use |
|-------|-------------|
| straight | Switch-Router, Switch-PC |
| cross | Router-Router, Switch-Switch, PC-PC |
| serial | Router Serial-Router Serial (WAN) |
| fiber | Fiber optic connections |
| auto | Auto-detect |

---

## IP Addressing

- **LANs** -- `192.168.X.0/24`, gateway at `.1`, PCs from `.2`
- **Inter-router links** -- `10.0.X.0/30`, point-to-point between routers
- **DHCP** -- automatic pool per LAN with gateway exclusion

## Routing

| Protocol | Status | Generates |
|----------|--------|-----------|
| static | Complete | `ip route` commands |
| ospf | Complete | `router ospf` configs |
| rip | Complete | `router rip` configs |
| eigrp | Enum only | Not implemented |
| none | Complete | No routing |

---

## Templates

| Template | Description |
|----------|-------------|
| `single_lan` | 1 router + 1 switch + PCs |
| `multi_lan` | N routers interconnected, each with its own LAN |
| `multi_lan_wan` | Multi LAN with WAN cloud |
| `star` | Central router with satellite routers |
| `hub_spoke` | Hub-and-spoke topology |
| `branch_office` | Branch offices |
| `router_on_a_stick` | Inter-VLAN routing |
| `three_router_triangle` | 3 routers in a triangle |
| `custom` | Fully custom |

---

## Architecture

```
src/packet_tracer_mcp/
├── adapters/mcp/              # MCP protocol layer
│   ├── tool_registry.py       # 22 MCP tools
│   └── resource_registry.py   # 5 MCP resources
├── application/               # Use cases + DTOs (requests/responses)
├── domain/                    # Core business logic
│   ├── models/               # TopologyPlan, DevicePlan, LinkPlan, errors
│   ├── services/             # Orchestrator, IPPlanner, Validator, AutoFixer
│   └── rules/                # Validation rules (devices, cables, IPs)
├── infrastructure/
│   ├── catalog/              # Device catalog, cables, templates, aliases
│   ├── generator/            # PTBuilder JS + CLI config generators
│   ├── execution/            # Executors + HTTP bridge
│   │   ├── live_bridge.py    # PTCommandBridge (HTTP server :54321)
│   │   ├── live_executor.py  # LiveExecutor (sends plan → bridge → PT)
│   │   ├── deploy_executor.py# DeployExecutor (clipboard + instructions)
│   │   └── manual_executor.py# ManualExecutor (file export)
│   └── persistence/          # Project save/load
├── shared/                    # Enums, constants, utilities
├── server.py                  # MCP server entry point
└── settings.py                # Version + config
```

### Data Flow

```
TopologyRequest → Orchestrator → IPPlanner → Validator → AutoFixer
                                                            ↓
                                              TopologyPlan (validated)
                                                            ↓
                                    ┌───────────────────────┼──────────────────┐
                                    ↓                       ↓                  ↓
                            PTBuilder Script          CLI Configs        Live Deploy
                           (addDevice/addLink)    (hostname, IPs,     (HTTP bridge
                                                   DHCP, routing)      → PT real-time)
```

---

## PTBuilder Extension

The `PTBuilder/` directory contains the source code for the Script Module "Builder Code Editor":

| File | Purpose |
|------|---------|
| `source/main.js` | Entry point -- creates menu and webview |
| `source/runcode.js` | `runCode(scriptText)` -- executes JS in Script Engine |
| `source/userfunctions.js` | `addDevice()`, `addLink()`, `configureIosDevice()`, `configurePcIp()`, `queryTopology()`, `deleteDevice()`, `renameDevice()`, `moveDevice()`, `deleteLink()` |
| `source/devices.js` | Model → PT numeric type mapping |
| `source/links.js` | Cable type → numeric ID mapping |
| `source/modules.js` | Hardware module mapping |
| `source/window.js` | Webview window management (QWebEngine) |
| `source/interface/` | HTML + JS for the web editor (status panel + real-time logging) |
| `Builder.pts` | Compiled extension package (binary, not editable) |

---

## Tests

```bash
# All tests
python -m pytest tests/ -v

# Single file
python -m pytest tests/test_full_build.py -v

# Specific test
python -m pytest tests/test_full_build.py::TestFullBuild::test_basic_2_routers -v
```

34 tests covering IP planning, validation, auto-fix, explanation, estimation, generation, and full build integration.

---

## Quick Example

```
User:  "Build me a network with 2 routers, 2 switches, 4 PCs, DHCP and static routing"

→ pt_full_build generates:
  - 8 devices: R1, R2, SW1, SW2, PC1, PC2, PC3, PC4
  - 7 links: R1↔R2 (cross), R1↔SW1 (straight), R2↔SW2 (straight), SW1↔PC1, SW1↔PC2, SW2↔PC3, SW2↔PC4
  - IPs: LAN1 192.168.0.0/24, LAN2 192.168.1.0/24, Inter-router 10.0.0.0/30
  - DHCP pools on R1 and R2
  - Bidirectional static routes
  - 23 JavaScript commands sent to PT

→ pt_live_deploy sends everything to Packet Tracer and the devices appear fully configured
```

## Requirements

- Python 3.11+
- Cisco Packet Tracer 8.2+ (for live deploy)
- PTBuilder extension installed in PT (included in `PTBuilder/`)

## License

[MIT](LICENSE)
