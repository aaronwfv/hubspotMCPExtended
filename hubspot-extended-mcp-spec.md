# HubSpot Extended MCP Server Specification

## Overview
Build a standalone MCP (Model Context Protocol) server that extends HubSpot functionality for post-call processing and pre-call preparation workflows. This server will work alongside the existing HubSpot MCP server to provide access to meetings, tasks, and notes data.

## Core Requirements

### Authentication
- Use HubSpot Private App token authentication
- Environment variable: `HUBSPOT_ACCESS_TOKEN`
- All requests to HubSpot API should include `Authorization: Bearer {token}`

### Base Configuration
```json
{
  "mcpVersion": "2024-11-05",
  "name": "hubspot-extended",
  "version": "1.0.0",
  "description": "Extended HubSpot MCP server for meetings, tasks, and notes"
}
```

## Required Tools

### 1. Get Meeting Details (`get_meeting_details`)
**Purpose**: Retrieve complete meeting information including description and all meeting properties

**HubSpot API**: `GET /crm/v3/objects/meetings/{meetingId}`
- **Endpoint**: `https://api.hubapi.com/crm/v3/objects/meetings/{meetingId}`
- **Method**: GET
- **Documentation**: https://developers.hubspot.com/docs/api-reference/crm-meetings-v3/basic/get-crm-v3-objects-meetings-meetingId

**Parameters**:
- `meeting_id` (required): The HubSpot meeting ID
- `properties` (optional): Array of specific properties to retrieve (default: all standard properties)

**Key Properties to Return**:
- `hs_meeting_title` - Meeting title
- `hs_meeting_body` - Meeting description/notes
- `hs_meeting_start_time` - Start time
- `hs_meeting_end_time` - End time
- `hs_meeting_outcome` - Meeting outcome
- `hubspot_owner_id` - Meeting owner
- `hs_attendee_owner_ids` - Attendee owner IDs
- All other available properties

**Response Format**:
```json
{
  "id": "meeting_id",
  "properties": {
    "hs_meeting_title": "...",
    "hs_meeting_body": "...",
    "hs_meeting_start_time": "...",
    "hs_meeting_end_time": "...",
    "hs_meeting_outcome": "...",
    "hubspot_owner_id": "...",
    "hs_attendee_owner_ids": "..."
  },
  "createdAt": "...",
  "updatedAt": "...",
  "associations": {}
}
```

### 2. Get Deal Notes (`get_deal_notes`)
**Purpose**: Retrieve all notes associated with a specific deal

**HubSpot API**: `GET /crm/v3/objects/notes`
- **Endpoint**: `https://api.hubapi.com/crm/v3/objects/notes`
- **Method**: GET
- **Documentation**: https://developers.hubspot.com/docs/api-reference/crm-notes-v3/guide

**Parameters**:
- `deal_id` (required): The HubSpot deal ID to get notes for
- `limit` (optional): Number of notes to retrieve (default: 100)

**Implementation Notes**:
- Use associations to filter notes by deal
- Filter parameter: `associations.deal` equals the provided deal_id
- Sort by `hs_createdate` descending to get most recent notes first

**Key Properties to Return**:
- `hs_note_body` - Note content
- `hs_timestamp` - When note was created
- `hubspot_owner_id` - Note author
- `hs_createdate` - Creation date
- `hs_lastmodifieddate` - Last modified date

### 3. Create Task (`create_task`)
**Purpose**: Create a new task with proper associations to contacts and deals

**HubSpot API**: `POST /automation/v4/actions/TASK_CREATION`
**Alternative API**: `POST /crm/v3/objects/tasks`
- **Endpoint**: `https://api.hubapi.com/automation/v4/actions/TASK_CREATION`
- **Method**: POST
- **Documentation**: https://developers.hubspot.com/docs/api-reference/automation-automation-v4-v4/guide#create-task

**Parameters**:
- `title` (required): Task title
- `description` (optional): Task description
- `due_date` (optional): Due date in ISO format
- `priority` (optional): Task priority (HIGH, MEDIUM, LOW)
- `assigned_to_user_id` (required): HubSpot user ID to assign task to
- `contact_id` (optional): Contact ID to associate with
- `deal_id` (optional): Deal ID to associate with
- `task_type` (optional): Type of task (TODO, CALL, EMAIL, etc.)

**Request Body Structure**:
```json
{
  "objectType": "TASK",
  "properties": {
    "hs_task_subject": "Task Title",
    "hs_task_body": "Task Description",
    "hs_task_status": "NOT_STARTED",
    "hs_task_priority": "HIGH",
    "hubspot_owner_id": "user_id",
    "hs_task_type": "TODO",
    "hs_timestamp": "due_date_timestamp"
  },
  "associations": [
    {
      "to": {
        "id": "contact_id"
      },
      "types": [
        {
          "associationCategory": "HUBSPOT_DEFINED",
          "associationTypeId": 204
        }
      ]
    },
    {
      "to": {
        "id": "deal_id"
      },
      "types": [
        {
          "associationCategory": "HUBSPOT_DEFINED",
          "associationTypeId": 216
        }
      ]
    }
  ]
}
```

### 4. Get Tasks (`get_tasks`)
**Purpose**: Retrieve tasks with optional filtering

**HubSpot API**: `GET /crm/v3/objects/tasks`
- **Endpoint**: `https://api.hubapi.com/crm/v3/objects/tasks`
- **Method**: GET

**Parameters**:
- `owner_id` (optional): Filter tasks by owner
- `contact_id` (optional): Filter tasks associated with specific contact
- `deal_id` (optional): Filter tasks associated with specific deal
- `status` (optional): Filter by task status (NOT_STARTED, IN_PROGRESS, COMPLETED, etc.)
- `limit` (optional): Number of tasks to retrieve (default: 100)

**Key Properties to Return**:
- `hs_task_subject` - Task title
- `hs_task_body` - Task description
- `hs_task_status` - Task status
- `hs_task_priority` - Task priority
- `hubspot_owner_id` - Task owner
- `hs_task_type` - Task type
- `hs_timestamp` - Due date
- `hs_createdate` - Created date

### 5. Get Task Details (`get_task_details`)
**Purpose**: Retrieve detailed information for a specific task

**HubSpot API**: `GET /crm/v3/objects/tasks/{taskId}`
- **Endpoint**: `https://api.hubapi.com/crm/v3/objects/tasks/{taskId}`
- **Method**: GET

**Parameters**:
- `task_id` (required): The HubSpot task ID
- `properties` (optional): Array of specific properties to retrieve

**Response**: Full task object with all properties and associations

## Error Handling
- Handle HTTP 401 (Unauthorized) - Invalid or expired token
- Handle HTTP 403 (Forbidden) - Insufficient permissions
- Handle HTTP 404 (Not Found) - Object doesn't exist
- Handle HTTP 429 (Rate Limited) - Implement retry with exponential backoff
- Handle HTTP 500 (Server Error) - HubSpot API issues

## Implementation Notes

### Rate Limiting
- HubSpot API has rate limits (100 requests per 10 seconds for most endpoints)
- Implement exponential backoff for 429 responses
- Consider batching operations where possible

### Association Type IDs
- Contact to Task: 204
- Deal to Task: 216
- Meeting to Contact: 196
- Meeting to Deal: 208

### Date Handling
- All timestamps should be in milliseconds since epoch
- Convert ISO date strings to timestamps when needed
- Handle timezone conversions properly

### Error Response Format
```json
{
  "error": {
    "message": "Description of error",
    "category": "VALIDATION_ERROR|AUTHENTICATION|NOT_FOUND|RATE_LIMIT|SERVER_ERROR",
    "details": {}
  }
}
```

## Dependencies
- HTTP client for API requests
- JSON parsing
- Environment variable handling
- MCP protocol implementation

## Testing Requirements
- Test with valid HubSpot account and access token
- Test error scenarios (invalid IDs, missing permissions)
- Test association creation
- Validate all returned data structures

## Usage Examples

### Get Meeting Details
```bash
# Get all properties for a meeting
get_meeting_details meeting_id=12345

# Get specific properties only
get_meeting_details meeting_id=12345 properties=["hs_meeting_title","hs_meeting_body"]
```

### Create Task with Associations
```bash
create_task title="Follow up on demo" description="Schedule next meeting" assigned_to_user_id=134774664 contact_id=67890 deal_id=54321 priority="HIGH" due_date="2025-09-25T14:00:00Z"
```

### Get Deal Notes
```bash
get_deal_notes deal_id=54321 limit=50
```

This specification provides everything needed to build a comprehensive HubSpot Extended MCP server that integrates seamlessly with existing HubSpot workflows for post-call processing and pre-call preparation.
