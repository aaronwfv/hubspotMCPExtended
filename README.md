# HubSpot Extended MCP Server

A standalone MCP (Model Context Protocol) server that extends HubSpot functionality for post-call processing and pre-call preparation workflows.

## Features

This server provides access to:
- **Meeting Details**: Retrieve complete meeting information including descriptions and properties
- **Meeting Creation**: Create new meetings with associations to deals and contacts
- **Deal Meetings**: Get all meetings associated with deals, with filtering and sorting
- **Deal Notes**: Get all notes associated with specific deals, sorted by timestamp
- **Task Management**: Create, retrieve, update, complete, and manage tasks with proper associations
- **Task Lookup**: Find tasks by deal or contact with fuzzy name matching support
- **Overdue Tasks**: Efficiently retrieve overdue tasks with owner filtering
- **Meeting Search**: Search meetings by keywords in descriptions
- **Filtering & Sorting**: Advanced filtering by outcome, exclude Calendly meetings, sort by date

## Prerequisites

- Python 3.8 or higher
- A HubSpot account with access to create private apps
- Claude Desktop (or another MCP-compatible client)

## Installation

### 1. Clone or Download the Repository

```bash
git clone <your-repo-url>
cd hubspotMcpExtended
```

Or download and extract the ZIP file to a location on your machine.

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up HubSpot Access Token

#### Create a HubSpot Private App:

1. Go to your HubSpot account
2. Navigate to Settings → Integrations → Private Apps
3. Click "Create a private app"
4. Give it a name (e.g., "MCP Server")
5. In the "Scopes" tab, select the following scopes:
   - `crm.objects.contacts.read`
   - `crm.objects.deals.read`
   - `crm.objects.meetings.read`
   - `crm.objects.meetings.write`
   - `crm.objects.notes.read`
   - `crm.objects.tasks.read`
   - `crm.objects.tasks.write`
6. Click "Create app" and copy the access token

#### Configure Environment:

Create a `.env` file in the project directory:

```bash
HUBSPOT_ACCESS_TOKEN=your_token_here
LOG_LEVEL=INFO
```

Replace `your_token_here` with the access token from your HubSpot private app.

### 4. Configure Claude Desktop

Add the server to your Claude Desktop configuration file:

**On macOS:**
```bash
open -a "TextEdit" ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**On Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

Add this configuration:

```json
{
  "mcpServers": {
    "hubspot-extended": {
      "command": "python",
      "args": ["/FULL/PATH/TO/hubspotMcpExtended/main_fastmcp.py"],
      "cwd": "/FULL/PATH/TO/hubspotMcpExtended"
    }
  }
}
```

**Important:** Replace `/FULL/PATH/TO/hubspotMcpExtended` with the actual full path to where you downloaded/cloned this project.

### 5. Restart Claude Desktop

1. Quit Claude Desktop completely (Cmd+Q on macOS, or close all windows on Windows)
2. Reopen Claude Desktop
3. The HubSpot Extended server should now be available

## Verify Installation

In Claude Desktop, try asking:
```
"Get the details for HubSpot meeting ID 12345"
```

If configured correctly, Claude will use the `get_meeting_details` tool from this server.

## Available Tools

### 1. `get_meeting_details`
Retrieve complete meeting information.

**Parameters:**
- `meeting_id` (required): HubSpot meeting ID
- `properties` (optional): Array of specific properties to retrieve

### 2. `create_meeting`
Create a new meeting with associations to contacts and deals.

**Parameters:**
- `title` (required): Meeting title/name
- `start_time` (required): Meeting start time in ISO format (e.g., "2025-10-30T14:00:00Z")
- `end_time` (optional): Meeting end time in ISO format
- `description` (optional): Meeting description/body
- `owner_id` (optional): HubSpot owner ID for the meeting creator
- `outcome` (optional): Meeting outcome (SCHEDULED, COMPLETED, RESCHEDULED, NO_SHOW, CANCELED)
- `location` (optional): Meeting location
- `contact_ids` (optional): List of contact IDs to associate with the meeting
- `deal_ids` (optional): List of deal IDs to associate with the meeting
- `meeting_type` (optional): Type of meeting based on account meeting types
- `internal_notes` (optional): Internal team notes about the meeting

**Examples:**
- Create simple meeting: `title="Client Call", start_time="2025-10-30T14:00:00Z"`
- Create with associations: `title="Sales Meeting", start_time="2025-10-30T14:00:00Z", deal_ids=["12345"], contact_ids=["67890"]`

### 3. `get_deal_notes`
Get all notes associated with a specific deal.

**Parameters:**
- `deal_id` (required): HubSpot deal ID
- `limit` (optional): Number of notes to retrieve (default: 100)

### 4. `create_task`
Create a new task with associations to contacts and deals.

**Parameters:**
- `title` (required): Task title
- `assigned_to_user_id` (required): HubSpot user ID to assign to
- `description` (optional): Task description
- `due_date` (optional): Due date in ISO format
- `priority` (optional): HIGH, MEDIUM, or LOW
- `contact_id` (optional): Contact ID to associate with
- `deal_id` (optional): Deal ID to associate with
- `task_type` (optional): TODO, CALL, EMAIL, etc.

### 5. `get_tasks`
Retrieve tasks with optional filtering.

**Parameters:**
- `owner_id` (optional): Filter by task owner
- `contact_id` (optional): Filter by associated contact
- `deal_id` (optional): Filter by associated deal
- `status` (optional): Filter by task status
- `limit` (optional): Number of tasks to retrieve (default: 100)

### 6. `get_task_details`
Get detailed information for a specific task.

**Parameters:**
- `task_id` (required): HubSpot task ID
- `properties` (optional): Array of specific properties to retrieve

### 7. `complete_task`
Mark a task as completed.

**Parameters:**
- `task_id` (required): HubSpot task ID
- `completion_notes` (optional): Notes about the completion
- `update_properties` (optional): Additional properties to update

### 8. `update_task`
Update an existing task with new property values.

**Parameters:**
- `task_id` (required): HubSpot task ID
- `title` (optional): New task title
- `description` (optional): New task description/notes
- `status` (optional): Task status (NOT_STARTED, IN_PROGRESS, COMPLETED, WAITING, DEFERRED)
- `priority` (optional): Task priority (HIGH, MEDIUM, LOW)
- `assigned_to_user_id` (optional): HubSpot user ID to reassign task to
- `due_date` (optional): New due date in ISO format
- `task_type` (optional): Type of task (TODO, CALL, EMAIL, etc.)

**Examples:**
- Update title: `task_id="123", title="Follow up with client"`
- Change priority: `task_id="123", priority="HIGH", status="IN_PROGRESS"`
- Reassign task: `task_id="123", assigned_to_user_id="456"`

### 9. `get_deal_meetings`
Retrieve all meetings associated with a deal, with filtering and sorting.

**Parameters:**
- `deal_id` (required): HubSpot deal ID
- `limit` (optional): Number of meetings to return (default: 100)
- `outcome_filter` (optional): Filter by outcome (e.g., "COMPLETED", "SCHEDULED")
- `exclude_calendly` (optional): Exclude automated Calendly meetings
- `sort_direction` (optional): "DESCENDING" (newest first, default) or "ASCENDING"

### 10. `get_overdue_tasks`
Efficiently retrieve overdue tasks.

**Parameters:**
- `owner_id` (optional): Filter by task owner
- `limit` (optional): Number of tasks to return (default: 100)

### 11. `search_meetings`
Search meetings by keywords in descriptions.

**Parameters:**
- `search_term` (required): Term to search for
- `limit` (optional): Number of results (default: 10, max: 100)
- `sort_direction` (optional): "DESCENDING" (newest first, default) or "ASCENDING"

### 12. `get_tasks_for_deal`
Get all tasks associated with a specific deal using ID or fuzzy name matching.

**Parameters:**
- `deal_id` (optional): HubSpot deal ID
- `deal_name` (optional): Deal name for fuzzy search (e.g., "Delta Dental")
- `include_completed` (optional): Include completed tasks (default: False)
- `limit` (optional): Number of tasks to retrieve (default: 100)

**Examples:**
- Get pending tasks: `deal_name="Delta Dental"`
- Get all tasks by ID: `deal_id="38702133148", include_completed=True`

### 13. `get_tasks_for_contact`
Get all tasks associated with a specific contact using ID, name, or email.

**Parameters:**
- `contact_id` (optional): HubSpot contact ID
- `contact_name` (optional): Contact name for fuzzy search
- `contact_email` (optional): Contact email for exact match
- `include_completed` (optional): Include completed tasks (default: False)
- `limit` (optional): Number of tasks to retrieve (default: 100)

**Examples:**
- Get tasks by name: `contact_name="John Smith"`
- Get tasks by email: `contact_email="john@example.com"`
- Get all tasks by ID: `contact_id="122794298695", include_completed=True`

## Configuration

Environment variables (set in `.env` file):
- `HUBSPOT_ACCESS_TOKEN`: Your HubSpot private app access token (required)
- `LOG_LEVEL`: Logging level (default: INFO, options: DEBUG, INFO, WARNING, ERROR)

## Error Handling

The server handles common API errors:
- **401 Unauthorized**: Invalid or expired token
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource doesn't exist
- **429 Rate Limited**: Automatic retry with exponential backoff
- **500+ Server Errors**: Automatic retry with exponential backoff

## Troubleshooting

### Server Not Appearing in Claude Desktop

1. Check the config file path is correct
2. Verify Python path in config (try `which python` in terminal)
3. Check that all dependencies are installed
4. Look for errors in Claude Desktop logs (Help → View Logs)

### API Errors

- **401 Unauthorized**: Check your `.env` file has the correct `HUBSPOT_ACCESS_TOKEN`
- **403 Forbidden**: Verify your private app has the required scopes
- **Rate Limit**: The server automatically retries, but you may need to reduce request frequency

### Meeting Sort Issues

If meetings appear in the wrong order, ensure you've restarted Claude Desktop after updating the code.

## Sharing with Others

To share this MCP server:

1. **Package the project**: ZIP the entire `hubspotMcpExtended` folder
2. **Share the ZIP** with other users
3. **Provide instructions**: Share this README with installation steps
4. **Note**: Each user needs their own HubSpot private app token
