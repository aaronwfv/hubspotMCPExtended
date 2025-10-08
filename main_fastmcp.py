#!/usr/bin/env python3
"""
Main entry point for HubSpot Extended MCP Server using FastMCP
"""

from src.fastmcp_server import mcp

if __name__ == "__main__":
    mcp.run()