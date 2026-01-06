# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HubSpot Extended MCP Server - A standalone Model Context Protocol (MCP) server that extends HubSpot CRM functionality with advanced features for meeting management, task tracking, and deal workflow automation. Built using FastMCP framework.

**Python Version**: This project uses Python 3 (python3/pip3 commands). Minimum version: Python 3.8+

## Architecture

### Core Components

**Entry Point**: `main_fastmcp.py`
- Imports and runs the FastMCP server instance from `src/fastmcp_server.py`
- Handles startup error logging to stderr

**Server Layer**: `src/fastmcp_server.py`
- Defines all MCP tools using FastMCP's `@mcp.tool()` decorator
- 13 tools for HubSpot operations: meetings, tasks, notes, deals, contacts
- Handles input validation and delegates to HubSpotClient
- Default values: `meeting_type="Workshop"`, `limit=100`, `sort_direction="DESCENDING"`
- Task operations: create, get, update, complete, search by deal/contact

**API Client**: `src/hubspot_client.py`
- `HubSpotClient` class: async HTTP client using httpx
- Authentication via Bearer token from `HUBSPOT_ACCESS_TOKEN` env var
- Retry logic with exponential backoff for rate limits (429) and server errors (500+)
- Error handling with custom `HubSpotError` exception (includes category and status_code)
- Date conversion: ISO format → milliseconds timestamp for HubSpot API
- Search APIs: Uses `/crm/v3/objects/{type}/search` for filtering and fuzzy matching
- Batch APIs: Uses `/crm/v3/objects/{type}/batch/read` for efficient bulk reads
- Association APIs: Uses `/crm/v4/objects/{type}/{id}/associations/{toObjectType}` for relationships

**Logging**: `src/logging_config.py`
- Uses structlog for structured logging with JSON output
- Logs to stderr to avoid interfering with MCP stdio protocol
- Configurable via `LOG_LEVEL` environment variable

### Key Design Patterns

**Fuzzy Search**: Tools like `get_tasks_for_deal` and `get_tasks_for_contact` support lookup by ID or name/email
- Search by name uses HubSpot's `CONTAINS_TOKEN` operator
- Returns most recently modified match first (`hs_lastmodifieddate DESC`)

**Filtering Options**:
- Calendly meeting detection: `exclude_calendly` checks for patterns in title, URL, location
- Outcome filtering: Filter meetings by status (COMPLETED, SCHEDULED, etc.)
- Task status filtering: Default excludes completed tasks unless `include_completed=True`

**Overdue Calculation**:
- Client-side calculation in `get_tasks()` adds `is_overdue` and `overdue_days` fields
- Server-side filtering in `get_overdue_tasks()` uses HubSpot search filters for efficiency

**Association Handling**:
- HubSpot association type IDs: 200 (meeting→contact), 204 (task→contact), 212 (meeting→deal), 216 (task→deal)
- Tools like `create_meeting` and `create_task` accept arrays of IDs to associate

## Development Commands

### Setup
```bash
# Install dependencies (use pip3 for Python 3)
pip3 install -r requirements.txt

# Configure environment
cp .env.example .env  # Create .env file
# Set HUBSPOT_ACCESS_TOKEN in .env file
```

### Running the Server
```bash
# Run directly (use python3)
python3 main_fastmcp.py

# Run via FastMCP CLI
mcp run main_fastmcp.py
```

### Testing
```bash
# Test task lookup functionality
python3 test_task_lookup.py

# Syntax check Python files
python3 -m py_compile src/hubspot_client.py src/fastmcp_server.py main_fastmcp.py

# Manual testing with MCP inspector
mcp dev main_fastmcp.py
```

### Claude Desktop Integration
The server is configured in Claude Desktop via `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "hubspot-extended": {
      "command": "python3",
      "args": ["/full/path/to/hubspotMcpExtended/main_fastmcp.py"],
      "cwd": "/full/path/to/hubspotMcpExtended"
    }
  }
}
```

**Note**: Use `python3` command to ensure Python 3 is used. On some systems, `python` may point to Python 2.

## Environment Configuration

Required:
- `HUBSPOT_ACCESS_TOKEN`: HubSpot private app access token with scopes:
  - `crm.objects.contacts.read`, `crm.objects.contacts.write`
  - `crm.objects.deals.read`, `crm.objects.deals.write`
  - `crm.objects.meetings.read`, `crm.objects.meetings.write`
  - `crm.objects.notes.read`
  - `crm.objects.tasks.read`, `crm.objects.tasks.write`

Optional:
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR) - default: INFO

## HubSpot API Details

### Property Naming
- Task properties: `hs_task_subject`, `hs_task_body`, `hs_task_status`, `hs_task_priority`, `hs_timestamp`
- Meeting properties: `hs_meeting_title`, `hs_meeting_body`, `hs_meeting_start_time`, `hs_meeting_outcome`
- Standard properties: `hubspot_owner_id`, `hs_createdate`, `hs_lastmodifieddate`, `hs_object_id`

### Date/Time Handling
- Input: ISO 8601 format strings (e.g., "2025-10-30T14:00:00Z")
- HubSpot API: Unix timestamps in milliseconds
- Conversion: `_convert_iso_to_timestamp()` method in HubSpotClient

### Search API Operators
- `EQ`: Exact match
- `NEQ`: Not equal
- `IN`: Match any value in array
- `CONTAINS_TOKEN`: Fuzzy/partial text search
- `LT`, `LTE`, `GT`, `GTE`: Numeric/date comparisons

## Common Pitfalls

1. **Date Format**: Always use ISO 8601 format for dates, not milliseconds
2. **Association Type IDs**: Use correct IDs (200, 204, 212, 216) - incorrect IDs fail silently
3. **Limit Caps**: HubSpot APIs have 100-item limits - code caps at 100 and logs warnings
4. **Null Values**: Meeting properties can be null - use `(value or "").lower()` pattern for string operations
5. **Sorting**: Search API sorting can be inconsistent - client-side sort used as fallback in `_sort_meetings_by_start_time()`
6. **MCP Protocol**: Never log to stdout (interferes with stdio protocol) - always use stderr
