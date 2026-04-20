"""
MCP Server for Packet Tracer.

Entry point: creates the server, registers tools/resources, and starts
on streamable-http (:39000) or stdio depending on the --stdio flag.

Binds to 0.0.0.0 by default so other machines on the LAN can connect.
Override with --host <ip> (e.g., --host 127.0.0.1 for localhost-only).
"""

from __future__ import annotations

import os
import sys

from mcp.server.fastmcp import FastMCP

from .adapters.mcp.resource_registry import register_resources
from .adapters.mcp.tool_registry import register_tools
from .settings import SERVER_NAME, SERVER_INSTRUCTIONS

TRANSPORT_PORT = 39000


def _resolve_host() -> str:
    """Pick the bind host. CLI flag beats env var beats default."""
    for i, arg in enumerate(sys.argv):
        if arg == "--host" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if arg.startswith("--host="):
            return arg.split("=", 1)[1]
    return os.environ.get("PT_MCP_HOST", "0.0.0.0")


TRANSPORT_HOST = _resolve_host()

mcp = FastMCP(
    SERVER_NAME,
    instructions=SERVER_INSTRUCTIONS,
    host=TRANSPORT_HOST,
    port=TRANSPORT_PORT,
    stateless_http=True,
)

register_tools(mcp)
register_resources(mcp)


def main():
    """Start the MCP server.

    Defaults to streamable-http on 0.0.0.0:39000 (LAN-accessible).
    With --stdio uses stdio transport (for debug or legacy clients).
    Use --host 127.0.0.1 to bind localhost-only.
    """
    if "--stdio" in sys.argv:
        mcp.run(transport="stdio")
    else:
        print(
            f"[packet-tracer-mcp] listening on http://{TRANSPORT_HOST}:{TRANSPORT_PORT}/mcp",
            file=sys.stderr,
        )
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
