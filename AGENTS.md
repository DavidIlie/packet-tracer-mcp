# Agent Guide -- packet-tracer MCP

A practical reference for AI agents working with this MCP server. Read this BEFORE calling tools in a new conversation.

## Core model: how it actually works

```
Your tool call → MCP server (:39000) → HTTP bridge (:54321) → PT webview → $se('runCode', js) → PT Script Engine
```

**You are sending JavaScript to a running Packet Tracer process.** Every topology tool is just a JS snippet. When the built-in tool doesn't cover your case, drop to `pt_send_raw` -- that's the intended workflow, not a fallback.

## The most important rule

**Silent failure is the default.** The bridge queues commands fire-and-forget. If a command throws, you get no error -- PT just... does nothing. Always verify writes:

- After `addDevice` → query `ipc.network().getDeviceCount()`
- After `addLink` → query `port.getLink()` on one end
- After CLI config → `cl.getPrompt()` should reflect the new mode, or read `show running-config`
- After `setName` → `getDevice(newName)` should return non-null

The built-in topology tools now self-verify (they were silently broken before the fix). When you write your own via `pt_send_raw`, you must verify manually.

## Tool tiers -- when to use what

### Tier 1: Planning (no PT needed)
`pt_list_devices`, `pt_list_templates`, `pt_get_device_details`, `pt_estimate_plan`, `pt_plan_topology`, `pt_validate_plan`, `pt_fix_plan`, `pt_explain_plan`, `pt_generate_script`, `pt_generate_configs`, `pt_export`.

These are pure Python. No bridge needed. Use them to prototype a topology before touching PT.

### Tier 2: High-level deploy
`pt_full_build`, `pt_live_deploy`, `pt_deploy`.

`pt_live_deploy` pushes a whole plan in one shot. Good for cookie-cutter topologies. For labs with VLANs, HWIC modules, custom serials, etc. -- it won't cover the config, you'll still need to drive CLI yourself.

### Tier 3: Topology interaction (verified)
`pt_query_topology`, `pt_delete_device`, `pt_rename_device`, `pt_move_device`, `pt_delete_link`, `pt_read_cli`.

These each do one operation and verify it. Use them for simple CRUD.

### Tier 4: Escape hatches
`pt_send_raw`, `pt_ipc`.

**Use these aggressively.** Anytime a built-in tool doesn't fit, compose the JS yourself. Examples where Tier 4 is the right answer:
- Adding VLANs / SVIs (no dedicated tool)
- Configuring trunk ports
- Adding Loopback interfaces
- Reading `show` command output
- Any hardware operation (HWIC installation can't be scripted -- ask user)
- Enumerating properties of an unfamiliar object

## The `pt_ipc` shortcut

Instead of writing full JS for common IPC calls, use `pt_ipc(target, method, args)`. Target syntax traverses the object graph:

| Target | Resolves to |
|--------|-------------|
| `network` | `ipc.network()` |
| `appWindow` | `ipc.appWindow()` |
| `ws` | `...getActiveWorkspace()` |
| `lw` | `...getLogicalWorkspace()` |
| `device:R1` | `ipc.network().getDevice("R1")` |
| `device:R1.port:Gig0/0` | `...getPort("Gig0/0")` |
| `device:R1.cl` | `...getCommandLine()` |
| `device:R1.port:Gig0/0.link` | `...getLink()` |

Special method `"list"` returns all methods/properties on the object -- use it when you don't know what's available.

Examples:
```
pt_ipc("network", "getDeviceCount")                           # -> "9"
pt_ipc("device:R1", "list")                                    # -> method enumeration
pt_ipc("device:R1", "setName", ["NewR1"])                     # rename
pt_ipc("device:R1.cl", "enterCommand", ["show ip int brief"]) # send CLI
pt_ipc("device:R1.port:Gig0/0", "deleteLink")                 # unplug
```

## Canonical IPC paths (memorize these)

```javascript
ipc.network()                          // device/link enumeration
ipc.appWindow()                        // UI / workspace root
ipc.appWindow().getActiveWorkspace()                         // workspace
ipc.appWindow().getActiveWorkspace().getLogicalWorkspace()   // canvas ops (addDevice, removeDevice, removeCanvasItem)

// Device access
ipc.network().getDevice(name)          // by name
ipc.network().getDeviceAt(i)           // by index
ipc.network().getDeviceCount()

// Port access
dev.getPort(name)                      // by name
dev.getPortAt(i)                       // by index
dev.getPortCount()

// CLI
dev.getCommandLine()                   // CommandLine object
cl.enterCommand(str)                   // send one command
cl.getOutput()                         // full cumulative buffer
cl.getPrompt()                         // current prompt (e.g. "R1(config)#")
cl.getMode()                           // "enable", "global", "interface", ...

// Mutations
dev.setName(new)
dev.moveToLocation(x, y)
dev.getXCoordinate() / dev.getYCoordinate()
port.deleteLink()
lw.removeDevice(name)   // takes STRING, not object or UUID
lw.addDevice(type, model, x, y)
```

## Caveats by category

### JavaScript execution
- **Newlines get stripped.** `/* */` comments are safe; `//` eats the rest of the line.
- **No XMLHttpRequest in Script Engine.** To POST results back, must use `window.webview.evaluateJavaScriptAsync(...)` (already handled by `_bridge_send_and_wait`).
- **Each `$se('runCode', cmd)` runs in a fresh scope.** Function definitions don't persist between tool calls -- you can't define `reportResult` once and reuse it.
- **Command output is captured via return.** Use `return expr;` and call with `wait_result=True`.

### Router CLI
- **Initial boot dialog:** New routers ask "Would you like to enter the initial configuration dialog? [yes/no]". Send `""`, `"no"`, `""` before `enable` to get past it.
- **Terminal paging:** Run `terminal length 0` in enable mode before large `show` commands, otherwise output stops at `--More--`.
- **Mode matters for `show`:** Most `show` commands need enable (`#`) mode, not config (`(config)#`). Send `end` to exit config.
- **`write memory`** saves the running config -- call it after you're done.
- **Filter pipe (`| include`, `| section`) may not work** on all IOS versions in PT. Fall back to reading the full output and slicing in JS.

### Command Line API quirks
- `cl.getOutput()` is cumulative from device boot. To read just the latest command's output, do:
  ```javascript
  cl.enterCommand("show ip interface brief");
  var out = cl.getOutput();
  return out.substring(out.lastIndexOf("show ip interface brief"));
  ```
- `cl.enterCommand` is synchronous for syntax, but **ping output is asynchronous** -- sleep a few seconds before re-reading output.
- Many commands share prefixes -- `lastIndexOf` on the exact typed string (not a truncation) is safest.

### Hardware modules (HWIC, NIM, etc.)
- **Cannot be installed via script.** The Script Engine does not expose module installation. User must do this manually in the Physical tab (power off → drag module → power on).
- 1941/2901/2911 have **no serial ports by default** -- HWIC-2T is required for Serial0/1/0 and Serial0/1/1 (yes, slot 1, not slot 0 -- a common gotcha).
- After user installs HWIC-2T, run `dev.getPortCount()` to confirm serial ports appeared.

### Switch / VLAN patterns
- 2960 is L2-only: no `ip routing`, no SVIs as routing interfaces (only management VLAN 1/99).
- 3560-24PS is L3: needs `ip routing` in global config to enable inter-VLAN routing via SVIs.
- Trunk syntax: `switchport trunk encapsulation dot1q` (required on 3560) before `switchport mode trunk`.
- Access switches need `switchport mode trunk` + `switchport trunk allowed vlan N,M` on uplinks to the core.

### Links
- **Cable type matters.** Wrong type makes the link light stay amber/red.
  - `straight`: router↔switch, switch↔PC (different types)
  - `cross`: router↔router, switch↔switch, PC↔PC (same types)
  - `serial`: WAN links between router serial interfaces
- `pt_fix_plan` auto-corrects wrong cable types.
- L3-switch-to-router can be either, depending on whether the switch port is `no switchport` (routed) or not.

### End devices (PC-PT, Server-PT)
- Configure IP via `configurePcIp(name, dhcp, ip, mask, gw)` -- `dhcp=false` for static, `true` for DHCP.
- Verify via `dev.getPort("FastEthernet0").getIpAddress()`.
- To run a CLI command on a PC (ping, ipconfig), use `dev.getCommandLine().enterCommand("ping 1.2.3.4")`.
- Pings take seconds to complete -- wait 4-5s then re-read output.

### Topology mutations
- `lw.removeDevice(name)` -- STRING name only. Passing the device object or UUID silently no-ops.
- Deleting a device auto-deletes its links.
- After `renameDevice`, the old name is immediately invalid -- use the new name everywhere.
- `addDevice` placement uses logical workspace coordinates (roughly 0-1000 for a default canvas).

## Working patterns

### Discover before you write
When unsure what methods exist on an object, call `pt_ipc("device:R1", "list")` (or equivalent) first. Cheaper than failing five times.

### Small batches
Each `pt_send_raw` call ships one JS blob. Batch 5-10 `enterCommand` calls per blob -- more than ~20 and the wait-for-result can time out.

### Config then verify
Pattern for IOS config:
1. `cl.enterCommand("configure terminal")`
2. ...config commands...
3. `cl.enterCommand("end")` -- back to enable mode
4. `cl.enterCommand("show running-config | include <thing>")` -- or read full running-config
5. Substring the output from `lastIndexOf("show running-config")` to get just the new content

### When pings "fail"
First ping after adding a route usually fails due to ARP resolution. `3/4 replies` is normal for a fresh path. Send another ping burst to see steady-state.

### Connection lost mid-session
If tools start timing out, check `pt_bridge_status`. If PT crashed or the bootstrap polling died, user has to re-paste the bootstrap into Builder Code Editor.

## Bootstrap (user action)

If a fresh PT session: user pastes this into Extensions → Builder Code Editor → Run:

```javascript
/* PT-MCP Bridge */ window.webview.evaluateJavaScriptAsync("setInterval(function(){var x=new XMLHttpRequest();x.open('GET','http://127.0.0.1:54321/next',true);x.onload=function(){if(x.status===200&&x.responseText){$se('runCode',x.responseText)}};x.onerror=function(){};x.send()},500)");
```

One-time per PT process. Runs until PT closes.

## Things that are not possible

- Installing/removing hardware modules (HWIC, NIM, WIC-cover)
- Changing the router model after placement (must delete + re-add)
- Querying Script Engine globals defined in a previous `runCode` call
- Getting structured JS errors out of fire-and-forget commands (must use `wait_result=True`)
- Making PT run faster than real time (boot takes ~20s)

## Debugging checklist

Tool returned "No response from PT (timeout)":
1. `pt_bridge_status` -- bridge up + PT connected?
2. If not connected: user needs to re-paste bootstrap.
3. If connected: PT may be frozen on a modal dialog (check the GUI).
4. If still stuck: `pt_send_raw("return 1;", wait_result=True)` should return "1" -- if even that hangs, the bootstrap stopped polling.

Tool returned "ERROR:ReferenceError: X is not defined":
- Helper function `X` doesn't exist in this PT version. Rewrite using native `ipc.*` APIs (see canonical paths above).

Tool reported success but nothing changed in PT:
- You got silent failure. The command was queued but the JS threw inside PT. Retry with `pt_send_raw(..., wait_result=True)` -- that version does catch and surface errors.

CLI command returns "% Invalid input detected":
- Wrong mode (`#` vs `(config)#` vs `(config-if)#`). Check `cl.getMode()` and `cl.getPrompt()`.
- Or IOS version doesn't support the syntax -- try without filters / with legacy form.
