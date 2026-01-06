#!/usr/bin/env python3
"""
Main entry point for HubSpot Extended MCP Server using FastMCP
"""

from src.fastmcp_server import mcp

import sys
import os
import traceback

# Debug: Print startup message to stderr
print(f"Starting hubspot-extended MCP server... Tokens present: {'HUBSPOT_ACCESS_TOKEN' in os.environ}", file=sys.stderr)
sys.stderr.flush()

if __name__ == "__main__":
    try:
        mcp.run()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)