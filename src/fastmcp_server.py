#!/usr/bin/env python3
"""
HubSpot Extended MCP Server using FastMCP
"""

import os
from typing import List, Optional, Dict, Any
from datetime import datetime

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .hubspot_client import HubSpotClient
from .logging_config import configure_logging

load_dotenv()

# Configure logging
configure_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))

# Initialize FastMCP server
mcp = FastMCP("hubspot-extended")

# Initialize HubSpot client
hubspot_client = HubSpotClient()


@mcp.tool()
async def get_meeting_details(
    meeting_id: str,
    properties: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Retrieve complete meeting information including description and all meeting properties.

    Args:
        meeting_id: The HubSpot meeting ID
        properties: Array of specific properties to retrieve (optional, default: all standard properties)

    Returns:
        Complete meeting object with properties, creation date, and associations
    """
    return await hubspot_client.get_meeting_details(meeting_id, properties)


@mcp.tool()
async def get_deal_notes(
    deal_id: str,
    limit: int = 100,
    sort_direction: str = "DESCENDING"
) -> Dict[str, Any]:
    """
    Retrieve all notes associated with a specific deal.

    Args:
        deal_id: The HubSpot deal ID to get notes for
        limit: Number of notes to retrieve (default: 100)
        sort_direction: Sort by note timestamp - "DESCENDING" for most recent first, "ASCENDING" for oldest first (default: "DESCENDING")

    Returns:
        Notes collection with note content, timestamps, and authors sorted by timestamp
    """
    return await hubspot_client.get_deal_notes(deal_id, limit, sort_direction)


@mcp.tool()
async def create_task(
    title: str,
    assigned_to_user_id: str,
    description: Optional[str] = None,
    due_date: Optional[str] = None,
    priority: Optional[str] = None,
    contact_id: Optional[str] = None,
    deal_id: Optional[str] = None,
    task_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new task with proper associations to contacts and deals.

    Args:
        title: Task title
        assigned_to_user_id: HubSpot user ID to assign task to
        description: Task description (optional)
        due_date: Due date in ISO format (optional)
        priority: Task priority - HIGH, MEDIUM, or LOW (optional)
        contact_id: Contact ID to associate with (optional)
        deal_id: Deal ID to associate with (optional)
        task_type: Type of task - TODO, CALL, EMAIL, etc. (optional)

    Returns:
        Created task object with ID and all properties
    """
    return await hubspot_client.create_task(
        title=title,
        assigned_to_user_id=assigned_to_user_id,
        description=description,
        due_date=due_date,
        priority=priority,
        contact_id=contact_id,
        deal_id=deal_id,
        task_type=task_type
    )


@mcp.tool()
async def get_tasks(
    owner_id: Optional[str] = None,
    contact_id: Optional[str] = None,
    deal_id: Optional[str] = None,
    status: Optional[str] = None,
    due_date_start: Optional[str] = None,
    due_date_end: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Retrieve tasks with optional filtering including date ranges.

    IMPORTANT: For date-based queries like "tasks due today" or "tasks due this week", use due_date_start and due_date_end parameters for efficient API filtering.

    Common date filtering patterns:
    - Tasks due today: due_date_start="2025-09-24T00:00:00", due_date_end="2025-09-24T23:59:59"
    - Tasks due this week: due_date_start="2025-09-23T00:00:00", due_date_end="2025-09-29T23:59:59"
    - Overdue tasks: Use get_overdue_tasks tool instead for better performance

    Args:
        owner_id: Filter tasks by owner - RECOMMENDED: Get from HubSpot:get_user_details first
        contact_id: Filter tasks associated with specific contact (optional)
        deal_id: Filter tasks associated with specific deal (optional)
        status: Filter by task status - NOT_STARTED, IN_PROGRESS, COMPLETED, etc. (optional)
        due_date_start: Start of date range in ISO format (e.g. "2025-09-24T00:00:00") (optional)
        due_date_end: End of date range in ISO format (e.g. "2025-09-24T23:59:59") (optional)
        limit: Number of tasks to retrieve (default: 100)

    Returns:
        Tasks collection with titles, descriptions, status, priority, due dates, and associations
    """
    return await hubspot_client.get_tasks(
        owner_id=owner_id,
        contact_id=contact_id,
        deal_id=deal_id,
        status=status,
        due_date_start=due_date_start,
        due_date_end=due_date_end,
        limit=limit
    )


@mcp.tool()
async def get_task_details(
    task_id: str,
    properties: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Retrieve detailed information for a specific task.

    Args:
        task_id: The HubSpot task ID
        properties: Array of specific properties to retrieve (optional)

    Returns:
        Complete task object with all properties and associations
    """
    return await hubspot_client.get_task_details(task_id, properties)


@mcp.tool()
async def complete_task(
    task_id: str,
    completion_notes: Optional[str] = None,
    update_properties: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Complete a HubSpot task by updating its status to COMPLETED.

    Args:
        task_id: The HubSpot task ID to complete
        completion_notes: Optional completion notes to add to the task body (optional)
        update_properties: Additional properties to update alongside completion (optional)

    Returns:
        Updated task object with COMPLETED status and confirmation of completion

    Examples:
        - Simple completion: task_id="123456789"
        - With notes: task_id="123456789", completion_notes="Called client, discussed requirements"
        - With additional updates: task_id="123456789", update_properties={"hs_task_priority": "LOW"}
    """
    return await hubspot_client.complete_task(task_id, completion_notes, update_properties)


@mcp.tool()
async def get_deal_meetings(
    deal_id: str,
    limit: int = 100,
    outcome_filter: Optional[str] = None,
    exclude_calendly: bool = False,
    sort_direction: str = "DESCENDING"
) -> Dict[str, Any]:
    """
    Retrieve meetings associated with a specific deal with optional filtering.

    Args:
        deal_id: The HubSpot deal ID to get meetings for
        limit: Number of meetings to retrieve (default: 100)
        outcome_filter: Filter by meeting outcome - use "COMPLETED" for completed meetings,
                       "SCHEDULED" for scheduled meetings, etc. (optional)
        exclude_calendly: Set to true to filter out automated Calendly/booking system meetings (optional)
        sort_direction: Sort by meeting start time - "DESCENDING" for most recent first, "ASCENDING" for oldest first (default: "DESCENDING")

    Returns:
        Collection of meetings with complete meeting details, including titles, descriptions,
        start/end times, outcomes, and attendee information. When filtering is applied,
        only meetings matching the criteria are returned for more efficient "real" meeting analysis.

    Examples:
        - Get only completed meetings: outcome_filter="COMPLETED"
        - Get completed meetings excluding Calendly: outcome_filter="COMPLETED", exclude_calendly=true
        - Exclude automated bookings: exclude_calendly=true
    """
    return await hubspot_client.get_deal_meetings(deal_id, limit, outcome_filter, exclude_calendly, sort_direction)


@mcp.tool()
async def get_overdue_tasks(
    owner_id: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Efficiently retrieve overdue tasks by filtering for NOT_STARTED/IN_PROGRESS status with due dates before current time.

    IMPORTANT: When user asks for "my overdue tasks" or "overdue tasks", first use HubSpot:get_user_details
    to get their HubSpot owner ID, then pass it as owner_id parameter to filter results efficiently.

    Args:
        owner_id: Filter overdue tasks by owner - RECOMMENDED: Get from HubSpot:get_user_details first
        limit: Number of overdue tasks to retrieve (default: 100)

    Returns:
        Collection of overdue tasks with titles, descriptions, status, priority, due dates,
        and calculated overdue days. Only returns tasks that are actually overdue.
    """
    return await hubspot_client.get_overdue_tasks(owner_id, limit)


@mcp.tool()
async def search_meetings(
    search_term: str,
    limit: int = 10,
    sort_direction: str = "DESCENDING"
) -> Dict[str, Any]:
    """
    Search for meetings where customers mentioned specific tools or topics in the meeting description.
    Useful for product team research to understand customer interests and needs.

    Args:
        search_term: The term to search for in meeting descriptions (e.g., "MISP", "Slack", "API integration")
        limit: Number of meetings to retrieve (default: 10, max: 100)
        sort_direction: Sort by meeting start time - "DESCENDING" for most recent first, "ASCENDING" for oldest first (default: "DESCENDING")

    Returns:
        Collection of meetings containing the search term with title, description, start time, and outcome

    Examples:
        - Find mentions of a competitor: search_term="MISP"
        - Research feature requests: search_term="API integration"
        - Track product discussions: search_term="automation"
    """
    return await hubspot_client.search_meetings(search_term, limit, sort_direction)


if __name__ == "__main__":
    mcp.run()