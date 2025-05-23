from typing import Dict, List, Any, Optional
import sys
import os
import json
from mcp.server.fastmcp import FastMCP
import difflib
import logging

# Import database models and setup
from app import create_app, db
from app.models.project import Project
from app.models.ticket import Ticket, TicketState
from app.models.comments import Comment

# Initialize FastMCP server
mcp = FastMCP("kanban-board")

# Create app context for database access
app = create_app()
app_context = app.app_context()

MOVE_MSG = "This script has moved. Please update your script or MCP configuration to use 'mcp/kanban.py' instead of 'kanban_mcp_server.py'."


# Database access functions
def get_projects_from_db():
    """Get all projects directly from the database."""
    print("Accessing database directly for projects", file=sys.stderr)

    try:
        # Query all projects
        projects = Project.query.all()

        if not projects:
            print("No projects found in database", file=sys.stderr)
            return "No projects found."

        print(f"Found {len(projects)} projects in database", file=sys.stderr)

        # Convert projects to dictionaries for formatting
        project_dicts = [project.to_dict() for project in projects]

        # Format the result string
        result = "Projects:\n\n"
        for project in project_dicts:
            result += f"ID: {project['id']}\n"
            result += f"Name: {project['name']}\n"
            result += f"Description: {project['description']}\n"
            result += f"Tickets: {project.get('ticket_count', 0)}\n\n"

        return result
    except Exception as e:
        print(f"Error accessing database: {str(e)}", file=sys.stderr)
        return f"Error fetching projects: {str(e)}"


def get_tickets_from_db(project_id=None):
    """Get tickets directly from the database, optionally filtered by project."""
    print(
        f"Accessing database directly for tickets (project_id={project_id})",
        file=sys.stderr,
    )

    try:
        # Build query
        query = Ticket.query
        if project_id:
            query = query.filter_by(project_id=project_id)

        tickets = query.all()

        if not tickets:
            return "No tickets found."

        # Format the result
        result = f"Tickets{f' for Project {project_id}' if project_id else ''}:\n\n"
        for ticket in tickets:
            ticket_dict = ticket.to_dict()
            result += f"ID: {ticket_dict['id']}\n"
            result += f"What: {ticket_dict['what']}\n"
            result += f"State: {ticket_dict.get('state_name', 'Unknown')}\n"
            result += f"Type: {ticket_dict.get('type_name', 'Unknown')}\n"
            if ticket_dict.get("why"):
                result += f"Why: {ticket_dict['why']}\n"
            result += "\n"

        return result
    except Exception as e:
        print(f"Error accessing database: {str(e)}", file=sys.stderr)
        return f"Error fetching tickets: {str(e)}"


def create_ticket_in_db(
    project_id, what, why=None, acceptance_criteria=None, test_steps=None, ticket_type=2
):
    """Create a new ticket directly in the database."""
    print(f"Creating ticket in database: {what}", file=sys.stderr)

    try:
        # Find the project
        project = Project.query.get(project_id)
        if not project:
            return f"Error: Project with ID {project_id} not found."

        # Create ticket
        ticket = Ticket(
            project_id=project_id,
            what=what,
            why=why,
            acceptance_criteria=acceptance_criteria,
            test_steps=test_steps,
            type=ticket_type,  # Use the provided ticket_type parameter
            state=1,  # Default to 'backlog'
        )

        db.session.add(ticket)
        db.session.commit()

        return f"Successfully created ticket #{ticket.id}: {ticket.what}"
    except Exception as e:
        db.session.rollback()
        print(f"Error creating ticket: {str(e)}", file=sys.stderr)
        return f"Error creating ticket: {str(e)}"


def update_ticket_state_in_db(ticket_id, state_name):
    """Update a ticket's state directly in the database."""
    logging.info(f"Updating ticket #{ticket_id} state to '{state_name}'")
    try:
        # Find the ticket
        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            return f"Error: Ticket with ID {ticket_id} not found."

        # Dynamically look up the state ID from the database
        state = TicketState.query.filter(TicketState.name.ilike(state_name)).first()
        if not state:
            return f"Error: Invalid state '{state_name}'."
        state_id = state.id

        # Update ticket state
        ticket.state = state_id

        # If marking as done, set completed date
        if state.name.lower() == "done":
            from datetime import datetime, UTC

            ticket.completed_date = datetime.now(UTC)
        db.session.commit()
        return f"Successfully updated ticket #{ticket_id} to state '{state_name}'"
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating ticket state: {str(e)}")
        return f"Error updating ticket state: {str(e)}"


def add_comment_to_db(ticket_id, content):
    """Add a comment to a ticket directly in the database."""
    print(f"Adding comment to ticket #{ticket_id}", file=sys.stderr)

    try:
        # Find the ticket
        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            return f"Error: Ticket with ID {ticket_id} not found."

        # Create comment
        comment = Comment(ticket_id=ticket_id, content=content)

        db.session.add(comment)
        db.session.commit()

        return f"Successfully added comment to ticket #{ticket_id}"
    except Exception as e:
        db.session.rollback()
        print(f"Error adding comment: {str(e)}", file=sys.stderr)
        return f"Error adding comment: {str(e)}"


def get_kanban_status_from_db():
    """Get Kanban board status directly from the database."""
    print("Getting Kanban status from database", file=sys.stderr)

    try:
        # Get all projects
        projects = Project.query.all()
        project_dicts = [project.to_dict() for project in projects]

        # Get all tickets
        tickets = Ticket.query.all()

        # Count tickets by state
        state_names = {1: "backlog", 2: "in progress", 3: "done", 4: "on hold"}
        states = {state_name: 0 for state_name in state_names.values()}

        for ticket in tickets:
            state_name = state_names.get(ticket.state)
            if state_name:
                states[state_name] += 1

        # Format the result
        status_text = "Kanban Board Status:\n\n"
        status_text += f"Total Tickets: {len(tickets)}\n\n"

        status_text += "Tickets by State:\n"
        for state, count in states.items():
            status_text += f"- {state}: {count}\n"

        status_text += "\nProjects:\n"
        for project in project_dicts:
            status_text += (
                f"- {project['name']}: {project.get('ticket_count', 0)} tickets\n"
            )

        return status_text
    except Exception as e:
        print(f"Error getting Kanban status: {str(e)}", file=sys.stderr)
        return f"Error getting Kanban status: {str(e)}"


def get_project_id_by_name_fuzzy(name: str) -> Optional[int]:
    """
    Find a project ID by fuzzy-matching the provided name against all project names.
    Matching is case-insensitive and typo-tolerant (using difflib).

    Args:
        name (str): The project name or partial name to search for.

    Returns:
        Optional[int]: The ID of the best-matching project, or None if no match is found.
    """
    try:
        projects = Project.query.all()
        if not projects:
            return None
        project_names = [project.name for project in projects]
        # Use difflib to find the closest match (case-insensitive)
        matches = difflib.get_close_matches(
            name.lower(), [n.lower() for n in project_names], n=1, cutoff=0.6
        )
        if matches:
            # Find the original project with the matched name (case-insensitive)
            for project in projects:
                if project.name.lower() == matches[0]:
                    return project.id
        return None
    except Exception as e:
        print(f"Error in fuzzy project name lookup: {str(e)}", file=sys.stderr)
        return None


@mcp.tool()
async def get_project_id_by_name(name: str) -> str:
    return MOVE_MSG


# MCP Tool Implementations
@mcp.tool()
async def get_kanban_status() -> str:
    return MOVE_MSG


@mcp.tool()
async def create_ticket(
    project_id: int,
    what: str,
    why: Optional[str] = None,
    acceptance_criteria: Optional[str] = None,
    test_steps: Optional[str] = None,
    ticket_type: int = 2,
) -> str:
    return MOVE_MSG


@mcp.tool()
async def update_ticket_state(ticket_id: int, state: str) -> str:
    return MOVE_MSG


@mcp.tool()
async def list_projects() -> str:
    return MOVE_MSG


@mcp.tool()
async def list_tickets(project_id: Optional[int] = None) -> str:
    return MOVE_MSG


@mcp.tool()
async def add_comment(ticket_id: int, content: str) -> str:
    return MOVE_MSG


# Run the server
if __name__ == "__main__":
    mcp.run(transport="stdio")
