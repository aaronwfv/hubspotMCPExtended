"""
HubSpot API Client for MCP Server
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx
import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


class HubSpotError(Exception):
    """Base exception for HubSpot API errors."""

    def __init__(self, message: str, category: str = "UNKNOWN", status_code: Optional[int] = None):
        self.message = message
        self.category = category
        self.status_code = status_code
        super().__init__(message)


class HubSpotClient:
    """HubSpot API client with authentication and error handling."""

    def __init__(self):
        self.access_token = os.getenv("HUBSPOT_ACCESS_TOKEN")
        if not self.access_token:
            raise ValueError("HUBSPOT_ACCESS_TOKEN environment variable is required")

        self.base_url = "https://api.hubapi.com"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        # Initialize HTTP client with timeouts and retry logic
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers=self.headers
        )

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        retries: int = 3
    ) -> Dict[str, Any]:
        """Make authenticated request to HubSpot API with error handling and retries."""
        url = f"{self.base_url}{endpoint}"

        for attempt in range(retries + 1):
            try:
                if method.upper() == "GET":
                    response = await self.client.get(url, params=params)
                elif method.upper() == "POST":
                    response = await self.client.post(url, json=data, params=params)
                elif method.upper() == "PATCH":
                    response = await self.client.patch(url, json=data, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Handle rate limiting with exponential backoff
                if response.status_code == 429:
                    if attempt < retries:
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limited, retrying in {wait_time}s", attempt=attempt + 1)
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise HubSpotError(
                            "Rate limit exceeded after retries",
                            "RATE_LIMIT",
                            429
                        )

                # Handle other HTTP errors
                if response.status_code == 401:
                    raise HubSpotError(
                        "Invalid or expired access token",
                        "AUTHENTICATION",
                        401
                    )
                elif response.status_code == 403:
                    raise HubSpotError(
                        "Insufficient permissions for this operation",
                        "AUTHENTICATION",
                        403
                    )
                elif response.status_code == 404:
                    raise HubSpotError(
                        "Resource not found",
                        "NOT_FOUND",
                        404
                    )
                elif response.status_code >= 500:
                    if attempt < retries:
                        wait_time = 2 ** attempt
                        logger.warning(f"Server error, retrying in {wait_time}s", attempt=attempt + 1)
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise HubSpotError(
                            "HubSpot API server error",
                            "SERVER_ERROR",
                            response.status_code
                        )
                elif not response.is_success:
                    error_data = response.json() if response.content else {}
                    raise HubSpotError(
                        error_data.get("message", f"HTTP {response.status_code}"),
                        "VALIDATION_ERROR",
                        response.status_code
                    )

                # Success - return JSON response
                return response.json()

            except httpx.RequestError as e:
                if attempt < retries:
                    wait_time = 2 ** attempt
                    logger.warning(f"Request error, retrying in {wait_time}s", error=str(e), attempt=attempt + 1)
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise HubSpotError(f"Network error: {str(e)}", "NETWORK_ERROR")

    def _convert_iso_to_timestamp(self, iso_date: str) -> int:
        """Convert ISO date string to milliseconds timestamp."""
        try:
            dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1000)
        except ValueError:
            raise HubSpotError(f"Invalid date format: {iso_date}", "VALIDATION_ERROR")

    async def get_meeting_details(
        self,
        meeting_id: str,
        properties: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Retrieve complete meeting information."""
        logger.info("Getting meeting details", meeting_id=meeting_id)

        params = {}
        if properties:
            params["properties"] = ",".join(properties)

        endpoint = f"/crm/v3/objects/meetings/{meeting_id}"
        result = await self._make_request("GET", endpoint, params=params)

        logger.info("Retrieved meeting details", meeting_id=meeting_id)
        return result

    async def get_deal_notes(
        self,
        deal_id: str,
        limit: int = 100,
        sort_direction: str = "DESCENDING"
    ) -> Dict[str, Any]:
        """Retrieve all notes associated with a specific deal."""
        logger.info("Getting deal notes", deal_id=deal_id, limit=limit, sort_direction=sort_direction)

        # Get note associations for the deal using v4 associations API
        params = {"limit": limit}
        endpoint = f"/crm/v4/objects/deal/{deal_id}/associations/note"

        try:
            associations_result = await self._make_request("GET", endpoint, params=params)
        except HubSpotError as e:
            if e.status_code == 404:
                logger.info("Deal not found or no note associations", deal_id=deal_id)
                return {
                    "results": [],
                    "total": 0,
                    "deal_id": deal_id
                }
            raise

        # Extract note IDs from associations
        note_ids = []
        if "results" in associations_result:
            note_ids = [assoc["toObjectId"] for assoc in associations_result["results"]]

        # If no notes found, return empty result
        if not note_ids:
            logger.info("No notes found for deal", deal_id=deal_id)
            return {
                "results": [],
                "total": 0,
                "deal_id": deal_id
            }

        # Get detailed note information using search API for better sorting
        if note_ids:
            search_data = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "hs_object_id",
                                "operator": "IN",
                                "values": note_ids
                            }
                        ]
                    }
                ],
                "properties": [
                    "hs_note_body",
                    "hs_timestamp",
                    "hubspot_owner_id",
                    "hs_createdate",
                    "hs_lastmodifieddate"
                ],
                "sorts": [
                    {
                        "propertyName": "hs_timestamp",
                        "direction": sort_direction
                    }
                ],
                "limit": len(note_ids)
            }

            try:
                endpoint = "/crm/v3/objects/notes/search"
                search_result = await self._make_request("POST", endpoint, data=search_data)
                notes = search_result.get("results", [])
            except HubSpotError as e:
                logger.warning("Failed to use search API for notes, falling back to individual requests", error=str(e))
                # Fallback to individual requests
                notes = []
                properties = "hs_note_body,hs_timestamp,hubspot_owner_id,hs_createdate,hs_lastmodifieddate"
                for note_id in note_ids:
                    try:
                        endpoint = f"/crm/v3/objects/notes/{note_id}"
                        params = {"properties": properties}
                        note_details = await self._make_request("GET", endpoint, params=params)
                        notes.append(note_details)
                    except HubSpotError as e:
                        logger.warning("Failed to get note details", note_id=note_id, error=str(e))
                        continue
        else:
            notes = []

        result = {
            "results": notes,
            "total": len(notes),
            "deal_id": deal_id,
            "associations": associations_result
        }

        logger.info("Retrieved deal notes", deal_id=deal_id, count=len(notes))
        return result

    async def create_task(
        self,
        title: str,
        assigned_to_user_id: str,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        priority: Optional[str] = None,
        contact_id: Optional[str] = None,
        deal_id: Optional[str] = None,
        task_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new task with proper associations."""
        logger.info("Creating task", title=title, assigned_to=assigned_to_user_id)

        # Build task properties
        properties = {
            "hs_task_subject": title,
            "hs_task_status": "NOT_STARTED",
            "hubspot_owner_id": assigned_to_user_id,
        }

        if description:
            properties["hs_task_body"] = description
        if priority:
            properties["hs_task_priority"] = priority
        if task_type:
            properties["hs_task_type"] = task_type
        if due_date:
            properties["hs_timestamp"] = str(self._convert_iso_to_timestamp(due_date))

        # Build associations
        associations = []
        if contact_id:
            associations.append({
                "to": {"id": contact_id},
                "types": [{
                    "associationCategory": "HUBSPOT_DEFINED",
                    "associationTypeId": 204
                }]
            })

        if deal_id:
            associations.append({
                "to": {"id": deal_id},
                "types": [{
                    "associationCategory": "HUBSPOT_DEFINED",
                    "associationTypeId": 216
                }]
            })

        data = {
            "properties": properties,
            "associations": associations
        }

        endpoint = "/crm/v3/objects/tasks"
        result = await self._make_request("POST", endpoint, data=data)

        logger.info("Created task", task_id=result.get("id"), title=title)
        return result

    async def get_tasks(
        self,
        owner_id: Optional[str] = None,
        contact_id: Optional[str] = None,
        deal_id: Optional[str] = None,
        status: Optional[str] = None,
        due_date_start: Optional[str] = None,
        due_date_end: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Retrieve tasks with optional filtering including date ranges."""
        logger.info("Getting tasks", owner_id=owner_id, contact_id=contact_id, deal_id=deal_id, status=status, due_date_start=due_date_start, due_date_end=due_date_end)

        # Cap limit at 100 to avoid API errors
        if limit > 100:
            logger.warning("Limit capped at 100 due to API restrictions", requested_limit=limit)
            limit = 100

        # Build request body for search API
        search_data = {
            "filterGroups": [],
            "properties": [
                "hs_task_subject",
                "hs_task_body",
                "hs_task_status",
                "hs_task_priority",
                "hubspot_owner_id",
                "hs_task_type",
                "hs_timestamp",
                "hs_createdate",
                "hs_task_due_date"
            ],
            "limit": limit,
            "sorts": [
                {
                    "propertyName": "hs_timestamp",
                    "direction": "ASCENDING"
                }
            ]
        }

        # Build filter groups for search API
        if owner_id or status or due_date_start or due_date_end:
            filters = []
            if owner_id:
                filters.append({
                    "propertyName": "hubspot_owner_id",
                    "operator": "EQ",
                    "value": owner_id
                })
            if status:
                filters.append({
                    "propertyName": "hs_task_status",
                    "operator": "EQ",
                    "value": status
                })

            # Add date range filters
            if due_date_start:
                try:
                    start_ms = str(self._convert_iso_to_timestamp(due_date_start))
                    filters.append({
                        "propertyName": "hs_timestamp",
                        "operator": "GTE",
                        "value": start_ms
                    })
                except HubSpotError:
                    logger.warning("Invalid due_date_start format", due_date_start=due_date_start)

            if due_date_end:
                try:
                    end_ms = str(self._convert_iso_to_timestamp(due_date_end))
                    filters.append({
                        "propertyName": "hs_timestamp",
                        "operator": "LTE",
                        "value": end_ms
                    })
                except HubSpotError:
                    logger.warning("Invalid due_date_end format", due_date_end=due_date_end)

            if filters:
                search_data["filterGroups"].append({"filters": filters})

        logger.debug("Search request data", search_data=search_data)

        endpoint = "/crm/v3/objects/tasks/search"
        result = await self._make_request("POST", endpoint, data=search_data)

        # Post-filter by associations if needed
        if contact_id or deal_id:
            filtered_results = []
            if "results" in result:
                for task in result["results"]:
                    task_id = task["id"]
                    # Get task associations
                    assoc_endpoint = f"/crm/v3/objects/tasks/{task_id}/associations/contacts,deals"
                    try:
                        associations = await self._make_request("GET", assoc_endpoint)

                        match = True
                        if contact_id and not any(
                            assoc["id"] == contact_id
                            for assoc in associations.get("associations", {}).get("contacts", {}).get("results", [])
                        ):
                            match = False

                        if deal_id and not any(
                            assoc["id"] == deal_id
                            for assoc in associations.get("associations", {}).get("deals", {}).get("results", [])
                        ):
                            match = False

                        if match:
                            filtered_results.append(task)
                    except HubSpotError:
                        # Skip tasks we can't get associations for
                        continue

            result["results"] = filtered_results
            result["total"] = len(filtered_results)

        # Add overdue status to tasks
        if "results" in result:
            current_time = datetime.now().timestamp() * 1000  # Current time in milliseconds
            for task in result["results"]:
                task_props = task.get("properties", {})

                # Check if task has a due date and is overdue
                due_date = task_props.get("hs_task_due_date") or task_props.get("hs_timestamp")
                task["is_overdue"] = False
                task["overdue_days"] = 0

                if due_date and task_props.get("hs_task_status") not in ["COMPLETED", "DEFERRED"]:
                    try:
                        due_date_ms = int(due_date)
                        if current_time > due_date_ms:
                            task["is_overdue"] = True
                            # Calculate days overdue
                            overdue_ms = current_time - due_date_ms
                            task["overdue_days"] = int(overdue_ms / (24 * 60 * 60 * 1000))
                    except (ValueError, TypeError):
                        # Invalid date format, skip overdue calculation
                        pass

        logger.info("Retrieved tasks", count=len(result.get("results", [])),
                   overdue_count=len([t for t in result.get("results", []) if t.get("is_overdue", False)]))
        return result

    async def _enrich_tasks_with_associations(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enrich tasks with associated deal and contact details.

        For each task, fetches associations and then batch-fetches deal names
        and contact names to provide full context.
        """
        if not tasks:
            return tasks

        # Collect associations for each task
        task_associations: Dict[str, Dict[str, List[str]]] = {}
        all_deal_ids: set = set()
        all_contact_ids: set = set()

        for task in tasks:
            task_id = task.get("id")
            if not task_id:
                continue

            task_associations[task_id] = {"deal_ids": [], "contact_ids": []}

            # Fetch deal associations for this task
            try:
                deal_assoc_endpoint = f"/crm/v4/objects/task/{task_id}/associations/deal"
                deal_assoc_result = await self._make_request("GET", deal_assoc_endpoint)
                # Convert to strings for consistent lookup (batch read returns string IDs)
                deal_ids = [str(assoc["toObjectId"]) for assoc in deal_assoc_result.get("results", [])]
                task_associations[task_id]["deal_ids"] = deal_ids
                all_deal_ids.update(deal_ids)
            except HubSpotError as e:
                logger.warning("Failed to fetch deal associations for task", task_id=task_id, error=str(e))

            # Fetch contact associations for this task
            try:
                contact_assoc_endpoint = f"/crm/v4/objects/task/{task_id}/associations/contact"
                contact_assoc_result = await self._make_request("GET", contact_assoc_endpoint)
                # Convert to strings for consistent lookup (batch read returns string IDs)
                contact_ids = [str(assoc["toObjectId"]) for assoc in contact_assoc_result.get("results", [])]
                task_associations[task_id]["contact_ids"] = contact_ids
                all_contact_ids.update(contact_ids)
            except HubSpotError as e:
                logger.warning("Failed to fetch contact associations for task", task_id=task_id, error=str(e))

        # Batch fetch deal details
        deal_details: Dict[str, Dict[str, Any]] = {}
        if all_deal_ids:
            try:
                batch_data = {
                    "inputs": [{"id": deal_id} for deal_id in all_deal_ids],
                    "properties": ["dealname"]
                }
                endpoint = "/crm/v3/objects/deals/batch/read"
                batch_result = await self._make_request("POST", endpoint, data=batch_data)
                for deal in batch_result.get("results", []):
                    deal_id = deal.get("id")
                    deal_name = deal.get("properties", {}).get("dealname", "")
                    deal_details[deal_id] = {"id": deal_id, "name": deal_name}
            except HubSpotError as e:
                logger.warning("Failed to batch fetch deal details", error=str(e))

        # Batch fetch contact details
        contact_details: Dict[str, Dict[str, Any]] = {}
        if all_contact_ids:
            try:
                batch_data = {
                    "inputs": [{"id": contact_id} for contact_id in all_contact_ids],
                    "properties": ["firstname", "lastname", "email"]
                }
                endpoint = "/crm/v3/objects/contacts/batch/read"
                batch_result = await self._make_request("POST", endpoint, data=batch_data)
                for contact in batch_result.get("results", []):
                    contact_id = contact.get("id")
                    props = contact.get("properties", {})
                    firstname = props.get("firstname", "") or ""
                    lastname = props.get("lastname", "") or ""
                    name = f"{firstname} {lastname}".strip()
                    email = props.get("email", "")
                    contact_details[contact_id] = {"id": contact_id, "name": name, "email": email}
            except HubSpotError as e:
                logger.warning("Failed to batch fetch contact details", error=str(e))

        # Attach enriched associations to each task
        for task in tasks:
            task_id = task.get("id")
            if task_id and task_id in task_associations:
                assoc = task_associations[task_id]
                task["associations"] = {
                    "deals": [deal_details.get(did, {"id": did, "name": ""}) for did in assoc["deal_ids"]],
                    "contacts": [contact_details.get(cid, {"id": cid, "name": "", "email": ""}) for cid in assoc["contact_ids"]]
                }
            else:
                task["associations"] = {"deals": [], "contacts": []}

        logger.info("Enriched tasks with associations",
                   task_count=len(tasks),
                   deals_fetched=len(deal_details),
                   contacts_fetched=len(contact_details))
        return tasks

    async def get_overdue_tasks(
        self,
        owner_id: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Efficiently retrieve overdue tasks using API filters for status and due date."""
        logger.info("Getting overdue tasks", owner_id=owner_id)

        # Cap limit at 100 to avoid API errors
        if limit > 100:
            logger.warning("Limit capped at 100 due to API restrictions", requested_limit=limit)
            limit = 100

        # Get current time in milliseconds
        current_time_ms = int(datetime.now().timestamp() * 1000)

        # Build search data with filters for overdue tasks
        search_data = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "hs_task_status",
                            "operator": "IN",
                            "values": ["NOT_STARTED", "IN_PROGRESS"]
                        },
                        {
                            "propertyName": "hs_timestamp",
                            "operator": "LT",
                            "value": str(current_time_ms)
                        }
                    ]
                }
            ],
            "properties": [
                "hs_task_subject",
                "hs_task_body",
                "hs_task_status",
                "hs_task_priority",
                "hubspot_owner_id",
                "hs_task_type",
                "hs_timestamp",
                "hs_createdate",
                "hs_task_due_date"
            ],
            "limit": limit,
            "sorts": [
                {
                    "propertyName": "hs_timestamp",
                    "direction": "ASCENDING"
                }
            ]
        }

        # Add owner filter if specified
        if owner_id:
            search_data["filterGroups"][0]["filters"].append({
                "propertyName": "hubspot_owner_id",
                "operator": "EQ",
                "value": owner_id
            })

        logger.debug("Overdue tasks search request", search_data=search_data)

        endpoint = "/crm/v3/objects/tasks/search"
        result = await self._make_request("POST", endpoint, data=search_data)

        # Add overdue calculations to results
        if "results" in result:
            for task in result["results"]:
                task_props = task.get("properties", {})
                due_date = task_props.get("hs_task_due_date") or task_props.get("hs_timestamp")
                task["is_overdue"] = True  # All results should be overdue by definition
                task["overdue_days"] = 0

                if due_date:
                    try:
                        due_date_ms = int(due_date)
                        overdue_ms = current_time_ms - due_date_ms
                        task["overdue_days"] = int(overdue_ms / (24 * 60 * 60 * 1000))
                    except (ValueError, TypeError):
                        pass

        # Enrich tasks with association details (deal names, contact names)
        if result.get("results"):
            result["results"] = await self._enrich_tasks_with_associations(result["results"])

        logger.info("Retrieved overdue tasks", count=len(result.get("results", [])))
        return result

    async def get_task_details(
        self,
        task_id: str,
        properties: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Retrieve detailed information for a specific task."""
        logger.info("Getting task details", task_id=task_id)

        params = {}
        if properties:
            params["properties"] = ",".join(properties)

        endpoint = f"/crm/v3/objects/tasks/{task_id}"
        result = await self._make_request("GET", endpoint, params=params)

        logger.info("Retrieved task details", task_id=task_id)
        return result

    async def complete_task(
        self,
        task_id: str,
        completion_notes: Optional[str] = None,
        update_properties: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Complete a task by updating its status to COMPLETED.

        Args:
            task_id: The HubSpot task ID to complete
            completion_notes: Optional notes to add to the task body (optional)
            update_properties: Additional properties to update alongside completion (optional)

        Returns:
            Updated task object with COMPLETED status
        """
        logger.info("Completing task", task_id=task_id)

        # Build properties to update
        properties = {
            "hs_task_status": "COMPLETED"
        }

        # Add completion notes to task body if provided
        if completion_notes:
            properties["hs_task_body"] = completion_notes

        # Add any additional properties to update
        if update_properties:
            properties.update(update_properties)

        data = {
            "properties": properties
        }

        endpoint = f"/crm/v3/objects/tasks/{task_id}"
        result = await self._make_request("PATCH", endpoint, data=data)

        logger.info("Completed task", task_id=task_id, status=result.get("properties", {}).get("hs_task_status"))
        return result

    async def update_task(
        self,
        task_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to_user_id: Optional[str] = None,
        due_date: Optional[str] = None,
        task_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update an existing task with new property values.

        Args:
            task_id: The HubSpot task ID to update (required)
            title: New task title (optional)
            description: New task description/body (optional)
            status: Task status - NOT_STARTED, IN_PROGRESS, COMPLETED, WAITING, DEFERRED (optional)
            priority: Task priority - HIGH, MEDIUM, or LOW (optional)
            assigned_to_user_id: HubSpot user ID to reassign task to (optional)
            due_date: New due date in ISO format (optional)
            task_type: Type of task - TODO, CALL, EMAIL, etc. (optional)

        Returns:
            Updated task object with new property values

        Examples:
            - Update title: task_id="123", title="Updated title"
            - Change priority and status: task_id="123", priority="HIGH", status="IN_PROGRESS"
            - Reassign task: task_id="123", assigned_to_user_id="456"
        """
        logger.info("Updating task", task_id=task_id)

        # Build properties to update
        properties = {}

        if title is not None:
            properties["hs_task_subject"] = title
        if description is not None:
            properties["hs_task_body"] = description
        if status is not None:
            properties["hs_task_status"] = status
        if priority is not None:
            properties["hs_task_priority"] = priority
        if assigned_to_user_id is not None:
            properties["hubspot_owner_id"] = assigned_to_user_id
        if task_type is not None:
            properties["hs_task_type"] = task_type
        if due_date is not None:
            properties["hs_timestamp"] = str(self._convert_iso_to_timestamp(due_date))

        # Ensure we have at least one property to update
        if not properties:
            raise HubSpotError("At least one property must be provided to update", "VALIDATION_ERROR")

        data = {
            "properties": properties
        }

        endpoint = f"/crm/v3/objects/tasks/{task_id}"
        result = await self._make_request("PATCH", endpoint, data=data)

        logger.info("Updated task", task_id=task_id, updated_properties=list(properties.keys()))
        return result

    async def get_deal_meetings(
        self,
        deal_id: str,
        limit: int = 100,
        outcome_filter: Optional[str] = None,
        exclude_calendly: bool = False,
        sort_direction: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieve meetings associated with a specific deal with optional filtering.

        Args:
            deal_id: The HubSpot deal ID
            limit: Number of meetings to retrieve (default: 100)
            outcome_filter: Filter by meeting outcome (e.g., "COMPLETED", "SCHEDULED", "NO_SHOW", "CANCELED")
            exclude_calendly: If True, attempts to filter out automated Calendly meetings
            sort_direction: Sort direction for meeting start time - "DESCENDING" or "ASCENDING" (default: "DESCENDING")
        """
        # Default to DESCENDING (most recent first) if not specified
        if not sort_direction:
            sort_direction = "DESCENDING"

        logger.info("Getting deal meetings", deal_id=deal_id, limit=limit, outcome_filter=outcome_filter, exclude_calendly=exclude_calendly, sort_direction=sort_direction)

        # Get ALL meeting associations for the deal first (we'll filter/limit after sorting)
        # Use a high limit to get all meetings, then we can filter and sort properly
        params = {"limit": 500}  # Get all meetings first, then filter/sort
        endpoint = f"/crm/v4/objects/deal/{deal_id}/associations/meeting"
        associations_result = await self._make_request("GET", endpoint, params=params)

        # Extract meeting IDs from associations
        meeting_ids = []
        if "results" in associations_result:
            meeting_ids = [assoc["toObjectId"] for assoc in associations_result["results"]]

        # If no meetings found, return empty result
        if not meeting_ids:
            logger.info("No meetings found for deal", deal_id=deal_id)
            return {
                "results": [],
                "total": 0,
                "deal_id": deal_id
            }

        # Always use filtered meetings path to ensure proper sorting
        # (The search API allows us to sort, while batch API does not)
        meetings = await self._get_filtered_meetings(meeting_ids, outcome_filter, exclude_calendly, sort_direction)

        # Apply the limit AFTER filtering and sorting to get the top N results
        limited_meetings = meetings[:limit] if limit else meetings

        result = {
            "results": limited_meetings,
            "total": len(limited_meetings),
            "deal_id": deal_id,
            "associations": associations_result
        }

        logger.info("Retrieved deal meetings", deal_id=deal_id, count=len(meetings))
        return result

    async def _get_filtered_meetings(
        self,
        meeting_ids: List[str],
        outcome_filter: Optional[str] = None,
        exclude_calendly: bool = False,
        sort_direction: str = "DESCENDING"
    ) -> List[Dict[str, Any]]:
        """Filter meetings using the search API for better performance."""
        if not meeting_ids:
            return []

        # Build search filters
        filters = [
            {
                "propertyName": "hs_object_id",
                "operator": "IN",
                "values": meeting_ids
            }
        ]

        # Add outcome filter
        if outcome_filter:
            filters.append({
                "propertyName": "hs_meeting_outcome",
                "operator": "EQ",
                "value": outcome_filter
            })

        # Build search request
        search_data = {
            "filterGroups": [{"filters": filters}],
            "properties": [
                "hs_meeting_title",
                "hs_meeting_body",
                "hs_meeting_start_time",
                "hs_meeting_end_time",
                "hs_meeting_outcome",
                "hs_meeting_location",
                "hs_meeting_external_url",
                "hs_activity_type",
                "hs_timestamp",
                "hs_createdate",
                "hs_lastmodifieddate",
                "hubspot_owner_id"
            ],
            "limit": len(meeting_ids),
            "sorts": [
                {
                    "propertyName": "hs_meeting_start_time",
                    "direction": sort_direction
                }
            ]
        }

        try:
            endpoint = "/crm/v3/objects/meetings/search"
            logger.debug("Search API request",
                        endpoint=endpoint,
                        filter_count=len(filters),
                        has_outcome_filter=bool(outcome_filter),
                        meeting_ids_count=len(meeting_ids))
            search_result = await self._make_request("POST", endpoint, data=search_data)
            meetings = search_result.get("results", [])
            logger.debug("Search API response",
                        returned_count=len(meetings),
                        total_meeting_ids=len(meeting_ids))

            # Additional filtering for Calendly meetings if requested
            if exclude_calendly:
                meetings = self._filter_calendly_meetings(meetings)

            # Client-side sort as fallback to ensure correct ordering
            meetings = self._sort_meetings_by_start_time(meetings, sort_direction)

            return meetings

        except HubSpotError as e:
            logger.warning("Failed to use search API for meeting filtering, falling back to individual requests", error=str(e))

            # Fallback to individual meeting requests
            meetings = []
            for meeting_id in meeting_ids:
                try:
                    meeting_details = await self.get_meeting_details(meeting_id)

                    # Apply filters manually
                    if outcome_filter:
                        meeting_outcome = meeting_details.get("properties", {}).get("hs_meeting_outcome")
                        if meeting_outcome != outcome_filter:
                            continue

                    if exclude_calendly and self._is_calendly_meeting(meeting_details):
                        continue

                    meetings.append(meeting_details)

                except HubSpotError:
                    continue

            # Client-side sort for fallback path
            meetings = self._sort_meetings_by_start_time(meetings, sort_direction)

            return meetings

    def _filter_calendly_meetings(self, meetings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out likely Calendly/automated meetings based on various indicators."""
        filtered_meetings = []

        for meeting in meetings:
            if self._is_calendly_meeting(meeting):
                logger.debug("Filtering out potential Calendly meeting", meeting_id=meeting.get("id"))
                continue
            filtered_meetings.append(meeting)

        return filtered_meetings

    def _is_calendly_meeting(self, meeting: Dict[str, Any]) -> bool:
        """Determine if a meeting is likely from Calendly or other automated booking systems."""
        props = meeting.get("properties", {})

        # Check external URL for Calendly indicators
        # FIXED: Use (value or "") pattern to handle None values
        external_url = (props.get("hs_meeting_external_url") or "").lower()
        if "calendly.com" in external_url:
            return True

        # Check meeting title for Calendly patterns
        title = (props.get("hs_meeting_title") or "").lower()
        calendly_patterns = [
            "calendly",
            "quick call",
            "discovery call",
            "15 minute",
            "30 minute",
            "book a time",
            "schedule a call"
        ]

        if any(pattern in title for pattern in calendly_patterns):
            return True

        # Check location for virtual meeting indicators that might be automated
        location = (props.get("hs_meeting_location") or "").lower()
        if location and any(indicator in location for indicator in ["calendly", "automated", "zoom.us/j/"]):
            return True

        return False

    def _sort_meetings_by_start_time(self, meetings: List[Dict[str, Any]], sort_direction: str) -> List[Dict[str, Any]]:
        """Sort meetings by start time, handling null values properly."""
        def get_start_time(meeting: Dict[str, Any]) -> int:
            """Extract start time as milliseconds, defaulting to 0 for null values."""
            props = meeting.get("properties", {})
            start_time = props.get("hs_meeting_start_time")
            if start_time:
                try:
                    return int(start_time)
                except (ValueError, TypeError):
                    pass
            return 0

        # Sort with reverse=True for DESCENDING (most recent first)
        sorted_meetings = sorted(meetings, key=get_start_time, reverse=(sort_direction == "DESCENDING"))

        # Log first and last meeting for debugging
        if sorted_meetings:
            first_meeting = sorted_meetings[0]
            last_meeting = sorted_meetings[-1]
            logger.debug("Sorted meetings",
                        sort_direction=sort_direction,
                        first_meeting_time=first_meeting.get("properties", {}).get("hs_meeting_start_time"),
                        last_meeting_time=last_meeting.get("properties", {}).get("hs_meeting_start_time"),
                        total_count=len(sorted_meetings))

        return sorted_meetings

    async def _get_meetings_batch(self, meeting_ids: List[str]) -> List[Dict[str, Any]]:
        """Get meeting details using the batch API for better efficiency."""
        if not meeting_ids:
            return []

        meetings = []
        batch_size = 100  # HubSpot limit for batch read

        # Process meetings in batches of 100
        for i in range(0, len(meeting_ids), batch_size):
            batch_ids = meeting_ids[i:i + batch_size]

            # Build batch request
            batch_data = {
                "inputs": [{"id": meeting_id} for meeting_id in batch_ids],
                "properties": [
                    "hs_meeting_title",
                    "hs_meeting_body",
                    "hs_meeting_start_time",
                    "hs_meeting_end_time",
                    "hs_meeting_outcome",
                    "hs_meeting_location",
                    "hs_meeting_external_url",
                    "hs_activity_type",
                    "hs_timestamp",
                    "hs_createdate",
                    "hs_lastmodifieddate",
                    "hubspot_owner_id"
                ]
            }

            try:
                endpoint = "/crm/v3/objects/meetings/batch/read"
                batch_result = await self._make_request("POST", endpoint, data=batch_data)

                if "results" in batch_result:
                    meetings.extend(batch_result["results"])

                # Log any errors from the batch
                if "errors" in batch_result:
                    for error in batch_result["errors"]:
                        logger.warning("Batch read error for meeting",
                                     meeting_id=error.get("id"),
                                     error=error.get("message"))

            except HubSpotError as e:
                logger.warning("Batch API failed, falling back to individual requests",
                             batch_size=len(batch_ids), error=str(e))

                # Fallback to individual meeting requests for this batch
                for meeting_id in batch_ids:
                    try:
                        meeting_details = await self.get_meeting_details(meeting_id)
                        meetings.append(meeting_details)
                    except HubSpotError:
                        # Skip meetings we can't access
                        continue

        logger.info("Retrieved meetings via batch API",
                   requested_count=len(meeting_ids),
                   retrieved_count=len(meetings))

        return meetings

    async def search_meetings(
        self,
        search_term: str,
        limit: int = 10,
        sort_direction: str = "DESCENDING"
    ) -> Dict[str, Any]:
        """
        Search for meetings by content in the meeting description.

        Args:
            search_term: The term to search for in meeting descriptions
            limit: Number of meetings to retrieve (default: 10, max: 100)
            sort_direction: Sort direction for meeting start time - "DESCENDING" or "ASCENDING" (default: "DESCENDING")

        Returns:
            Collection of meetings matching the search term with title, description, and start time
        """
        logger.info("Searching meetings", search_term=search_term, limit=limit)

        # Cap limit at 100 to avoid API errors
        if limit > 100:
            logger.warning("Limit capped at 100 due to API restrictions", requested_limit=limit)
            limit = 100

        # Build search payload
        search_data = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "hs_meeting_body",
                            "operator": "CONTAINS_TOKEN",
                            "value": search_term
                        }
                    ]
                }
            ],
            "properties": [
                "hs_meeting_title",
                "hs_meeting_body",
                "hs_meeting_start_time",
                "hs_meeting_end_time",
                "hs_meeting_outcome",
                "hs_meeting_location",
                "hs_timestamp",
                "hubspot_owner_id"
            ],
            "sorts": [
                {
                    "propertyName": "hs_meeting_start_time",
                    "direction": sort_direction
                }
            ],
            "limit": limit
        }

        endpoint = "/crm/v3/objects/meetings/search"
        result = await self._make_request("POST", endpoint, data=search_data)

        logger.info("Found meetings", search_term=search_term, count=len(result.get("results", [])))
        return result

    async def search_deals_by_name(
        self,
        deal_name: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for deals by name using fuzzy matching.

        Args:
            deal_name: The deal name to search for
            limit: Number of results to return (default: 10)

        Returns:
            Collection of matching deals sorted by most recently modified
        """
        logger.info("Searching deals by name", deal_name=deal_name, limit=limit)

        search_data = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "dealname",
                            "operator": "CONTAINS_TOKEN",
                            "value": deal_name
                        }
                    ]
                }
            ],
            "properties": [
                "dealname",
                "dealstage",
                "amount",
                "closedate",
                "pipeline",
                "hs_lastmodifieddate",
                "hs_createdate",
                "hubspot_owner_id"
            ],
            "sorts": [
                {
                    "propertyName": "hs_lastmodifieddate",
                    "direction": "DESCENDING"
                }
            ],
            "limit": limit
        }

        endpoint = "/crm/v3/objects/deals/search"
        result = await self._make_request("POST", endpoint, data=search_data)

        logger.info("Found deals by name", deal_name=deal_name, count=len(result.get("results", [])))
        return result

    async def search_contacts(
        self,
        contact_name: Optional[str] = None,
        contact_email: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search for contacts by name or email.

        Args:
            contact_name: Contact name to search for (searches firstname and lastname)
            contact_email: Contact email to search for (exact match)
            limit: Number of results to return (default: 10)

        Returns:
            Collection of matching contacts sorted by most recently modified
        """
        logger.info("Searching contacts", contact_name=contact_name, contact_email=contact_email, limit=limit)

        filters = []

        if contact_email:
            # Exact match for email
            filters.append({
                "propertyName": "email",
                "operator": "EQ",
                "value": contact_email
            })
        elif contact_name:
            # Use query parameter for name search across multiple fields
            search_data = {
                "query": contact_name,
                "properties": [
                    "firstname",
                    "lastname",
                    "email",
                    "phone",
                    "company",
                    "hs_lastmodifieddate",
                    "hs_createdate",
                    "hubspot_owner_id"
                ],
                "sorts": [
                    {
                        "propertyName": "hs_lastmodifieddate",
                        "direction": "DESCENDING"
                    }
                ],
                "limit": limit
            }

            endpoint = "/crm/v3/objects/contacts/search"
            result = await self._make_request("POST", endpoint, data=search_data)

            logger.info("Found contacts by name", contact_name=contact_name, count=len(result.get("results", [])))
            return result

        # Email search path
        search_data = {
            "filterGroups": [{"filters": filters}],
            "properties": [
                "firstname",
                "lastname",
                "email",
                "phone",
                "company",
                "hs_lastmodifieddate",
                "hs_createdate",
                "hubspot_owner_id"
            ],
            "sorts": [
                {
                    "propertyName": "hs_lastmodifieddate",
                    "direction": "DESCENDING"
                }
            ],
            "limit": limit
        }

        endpoint = "/crm/v3/objects/contacts/search"
        result = await self._make_request("POST", endpoint, data=search_data)

        logger.info("Found contacts by email", contact_email=contact_email, count=len(result.get("results", [])))
        return result

    async def get_tasks_for_deal(
        self,
        deal_id: Optional[str] = None,
        deal_name: Optional[str] = None,
        include_completed: bool = False,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get tasks associated with a deal, with optional fuzzy name matching.

        Args:
            deal_id: The HubSpot deal ID (optional if deal_name provided)
            deal_name: Deal name to search for (optional if deal_id provided)
            include_completed: Include completed tasks (default: False)
            limit: Number of tasks to retrieve (default: 100)

        Returns:
            Collection of tasks associated with the deal, including deal information
        """
        logger.info("Getting tasks for deal", deal_id=deal_id, deal_name=deal_name, include_completed=include_completed)

        # If deal_name provided, search for the deal first
        if not deal_id and deal_name:
            deals_result = await self.search_deals_by_name(deal_name, limit=5)
            deals = deals_result.get("results", [])

            if not deals:
                logger.info("No deals found matching name", deal_name=deal_name)
                return {
                    "results": [],
                    "total": 0,
                    "deal_info": None,
                    "message": f"No deals found matching '{deal_name}'"
                }

            # Take the most recently modified deal (first result)
            deal_id = deals[0]["id"]
            deal_info = deals[0]
            logger.info("Found matching deal", deal_id=deal_id, deal_name=deal_info.get("properties", {}).get("dealname"))
        elif deal_id:
            # Get deal info for context
            try:
                endpoint = f"/crm/v3/objects/deals/{deal_id}"
                params = {"properties": "dealname,dealstage,amount,closedate,pipeline,hs_lastmodifieddate"}
                deal_info = await self._make_request("GET", endpoint, params=params)
            except HubSpotError as e:
                logger.warning("Failed to get deal info", deal_id=deal_id, error=str(e))
                deal_info = {"id": deal_id}
        else:
            raise HubSpotError("Either deal_id or deal_name must be provided", "VALIDATION_ERROR")

        # Build task search filters
        filters = [
            {
                "propertyName": "associations.deal",
                "operator": "EQ",
                "value": deal_id
            }
        ]

        # Filter out completed tasks unless requested
        if not include_completed:
            filters.append({
                "propertyName": "hs_task_status",
                "operator": "NEQ",
                "value": "COMPLETED"
            })

        search_data = {
            "filterGroups": [{"filters": filters}],
            "properties": [
                "hs_task_subject",
                "hs_task_body",
                "hs_task_status",
                "hs_task_priority",
                "hubspot_owner_id",
                "hs_task_type",
                "hs_timestamp",
                "hs_createdate",
                "hs_task_due_date"
            ],
            "sorts": [
                {
                    "propertyName": "hs_timestamp",
                    "direction": "ASCENDING"
                }
            ],
            "limit": min(limit, 100)
        }

        endpoint = "/crm/v3/objects/tasks/search"
        result = await self._make_request("POST", endpoint, data=search_data)

        # Add overdue status to tasks
        if "results" in result:
            current_time = datetime.now().timestamp() * 1000
            for task in result["results"]:
                task_props = task.get("properties", {})
                due_date = task_props.get("hs_task_due_date") or task_props.get("hs_timestamp")
                task["is_overdue"] = False
                task["overdue_days"] = 0

                if due_date and task_props.get("hs_task_status") not in ["COMPLETED", "DEFERRED"]:
                    try:
                        due_date_ms = int(due_date)
                        if current_time > due_date_ms:
                            task["is_overdue"] = True
                            overdue_ms = current_time - due_date_ms
                            task["overdue_days"] = int(overdue_ms / (24 * 60 * 60 * 1000))
                    except (ValueError, TypeError):
                        pass

        result["deal_info"] = deal_info
        result["total"] = len(result.get("results", []))

        logger.info("Retrieved tasks for deal", deal_id=deal_id, count=result["total"])
        return result

    async def get_tasks_for_contact(
        self,
        contact_id: Optional[str] = None,
        contact_name: Optional[str] = None,
        contact_email: Optional[str] = None,
        include_completed: bool = False,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get tasks associated with a contact, with optional name/email matching.

        Args:
            contact_id: The HubSpot contact ID (optional if contact_name/email provided)
            contact_name: Contact name to search for (optional if contact_id provided)
            contact_email: Contact email to search for (optional if contact_id provided)
            include_completed: Include completed tasks (default: False)
            limit: Number of tasks to retrieve (default: 100)

        Returns:
            Collection of tasks associated with the contact, including contact information
        """
        logger.info("Getting tasks for contact", contact_id=contact_id, contact_name=contact_name,
                   contact_email=contact_email, include_completed=include_completed)

        # If contact_name or contact_email provided, search for the contact first
        if not contact_id and (contact_name or contact_email):
            contacts_result = await self.search_contacts(contact_name=contact_name, contact_email=contact_email, limit=5)
            contacts = contacts_result.get("results", [])

            if not contacts:
                search_term = contact_email or contact_name
                logger.info("No contacts found matching search", search_term=search_term)
                return {
                    "results": [],
                    "total": 0,
                    "contact_info": None,
                    "message": f"No contacts found matching '{search_term}'"
                }

            # Take the most recently modified contact (first result)
            contact_id = contacts[0]["id"]
            contact_info = contacts[0]
            logger.info("Found matching contact", contact_id=contact_id,
                       email=contact_info.get("properties", {}).get("email"))
        elif contact_id:
            # Get contact info for context
            try:
                endpoint = f"/crm/v3/objects/contacts/{contact_id}"
                params = {"properties": "firstname,lastname,email,phone,company,hs_lastmodifieddate"}
                contact_info = await self._make_request("GET", endpoint, params=params)
            except HubSpotError as e:
                logger.warning("Failed to get contact info", contact_id=contact_id, error=str(e))
                contact_info = {"id": contact_id}
        else:
            raise HubSpotError("Either contact_id, contact_name, or contact_email must be provided", "VALIDATION_ERROR")

        # Build task search filters
        filters = [
            {
                "propertyName": "associations.contact",
                "operator": "EQ",
                "value": contact_id
            }
        ]

        # Filter out completed tasks unless requested
        if not include_completed:
            filters.append({
                "propertyName": "hs_task_status",
                "operator": "NEQ",
                "value": "COMPLETED"
            })

        search_data = {
            "filterGroups": [{"filters": filters}],
            "properties": [
                "hs_task_subject",
                "hs_task_body",
                "hs_task_status",
                "hs_task_priority",
                "hubspot_owner_id",
                "hs_task_type",
                "hs_timestamp",
                "hs_createdate",
                "hs_task_due_date"
            ],
            "sorts": [
                {
                    "propertyName": "hs_timestamp",
                    "direction": "ASCENDING"
                }
            ],
            "limit": min(limit, 100)
        }

        endpoint = "/crm/v3/objects/tasks/search"
        result = await self._make_request("POST", endpoint, data=search_data)

        # Add overdue status to tasks
        if "results" in result:
            current_time = datetime.now().timestamp() * 1000
            for task in result["results"]:
                task_props = task.get("properties", {})
                due_date = task_props.get("hs_task_due_date") or task_props.get("hs_timestamp")
                task["is_overdue"] = False
                task["overdue_days"] = 0

                if due_date and task_props.get("hs_task_status") not in ["COMPLETED", "DEFERRED"]:
                    try:
                        due_date_ms = int(due_date)
                        if current_time > due_date_ms:
                            task["is_overdue"] = True
                            overdue_ms = current_time - due_date_ms
                            task["overdue_days"] = int(overdue_ms / (24 * 60 * 60 * 1000))
                    except (ValueError, TypeError):
                        pass

        result["contact_info"] = contact_info
        result["total"] = len(result.get("results", []))

        logger.info("Retrieved tasks for contact", contact_id=contact_id, count=result["total"])
        return result

    async def create_meeting(
        self,
        title: str,
        start_time: str,
        end_time: Optional[str] = None,
        description: Optional[str] = None,
        owner_id: Optional[str] = None,
        outcome: Optional[str] = None,
        location: Optional[str] = None,
        contact_ids: Optional[List[str]] = None,
        deal_ids: Optional[List[str]] = None,
        meeting_type: Optional[str] = "Workshop",  # Changed from None to "Workshop"
        internal_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new meeting with associations to contacts and deals.

        Args:
            title: Meeting title/name (required)
            start_time: Meeting start time in ISO format (required)
            end_time: Meeting end time in ISO format (optional)
            description: Meeting description/body (optional)
            owner_id: HubSpot owner ID for the meeting creator (optional)
            outcome: Meeting outcome - SCHEDULED, COMPLETED, RESCHEDULED, NO_SHOW, CANCELED (optional)
            location: Meeting location - physical address, conference room, or call details (optional)
            contact_ids: List of contact IDs to associate with the meeting (optional)
            deal_ids: List of deal IDs to associate with the meeting (optional)
            meeting_type: Type of meeting - must match a configured type in HubSpot. 
                        Valid option: "Workshop". 
                        Defaults to "Workshop" if not specified.
            internal_notes: Internal team notes about the meeting (optional)

        Returns:
            Created meeting object with ID and all properties
        """
        logger.info("Creating meeting", title=title, start_time=start_time)

        # Convert ISO date to timestamp (milliseconds)
        timestamp_ms = self._convert_iso_to_timestamp(start_time)

        # Build meeting properties
        properties = {
            "hs_timestamp": str(timestamp_ms),
            "hs_meeting_start_time": str(timestamp_ms),
            "hs_meeting_title": title,
        }

        if end_time:
            end_timestamp_ms = self._convert_iso_to_timestamp(end_time)
            properties["hs_meeting_end_time"] = str(end_timestamp_ms)

        if description:
            properties["hs_meeting_body"] = description

        if owner_id:
            properties["hubspot_owner_id"] = owner_id

        if outcome:
            properties["hs_meeting_outcome"] = outcome

        if location:
            properties["hs_meeting_location"] = location

        if meeting_type:
            properties["hs_activity_type"] = meeting_type

        if internal_notes:
            properties["hs_internal_meeting_notes"] = internal_notes

        # Build associations
        associations = []

        # Associate with contacts
        if contact_ids:
            for contact_id in contact_ids:
                associations.append({
                    "to": {"id": contact_id},
                    "types": [{
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": 200  # Meeting to contact association
                    }]
                })

        # Associate with deals
        if deal_ids:
            for deal_id in deal_ids:
                associations.append({
                    "to": {"id": deal_id},
                    "types": [{
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": 212  # Meeting to deal association
                    }]
                })

        data = {
            "properties": properties,
            "associations": associations
        }

        endpoint = "/crm/v3/objects/meetings"
        result = await self._make_request("POST", endpoint, data=data)

        logger.info("Created meeting", meeting_id=result.get("id"), title=title)
        return result

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()