#!/usr/bin/env python3
"""
plan.py - Manage the personal planning system JSON files.

Usage:
    python3 plan.py <command> [options]

Commands:
    goals:      List, add, get, update, archive goals
    projects:   List, add, get, update, archive projects
    tasks:      List, add, get, update, archive tasks
    plan:       Show, set, or clear the daily plan
    state:      Show, set, or reset the current state
    history:    Record or view daily history
    validate:   Validate all JSON files against their schemas

Examples:
    python3 plan.py goals add --title "Learn Python" --description "Master Python programming" --priority high
    python3 plan.py tasks list --status in_progress
    python3 plan.py tasks done task-abc123 --date 2026-08-17 --note "Implemented feature X"
    python3 plan.py projects done project-xyz789
    python3 plan.py history record --date 2026-08-17 --completed task-abc123,task-def456
"""

import argparse
import json
import os
import re
import sys
import random
import string
from datetime import datetime, date
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()

PRIORITY_LEVELS = ["critical", "high", "medium", "low"]

VALID_STATUSES = {
    "goals": ["active", "paused"],
    "projects": ["active", "paused"],
    "tasks": ["todo", "in_progress", "blocked"],
}

ID_PATTERNS = {
    "goals": r"^goal-[a-z0-9-]+$",
    "projects": r"^project-[a-z0-9-]+$",
    "tasks": r"^task-[a-z0-9-]+$",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def generate_id(prefix: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-")
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{prefix}{ts}{rand}"


def today_iso() -> str:
    return date.today().isoformat()


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return None
            return json.loads(content)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Error: Could not read {path}: {exc}", file=sys.stderr)
        sys.exit(1)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_entities(kind: str):
    path = BASE_DIR / f"{kind}.json"
    data = load_json(path)
    if data is None:
        return []
    if not isinstance(data, list):
        return []
    return data


def save_entities(kind: str, entities):
    path = BASE_DIR / f"{kind}.json"
    save_json(path, entities)


def validate_priority(value, entity_name):
    if value not in PRIORITY_LEVELS:
        print(
            f"Error: Invalid priority '{value}'. Allowed: {', '.join(PRIORITY_LEVELS)}",
            file=sys.stderr,
        )
        sys.exit(1)


def validate_status(kind: str, value, entity_name):
    allowed = VALID_STATUSES.get(kind, [])
    if value not in allowed:
        print(
            f"Error: Invalid status '{value}' for {entity_name}. Allowed: {', '.join(allowed)}",
            file=sys.stderr,
        )
        sys.exit(1)


def validate_id(kind: str, value, entity_name):
    pattern = ID_PATTERNS[kind]
    if not re.match(pattern, value):
        prefix = {"goals": "goal-", "projects": "project-", "tasks": "task-"}[kind]
        print(
            f"Error: Invalid ID '{value}' for {entity_name}. Must match pattern: {prefix}lowercase-letters-and-numbers",
            file=sys.stderr,
        )
        sys.exit(1)


def find_entity(entities, entity_id):
    for entity in entities:
        if entity.get("id") == entity_id:
            return entity
    return None


def find_entity_index(entities, entity_id):
    for i, entity in enumerate(entities):
        if entity.get("id") == entity_id:
            return i
    return -1


def parse_date(date_str: str, field_name: str):
    if date_str is None:
        return None
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        print(f"Error: Invalid date format for {field_name}: '{date_str}'. Use YYYY-MM-DD.", file=sys.stderr)
        sys.exit(1)


def parse_int_list(value: str):
    if value is None:
        return None
    items = [v.strip() for v in value.split(",") if v.strip()]
    return items if items else None


def validate_ids_exist(kind: str, id_list, ref_kind: str, ref_label: str):
    if not id_list:
        return
    ref_entities = load_entities(ref_kind)
    ref_ids = {e["id"] for e in ref_entities}
    for rid in id_list:
        validate_id(ref_kind, rid, f"{ref_label} reference")
        if rid not in ref_ids:
            print(f"Error: {ref_label} ID '{rid}' does not exist.", file=sys.stderr)
            sys.exit(1)


def validate_ids_exist_any(kind: str, id_list, ref_kind: str, ref_label: str):
    """Validate IDs against both active and archived (done) entities."""
    if not id_list:
        return
    ref_entities = load_entities(ref_kind)
    done_path = BASE_DIR / "history" / f"{ref_kind}.done.json"
    done_entities = load_json(done_path) or []
    ref_ids = {e["id"] for e in ref_entities} | {e["id"] for e in done_entities}
    for rid in id_list:
        validate_id(ref_kind, rid, f"{ref_label} reference")
        if rid not in ref_ids:
            print(f"Error: {ref_label} ID '{rid}' does not exist.", file=sys.stderr)
            sys.exit(1)


# ---------------------------------------------------------------------------
# Command formatters
# ---------------------------------------------------------------------------

def format_entity(entity, indent=""):
    lines = []
    for key, value in entity.items():
        if isinstance(value, list):
            val_str = ", ".join(str(v) for v in value) if value else "[]"
            lines.append(f"{indent}{key}: {val_str}")
        elif isinstance(value, dict):
            lines.append(f"{indent}{key}:")
            for k2, v2 in value.items():
                lines.append(f"{indent}  {k2}: {v2}")
        else:
            lines.append(f"{indent}{key}: {value}")
    return "\n".join(lines)


def print_entity_short(entity):
    print(f"  {entity['id']}: {entity['title']} [priority: {entity.get('priority', 'N/A')}] [status: {entity.get('status', 'N/A')}]")


# ---------------------------------------------------------------------------
# Goal commands
# ---------------------------------------------------------------------------

def cmd_goal_list(args):
    entities = load_entities("goals")
    if not entities:
        print("No goals found.")
        return
    print(f"Goals ({len(entities)}):")
    for e in entities:
        print_entity_short(e)


def cmd_goal_get(args):
    entities = load_entities("goals")
    entity = find_entity(entities, args.id)
    if not entity:
        print(f"Goal '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)
    print(format_entity(entity))


def cmd_goal_add(args):
    entities = load_entities("goals")
    entity_id = args.id or generate_id("goal-")
    validate_id("goals", entity_id, "goal")
    if find_entity(entities, entity_id) is not None:
        print(f"Error: Goal with ID '{entity_id}' already exists.", file=sys.stderr)
        sys.exit(1)

    if args.priority:
        validate_priority(args.priority, "goal")

    entity = {
        "id": entity_id,
        "title": args.title,
        "description": args.description,
        "priority": args.priority,
        "status": args.status or "active",
    }
    if args.deadline is not None:
        entity["deadline"] = parse_date(args.deadline, "deadline")
    if args.success_criteria:
        entity["success_criteria"] = parse_int_list(args.success_criteria)
    entity["created_at"] = now_iso()
    entity["updated_at"] = now_iso()

    validate_status("goals", entity["status"], "goal")

    entities.append(entity)
    save_entities("goals", entities)
    print(f"Created goal '{entity_id}'.")


def cmd_goal_update(args):
    entities = load_entities("goals")
    entity = find_entity(entities, args.id)
    if not entity:
        print(f"Goal '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)

    if args.title is not None:
        entity["title"] = args.title
    if args.description is not None:
        entity["description"] = args.description
    if args.priority is not None:
        validate_priority(args.priority, "goal")
        entity["priority"] = args.priority
    if args.status is not None:
        validate_status("goals", args.status, "goal")
        entity["status"] = args.status
    if args.deadline is not None:
        entity["deadline"] = parse_date(args.deadline, "deadline")
    if args.success_criteria is not None:
        entity["success_criteria"] = parse_int_list(args.success_criteria)
    entity["updated_at"] = now_iso()

    save_entities("goals", entities)
    print(f"Updated goal '{args.id}'.")


def archive_entity(kind: str, entity, done_file: str):
    """Archive an entity to the done file and return it."""
    done_path = BASE_DIR / "history" / done_file
    done = load_json(done_path) or []
    entity["archived_at"] = now_iso()
    if kind in ("goals", "projects"):
        entity["status"] = "completed"
    elif kind == "tasks":
        entity["status"] = "done"
    done.append(entity)
    save_json(done_path, done)
    return entity


def cmd_goal_done(args):
    entities = load_entities("goals")
    archived = []
    for entity_id in args.ids:
        entity = find_entity(entities, entity_id)
        if not entity:
            print(f"Error: Goal '{entity_id}' not found.", file=sys.stderr)
            sys.exit(1)
        archive_entity("goals", entity, "goals.done.json")
        idx = find_entity_index(entities, entity_id)
        entities.pop(idx)
        archived.append(entity_id)
    save_entities("goals", entities)
    for aid in archived:
        print(f"Goal '{aid}' archived as completed.")


# ---------------------------------------------------------------------------
# Project commands
# ---------------------------------------------------------------------------

def cmd_project_list(args):
    entities = load_entities("projects")
    if not entities:
        print("No projects found.")
        return
    print(f"Projects ({len(entities)}):")
    for e in entities:
        print_entity_short(e)


def cmd_project_get(args):
    entities = load_entities("projects")
    entity = find_entity(entities, args.id)
    if not entity:
        print(f"Project '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)
    print(format_entity(entity))


def cmd_project_add(args):
    entities = load_entities("projects")
    entity_id = args.id or generate_id("project-")
    validate_id("projects", entity_id, "project")
    if find_entity(entities, entity_id) is not None:
        print(f"Error: Project with ID '{entity_id}' already exists.", file=sys.stderr)
        sys.exit(1)

    if args.priority:
        validate_priority(args.priority, "project")

    goal_ids = parse_int_list(args.goal_ids) if args.goal_ids else None
    if goal_ids is None:
        print("Error: --goal-ids is required for projects.", file=sys.stderr)
        sys.exit(1)
    validate_ids_exist("projects", goal_ids, "goals", "goal")

    entity = {
        "id": entity_id,
        "title": args.title,
        "description": args.description,
        "goal_ids": goal_ids,
        "priority": args.priority,
        "status": args.status or "active",
    }
    if args.deadline is not None:
        entity["deadline"] = parse_date(args.deadline, "deadline")
    if args.success_criteria:
        entity["success_criteria"] = parse_int_list(args.success_criteria)
    if args.next_action is not None:
        entity["next_action"] = args.next_action
    entity["created_at"] = now_iso()
    entity["updated_at"] = now_iso()

    validate_status("projects", entity["status"], "project")

    entities.append(entity)
    save_entities("projects", entities)
    print(f"Created project '{entity_id}'.")


def cmd_project_update(args):
    entities = load_entities("projects")
    entity = find_entity(entities, args.id)
    if not entity:
        print(f"Project '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)

    if args.title is not None:
        entity["title"] = args.title
    if args.description is not None:
        entity["description"] = args.description
    if args.priority is not None:
        validate_priority(args.priority, "project")
        entity["priority"] = args.priority
    if args.status is not None:
        validate_status("projects", args.status, "project")
        entity["status"] = args.status
    if args.goal_ids is not None:
        goal_ids = parse_int_list(args.goal_ids)
        validate_ids_exist("projects", goal_ids, "goals", "goal")
        entity["goal_ids"] = goal_ids
    if args.deadline is not None:
        entity["deadline"] = parse_date(args.deadline, "deadline")
    if args.success_criteria is not None:
        entity["success_criteria"] = parse_int_list(args.success_criteria)
    if args.next_action is not None:
        entity["next_action"] = args.next_action
    entity["updated_at"] = now_iso()

    save_entities("projects", entities)
    print(f"Updated project '{args.id}'.")


def cmd_project_done(args):
    entities = load_entities("projects")
    archived = []
    for entity_id in args.ids:
        entity = find_entity(entities, entity_id)
        if not entity:
            print(f"Error: Project '{entity_id}' not found.", file=sys.stderr)
            sys.exit(1)
        archive_entity("projects", entity, "projects.done.json")
        idx = find_entity_index(entities, entity_id)
        entities.pop(idx)
        archived.append(entity_id)
    save_entities("projects", entities)
    for aid in archived:
        print(f"Project '{aid}' archived as completed.")


# ---------------------------------------------------------------------------
# Task commands
# ---------------------------------------------------------------------------

def cmd_task_list(args):
    entities = load_entities("tasks")
    if not entities:
        print("No tasks found.")
        return
    # Filter
    filtered = entities
    if args.status:
        filtered = [t for t in filtered if t.get("status") == args.status]
    if args.priority:
        filtered = [t for t in filtered if t.get("priority") == args.priority]
    if args.project_id:
        filtered = [t for t in filtered if t.get("project_id") == args.project_id]

    print(f"Tasks ({len(filtered)}{' of ' + str(len(entities)) if args.status or args.priority or args.project_id else ''}):")
    for e in filtered:
        print_entity_short(e)


def cmd_task_get(args):
    entities = load_entities("tasks")
    entity = find_entity(entities, args.id)
    if not entity:
        print(f"Task '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)
    print(format_entity(entity))


def cmd_task_add(args):
    entities = load_entities("tasks")
    entity_id = args.id or generate_id("task-")
    validate_id("tasks", entity_id, "task")
    if find_entity(entities, entity_id) is not None:
        print(f"Error: Task with ID '{entity_id}' already exists.", file=sys.stderr)
        sys.exit(1)

    if args.priority:
        validate_priority(args.priority, "task")

    goal_ids = parse_int_list(args.goal_ids) if args.goal_ids else None
    if goal_ids:
        validate_ids_exist("tasks", goal_ids, "goals", "goal")

    if args.project_id:
        validate_id("projects", args.project_id, "project reference")
        projects = load_entities("projects")
        if find_entity(projects, args.project_id) is None:
            print(f"Error: Project ID '{args.project_id}' does not exist.", file=sys.stderr)
            sys.exit(1)

    entity = {
        "id": entity_id,
        "title": args.title,
        "priority": args.priority,
        "status": args.status or "todo",
    }
    if goal_ids:
        entity["goal_ids"] = goal_ids
    if args.project_id:
        entity["project_id"] = args.project_id
    if args.estimate_minutes is not None:
        entity["estimate_minutes"] = args.estimate_minutes
    if args.due is not None:
        entity["due"] = parse_date(args.due, "due")
    if args.scheduled is not None:
        entity["scheduled"] = parse_date(args.scheduled, "scheduled")
    if args.dependency_ids:
        dep_ids = parse_int_list(args.dependency_ids)
        validate_ids_exist("tasks", dep_ids, "tasks", "dependency")
        entity["dependency_ids"] = dep_ids
    if args.notes is not None:
        entity["notes"] = args.notes
    entity["created_at"] = now_iso()
    entity["updated_at"] = now_iso()

    validate_status("tasks", entity["status"], "task")

    entities.append(entity)
    save_entities("tasks", entities)
    print(f"Created task '{entity_id}'.")


def cmd_task_update(args):
    entities = load_entities("tasks")
    entity = find_entity(entities, args.id)
    if not entity:
        print(f"Task '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)

    if args.title is not None:
        entity["title"] = args.title
    if args.priority is not None:
        validate_priority(args.priority, "task")
        entity["priority"] = args.priority
    if args.status is not None:
        validate_status("tasks", args.status, "task")
        entity["status"] = args.status
    if args.goal_ids is not None:
        goal_ids = parse_int_list(args.goal_ids)
        validate_ids_exist("tasks", goal_ids, "goals", "goal")
        entity["goal_ids"] = goal_ids
    if args.project_id is not None:
        if args.project_id == "":
            entity.pop("project_id", None)
        else:
            validate_id("projects", args.project_id, "project reference")
            projects = load_entities("projects")
            if find_entity(projects, args.project_id) is None:
                print(f"Error: Project ID '{args.project_id}' does not exist.", file=sys.stderr)
                sys.exit(1)
            entity["project_id"] = args.project_id
    if args.estimate_minutes is not None:
        entity["estimate_minutes"] = args.estimate_minutes
    if args.due is not None:
        entity["due"] = parse_date(args.due, "due")
    if args.scheduled is not None:
        entity["scheduled"] = parse_date(args.scheduled, "scheduled")
    if args.dependency_ids is not None:
        dep_ids = parse_int_list(args.dependency_ids)
        validate_ids_exist("tasks", dep_ids, "tasks", "dependency")
        entity["dependency_ids"] = dep_ids
    if args.notes is not None:
        entity["notes"] = args.notes
    entity["updated_at"] = now_iso()

    save_entities("tasks", entities)
    print(f"Updated task '{args.id}'.")


def cmd_task_done(args):
    entities = load_entities("tasks")
    archived = []
    for entity_id in args.ids:
        entity = find_entity(entities, entity_id)
        if not entity:
            print(f"Error: Task '{entity_id}' not found.", file=sys.stderr)
            sys.exit(1)
        archive_entity("tasks", entity, "tasks.done.json")
        idx = find_entity_index(entities, entity_id)
        entities.pop(idx)
        archived.append(entity_id)
    save_entities("tasks", entities)
    for aid in archived:
        print(f"Task '{aid}' archived as done.")


# ---------------------------------------------------------------------------
# Plan commands
# ---------------------------------------------------------------------------

def cmd_plan_show(args):
    path = BASE_DIR / "plan.json"
    data = load_json(path)
    if data is None:
        print("No plan set.")
        return
    print(format_entity(data))


def cmd_plan_set(args):
    path = BASE_DIR / "plan.json"
    data = load_json(path) or {}

    data["date"] = args.date or today_iso()
    if args.date:
        parse_date(args.date, "date")
    data["objective"] = args.objective
    data["task_ids"] = parse_int_list(args.task_ids) or []

    validate_ids_exist("plan", data["task_ids"], "tasks", "task")

    if args.schedule is not None:
        items = []
        for item in args.schedule.split(";"):
            parts = item.strip().split("|")
            if len(parts) >= 2:
                start = parts[1].strip()
                end = parts[2].strip() if len(parts) > 2 and parts[2].strip() else None
                items.append({"task_id": parts[0].strip(), "start": start, "end": end})
        data["schedule"] = items

    if args.notes:
        data["notes"] = parse_int_list(args.notes)

    save_json(path, data)
    print(f"Plan set for {data['date']}.")


def cmd_plan_clear(args):
    path = BASE_DIR / "plan.json"
    save_json(path, {})
    print("Plan cleared.")


# ---------------------------------------------------------------------------
# State commands
# ---------------------------------------------------------------------------

def cmd_state_show(args):
    path = BASE_DIR / "state.json"
    data = load_json(path)
    if data is None:
        print("No state set.")
        return
    print(format_entity(data))


def cmd_state_set(args):
    path = BASE_DIR / "state.json"
    data = load_json(path) or {}

    if args.current_focus is not None:
        data["current_focus"] = args.current_focus
    if args.active_goal_ids is not None:
        ids = parse_int_list(args.active_goal_ids)
        validate_ids_exist("state", ids, "goals", "goal")
        data["active_goal_ids"] = ids
    if args.active_project_ids is not None:
        ids = parse_int_list(args.active_project_ids)
        validate_ids_exist("state", ids, "projects", "project")
        data["active_project_ids"] = ids
    if args.current_task_ids is not None:
        ids = parse_int_list(args.current_task_ids)
        validate_ids_exist("state", ids, "tasks", "task")
        data["current_task_ids"] = ids
    if args.blockers is not None:
        data["blockers"] = parse_int_list(args.blockers)
    if args.notes is not None:
        data["notes"] = parse_int_list(args.notes)

    data["updated_at"] = now_iso()

    save_json(path, data)
    print("State updated.")


def cmd_state_reset(args):
    path = BASE_DIR / "state.json"
    save_json(path, {})
    print("State reset.")


# ---------------------------------------------------------------------------
# History commands
# ---------------------------------------------------------------------------

def daily_history_path(date_str: str) -> Path:
    """Return the file path for a daily history record."""
    parsed = datetime.strptime(date_str, "%Y-%m-%d")
    return BASE_DIR / "history" / "daily" / str(parsed.year) / f"{parsed.month:02d}" / f"{parsed.day:02d}.json"


def cmd_history_show(args):
    date_str = args.date or today_iso()
    parse_date(date_str, "date")
    path = daily_history_path(date_str)
    data = load_json(path)
    if data is None:
        print(f"No history record for {date_str}.")
        return
    print(format_entity(data))


def cmd_history_record(args):
    date_str = args.date or today_iso()
    parse_date(date_str, "date")
    path = daily_history_path(date_str)
    data = load_json(path) or {"date": date_str}

    data["date"] = date_str

    if args.planned_task_ids is not None:
        data["planned_task_ids"] = parse_int_list(args.planned_task_ids)
        validate_ids_exist_any("tasks", data["planned_task_ids"], "tasks", "task")
    if args.completed_task_ids is not None:
        data["completed_task_ids"] = parse_int_list(args.completed_task_ids)
        validate_ids_exist_any("tasks", data["completed_task_ids"], "tasks", "task")
    if args.cancelled_task_ids is not None:
        data["cancelled_task_ids"] = parse_int_list(args.cancelled_task_ids)
        validate_ids_exist_any("tasks", data["cancelled_task_ids"], "tasks", "task")
    if args.completed_project_ids is not None:
        ids = parse_int_list(args.completed_project_ids)
        validate_ids_exist_any("projects", ids, "projects", "project")
        data["completed_project_ids"] = ids
    if args.completed_goal_ids is not None:
        ids = parse_int_list(args.completed_goal_ids)
        validate_ids_exist_any("goals", ids, "goals", "goal")
        data["completed_goal_ids"] = ids
    if args.notes is not None:
        data["notes"] = parse_int_list(args.notes)

    save_json(path, data)
    print(f"History record saved for {date_str}.")


# ---------------------------------------------------------------------------
# Validation commands
# ---------------------------------------------------------------------------

def cmd_validate(args):
    files = [
        "goals.json",
        "projects.json",
        "tasks.json",
        "plan.json",
        "state.json",
        "history/goals.done.json",
        "history/projects.done.json",
        "history/tasks.done.json",
    ]
    all_ok = True
    for f in files:
        path = BASE_DIR / f
        if path.exists():
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                print(f"  [empty] {f} (valid: empty or placeholder)")
                continue
            try:
                json.loads(content)
                print(f"  [valid JSON] {f}")
            except json.JSONDecodeError as exc:
                print(f"  [INVALID] {f}: {exc}", file=sys.stderr)
                all_ok = False

    if all_ok:
        print("\nAll files are valid JSON.")
    else:
        print("\nSome files have errors.", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plan.py",
        description="Manage the personal planning system.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Top-level command")

    # -- Goals --
    sp = subparsers.add_parser("goals", help="Manage goals")
    sp.subparsers = sp.add_subparsers(dest="subcommand", required=True)

    p = sp.subparsers.add_parser("list", help="List all active goals")
    p.set_defaults(func=cmd_goal_list)

    p = sp.subparsers.add_parser("get", help="Get a single goal by ID")
    p.add_argument("id", help="Goal ID")
    p.set_defaults(func=cmd_goal_get)

    p = sp.subparsers.add_parser("add", help="Add a new goal")
    p.add_argument("--id", help="Goal ID (auto-generated if omitted)")
    p.add_argument("--title", required=True, help="Short name")
    p.add_argument("--description", required=True, help="Description of desired outcome")
    p.add_argument("--priority", choices=PRIORITY_LEVELS, required=True, help="Priority level")
    p.add_argument("--status", choices=VALID_STATUSES["goals"], default="active")
    p.add_argument("--deadline", help="Deadline (YYYY-MM-DD)")
    p.add_argument("--success-criteria", help="Comma-separated success criteria")
    p.set_defaults(func=cmd_goal_add)

    p = sp.subparsers.add_parser("update", help="Update an existing goal")
    p.add_argument("id", help="Goal ID")
    p.add_argument("--title")
    p.add_argument("--description")
    p.add_argument("--priority", choices=PRIORITY_LEVELS)
    p.add_argument("--status", choices=VALID_STATUSES["goals"])
    p.add_argument("--deadline")
    p.add_argument("--success-criteria")
    p.set_defaults(func=cmd_goal_update)

    p = sp.subparsers.add_parser("done", help="Archive one or more goals as completed")
    p.add_argument("ids", nargs="+", help="Goal ID(s)")
    p.set_defaults(func=cmd_goal_done)

    # -- Projects --
    sp = subparsers.add_parser("projects", help="Manage projects")
    sp.subparsers = sp.add_subparsers(dest="subcommand", required=True)

    p = sp.subparsers.add_parser("list", help="List all active projects")
    p.set_defaults(func=cmd_project_list)

    p = sp.subparsers.add_parser("get", help="Get a single project by ID")
    p.add_argument("id", help="Project ID")
    p.set_defaults(func=cmd_project_get)

    p = sp.subparsers.add_parser("add", help="Add a new project")
    p.add_argument("--id", help="Project ID (auto-generated if omitted)")
    p.add_argument("--title", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--goal-ids", required=True, help="Comma-separated goal IDs")
    p.add_argument("--priority", choices=PRIORITY_LEVELS, required=True)
    p.add_argument("--status", choices=VALID_STATUSES["projects"], default="active")
    p.add_argument("--deadline")
    p.add_argument("--success-criteria")
    p.add_argument("--next-action")
    p.set_defaults(func=cmd_project_add)

    p = sp.subparsers.add_parser("update", help="Update an existing project")
    p.add_argument("id", help="Project ID")
    p.add_argument("--title")
    p.add_argument("--description")
    p.add_argument("--priority", choices=PRIORITY_LEVELS)
    p.add_argument("--status", choices=VALID_STATUSES["projects"])
    p.add_argument("--goal-ids")
    p.add_argument("--deadline")
    p.add_argument("--success-criteria")
    p.add_argument("--next-action")
    p.set_defaults(func=cmd_project_update)

    p = sp.subparsers.add_parser("done", help="Archive one or more projects as completed")
    p.add_argument("ids", nargs="+", help="Project ID(s)")
    p.set_defaults(func=cmd_project_done)

    # -- Tasks --
    sp = subparsers.add_parser("tasks", help="Manage tasks")
    sp.subparsers = sp.add_subparsers(dest="subcommand", required=True)

    p = sp.subparsers.add_parser("list", help="List tasks (optionally filtered)")
    p.add_argument("--status", choices=VALID_STATUSES["tasks"])
    p.add_argument("--priority", choices=PRIORITY_LEVELS)
    p.add_argument("--project-id")
    p.set_defaults(func=cmd_task_list)

    p = sp.subparsers.add_parser("get", help="Get a single task by ID")
    p.add_argument("id", help="Task ID")
    p.set_defaults(func=cmd_task_get)

    p = sp.subparsers.add_parser("add", help="Add a new task")
    p.add_argument("--id", help="Task ID (auto-generated if omitted)")
    p.add_argument("--title", required=True)
    p.add_argument("--priority", choices=PRIORITY_LEVELS, required=True)
    p.add_argument("--status", choices=VALID_STATUSES["tasks"], default="todo")
    p.add_argument("--goal-ids", help="Comma-separated goal IDs")
    p.add_argument("--project-id", help="Project ID this task belongs to")
    p.add_argument("--estimate-minutes", type=int)
    p.add_argument("--due")
    p.add_argument("--scheduled")
    p.add_argument("--dependency-ids", help="Comma-separated task IDs")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_task_add)

    p = sp.subparsers.add_parser("update", help="Update an existing task")
    p.add_argument("id", help="Task ID")
    p.add_argument("--title")
    p.add_argument("--priority", choices=PRIORITY_LEVELS)
    p.add_argument("--status", choices=VALID_STATUSES["tasks"])
    p.add_argument("--goal-ids")
    p.add_argument("--project-id")
    p.add_argument("--estimate-minutes", type=int)
    p.add_argument("--due")
    p.add_argument("--scheduled")
    p.add_argument("--dependency-ids")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_task_update)

    p = sp.subparsers.add_parser("done", help="Archive one or more tasks as completed")
    p.add_argument("ids", nargs="+", help="Task ID(s)")
    p.set_defaults(func=cmd_task_done)

    # -- Plan --
    sp = subparsers.add_parser("plan", help="Manage the daily plan")
    sp.subparsers = sp.add_subparsers(dest="subcommand", required=True)

    p = sp.subparsers.add_parser("show", help="Show the current plan")
    p.set_defaults(func=cmd_plan_show)

    p = sp.subparsers.add_parser("set", help="Set the daily plan")
    p.add_argument("--date", help="Date (YYYY-MM-DD). Defaults to today.")
    p.add_argument("--objective", required=True)
    p.add_argument("--task-ids", required=True, help="Comma-separated task IDs in order")
    p.add_argument("--schedule", help="Schedule: 'task-id|HH:MM|HH:MM;task-id|HH:MM'")
    p.add_argument("--notes", help="Comma-separated notes")
    p.set_defaults(func=cmd_plan_set)

    p = sp.subparsers.add_parser("clear", help="Clear the daily plan")
    p.set_defaults(func=cmd_plan_clear)

    # -- State --
    sp = subparsers.add_parser("state", help="Manage the current state snapshot")
    sp.subparsers = sp.add_subparsers(dest="subcommand", required=True)

    p = sp.subparsers.add_parser("show", help="Show current state")
    p.set_defaults(func=cmd_state_show)

    p = sp.subparsers.add_parser("set", help="Update state fields")
    p.add_argument("--current-focus")
    p.add_argument("--active-goal-ids")
    p.add_argument("--active-project-ids")
    p.add_argument("--current-task-ids")
    p.add_argument("--blockers")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_state_set)

    p = sp.subparsers.add_parser("reset", help="Reset state to empty")
    p.set_defaults(func=cmd_state_reset)

    # -- History --
    sp = subparsers.add_parser("history", help="Manage daily history records")
    sp.subparsers = sp.add_subparsers(dest="subcommand", required=True)

    p = sp.subparsers.add_parser("show", help="Show a daily history record")
    p.add_argument("--date", help="Date (YYYY-MM-DD). Defaults to today.")
    p.set_defaults(func=cmd_history_show)

    p = sp.subparsers.add_parser("record", help="Record daily activity")
    p.add_argument("--date", help="Date (YYYY-MM-DD). Defaults to today.")
    p.add_argument("--planned-task-ids")
    p.add_argument("--completed-task-ids")
    p.add_argument("--cancelled-task-ids")
    p.add_argument("--completed-project-ids")
    p.add_argument("--completed-goal-ids")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_history_record)

    # -- Validate --
    p = subparsers.add_parser("validate", help="Validate all JSON files")
    p.set_defaults(func=cmd_validate)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
